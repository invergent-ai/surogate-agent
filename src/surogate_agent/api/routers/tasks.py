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
    # originator's session shows it as soon as the lock is released.
    from surogate_agent.hitl.resume import (
        _append_task_response_to_history,
        _release_session_lock,
    )
    _append_task_response_to_history(origin_session_id, origin_user_id, task_type, response)

    # Release the session lock now — ChatHistory is already updated above, so
    # the frontend's history reload on unlock will show the task response.
    _release_session_lock(origin_session_id)

    # Schedule a background task to resume the LangGraph checkpoint so the
    # agent has full context if the originator asks a follow-up question.
    try:
        from surogate_agent.hitl.resume import resume_hitl_session
        asyncio.create_task(resume_hitl_session(
            origin_session_id=origin_session_id,
            origin_user_id=origin_user_id,
            context_json=context_json,
            response=response,
        ))
    except Exception as exc:
        log.warning("could not schedule HITL checkpoint resume for task %s: %s", task_id, exc)

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
    )
    _append_task_response_to_history(origin_session_id, origin_user_id, task_type, response)
    _release_session_lock(origin_session_id)

    try:
        from surogate_agent.hitl.resume import resume_hitl_session
        asyncio.create_task(resume_hitl_session(
            origin_session_id=origin_session_id,
            origin_user_id=origin_user_id,
            context_json=context_json,
            response=response,
        ))
    except Exception as exc:
        log.warning("could not schedule HITL checkpoint resume for task %s: %s", task_id, exc)

    return {"ok": True, "files": saved_paths}


@router.delete("/{task_id}")
def cancel_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """Cancel a pending task.  Only the originator may cancel."""
    task = db.query(HumanTask).filter_by(id=task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.origin_user_id != current_user.username:
        raise HTTPException(status_code=403, detail="Only the task originator may cancel it")
    if task.status != "pending":
        raise HTTPException(status_code=409, detail=f"Task is already {task.status}")

    task.status = "cancelled"
    lock = db.query(SessionLock).filter_by(session_id=task.origin_session_id).first()
    if lock and lock.task_id == task_id:
        db.delete(lock)
    db.commit()
    log.info("task %s cancelled by originator %r", task_id, current_user.username)
    return {"ok": True}
