"""
Chat router — POST /chat  (Server-Sent Events stream)
"""

from __future__ import annotations

import json
import re
import time
from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from starlette.requests import Request

from surogate_agent.api.deps import ServerSettings, settings_dep
from surogate_agent.api.models import ChatRequest
from surogate_agent.auth.jwt import get_current_user
from surogate_agent.auth.models import User
from surogate_agent.core.agent import create_agent, subagent_activity_queue
from surogate_agent.core.config import AgentConfig, _DEFAULT_SKILLS_DIR
from surogate_agent.core.logging import get_logger
from surogate_agent.core.roles import Role
from surogate_agent.core.session import SessionManager

log = get_logger(__name__)

try:
    from sse_starlette.sse import EventSourceResponse
except ImportError:
    EventSourceResponse = None  # type: ignore[assignment,misc]

router = APIRouter(tags=["chat"])


def _sse_event(event: str, data: dict) -> dict:
    return {"event": event, "data": json.dumps(data)}


def _extract_thinking(content) -> str:
    """Extract structured thinking blocks (Claude extended thinking format)."""
    if not isinstance(content, list):
        return ""
    parts = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "thinking":
            parts.append(block.get("thinking", ""))
        elif hasattr(block, "type") and getattr(block, "type", None) == "thinking":
            parts.append(getattr(block, "thinking", ""))
    return "\n\n".join(p for p in parts if p)


def _extract_openrouter_reasoning(msg) -> str:
    """Extract the OpenRouter reasoning field from a message.

    When ``include: ["reasoning"]`` is sent, OpenRouter adds a ``reasoning``
    string field alongside ``content`` on the assistant message.  LangChain
    surfaces this in ``additional_kwargs`` or directly on the message object.
    """
    ak = (
        msg.get("additional_kwargs", {}) if isinstance(msg, dict)
        else getattr(msg, "additional_kwargs", {})
    )
    return ak.get("reasoning", "") or ""


def _extract_content_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif hasattr(block, "type") and getattr(block, "type", None) == "text":
                parts.append(getattr(block, "text", ""))
        return "".join(parts)
    return ""


_THINK_TAG_RE = re.compile(r"<think>(.*?)</think>", re.DOTALL | re.IGNORECASE)


def _split_inline_thinking(text: str) -> tuple[str, str]:
    """Extract <think>…</think> blocks from a plain-text response.

    Models like Qwen3 embed their chain-of-thought inline as ``<think>`` tags
    rather than returning structured thinking blocks.  This splits them out so
    the frontend can render them in the thinking panel instead of as raw text.

    Returns ``(thinking, clean_text)`` where *thinking* is the joined content
    of all ``<think>`` blocks and *clean_text* is the remainder with the tags
    removed and leading/trailing whitespace stripped.
    """
    parts = _THINK_TAG_RE.findall(text)
    clean = _THINK_TAG_RE.sub("", text).strip()
    return "\n\n".join(p.strip() for p in parts if p.strip()), clean


def _unwrap_messages(raw) -> list:
    if raw is None:
        return []
    if hasattr(raw, "value"):
        raw = raw.value
    if isinstance(raw, list):
        return raw
    return []


def _iter_messages(chunk):
    if not isinstance(chunk, dict):
        if isinstance(chunk, tuple) and chunk:
            item = chunk[0]
            if _looks_like_message(item):
                yield item
        return

    if "messages" in chunk:
        msgs = _unwrap_messages(chunk["messages"])
        if msgs:
            yield msgs[-1]
        return

    for node_output in chunk.values():
        if isinstance(node_output, dict):
            for msg in _unwrap_messages(node_output.get("messages")):
                yield msg
        elif isinstance(node_output, list):
            for item in node_output:
                if _looks_like_message(item):
                    yield item


# Tokens reserved for system prompt + tool schemas + model output.
# Applies when vllm_context_length is set.  Tools alone can be 1000–2000 tokens;
# the system prompt adds another 500–1000.  This constant keeps a safe margin.
_VLLM_OVERHEAD_RESERVE = 3000


def _estimate_msg_tokens(msg) -> int:
    """Rough token estimate for a LangGraph message (4 chars ≈ 1 token)."""
    content = (
        msg.get("content", "") if isinstance(msg, dict)
        else getattr(msg, "content", "")
    )
    if isinstance(content, str):
        return max(1, len(content) // 4)
    if isinstance(content, list):
        total = 0
        for block in content:
            text = (
                block.get("text", "") if isinstance(block, dict)
                else getattr(block, "text", "")
            )
            total += max(1, len(str(text)) // 4)
        return max(1, total)
    return max(1, len(str(content)) // 4)


async def _trim_checkpoint_to_context(
    checkpointer,
    invoke_config: dict,
    checkpoint_tuple,
    context_length: int,
) -> None:
    """Remove oldest messages from the LangGraph checkpoint so the stored
    history fits within ``context_length - _VLLM_OVERHEAD_RESERVE`` tokens.

    Always retains at least the last two messages (one complete exchange) so
    the agent always has some context to work with.  Writes the trimmed
    checkpoint back via ``aput`` so the next agent run sees the shorter state.
    """
    if not checkpoint_tuple or not checkpoint_tuple.checkpoint:
        return

    msg_budget = max(200, context_length - _VLLM_OVERHEAD_RESERVE)
    channel_values = checkpoint_tuple.checkpoint.get("channel_values", {})
    messages = _unwrap_messages(channel_values.get("messages"))
    if not messages:
        return

    total = sum(_estimate_msg_tokens(m) for m in messages)
    if total <= msg_budget:
        return  # already fits

    trimmed = list(messages)
    while len(trimmed) > 2 and sum(_estimate_msg_tokens(m) for m in trimmed) > msg_budget:
        trimmed.pop(0)

    log.warning(
        "context trim: %d → %d history messages to fit context_length=%d tokens (budget=%d tokens)",
        len(messages), len(trimmed), context_length, msg_budget,
    )

    import copy
    new_checkpoint = copy.deepcopy(checkpoint_tuple.checkpoint)
    new_checkpoint["channel_values"]["messages"] = trimmed
    try:
        await checkpointer.aput(
            invoke_config,
            new_checkpoint,
            checkpoint_tuple.metadata or {},
            {},
        )
    except Exception as exc:
        log.warning("could not write trimmed checkpoint: %s", exc)


def _looks_like_message(obj) -> bool:
    t = getattr(obj, "type", None)
    if isinstance(t, str):
        return True
    return isinstance(obj, dict) and "role" in obj


def _extract_subagent_activity(expert_name: str, messages: list) -> dict:
    """Convert a subagent's final message history into a compact activity dict
    suitable for the ``subagent_activity`` SSE event."""
    import asyncio as _asyncio
    items: list[dict] = []
    for msg in messages:
        msg_type = (
            msg.get("type") if isinstance(msg, dict)
            else getattr(msg, "type", None)
        )
        if msg_type in ("ai", "assistant"):
            content = (
                msg.get("content", "") if isinstance(msg, dict)
                else getattr(msg, "content", "")
            )
            tool_calls = (
                msg.get("tool_calls", []) if isinstance(msg, dict)
                else getattr(msg, "tool_calls", [])
            )
            thinking = _extract_thinking(content) or _extract_openrouter_reasoning(msg)
            if thinking:
                items.append({"type": "thinking", "text": thinking})
            for tc in tool_calls or []:
                name = tc.get("name", "?") if isinstance(tc, dict) else getattr(tc, "name", "?")
                args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
                items.append({"type": "tool_call", "name": name, "args": args})
            text = _extract_content_text(content)
            if text:
                inline_thinking, clean = _split_inline_thinking(text)
                if inline_thinking:
                    items.append({"type": "thinking", "text": inline_thinking})
                if clean:
                    items.append({"type": "text", "text": clean})
        elif msg_type == "tool":
            name = (
                msg.get("name") or msg.get("tool_call_id", "?")
                if isinstance(msg, dict)
                else (getattr(msg, "name", None) or getattr(msg, "tool_call_id", "?"))
            )
            result_content = (
                msg.get("content", "") if isinstance(msg, dict)
                else getattr(msg, "content", "")
            )
            for item in reversed(items):
                if item["type"] == "tool_call" and item.get("name") == name and "result" not in item:
                    item["result"] = str(result_content)[:500]
                    break
    return {"subagent": expert_name, "items": items}


async def _stream_chat(
    req: ChatRequest,
    settings: ServerSettings,
    experts_data: list[dict] | None = None,
    expert_lookup_enabled: bool = False,
) -> AsyncGenerator[dict, None]:
    try:
        # Resolve role
        try:
            role = Role(req.role.lower())
        except ValueError:
            log.warning("invalid role requested: '%s'", req.role)
            yield _sse_event("error", {"detail": f"Invalid role '{req.role}'"})
            return

        log.info(
            "chat request: role=%s model=%s session_id=%r user=%r",
            req.role, req.model or settings.model, req.session_id, req.user_id,
        )

        # Build config
        # Developer role always gets shell execution — same as CLI behaviour.
        # For user role, allow_execute may be set by the request (or auto-detected
        # from skill frontmatter inside create_agent()).
        effective_allow_execute = True if role == Role.DEVELOPER else req.allow_execute
        model = req.model or settings.model

        # Convert comma-separated provider string to OpenRouter provider dict.
        # e.g. "MiniMax" → {"order": ["MiniMax"]}
        #      "MiniMax,Fireworks" → {"order": ["MiniMax", "Fireworks"]}
        provider_str = req.openrouter_provider.strip()
        openrouter_provider = (
            {"order": [p.strip() for p in provider_str.split(",") if p.strip()]}
            if provider_str else None
        )

        config = AgentConfig(
            model=model,
            user_skills_dir=settings.skills_dir,
            sessions_dir=settings.sessions_dir,
            dev_workspace_dir=settings.workspace_dir,
            mcp_workspace_dir=settings.mcp_workspace_dir,
            mcp_scripts_dir=settings.mcp_scripts_dir,
            allow_execute=effective_allow_execute,
            api_key=req.api_key,
            openrouter_provider=openrouter_provider,
            vllm_base_url=req.vllm_url,
            vllm_tool_calling=req.vllm_tool_calling,
            vllm_temperature=req.vllm_temperature,
            vllm_top_k=req.vllm_top_k,
            vllm_top_p=req.vllm_top_p,
            vllm_min_p=req.vllm_min_p,
            vllm_presence_penalty=req.vllm_presence_penalty,
            vllm_context_length=req.vllm_context_length,
            thinking_enabled=req.thinking_enabled,
            thinking_budget=req.thinking_budget,
            experts=experts_data or [],
            expert_lookup_enabled=expert_lookup_enabled,
        )

        # Session setup
        sm = SessionManager(settings.sessions_dir)
        dev_skill = ""
        if role == Role.DEVELOPER:
            dev_skill = req.skill.strip()
            config.dev_workspace_dir.mkdir(parents=True, exist_ok=True)
            if dev_skill:
                # Use the frontend-provided session_id as the thread_id when
                # available — clearMessages() on the frontend generates a fresh
                # ID to force a new LangGraph thread (no stale checkpoint context).
                # Fall back to the stable per-skill ID on the very first message.
                thread_id = req.session_id.strip() if req.session_id.strip() else f"dev:{dev_skill}"
                skill_workspace = config.dev_workspace_dir / dev_skill
            else:
                thread_id = req.session_id.strip() if req.session_id.strip() else f"dev:{int(time.time())}"
                skill_workspace = config.dev_workspace_dir
            skill_workspace.mkdir(parents=True, exist_ok=True)
            from surogate_agent.core.session import Session
            session = Session(session_id=thread_id, workspace_dir=skill_workspace)
        else:
            session = (
                sm.resume_or_create(req.session_id)
                if req.session_id
                else sm.new_session()
            )
            thread_id = session.session_id
            # Eagerly create the session workspace so MCP tools (which write
            # directly to the filesystem path) don't fail with "directory does
            # not exist" on the first message of a new session.
            session.workspace_dir.mkdir(parents=True, exist_ok=True)

        # Checkpointer — dedicated checkpoints.db, separate from the auth DB.
        # Always use the persistent SQLite saver so history is continuous across
        # requests.  Without this, the first request (no session_id yet) would
        # use an ephemeral MemorySaver while subsequent requests (session_id
        # received via the done event) would use SQLite — causing message 1 to
        # be permanently lost from the checkpointed history.
        checkpointer = None
        _checkpointer_ctx = None
        try:
            from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
            settings.checkpointer_db.parent.mkdir(parents=True, exist_ok=True)
            _checkpointer_ctx = AsyncSqliteSaver.from_conn_string(str(settings.checkpointer_db))
            checkpointer = await _checkpointer_ctx.__aenter__()
        except ImportError:
            pass

        if checkpointer is None:
            try:
                from langgraph.checkpoint.memory import MemorySaver
                checkpointer = MemorySaver()
                log.debug("using MemorySaver checkpointer (in-memory, no persistence)")
            except ImportError:
                log.debug("no checkpointer available (langgraph not installed)")
        else:
            log.debug("using persistent SQLite checkpointer")

        # Inject MCP tools for all roles (optional — never blocks chat)
        try:
            from surogate_agent.mcp.lifecycle import MCPLifecycle, _HTTP_TOOLS
            from surogate_agent.mcp.registry import MCPRegistry
            _mcp_registry = MCPRegistry(settings.mcp_scripts_dir)
            _mcp_lifecycle = MCPLifecycle(settings.mcp_scripts_dir)
            for _entry in _mcp_registry.list():
                # Auto-start enabled stdio servers that are registered but not yet
                # running in memory (e.g. registered via mcp-manager skill writing
                # registry.json directly rather than through the API endpoint).
                if (
                    _entry.transport == "stdio"
                    and _entry.enabled
                    and _mcp_lifecycle.get_status(_entry) != "running"
                ):
                    log.info("auto-starting stdio server %r (registered but not running)", _entry.name)
                    try:
                        await asyncio.wait_for(
                            _mcp_lifecycle.start_stdio_server(_entry),
                            timeout=30,
                        )
                    except Exception as _start_exc:
                        log.warning("auto-start stdio %r failed: %s", _entry.name, _start_exc)
                # Auto-cache tools for enabled HTTP/SSE servers not yet in cache.
                if (
                    _entry.enabled
                    and _entry.transport in ("http", "sse")
                    and _entry.name not in _HTTP_TOOLS
                    and _mcp_lifecycle.get_status(_entry) == "running"
                ):
                    try:
                        await _mcp_lifecycle._fetch_and_cache_http_tools(_entry)
                    except Exception as _fetch_exc:
                        log.debug("auto-cache http tools %r failed: %s", _entry.name, _fetch_exc)
                if _mcp_lifecycle.get_status(_entry) == "running":
                    config.extra_tools.extend(await _mcp_lifecycle.get_tools(_entry))
        except Exception as _mcp_exc:
            log.debug("MCP tool injection skipped: %s", _mcp_exc)

        # For user role: filter config.experts to only those declared in at least
        # one user skill's ``experts:`` frontmatter.
        #
        # When req.skill is set (e.g. developer "Test as User" with a skill pre-
        # selected), restrict further to that specific skill's experts list.
        # When req.skill is empty (normal user chat — skill is chosen dynamically
        # by the agent at runtime), include experts referenced by ANY installed
        # user skill so the agent can use them after reading the skill's SKILL.md.
        #
        # Developer role: config.experts is left intact so _build_system_suffix
        # can show the catalog; _build_expert_subagents guards against injecting
        # subagents for the developer role at the create_agent level.
        if role == Role.USER and config.experts:
            try:
                from surogate_agent.skills.loader import SkillLoader
                _all_skill_experts: set[str] = set()
                for _root in [config.user_skills_dir] + list(config.skills_dirs):
                    if not _root.exists():
                        continue
                    for _si in SkillLoader(_root).load():
                        if not _si.is_developer_only:
                            _all_skill_experts.update(_si.experts)
            except Exception as _sl_exc:
                log.debug("could not load skill experts list: %s", _sl_exc)
                _all_skill_experts = set()

            if req.skill.strip():
                # Narrow further to the explicitly selected skill's experts.
                _active_skill_name = req.skill.strip()
                _skill_experts: set[str] = set()
                _skill_found = False
                try:
                    from surogate_agent.skills.loader import SkillLoader
                    for _root in [config.user_skills_dir] + list(config.skills_dirs):
                        if not _root.exists():
                            continue
                        for _si in SkillLoader(_root).load():
                            if _si.name == _active_skill_name:
                                _skill_experts = set(_si.experts)
                                _skill_found = True
                                break
                        if _skill_found:
                            break
                except Exception as _sl_exc2:
                    log.debug("could not load active skill experts list: %s", _sl_exc2)
                _all_skill_experts = _skill_experts
                log.debug("skill '%s' experts: %s", _active_skill_name, sorted(_all_skill_experts))

            config.experts = [
                e for e in config.experts if e.get("name") in _all_skill_experts
            ]
            log.debug("user experts after filter: %s", [e.get("name") for e in config.experts])

        # Set up per-request subagent activity queue so _CapturingRunnable
        # can forward expert message histories back to this SSE stream.
        import asyncio as _asyncio
        _sa_queue: _asyncio.Queue = _asyncio.Queue()
        _sa_token = subagent_activity_queue.set(_sa_queue)

        # Create agent
        agent = create_agent(
            role=role,
            config=config,
            session=session,
            user_id=req.user_id or f"api-{role.value}",
            checkpointer=checkpointer,
            active_skill=dev_skill,
        )

        # For user-role chats, announce which skills are loaded so the frontend
        # can display a real-time "Skill activity" panel with names and descriptions.
        if role == Role.USER:
            from surogate_agent.skills.registry import SkillRegistry
            _skill_registry = SkillRegistry()
            if _DEFAULT_SKILLS_DIR.exists():
                _skill_registry.scan(_DEFAULT_SKILLS_DIR)
            if config.user_skills_dir.exists():
                _skill_registry.scan(config.user_skills_dir)
            _user_paths = _skill_registry.paths_for_role(Role.USER)
            _active_skills = [
                s for s in _skill_registry.all_skills()
                if s.path in _user_paths
            ]
            if req.skill.strip():
                _active_skills = [s for s in _active_skills if s.name == req.skill.strip()]
            for _si in _active_skills:
                log.debug("SSE skill_use: %s", _si.name)
                yield _sse_event("skill_use", {"name": _si.name, "description": _si.description})

        invoke_config = {"configurable": {"thread_id": thread_id}}

        # Truncate new user message to fit the model's context window.
        # Uses 4 chars-per-token approximation; _VLLM_OVERHEAD_RESERVE tokens
        # are reserved for system prompt + tool schemas + model output.
        message_text = req.message
        if config.vllm_context_length and config.vllm_base_url:
            max_chars = max(0, (config.vllm_context_length - _VLLM_OVERHEAD_RESERVE) * 4)
            if len(message_text) > max_chars:
                log.warning(
                    "message truncated: original=%d chars, limit=%d chars (context_length=%d tokens)",
                    len(message_text), max_chars, config.vllm_context_length,
                )
                message_text = message_text[:max_chars]

        invoke_input = {"messages": [{"role": "user", "content": message_text}]}

        rendered_ids: set[str] = set()
        _checkpoint_tuple = None

        # Load checkpoint: pre-seed rendered_ids so history is not re-streamed,
        # then trim old messages if a context_length limit is configured.
        if checkpointer is not None:
            try:
                _checkpoint_tuple = await checkpointer.aget_tuple(invoke_config)
                if _checkpoint_tuple and _checkpoint_tuple.checkpoint:
                    existing = _unwrap_messages(
                        _checkpoint_tuple.checkpoint
                        .get("channel_values", {})
                        .get("messages")
                    )
                    for m in existing:
                        mid = (
                            m.get("id") if isinstance(m, dict)
                            else getattr(m, "id", None)
                        )
                        if mid:
                            rendered_ids.add(mid)
                    log.debug(
                        "pre-seeded %d rendered_ids from checkpoint thread=%s",
                        len(rendered_ids), thread_id,
                    )
            except Exception as exc:
                log.debug("could not pre-seed rendered_ids: %s", exc)

        # Trim stored history so the full request (history + new message +
        # system/tools) fits inside the model's context window.
        if config.vllm_context_length and config.vllm_base_url and checkpointer is not None and _checkpoint_tuple is not None:
            await _trim_checkpoint_to_context(
                checkpointer, invoke_config, _checkpoint_tuple, config.vllm_context_length,
            )

        def _is_context_overflow(exc: Exception) -> bool:
            """Detect vLLM / OpenAI-compatible context-length errors."""
            msg = str(exc).lower()
            return any(kw in msg for kw in (
                "context length", "context window", "input_tokens",
                "maximum context", "too many tokens", "max_tokens",
            ))

        import asyncio as _asyncio

        async def _drain_subagent_queue():
            """Yield subagent_activity SSE events for all queued subagent updates.

            Queue entries are 3-tuples (expert_name, messages, is_partial).
            Partial entries are intermediate streaming updates; the final entry
            has is_partial=False and signals that the subagent has finished.
            """
            while not _sa_queue.empty():
                try:
                    entry = _sa_queue.get_nowait()
                    expert_name, messages = entry[0], entry[1]
                    is_partial = entry[2] if len(entry) > 2 else False
                    activity = _extract_subagent_activity(expert_name, messages)
                    activity["partial"] = is_partial
                    log.debug(
                        "SSE subagent_activity: %s (%d items, partial=%s)",
                        expert_name, len(activity["items"]), is_partial,
                    )
                    yield _sse_event("subagent_activity", activity)
                except Exception:
                    break

        def _process_msg(msg):
            """Yield SSE event dicts for a single LangGraph message."""
            msg_type = (
                msg.get("role") if isinstance(msg, dict)
                else getattr(msg, "type", None)
            )

            if msg_type in ("ai", "assistant"):
                content = (
                    msg.get("content", "") if isinstance(msg, dict)
                    else getattr(msg, "content", "")
                )
                tool_calls = (
                    msg.get("tool_calls", []) if isinstance(msg, dict)
                    else getattr(msg, "tool_calls", [])
                )

                if config.thinking_enabled:
                    thinking = _extract_thinking(content) or _extract_openrouter_reasoning(msg)
                    if thinking:
                        log.trace("SSE thinking block (%d chars)", len(thinking))  # type: ignore[attr-defined]
                        yield _sse_event("thinking", {"text": thinking})

                for tc in tool_calls or []:
                    name = (
                        tc.get("name", "?") if isinstance(tc, dict)
                        else getattr(tc, "name", "?")
                    )
                    args = (
                        tc.get("args", {}) if isinstance(tc, dict)
                        else getattr(tc, "args", {})
                    )
                    log.trace("SSE tool_call: %s args=%r", name, args)  # type: ignore[attr-defined]
                    yield _sse_event("tool_call", {"name": name, "args": args})

                text = _extract_content_text(content)
                if text:
                    inline_thinking, clean_text = _split_inline_thinking(text)
                    if inline_thinking and config.thinking_enabled:
                        log.trace("SSE thinking (inline <think> tag, %d chars)", len(inline_thinking))  # type: ignore[attr-defined]
                        yield _sse_event("thinking", {"text": inline_thinking})
                    display_text = clean_text if inline_thinking else text
                    if display_text:
                        log.trace("SSE text (%d chars)", len(display_text))  # type: ignore[attr-defined]
                        yield _sse_event("text", {"text": display_text})

            elif msg_type == "tool":
                name = (
                    msg.get("name", "?") if isinstance(msg, dict)
                    else getattr(msg, "name", getattr(msg, "tool_call_id", "?"))
                )
                result_content = (
                    msg.get("content", "") if isinstance(msg, dict)
                    else getattr(msg, "content", "")
                )
                log.trace("SSE tool_result: %s (%d chars)", name, len(str(result_content)))  # type: ignore[attr-defined]
                yield _sse_event(
                    "tool_result",
                    {"name": name, "result": str(result_content)[:500]},
                )

        async def _run_agent(the_agent):
            """Async generator that streams SSE events with real-time subagent activity.

            Runs the agent in a background asyncio task and polls the subagent
            activity queue every 100 ms so incremental subagent events are emitted
            while the task tool is still executing (not just after it returns).
            """
            buf: _asyncio.Queue = _asyncio.Queue()

            async def _agent_worker():
                try:
                    async for chunk in the_agent.astream(invoke_input, config=invoke_config):
                        await buf.put(("chunk", chunk))
                except Exception as exc:
                    await buf.put(("error", exc))
                finally:
                    await buf.put(("done", None))

            agent_task = _asyncio.create_task(_agent_worker())
            try:
                while True:
                    # Drain SA queue — emits real-time subagent activity between chunks
                    async for sa_event in _drain_subagent_queue():
                        yield sa_event

                    # Wait for next agent chunk (short timeout keeps SA queue responsive)
                    try:
                        kind, data = await _asyncio.wait_for(buf.get(), timeout=0.1)
                    except _asyncio.TimeoutError:
                        continue  # loop back, drain SA queue again

                    if kind == "done":
                        # Final drain after agent finishes
                        async for sa_event in _drain_subagent_queue():
                            yield sa_event
                        break
                    elif kind == "error":
                        raise data

                    # Process messages in this chunk
                    for msg in _iter_messages(data):
                        msg_id = (
                            msg.get("id") if isinstance(msg, dict)
                            else getattr(msg, "id", None)
                        )
                        if msg_id:
                            if msg_id in rendered_ids:
                                continue
                            rendered_ids.add(msg_id)

                        for sse_ev in _process_msg(msg):
                            yield sse_ev
            finally:
                agent_task.cancel()
                try:
                    await agent_task
                except _asyncio.CancelledError:
                    pass

        try:
            # First attempt — normal flow.
            # If the model rejects the request due to context overflow AND tool
            # calling is enabled, automatically retry without tool schemas.
            # Tool definitions alone can be 3000-6000 tokens and are the most
            # common cause of overflow on small-context models (≤8k).
            context_overflow_exc: Exception | None = None
            try:
                async for event in _run_agent(agent):
                    yield event
            except Exception as _stream_exc:
                if (
                    config.vllm_context_length
                    and config.vllm_base_url
                    and config.vllm_tool_calling
                    and _is_context_overflow(_stream_exc)
                ):
                    context_overflow_exc = _stream_exc
                else:
                    raise

            if context_overflow_exc is not None:
                log.warning(
                    "context overflow with tool calling enabled; retrying without tool schemas: %s",
                    context_overflow_exc,
                )
                yield _sse_event(
                    "text",
                    {"text": "\n\n*Context window exceeded — retrying without tool calling.*\n\n"},
                )
                config.vllm_tool_calling = False
                rendered_ids.clear()
                retry_agent = create_agent(
                    role=role,
                    config=config,
                    session=session,
                    user_id=req.user_id or f"api-{role.value}",
                    checkpointer=checkpointer,
                    active_skill=dev_skill,
                )
                async for event in _run_agent(retry_agent):
                    yield event

        finally:
            subagent_activity_queue.reset(_sa_token)
            if _checkpointer_ctx is not None:
                try:
                    await _checkpointer_ctx.__aexit__(None, None, None)
                except Exception:
                    pass

        # Done event
        files = [f.name for f in session.files]
        log.info(
            "chat completed: session=%s files=%d",
            session.session_id, len(files),
        )
        yield _sse_event("done", {"session_id": session.session_id, "files": files})

    except Exception as exc:
        log.error("unhandled exception in chat stream: %s", exc, exc_info=True)
        yield _sse_event("error", {"detail": str(exc)})


@router.post("/chat")
async def chat_endpoint(
    req: ChatRequest,
    request: Request,
    settings: ServerSettings = Depends(settings_dep),
    current_user: User = Depends(get_current_user),
):
    if EventSourceResponse is None:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=500,
            content={"detail": "sse-starlette is not installed. Run: pip install sse-starlette"},
        )

    # Role resolution: prevent privilege escalation (user→developer) but allow
    # a developer to explicitly downgrade to user for "Test as User" scenarios.
    requested_role = req.role.lower()
    if current_user.role == "developer":
        # Developer may request either role; default to their own.
        effective_role = requested_role if requested_role in ("developer", "user") else current_user.role
    else:
        # Non-developer accounts are always user — ignore any requested escalation.
        effective_role = current_user.role

    authed_req = req.model_copy(update={
        "role": effective_role,
        "user_id": current_user.username,
        "model": req.model or (current_user.model or ""),
        "api_key": req.api_key or (current_user.api_key or ""),
        "openrouter_provider": req.openrouter_provider or (current_user.openrouter_provider or ""),
        "vllm_url": req.vllm_url or (current_user.vllm_url or ""),
        # vLLM advanced settings: fall back to saved user profile when not in request
        "vllm_tool_calling": req.vllm_tool_calling if req.vllm_url else (
            current_user.vllm_tool_calling if current_user.vllm_tool_calling is not None else True
        ),
        "vllm_temperature": req.vllm_temperature if req.vllm_temperature is not None else current_user.vllm_temperature,
        "vllm_top_k": req.vllm_top_k if req.vllm_top_k is not None else current_user.vllm_top_k,
        "vllm_top_p": req.vllm_top_p if req.vllm_top_p is not None else current_user.vllm_top_p,
        "vllm_min_p": req.vllm_min_p if req.vllm_min_p is not None else current_user.vllm_min_p,
        "vllm_presence_penalty": req.vllm_presence_penalty if req.vllm_presence_penalty is not None else current_user.vllm_presence_penalty,
        "vllm_context_length": req.vllm_context_length if req.vllm_context_length is not None else current_user.vllm_context_length,
        "thinking_enabled": req.thinking_enabled if req.thinking_enabled else (current_user.thinking_enabled or False),
        "thinking_budget": req.thinking_budget if req.thinking_budget != 10000 else (current_user.thinking_budget or 10000),
    })

    # Load experts for the current user (use a short-lived session, not a Depends,
    # so tests that mock get_current_user but not get_db continue to work).
    experts_data: list[dict] = []
    expert_lookup_enabled_flag = bool(current_user.expert_lookup_enabled)
    try:
        from surogate_agent.auth.database import SessionLocal
        from surogate_agent.auth.schemas import ExpertResponse
        from surogate_agent.auth.service import list_all_experts
        with SessionLocal() as _db:
            _db_experts = list_all_experts(_db)
            for _exp in _db_experts:
                _schema = ExpertResponse.model_validate(_exp)
                experts_data.append(_schema.model_dump())
    except Exception as _exp_load_exc:
        log.debug("could not load experts: %s", _exp_load_exc)

    async def generator():
        async for event in _stream_chat(
            authed_req, settings,
            experts_data=experts_data,
            expert_lookup_enabled=expert_lookup_enabled_flag,
        ):
            yield event

    return EventSourceResponse(generator())
