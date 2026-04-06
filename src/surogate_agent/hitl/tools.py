"""HITL tools injected into user-role agents.

``request_approval`` and ``send_report`` let the agent route a task to another
user and (optionally) suspend execution until they respond.

The tools read the current session context from the ``hitl_session_context``
ContextVar that ``chat.py`` sets before invoking the agent.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from langchain_core.tools import tool

from surogate_agent.core.agent import hitl_session_context
from surogate_agent.core.logging import get_logger

log = get_logger(__name__)


def _create_task(
    task_type: str,
    assigned_to: str,
    title: str,
    description: str,
    context: dict[str, Any],
) -> str:
    """Write a HumanTask + SessionLock row and call interrupt().

    Returns the LangGraph resume value as a formatted string after the graph
    is resumed by the task router (i.e. only called AFTER human responds).
    """
    from surogate_agent.auth.database import SessionLocal
    from surogate_agent.auth.models import HumanTask, SessionLock

    ctx = hitl_session_context.get(None)
    if ctx is None:
        return (
            f"[HITL unavailable] Would have sent a {task_type} task titled "
            f"'{title}' to {assigned_to!r}."
        )

    origin_session_id = ctx["thread_id"]
    origin_user_id = ctx["user_id"]

    # LangGraph re-runs the entire tool node from the beginning when resuming
    # via Command(resume=...).  The caller (chat.py or resume.py) sets
    # ``is_resume=True`` in hitl_session_context before streaming the Command,
    # so we can distinguish a genuine resume from a fresh task creation.
    is_resume = ctx.get("is_resume", False) if ctx else False

    if not is_resume:
        # First execution — create the task and session lock.
        task_id = str(uuid.uuid4())
        try:
            # Enrich context with LLM settings so resume can use the same model/key.
            context_to_save = dict(context)
            if ctx.get("api_key"):
                context_to_save["_api_key"] = ctx["api_key"]
            if ctx.get("model"):
                context_to_save["_model"] = ctx["model"]
            with SessionLocal() as db:
                task = HumanTask(
                    id=task_id,
                    task_type=task_type,
                    status="pending",
                    origin_session_id=origin_session_id,
                    origin_user_id=origin_user_id,
                    assigned_user_id=assigned_to,
                    title=title,
                    description=description,
                    context_json=json.dumps(context_to_save),
                    created_at=datetime.utcnow(),
                )
                db.add(task)
                existing = db.get(SessionLock, origin_session_id)
                if not existing:
                    db.add(SessionLock(
                        session_id=origin_session_id,
                        task_id=task_id,
                        locked_at=datetime.utcnow(),
                    ))
                db.commit()
                log.info(
                    "HITL task created: id=%s type=%s assigned_to=%r origin=%s",
                    task_id, task_type, assigned_to, origin_session_id,
                )
        except Exception as exc:
            log.error("failed to create HITL task: %s", exc, exc_info=True)
            return f"Failed to create {task_type} task: {exc}"
    else:
        # Resume execution — find the pending task for this session to get
        # the task_id that interrupt() was originally called with.
        task_id_for_resume: str | None = None
        try:
            with SessionLocal() as _chk_db:
                _existing = (
                    _chk_db.query(HumanTask)
                    .filter_by(
                        origin_session_id=origin_session_id,
                        task_type=task_type,
                        status="completed",
                    )
                    .order_by(HumanTask.responded_at.desc())
                    .first()
                )
                if _existing:
                    task_id_for_resume = _existing.id
        except Exception as _chk_exc:
            log.debug("resume task-id lookup failed: %s", _chk_exc)

        if task_id_for_resume is None:
            log.warning(
                "HITL resume flag set but no completed task found for session %s type=%s",
                origin_session_id, task_type,
            )
            return f"[HITL resume error] Could not find completed task for session {origin_session_id}"

        task_id = task_id_for_resume
        log.info(
            "HITL resume detected for session %s: reusing task_id=%s",
            origin_session_id, task_id,
        )

    # Suspend the graph until the assigned user responds (first execution) or
    # return the stored response immediately (resume execution).
    try:
        from langgraph.types import interrupt
        response = interrupt({"task_id": task_id, "type": task_type})
        # This line only executes after the graph is resumed with the response.
        feedback = response.get("feedback", "") if isinstance(response, dict) else ""
        if task_type == "approval":
            decision = response.get("decision") if isinstance(response, dict) else str(response)
            log.info("HITL task %s resumed: decision=%r feedback=%r", task_id, decision, feedback)
            return (
                f"Approval received for task '{title}': {decision}."
                + (f" Feedback: {feedback}" if feedback else "")
            )
        elif task_type == "form_input":
            form_data = response.get("form_data", {}) if isinstance(response, dict) else {}
            log.info("HITL task %s resumed: form_data=%r", task_id, form_data)
            result = f"Form submitted by {assigned_to} for task '{title}'."
            if form_data:
                result += "\n\nSubmitted form data:\n" + "\n".join(
                    f"- **{k}**: {v}" for k, v in form_data.items()
                )
            if feedback:
                result += f"\n\nFeedback: {feedback}"
            return result
        elif task_type == "file_request":
            files = response.get("files", []) if isinstance(response, dict) else []
            log.info("HITL task %s resumed: files=%r", task_id, files)
            result = f"Files uploaded by {assigned_to} for task '{title}'."
            if files:
                result += "\n\nUploaded files:\n" + "\n".join(f"- `{f}`" for f in files)
            if feedback:
                result += f"\n\nFeedback: {feedback}"
            return result
        else:
            log.info("HITL task %s resumed: acknowledged, feedback=%r", task_id, feedback)
            return (
                f"Report acknowledged by {assigned_to}."
                + (f" Feedback: {feedback}" if feedback else "")
            )
    except ImportError:
        # LangGraph not installed or interrupt not available — return a
        # placeholder so the agent can still inform the user.
        log.warning("LangGraph interrupt() not available; HITL task %s created but agent not suspended", task_id)
        return (
            f"Task '{title}' sent to {assigned_to!r} (task id: {task_id}). "
            "The conversation will continue asynchronously."
        )


@tool
def request_form(
    assigned_to: str,
    title: str,
    description: str,
    form_schema: str,
    context: str = "{}",
) -> str:
    """Present a dynamic form to another user and collect their structured input.

    Use this tool when you need the user to fill in structured data (numbers,
    text, selections, dates, etc.) defined by a formio.js JSON schema.  The
    recipient sees a rendered form with the specified fields; after they submit
    the conversation resumes with their form data in ``form_data``.
    Do NOT use this for yes/no decisions (use request_approval) or plain file
    uploads (use request_files) or notifications (use send_report).

    IMPORTANT — two-turn confirmation protocol:
    1. Complete any prerequisite work first if applicable.
    2. Summarise the form you plan to send and ask "Should I send this?" — NO tool call yet.
    3. Call this tool only AFTER the user explicitly confirms in the next turn.
    SKIP steps 2-3 entirely when the active skill's instructions say to call this tool
    immediately or without asking for confirmation — skill instructions always override
    this default protocol. Also skip when the user's message is solely about requesting
    the form, they say to proceed right now, AND no prior work is needed.

    Args:
        assigned_to: Username of the user who should fill the form (e.g. "alice").
        title: Short task title shown in the inbox (max ~80 chars).
        description: Instructions for the form recipient — markdown supported.
        form_schema: Formio.js JSON schema string, e.g.
                     '{"components":[{"type":"textfield","key":"name","label":"Name"}]}'.
                     Read from a skill helper file via read_file() when available.
        context: JSON string with optional additional key-value context.
    """
    try:
        schema_obj = json.loads(form_schema) if form_schema.strip() else {}
    except json.JSONDecodeError:
        return f"Invalid form_schema: not valid JSON. Please provide a valid formio.js schema."
    try:
        ctx_dict = json.loads(context) if context.strip() else {}
    except json.JSONDecodeError:
        ctx_dict = {"note": context}
    ctx_dict["_form_schema"] = schema_obj
    return _create_task("form_input", assigned_to, title, description, ctx_dict)


@tool
def request_files(
    assigned_to: str,
    title: str,
    description: str,
    context: str = "{}",
) -> str:
    """Ask another user to upload one or more files into the current session.

    Use this tool when you need the user to provide files (documents, images,
    datasets, etc.) that you don't have yet.  The recipient sees a multi-file
    upload form; once they submit, the files are saved to the requesting
    session's workspace (input files section) and the conversation resumes with
    the list of uploaded file paths.  Do NOT use this tool for approval
    decisions or to share information — use request_approval or send_report.

    IMPORTANT — two-turn protocol (always required):
    1. Complete any requested work first if applicable.
    2. Summarise what files you need and ask "Should I request these?" — NO tool call yet.
    3. Call this tool only AFTER the user explicitly confirms in the next turn.
    Skip step 2 ONLY when: the user's message is solely about requesting files,
    they say to proceed right now, AND no prior work is needed.
    Never skip when the message combines work with routing.

    Args:
        assigned_to: Username of the user who should upload files (e.g. "alice").
        title: Short task title shown in the inbox (max ~80 chars).
        description: Explanation of what files are needed — markdown supported.
        context: JSON string with optional key-value context, e.g.
                 '{"format": "PDF or PNG", "max_size_mb": "10"}'.
    """
    try:
        ctx_dict = json.loads(context) if context.strip() else {}
    except json.JSONDecodeError:
        ctx_dict = {"note": context}
    return _create_task("file_request", assigned_to, title, description, ctx_dict)


@tool
def request_approval(
    assigned_to: str,
    title: str,
    description: str,
    context: str = "{}",
) -> str:
    """Send an APPROVAL REQUEST to another user — they get Approve / Reject buttons.

    Use this tool when the user wants a **yes/no decision** from another user
    ("send for approval", "get sign-off", "needs approval", "approve or reject").
    The recipient sees Approve and Reject buttons and their response unblocks
    execution.  Do NOT use this tool just to share information; use send_report
    instead when no decision is required.

    IMPORTANT — two-turn protocol (always required):
    1. Complete any requested work first (generate the content, run analysis, etc.).
    2. Summarise what you would send and ask "Should I send this?" — NO tool call yet.
    3. Call this tool only AFTER the user explicitly confirms in the next turn.
    Skip step 2 ONLY when: the user's current message is solely about routing
    (no work needed), they say to proceed right now, AND content is already ready.
    Never skip when the message combines work with routing ("create X and send to Y").

    Args:
        assigned_to: Username of the user who must approve (e.g. "alice").
        title: Short task title shown in the approval UI (max ~80 chars).
        description: Detailed explanation for the approver — markdown supported.
        context: JSON string with optional key-value context shown in the UI,
                 e.g. '{"invoice_id": "INV-42", "amount": "$1,200"}'.
    """
    try:
        ctx_dict = json.loads(context) if context.strip() else {}
    except json.JSONDecodeError:
        ctx_dict = {"note": context}
    return _create_task("approval", assigned_to, title, description, ctx_dict)


@tool
def send_report(
    assigned_to: str,
    title: str,
    description: str,
    context: str = "{}",
    require_acknowledgment: bool = True,
) -> str:
    """Send information, results, or updates to another user — they get an Acknowledge button only.

    Use this tool to SHARE content (reports, charts, summaries, notifications)
    when no decision is needed from the recipient.  Do NOT use this tool when
    the user says "send for approval", "approve/reject", or otherwise wants a
    yes/no decision — use request_approval instead.

    IMPORTANT — two-turn protocol (always required):
    1. Complete any requested work first (generate the content, run analysis, etc.).
    2. Summarise what you would send and ask "Should I send this?" — NO tool call yet.
    3. Call this tool only AFTER the user explicitly confirms in the next turn.
    Skip step 2 ONLY when: the user's current message is solely about routing
    (no work needed), they say to proceed right now, AND content is already ready.
    Never skip when the message combines work with routing ("create X and send to Y").

    Args:
        assigned_to: Username of the recipient (e.g. "alice").
        title: Report title shown in the task list.
        description: Report body — markdown supported.
        context: JSON string with optional supporting data.
        require_acknowledgment: When True, pauses until recipient responds.
    """
    try:
        ctx_dict = json.loads(context) if context.strip() else {}
    except json.JSONDecodeError:
        ctx_dict = {"note": context}

    if not require_acknowledgment:
        # Fire-and-forget: write the task but don't interrupt the graph.
        from surogate_agent.auth.database import SessionLocal
        from surogate_agent.auth.models import HumanTask

        ctx = hitl_session_context.get(None)
        task_id = str(uuid.uuid4())
        try:
            with SessionLocal() as db:
                db.add(HumanTask(
                    id=task_id,
                    task_type="report",
                    status="pending",
                    origin_session_id=ctx["thread_id"] if ctx else "",
                    origin_user_id=ctx["user_id"] if ctx else "",
                    assigned_user_id=assigned_to,
                    title=title,
                    description=description,
                    context_json=json.dumps(ctx_dict),
                    created_at=datetime.utcnow(),
                ))
                db.commit()
        except Exception as exc:
            log.error("failed to create fire-and-forget report: %s", exc)
            return f"Failed to send report: {exc}"
        return f"Report '{title}' sent to {assigned_to!r}. No acknowledgment required."

    return _create_task("report", assigned_to, title, description, ctx_dict)
