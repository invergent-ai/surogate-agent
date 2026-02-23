"""
Chat router — POST /chat  (Server-Sent Events stream)
"""

from __future__ import annotations

import json
import time
from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from starlette.requests import Request

from surogate_agent.api.deps import ServerSettings, settings_dep
from surogate_agent.api.models import ChatRequest
from surogate_agent.core.agent import create_agent
from surogate_agent.core.config import AgentConfig
from surogate_agent.core.roles import Role
from surogate_agent.core.session import SessionManager

try:
    from sse_starlette.sse import EventSourceResponse
except ImportError:
    EventSourceResponse = None  # type: ignore[assignment,misc]

router = APIRouter(tags=["chat"])


def _sse_event(event: str, data: dict) -> dict:
    return {"event": event, "data": json.dumps(data)}


def _extract_thinking(content) -> str:
    if not isinstance(content, list):
        return ""
    parts = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "thinking":
            parts.append(block.get("thinking", ""))
        elif hasattr(block, "type") and getattr(block, "type", None) == "thinking":
            parts.append(getattr(block, "thinking", ""))
    return "\n\n".join(p for p in parts if p)


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


def _looks_like_message(obj) -> bool:
    t = getattr(obj, "type", None)
    if isinstance(t, str):
        return True
    return isinstance(obj, dict) and "role" in obj


async def _stream_chat(
    req: ChatRequest,
    settings: ServerSettings,
) -> AsyncGenerator[dict, None]:
    try:
        # Resolve role
        try:
            role = Role(req.role.lower())
        except ValueError:
            yield _sse_event("error", {"detail": f"Invalid role '{req.role}'"})
            return

        # Build config
        model = req.model or settings.model
        config = AgentConfig(
            model=model,
            user_skills_dir=settings.skills_dir,
            sessions_dir=settings.sessions_dir,
            dev_workspace_dir=settings.workspace_dir,
            allow_execute=req.allow_execute,
        )

        # Session setup
        sm = SessionManager(settings.sessions_dir)
        if role == Role.DEVELOPER:
            dev_skill = req.skill.strip()
            config.dev_workspace_dir.mkdir(parents=True, exist_ok=True)
            if dev_skill:
                thread_id = f"dev:{dev_skill}"
                skill_workspace = config.dev_workspace_dir / dev_skill
            else:
                thread_id = f"dev:{int(time.time())}"
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

        # Checkpointer
        checkpointer = None
        _checkpointer_ctx = None
        if role == Role.DEVELOPER and req.skill.strip():
            history_db = config.dev_workspace_dir / ".history.db"
            try:
                from langgraph.checkpoint.sqlite import SqliteSaver
                _checkpointer_ctx = SqliteSaver.from_conn_string(str(history_db))
                checkpointer = _checkpointer_ctx.__enter__()
            except ImportError:
                pass
        elif role == Role.USER and req.session_id:
            history_db = settings.sessions_dir / ".history.db"
            try:
                from langgraph.checkpoint.sqlite import SqliteSaver
                _checkpointer_ctx = SqliteSaver.from_conn_string(str(history_db))
                checkpointer = _checkpointer_ctx.__enter__()
            except ImportError:
                pass

        if checkpointer is None:
            try:
                from langgraph.checkpoint.memory import MemorySaver
                checkpointer = MemorySaver()
            except ImportError:
                pass

        # Create agent
        agent = create_agent(
            role=role,
            config=config,
            session=session,
            user_id=req.user_id or f"api-{role.value}",
            checkpointer=checkpointer,
        )

        invoke_config = {"configurable": {"thread_id": thread_id}}
        invoke_input = {"messages": [{"role": "user", "content": req.message}]}

        rendered_ids: set[str] = set()

        try:
            async for chunk in agent.astream(invoke_input, config=invoke_config):
                for msg in _iter_messages(chunk):
                    msg_id = (
                        msg.get("id") if isinstance(msg, dict)
                        else getattr(msg, "id", None)
                    )
                    if msg_id:
                        if msg_id in rendered_ids:
                            continue
                        rendered_ids.add(msg_id)

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

                        thinking = _extract_thinking(content)
                        if thinking:
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
                            yield _sse_event("tool_call", {"name": name, "args": args})

                        text = _extract_content_text(content)
                        if text:
                            yield _sse_event("text", {"text": text})

                    elif msg_type == "tool":
                        name = (
                            msg.get("name", "?") if isinstance(msg, dict)
                            else getattr(msg, "name", getattr(msg, "tool_call_id", "?"))
                        )
                        result_content = (
                            msg.get("content", "") if isinstance(msg, dict)
                            else getattr(msg, "content", "")
                        )
                        yield _sse_event(
                            "tool_result",
                            {"name": name, "result": str(result_content)[:500]},
                        )

        finally:
            if _checkpointer_ctx is not None:
                try:
                    _checkpointer_ctx.__exit__(None, None, None)
                except Exception:
                    pass

        # Done event
        files = [f.name for f in session.files]
        yield _sse_event("done", {"session_id": session.session_id, "files": files})

    except Exception as exc:
        yield _sse_event("error", {"detail": str(exc)})


@router.post("/chat")
async def chat_endpoint(req: ChatRequest, request: Request, settings: ServerSettings = Depends(settings_dep)):
    if EventSourceResponse is None:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=500,
            content={"detail": "sse-starlette is not installed. Run: pip install sse-starlette"},
        )

    async def generator():
        async for event in _stream_chat(req, settings):
            yield event

    return EventSourceResponse(generator())
