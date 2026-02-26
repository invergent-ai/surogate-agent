"""
Sessions router — /sessions
"""

from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session as DBSession

from surogate_agent.api.deps import ServerSettings, settings_dep
from surogate_agent.api.models import (
    ChatHistoryResponse,
    ChatHistorySaveRequest,
    FileInfo,
    SessionMetaCreate,
    SessionMetaResponse,
    SessionMetaUpdate,
    SessionResponse,
)
from surogate_agent.auth.database import get_db
from surogate_agent.auth.jwt import get_current_user
from surogate_agent.auth.models import ChatHistory, SessionMetadata, User
from surogate_agent.core.logging import get_logger
from surogate_agent.core.session import SessionManager

log = get_logger(__name__)

router = APIRouter(
    prefix="/sessions",
    tags=["sessions"],
    dependencies=[Depends(get_current_user)],
)


def _session_manager(settings: ServerSettings) -> SessionManager:
    return SessionManager(settings.sessions_dir)


def _file_infos(session) -> list[FileInfo]:
    return [
        FileInfo(name=f.name, size_bytes=f.stat().st_size)
        for f in session.files
    ]


def _clean_db_records(session_id: str, user_id: str, db: DBSession) -> None:
    """Delete session metadata and chat history rows for a given session.

    Silently skips if the tables don't exist yet (e.g. first run before migration).
    """
    try:
        meta = db.query(SessionMetadata).filter_by(session_id=session_id, user_id=user_id).first()
        hist = db.query(ChatHistory).filter_by(session_id=session_id, user_id=user_id).first()
        if meta:
            db.delete(meta)
        if hist:
            db.delete(hist)
        if meta or hist:
            db.commit()
    except Exception:
        db.rollback()
        log.debug("_clean_db_records: skipped (tables may not exist yet)")


# ---------------------------------------------------------------------------
# Session metadata — must be declared BEFORE /{session_id} wildcard routes
# ---------------------------------------------------------------------------


@router.get("/meta", response_model=list[SessionMetaResponse])
def list_session_meta(
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all session metadata records owned by the current user."""
    records = (
        db.query(SessionMetadata)
        .filter_by(user_id=current_user.username)
        .order_by(SessionMetadata.created_at.desc())
        .all()
    )
    return [
        SessionMetaResponse(
            session_id=r.session_id,
            name=r.name,
            created_at=r.created_at.isoformat(),
        )
        for r in records
    ]


@router.post("/meta", response_model=SessionMetaResponse, status_code=201)
def create_session_meta(
    body: SessionMetaCreate,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new session metadata record (idempotent — returns existing if duplicate)."""
    existing = db.query(SessionMetadata).filter_by(session_id=body.session_id).first()
    if existing:
        return SessionMetaResponse(
            session_id=existing.session_id,
            name=existing.name,
            created_at=existing.created_at.isoformat(),
        )
    record = SessionMetadata(
        session_id=body.session_id,
        user_id=current_user.username,
        name=body.name,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return SessionMetaResponse(
        session_id=record.session_id,
        name=record.name,
        created_at=record.created_at.isoformat(),
    )


@router.patch("/meta/{session_id}", response_model=SessionMetaResponse)
def update_session_meta(
    session_id: str,
    body: SessionMetaUpdate,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Rename a session."""
    record = (
        db.query(SessionMetadata)
        .filter_by(session_id=session_id, user_id=current_user.username)
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail=f"Session metadata '{session_id}' not found")
    record.name = body.name
    db.commit()
    db.refresh(record)
    return SessionMetaResponse(
        session_id=record.session_id,
        name=record.name,
        created_at=record.created_at.isoformat(),
    )


@router.delete("/meta/{session_id}")
def delete_session_meta(
    session_id: str,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete session metadata and chat history from the database."""
    _clean_db_records(session_id, current_user.username, db)
    return {"deleted": session_id}


# ---------------------------------------------------------------------------
# Chat history
# ---------------------------------------------------------------------------


@router.get("/{session_id}/history", response_model=ChatHistoryResponse)
def get_session_history(
    session_id: str,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return stored chat messages for a session, or an empty list if none saved."""
    record = (
        db.query(ChatHistory)
        .filter_by(session_id=session_id, user_id=current_user.username)
        .first()
    )
    if not record:
        return ChatHistoryResponse(session_id=session_id, messages=[])
    return ChatHistoryResponse(
        session_id=session_id,
        messages=json.loads(record.messages_json),
    )


@router.put("/{session_id}/history")
def save_session_history(
    session_id: str,
    body: ChatHistorySaveRequest,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Save (upsert) rendered chat messages for a session."""
    messages_json = json.dumps(body.messages)
    record = (
        db.query(ChatHistory)
        .filter_by(session_id=session_id, user_id=current_user.username)
        .first()
    )
    if record:
        record.messages_json = messages_json
        record.updated_at = datetime.utcnow()
    else:
        record = ChatHistory(
            session_id=session_id,
            user_id=current_user.username,
            messages_json=messages_json,
        )
        db.add(record)
    db.commit()
    return {"saved": session_id}


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


@router.get("", response_model=list[SessionResponse])
def list_sessions(settings: ServerSettings = Depends(settings_dep)):
    log.debug("list_sessions")
    sm = _session_manager(settings)
    sessions = sm.list_sessions()
    log.debug("list_sessions: %d session(s)", len(sessions))
    return [
        SessionResponse(
            session_id=s.session_id,
            workspace_dir=str(s.workspace_dir),
            files=_file_infos(s),
        )
        for s in sessions
    ]


# ---------------------------------------------------------------------------
# Get
# ---------------------------------------------------------------------------


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(session_id: str, settings: ServerSettings = Depends(settings_dep)):
    sm = _session_manager(settings)
    session = sm.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return SessionResponse(
        session_id=session.session_id,
        workspace_dir=str(session.workspace_dir),
        files=_file_infos(session),
    )


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


@router.delete("/{session_id}")
def delete_session(
    session_id: str,
    settings: ServerSettings = Depends(settings_dep),
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    log.debug("delete_session: %s", session_id)
    sm = _session_manager(settings)
    deleted = sm.delete_session(session_id)
    if not deleted:
        log.debug("delete_session: '%s' not found", session_id)
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    _clean_db_records(session_id, current_user.username, db)
    log.info("session deleted via API: %s", session_id)
    return {"deleted": session_id}


# ---------------------------------------------------------------------------
# Files — list
# ---------------------------------------------------------------------------


@router.get("/{session_id}/files", response_model=list[FileInfo])
def list_session_files(session_id: str, settings: ServerSettings = Depends(settings_dep)):
    sm = _session_manager(settings)
    session = sm.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return _file_infos(session)


# ---------------------------------------------------------------------------
# Files — download
# ---------------------------------------------------------------------------


@router.get("/{session_id}/files/{file}")
def download_session_file(
    session_id: str,
    file: str,
    settings: ServerSettings = Depends(settings_dep),
):
    sm = _session_manager(settings)
    session = sm.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    target = session.workspace_dir / file
    if not target.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"File '{file}' not found in session '{session_id}'",
        )
    return FileResponse(str(target), filename=file)


# ---------------------------------------------------------------------------
# Files — upload
# ---------------------------------------------------------------------------


@router.post("/{session_id}/files", status_code=201)
async def upload_session_file(
    session_id: str,
    upload: UploadFile = File(...),
    filename: str = Query("", description="Override destination filename"),
    settings: ServerSettings = Depends(settings_dep),
):
    sm = _session_manager(settings)
    # create session if absent
    session = sm.resume_or_create(session_id)
    dest_name = filename or upload.filename or "upload"
    target = session.workspace_dir / dest_name
    session.workspace_dir.mkdir(parents=True, exist_ok=True)
    content = await upload.read()
    target.write_bytes(content)
    log.debug("session '%s': uploaded file '%s' (%d bytes)", session_id, dest_name, len(content))
    return {"uploaded": dest_name, "session_id": session_id, "size_bytes": len(content)}


# ---------------------------------------------------------------------------
# Files — delete
# ---------------------------------------------------------------------------


@router.delete("/{session_id}/files/{file}")
def delete_session_file(
    session_id: str,
    file: str,
    settings: ServerSettings = Depends(settings_dep),
):
    sm = _session_manager(settings)
    session = sm.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    target = session.workspace_dir / file
    if not target.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"File '{file}' not found in session '{session_id}'",
        )
    target.unlink()
    log.debug("session '%s': deleted file '%s'", session_id, file)
    return {"deleted": file}
