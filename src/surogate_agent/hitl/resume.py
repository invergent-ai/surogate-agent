"""Resume a paused HITL session after the assigned user responds.

Called as a background asyncio task from the tasks router.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime

from surogate_agent.core.logging import get_logger

log = get_logger(__name__)


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
            )

            agent = create_agent(
                role=Role.USER,
                config=config,
                session=session,
                user_id=origin_user_id,
                checkpointer=checkpointer,
            )

            invoke_config = {"configurable": {"thread_id": origin_session_id}}
            log.info("resuming HITL session %s with response %r", origin_session_id, response)

            # Mark as a HITL resume so _create_task() knows it's being re-run
            # by LangGraph (not called fresh) and skips duplicate task creation.
            from surogate_agent.core.agent import hitl_session_context
            _resume_tok = hitl_session_context.set({
                "thread_id": origin_session_id,
                "user_id": origin_user_id,
                "is_resume": True,
            })

            # Collect AI text from the resumed stream so we can persist it to
            # ChatHistory before releasing the session lock.
            text_parts: list[str] = []
            seen_ids: set[str] = set()
            try:
                async for chunk in agent.astream(Command(resume=response), config=invoke_config):
                    if not isinstance(chunk, dict):
                        continue
                    # Walk all node outputs looking for AI messages
                    for node_output in chunk.values():
                        if not isinstance(node_output, dict):
                            continue
                        raw_msgs = node_output.get("messages") or []
                        if hasattr(raw_msgs, "value"):
                            raw_msgs = raw_msgs.value
                        if not isinstance(raw_msgs, list):
                            raw_msgs = []
                        for msg in raw_msgs:
                            msg_id = (
                                msg.get("id") if isinstance(msg, dict)
                                else getattr(msg, "id", None)
                            )
                            if msg_id and msg_id in seen_ids:
                                continue
                            if msg_id:
                                seen_ids.add(msg_id)
                            msg_type = (
                                msg.get("type") if isinstance(msg, dict)
                                else getattr(msg, "type", None)
                            )
                            if msg_type not in ("ai", "assistant"):
                                continue
                            content = (
                                msg.get("content", "") if isinstance(msg, dict)
                                else getattr(msg, "content", "")
                            )
                            if isinstance(content, str) and content.strip():
                                text_parts.append(content)
                            elif isinstance(content, list):
                                for part in content:
                                    if isinstance(part, dict) and part.get("type") == "text":
                                        t = part.get("text", "")
                                        if t.strip():
                                            text_parts.append(t)
            finally:
                hitl_session_context.reset(_resume_tok)

            log.info(
                "HITL checkpoint resumed for session %s (%d text parts collected)",
                origin_session_id, len(text_parts),
            )

    except Exception as exc:
        log.error(
            "failed to resume HITL checkpoint for session %s: %s",
            origin_session_id, exc, exc_info=True,
        )


def _restore_model(context_json: str | None, settings) -> str:
    """Extract saved model from task context_json, fall back to server default."""
    try:
        ctx = json.loads(context_json or "{}")
        return ctx.get("_model", "") or settings.model
    except Exception:
        return settings.model


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


def _append_assistant_message(session_id: str, user_id: str, text: str) -> None:
    """Append an assistant message to the stored ChatHistory for a session.

    Uses a ``hitl_response`` block so the frontend renders it with the distinct
    amber-accented "Task response" style rather than a regular text bubble.
    Reads the current messages_json, appends the message, and writes it back.
    Creates a new row if none exists yet.
    """
    from surogate_agent.auth.database import SessionLocal
    from surogate_agent.auth.models import ChatHistory

    new_msg = {
        "id": f"msg-hitl-{uuid.uuid4().hex[:8]}",
        "role": "assistant",
        "blocks": [{"type": "hitl_response", "text": text}],
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
