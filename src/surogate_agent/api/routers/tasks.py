"""
Tasks router — /tasks

Endpoints for human-in-the-loop (HITL) task management.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from starlette.requests import Request
from sqlalchemy.orm import Session as DBSession

from surogate_agent.api.deps import ServerSettings, settings_dep
from surogate_agent.api.models import HumanTaskResponse, SessionLockResponse, TaskRespondRequest
from surogate_agent.auth.database import SessionLocal, get_db
from surogate_agent.auth.jwt import get_current_user
from surogate_agent.auth.models import HumanTask, SessionLock, User
from surogate_agent.core.logging import get_logger

try:
    from sse_starlette.sse import EventSourceResponse
except ImportError:
    EventSourceResponse = None  # type: ignore[assignment,misc]

log = get_logger(__name__)


def _save_form_files(form_data: dict, session_id: str, db: DBSession) -> dict:
    """Detect formio.js file-upload fields in *form_data*, save them to the
    originating session's workspace, and register them as input files.

    Formio submits file components as a list of objects::

        [{"name": "doc.pdf", "url": "data:application/pdf;base64,<b64>", ...}]

    Each such field is decoded, written to the session workspace directory, and
    registered in ``SessionInputFiles`` (same path as ``request_files``).
    The raw base64 payload is replaced with the workspace-relative file path so
    the agent receives a clean ``form_data`` without large binary strings.
    Fields that are not file-upload lists are left unchanged.
    """
    import base64
    import re as _re

    from surogate_agent.api.deps import get_settings
    from surogate_agent.api.routers.sessions import _add_input_file
    from surogate_agent.core.session import SessionManager

    settings = get_settings()
    sm = SessionManager(settings.sessions_dir)
    session = sm.resume_or_create(session_id)
    session.workspace_dir.mkdir(parents=True, exist_ok=True)

    processed = dict(form_data)
    for key, value in form_data.items():
        if not isinstance(value, list) or not value:
            continue
        # Detect formio file objects: list of dicts with 'name' + base64 'url'
        file_items = [
            item for item in value
            if isinstance(item, dict)
            and isinstance(item.get("name"), str)
            and isinstance(item.get("url"), str)
            and item["url"].startswith("data:")
            and ";base64," in item["url"]
        ]
        if not file_items:
            continue

        saved_refs: list[str] = []
        for item in file_items:
            raw_name: str = item["name"]
            # Sanitize: strip path separators, null bytes, and leading dots
            safe_name = _re.sub(r"[/\\:\0]", "_", raw_name).lstrip(".") or "upload"
            try:
                _, b64 = item["url"].split(";base64,", 1)
                dest = session.workspace_dir / safe_name
                dest.write_bytes(base64.b64decode(b64))
                _add_input_file(session_id, safe_name, db)
                saved_refs.append(f"sessions/{session_id}/{safe_name}")
                log.info(
                    "form file upload saved: session=%s key=%r file=%s",
                    session_id, key, safe_name,
                )
            except Exception as exc:
                log.warning("could not save form file %r: %s", raw_name, exc)

        if saved_refs:
            processed[key] = saved_refs

    return processed


def _utc_iso(dt: datetime) -> str:
    """Return an ISO-8601 string with an explicit UTC marker.

    ``datetime.utcnow()`` produces a naive datetime; ``.isoformat()`` on it
    omits any timezone suffix, so JavaScript's ``Date`` constructor parses it
    as local time — wrong for non-UTC users.  Appending ``Z`` fixes that.
    """
    iso = dt.isoformat()
    if iso.endswith("Z") or "+" in iso[10:]:
        return iso
    return iso + "Z"


router = APIRouter(
    prefix="/tasks",
    tags=["tasks"],
    dependencies=[Depends(get_current_user)],
)


def _task_to_response(task: HumanTask) -> HumanTaskResponse:
    return HumanTaskResponse(
        id=task.id,
        task_type=task.task_type,
        status=task.status,
        title=task.title,
        description=task.description,
        context=json.loads(task.context_json or "{}"),
        assigned_to=task.assigned_user_id,
        assigned_by=task.origin_user_id,
        created_at=_utc_iso(task.created_at),
        responded_at=_utc_iso(task.responded_at) if task.responded_at else None,
        response=json.loads(task.response_json) if task.response_json else None,
    )


@router.get("", response_model=list[HumanTaskResponse])
def list_tasks(
    role: str = Query("assigned", description="'assigned' = tasks for me; 'originated' = tasks I created"),
    status: str = Query("pending", description="'pending', 'completed', 'all'"),
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """List HITL tasks visible to the current user."""
    q = db.query(HumanTask)
    if role == "originated":
        q = q.filter(HumanTask.origin_user_id == current_user.username)
    else:
        q = q.filter(HumanTask.assigned_user_id == current_user.username)
    if status != "all":
        q = q.filter(HumanTask.status == status)
    tasks = q.order_by(HumanTask.created_at.desc()).all()
    return [_task_to_response(t) for t in tasks]


@router.get("/notifications")
async def task_notifications(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """SSE stream — emits ``new_task`` events when a new task is assigned to the user."""
    if EventSourceResponse is None:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=500,
            content={"detail": "sse-starlette is not installed"},
        )

    async def _event_gen():
        seen: set[str] = set()
        # Pre-seed with existing pending tasks so reconnecting clients don't
        # get flooded with stale notifications.
        with SessionLocal() as db:
            existing = db.query(HumanTask).filter_by(
                assigned_user_id=current_user.username,
                status="pending",
            ).all()
            for t in existing:
                seen.add(t.id)

        while True:
            if await request.is_disconnected():
                break
            with SessionLocal() as db:
                pending = db.query(HumanTask).filter_by(
                    assigned_user_id=current_user.username,
                    status="pending",
                ).all()
            for task in pending:
                if task.id not in seen:
                    seen.add(task.id)
                    yield {
                        "event": "new_task",
                        "data": json.dumps({
                            "task_id": task.id,
                            "task_type": task.task_type,
                            "title": task.title,
                            "assigned_by": task.origin_user_id,
                        }),
                    }
            await asyncio.sleep(0.5)

    return EventSourceResponse(_event_gen())


@router.get("/{task_id}", response_model=HumanTaskResponse)
def get_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """Get a single task by id.  Accessible to both the assignee and the originator."""
    task = db.query(HumanTask).filter_by(id=task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.assigned_user_id != current_user.username and task.origin_user_id != current_user.username:
        raise HTTPException(status_code=403, detail="Not authorised to view this task")
    return _task_to_response(task)


@router.post("/{task_id}/respond")
async def respond_to_task(
    task_id: str,
    payload: TaskRespondRequest,
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """Submit a response to a pending HITL task.

    For approval tasks: provide ``decision`` = "approved" | "rejected".
    For report tasks:   provide ``acknowledged`` = true.
    Both accept an optional ``feedback`` string.
    """
    task = db.query(HumanTask).filter_by(id=task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.assigned_user_id != current_user.username:
        raise HTTPException(status_code=403, detail="Not authorised to respond to this task")
    if task.status != "pending":
        raise HTTPException(status_code=409, detail=f"Task is already {task.status}")

    # Build the response dict that will be passed to interrupt() resume value
    response: dict = {"feedback": payload.feedback or ""}
    if task.task_type == "approval":
        if payload.decision not in ("approved", "rejected"):
            raise HTTPException(status_code=422, detail="decision must be 'approved' or 'rejected'")
        response["decision"] = payload.decision
    elif task.task_type == "form_input":
        form_data = payload.form_data or {}
        # Save any formio file-upload fields to the session workspace before
        # committing — _save_form_files calls _add_input_file which needs db open.
        if form_data:
            form_data = _save_form_files(form_data, task.origin_session_id, db)
        response["form_data"] = form_data
    else:
        response["acknowledged"] = True
        if payload.acknowledged is False:
            response["acknowledged"] = False

    # Capture plain strings NOW while the DB session is still open.
    # asyncio.create_task() schedules the coroutine but it doesn't start until
    # after this function returns and FastAPI's get_db() cleanup closes the
    # session — at which point the ORM object becomes detached and attribute
    # access raises DetachedInstanceError.
    origin_session_id = task.origin_session_id
    origin_user_id = task.origin_user_id
    context_json = task.context_json
    task_type = task.task_type

    # Update task status
    task.status = "completed"
    task.response_json = json.dumps(response)
    task.responded_at = datetime.utcnow()
    db.commit()
    log.info(
        "task %s responded to by %r: %r",
        task_id, current_user.username, response,
    )

    # Write the task response to ChatHistory immediately (sync) so the
    # originator's history already contains it when the lock is released.
    from surogate_agent.hitl.resume import (
        _append_task_response_to_history,
        _release_session_lock,
        resume_hitl_session,
    )
    _append_task_response_to_history(origin_session_id, origin_user_id, task_type, response)

    # Schedule the LangGraph resume.  The lock is released INSIDE
    # resume_hitl_session after the agent finishes, so the frontend's
    # history-reload on unlock sees both the task-response message and the
    # agent's continuation output in a single reload.
    try:
        asyncio.create_task(resume_hitl_session(
            origin_session_id=origin_session_id,
            origin_user_id=origin_user_id,
            context_json=context_json,
            response=response,
        ))
    except Exception as exc:
        log.warning("could not schedule HITL checkpoint resume for task %s: %s", task_id, exc)
        # If we can't schedule the resume, release the lock immediately so the
        # session doesn't stay locked forever.
        _release_session_lock(origin_session_id)

    return {"ok": True}


@router.post("/{task_id}/upload")
async def upload_task_files(
    task_id: str,
    files: list[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
    settings: ServerSettings = Depends(settings_dep),
):
    """Upload files for a pending file_request task.

    Saves files to the originating session's workspace under ``input/``,
    registers them as input files, then completes the task so the originating
    agent resumes with the list of uploaded file paths.
    """
    task = db.query(HumanTask).filter_by(id=task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.assigned_user_id != current_user.username:
        raise HTTPException(status_code=403, detail="Not authorised to respond to this task")
    if task.task_type != "file_request":
        raise HTTPException(status_code=422, detail="This endpoint is only for file_request tasks")
    if task.status != "pending":
        raise HTTPException(status_code=409, detail=f"Task is already {task.status}")

    from surogate_agent.core.session import SessionManager
    from surogate_agent.api.routers.sessions import _add_input_file

    sm = SessionManager(settings.sessions_dir)
    session = sm.resume_or_create(task.origin_session_id)

    saved_paths: list[str] = []
    for upload in files:
        fname = upload.filename or "upload"
        dest = session.workspace_dir / fname
        session.workspace_dir.mkdir(parents=True, exist_ok=True)
        content = await upload.read()
        dest.write_bytes(content)
        _add_input_file(task.origin_session_id, fname, db)
        saved_paths.append(fname)
        log.info(
            "task %s: saved %r (%d bytes) to session %s",
            task_id, fname, len(content), task.origin_session_id,
        )

    # Full session-relative paths for the agent to reference
    session_file_refs = [
        f"sessions/{task.origin_session_id}/{p}" for p in saved_paths
    ]

    # Capture before session close
    origin_session_id = task.origin_session_id
    origin_user_id = task.origin_user_id
    context_json = task.context_json
    task_type = task.task_type

    response: dict = {
        "files": session_file_refs,
        "feedback": f"{len(saved_paths)} file(s) uploaded",
    }
    task.status = "completed"
    task.response_json = json.dumps(response)
    task.responded_at = datetime.utcnow()
    db.commit()
    log.info("task %s completed by %r: %d file(s)", task_id, current_user.username, len(saved_paths))

    from surogate_agent.hitl.resume import (
        _append_task_response_to_history,
        _release_session_lock,
        resume_hitl_session,
    )
    _append_task_response_to_history(origin_session_id, origin_user_id, task_type, response)

    # Schedule LangGraph resume; lock is released INSIDE resume_hitl_session
    # after the agent finishes, so the frontend sees the full continuation.
    try:
        asyncio.create_task(resume_hitl_session(
            origin_session_id=origin_session_id,
            origin_user_id=origin_user_id,
            context_json=context_json,
            response=response,
        ))
    except Exception as exc:
        log.warning("could not schedule HITL checkpoint resume for task %s: %s", task_id, exc)
        _release_session_lock(origin_session_id)

    return {"ok": True, "files": saved_paths}


@router.delete("/{task_id}")
async def cancel_or_delete_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """Cancel a pending task or hard-delete a completed/cancelled one.

    - **Pending tasks**: only the originator may cancel.  The LangGraph interrupt
      is resumed with ``{"cancelled": True}`` so the agent unblocks and the session
      lock is released normally (inside ``resume_hitl_session``).
    - **Completed / cancelled tasks**: either the assignee or the originator may
      hard-delete the row (removes it from both parties' task lists).
    """
    task = db.query(HumanTask).filter_by(id=task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # ── Non-pending: hard delete ───────────────────────────────────────────────
    if task.status != "pending":
        if (task.assigned_user_id != current_user.username
                and task.origin_user_id != current_user.username):
            raise HTTPException(status_code=403, detail="Not authorised to delete this task")
        db.delete(task)
        db.commit()
        log.info("task %s deleted by %r (status was %r)", task_id, current_user.username, task.status)
        return {"ok": True}

    # ── Pending: cancel (originator only) ─────────────────────────────────────
    if task.origin_user_id != current_user.username:
        raise HTTPException(status_code=403, detail="Only the task originator may cancel it")

    # Check whether the session is currently locked waiting for this task.
    lock = db.query(SessionLock).filter_by(session_id=task.origin_session_id).first()
    has_lock = lock is not None and lock.task_id == task_id

    # Capture plain strings before the DB session is closed.
    origin_session_id = task.origin_session_id
    origin_user_id = task.origin_user_id
    context_json = task.context_json

    response: dict = {"cancelled": True}
    task.status = "cancelled"
    task.response_json = json.dumps(response)
    task.responded_at = datetime.utcnow()
    # Release the lock immediately so the frontend detects the unlock right away.
    # resume_hitl_session (scheduled below) will gracefully unblock LangGraph;
    # its _release_session_lock call is a no-op if the lock is already gone.
    if lock and lock.task_id == task_id:
        db.delete(lock)
    db.commit()
    log.info("task %s cancelled by originator %r (has_lock=%s)", task_id, current_user.username, has_lock)

    from surogate_agent.hitl.resume import (
        _append_assistant_message,
        resume_hitl_session,
    )

    # Always write the cancellation message to history so the originator sees it
    # when the session reloads (whether or not the session was locked).
    _append_assistant_message(
        origin_session_id,
        origin_user_id,
        "**Task cancelled.**\n\nThis task was cancelled before the assignee could respond.",
        block_type="hitl_response",
    )

    if has_lock:
        # Resume the paused LangGraph interrupt with a cancellation signal so the
        # agent unblocks gracefully.
        try:
            asyncio.create_task(resume_hitl_session(
                origin_session_id=origin_session_id,
                origin_user_id=origin_user_id,
                context_json=context_json,
                response=response,
            ))
        except Exception as exc:
            log.warning(
                "could not schedule HITL resume for cancelled task %s: %s",
                task_id, exc,
            )

    return {"ok": True}
