"""Resume a paused HITL session after the assigned user responds.

Called as a background asyncio task from the tasks router.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime

from surogate_agent.core.logging import get_logger

log = get_logger(__name__)


def _collect_ai_text(msg, seen_ids: set, text_parts: list) -> None:
    """Extract text from an AI/assistant message and append to text_parts.

    Skips messages whose id is already in seen_ids (deduplication for
    "values" stream mode which replays the full history on every chunk).
    Works with both LangChain message objects and plain dicts.
    """
    msg_id = msg.get("id") if isinstance(msg, dict) else getattr(msg, "id", None)
    if msg_id:
        if msg_id in seen_ids:
            return
        seen_ids.add(msg_id)

    msg_type = msg.get("type") if isinstance(msg, dict) else getattr(msg, "type", None)
    if msg_type not in ("ai", "assistant"):
        return

    content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
    if isinstance(content, str):
        if content.strip():
            text_parts.append(content)
    elif isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                t = part.get("text", "")
                if t.strip():
                    text_parts.append(t)
            elif not isinstance(part, dict):
                # Handle Pydantic content block objects (e.g. Anthropic extended thinking)
                part_type = getattr(part, "type", None)
                if part_type == "text":
                    t = getattr(part, "text", "")
                    if isinstance(t, str) and t.strip():
                        text_parts.append(t)


async def resume_hitl_session(
    origin_session_id: str,
    origin_user_id: str,
    context_json: str | None,
    response: dict,
) -> None:
    """Re-enter the paused LangGraph session with the human response.

    Opens a fresh ``AsyncSqliteSaver`` on the shared checkpoints.db,
    reconstructs the agent, and calls ``astream(Command(resume=response))``
    on the original ``thread_id``.  The agent continuation is written to
    ``ChatHistory`` and then the ``SessionLock`` is released so the
    originating user's frontend sees the response immediately on unlock.

    Parameters
    ----------
    origin_session_id:
        The session/thread_id of the originating user's conversation.
    origin_user_id:
        The user_id of the originating user.
    context_json:
        The ``HumanTask.context_json`` string (carries model/config).
    response:
        The dict built by the tasks router, e.g.
        ``{"decision": "approved", "feedback": "Looks good"}``.
    """
    try:
        from langgraph.types import Command
    except ImportError:
        log.warning("LangGraph not installed — cannot resume HITL session %s", origin_session_id)
        _release_session_lock(origin_session_id)
        return

    from surogate_agent.core.config import AgentConfig, get_checkpointer_path
    from surogate_agent.core.roles import Role
    from surogate_agent.core.session import Session, SessionManager
    from surogate_agent.core.agent import create_agent
    from surogate_agent.api.deps import get_settings

    settings = get_settings()
    checkpointer_path = get_checkpointer_path()

    try:
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        checkpointer_path.parent.mkdir(parents=True, exist_ok=True)
        async with AsyncSqliteSaver.from_conn_string(str(checkpointer_path)) as checkpointer:
            sm = SessionManager(settings.sessions_dir)
            session = sm.resume_or_create(origin_session_id)

            config = AgentConfig(
                user_skills_dir=settings.skills_dir,
                sessions_dir=settings.sessions_dir,
                dev_workspace_dir=settings.workspace_dir,
                mcp_workspace_dir=settings.mcp_workspace_dir,
                mcp_scripts_dir=settings.mcp_scripts_dir,
                model=_restore_model(context_json, settings),
                api_key=_restore_api_key(context_json),
            )

            agent = create_agent(
                role=Role.USER,
                config=config,
                session=session,
                user_id=origin_user_id,
                checkpointer=checkpointer,
            )

            invoke_config = {"configurable": {"thread_id": origin_session_id}}

            # Read the message IDs present in the checkpoint BEFORE resuming so
            # that after astream we can diff and find only the NEW AI messages.
            pre_ids: set[str] = set()
            try:
                _pre_tuple = await checkpointer.aget_tuple(invoke_config)
                if _pre_tuple and _pre_tuple.checkpoint:
                    _pre_msgs = _pre_tuple.checkpoint.get("channel_values", {}).get("messages", [])
                    if hasattr(_pre_msgs, "value"):
                        _pre_msgs = _pre_msgs.value
                    for _m in (_pre_msgs or []):
                        _mid = _m.get("id") if isinstance(_m, dict) else getattr(_m, "id", None)
                        if _mid:
                            pre_ids.add(_mid)
                    # Verify the checkpoint actually has a pending interrupt before resuming.
                    _has_interrupt = bool(
                        _pre_tuple.pending_writes and any(
                            (w[1] if isinstance(w, (tuple, list)) and len(w) > 1 else "") == "__interrupt__"
                            for w in _pre_tuple.pending_writes
                        )
                    )
                    if not _has_interrupt:
                        log.warning(
                            "HITL resume: no pending interrupt in checkpoint for session %s — skipping resume",
                            origin_session_id,
                        )
                        return
                else:
                    log.warning("HITL resume: no checkpoint found for session %s", origin_session_id)
                    return
            except Exception as _chk_exc:
                log.warning("HITL resume: checkpoint read failed for session %s: %s", origin_session_id, _chk_exc)
                # Continue anyway — let astream handle it

            # Mark as a HITL resume so _create_task() knows it's being re-run
            # by LangGraph (not called fresh) and skips duplicate task creation.
            from surogate_agent.core.agent import hitl_session_context
            _resume_tok = hitl_session_context.set({
                "thread_id": origin_session_id,
                "user_id": origin_user_id,
                "is_resume": True,
            })

            # Use astream (same as chat.py's proven auto-resume path).  Each
            # chunk is a dict of {node_name: node_output}; we extract the last
            # message from each chunk and collect any NEW AI text (not in pre_ids).
            text_parts: list[str] = []
            seen_ids: set[str] = set()
            chunk_count = 0
            try:
                log.warning("HITL resume: calling astream for session %s", origin_session_id)
                async for chunk in agent.astream(Command(resume=response), config=invoke_config):
                    chunk_count += 1
                    # Each chunk is {node_name: node_output} or similar dict.
                    # Mirrors _iter_messages() in chat.py.
                    msgs_in_chunk: list = []
                    if isinstance(chunk, dict):
                        # stream_mode="values": top-level "messages" key
                        if "messages" in chunk:
                            raw = chunk["messages"]
                            if hasattr(raw, "value"):
                                raw = raw.value
                            msgs_in_chunk.extend(raw if isinstance(raw, list) else [])
                        else:
                            # stream_mode="updates": {node_name: node_updates}
                            for node_output in chunk.values():
                                if isinstance(node_output, dict):
                                    node_msgs = node_output.get("messages", [])
                                    if hasattr(node_msgs, "value"):
                                        node_msgs = node_msgs.value
                                    msgs_in_chunk.extend(node_msgs if isinstance(node_msgs, list) else [])
                                elif isinstance(node_output, list):
                                    for item in node_output:
                                        if isinstance(getattr(item, "type", None), str):
                                            msgs_in_chunk.append(item)
                    for msg in msgs_in_chunk:
                        _mid = (
                            msg.get("id") if isinstance(msg, dict)
                            else getattr(msg, "id", None)
                        )
                        if _mid and _mid in pre_ids:
                            continue  # pre-existing message, skip
                        _collect_ai_text(msg, seen_ids, text_parts)
                log.warning(
                    "HITL resume: astream completed for session %s "
                    "(chunks=%d text_parts=%d)",
                    origin_session_id, chunk_count, len(text_parts),
                )
            finally:
                hitl_session_context.reset(_resume_tok)

            if not text_parts:
                log.warning(
                    "HITL resume: no AI text collected for session %s — "
                    "agent produced no visible text after resuming",
                    origin_session_id,
                )
            else:
                # Persist the agent's continuation to ChatHistory so the frontend
                # sees it when the lock is released below.
                continuation = "\n\n".join(text_parts)
                _append_assistant_message(
                    origin_session_id, origin_user_id, continuation, block_type="text"
                )

    except Exception as exc:
        log.error(
            "failed to resume HITL checkpoint for session %s: %s",
            origin_session_id, exc, exc_info=True,
        )
    finally:
        # Always release the lock — even on error — so the session never stays
        # locked forever.  The frontend detects this and reloads history.
        _release_session_lock(origin_session_id)


def _restore_model(context_json: str | None, settings) -> str:
    """Extract saved model from task context_json, fall back to server default."""
    try:
        ctx = json.loads(context_json or "{}")
        return ctx.get("_model", "") or settings.model
    except Exception:
        return settings.model


def _restore_api_key(context_json: str | None) -> str:
    """Extract saved api_key from task context_json (empty string if absent)."""
    try:
        ctx = json.loads(context_json or "{}")
        return ctx.get("_api_key", "")
    except Exception:
        return ""


def _format_task_response_text(task_type: str, response: dict) -> str:
    """Build a human-readable summary of a HITL task response."""
    feedback = response.get("feedback", "")
    if task_type == "approval":
        decision = response.get("decision", "unknown")
        text = f"**Approval decision: {decision.capitalize()}**"
    elif task_type == "file_request":
        files = response.get("files", [])
        text = f"**Files uploaded: {len(files)} file(s)**"
        if files:
            text += "\n\n" + "\n".join(f"- `{f}`" for f in files)
    elif task_type == "form_input":
        form_data = response.get("form_data", {})
        text = "**Form submitted.**"
        if form_data:
            text += "\n\n" + "\n".join(f"- **{k}**: {v}" for k, v in form_data.items())
    else:
        text = "**Report acknowledged.**"
    if feedback:
        text += f"\n\nFeedback: {feedback}"
    return text


def _append_task_response_to_history(
    session_id: str, user_id: str, task_type: str, response: dict
) -> None:
    """Write the HITL task response as a ``hitl_response`` block in ChatHistory.

    Called synchronously from ``respond_to_task()`` so the message is visible
    immediately when the frontend reloads history on session unlock.
    """
    text = _format_task_response_text(task_type, response)
    _append_assistant_message(session_id, user_id, text)


def _append_assistant_message(
    session_id: str,
    user_id: str,
    text: str,
    block_type: str = "hitl_response",
) -> None:
    """Append an assistant message to the stored ChatHistory for a session.

    ``block_type`` controls how the frontend renders the block:
    - ``"hitl_response"`` — amber-accented "Task response" style (task summaries)
    - ``"text"``          — plain assistant text bubble (agent continuation output)

    Reads the current messages_json, appends the message, and writes it back.
    Creates a new row if none exists yet.
    """
    from surogate_agent.auth.database import SessionLocal
    from surogate_agent.auth.models import ChatHistory

    new_msg = {
        "id": f"msg-hitl-{uuid.uuid4().hex[:8]}",
        "role": "assistant",
        "blocks": [{"type": block_type, "text": text}],
        "timestamp": datetime.utcnow().isoformat(),
        "finalized": True,
    }
    try:
        with SessionLocal() as db:
            record = db.query(ChatHistory).filter_by(
                session_id=session_id, user_id=user_id,
            ).first()
            if record:
                messages = json.loads(record.messages_json or "[]")
                messages.append(new_msg)
                record.messages_json = json.dumps(messages)
                record.updated_at = datetime.utcnow()
            else:
                db.add(ChatHistory(
                    session_id=session_id,
                    user_id=user_id,
                    messages_json=json.dumps([new_msg]),
                ))
            db.commit()
        log.info(
            "HITL continuation written to ChatHistory for session %s (%d chars)",
            session_id, len(text),
        )
    except Exception as exc:
        log.error(
            "failed to write HITL continuation to ChatHistory for session %s: %s",
            session_id, exc, exc_info=True,
        )


def _release_session_lock(session_id: str) -> None:
    """Delete the SessionLock row for a session (no-op if it doesn't exist)."""
    from surogate_agent.auth.database import SessionLocal
    from surogate_agent.auth.models import SessionLock

    try:
        with SessionLocal() as db:
            lock = db.query(SessionLock).filter_by(session_id=session_id).first()
            if lock:
                db.delete(lock)
                db.commit()
        log.info("session lock released for session %s", session_id)
    except Exception as exc:
        log.error(
            "failed to release session lock for session %s: %s",
            session_id, exc, exc_info=True,
        )
