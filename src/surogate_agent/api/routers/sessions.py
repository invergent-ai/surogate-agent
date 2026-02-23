"""
Sessions router — /sessions
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from surogate_agent.api.deps import ServerSettings, settings_dep
from surogate_agent.api.models import FileInfo, SessionResponse
from surogate_agent.core.session import SessionManager

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _session_manager(settings: ServerSettings) -> SessionManager:
    return SessionManager(settings.sessions_dir)


def _file_infos(session) -> list[FileInfo]:
    return [
        FileInfo(name=f.name, size_bytes=f.stat().st_size)
        for f in session.files
    ]


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


@router.get("", response_model=list[SessionResponse])
def list_sessions(settings: ServerSettings = Depends(settings_dep)):
    sm = _session_manager(settings)
    return [
        SessionResponse(
            session_id=s.session_id,
            workspace_dir=str(s.workspace_dir),
            files=_file_infos(s),
        )
        for s in sm.list_sessions()
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
def delete_session(session_id: str, settings: ServerSettings = Depends(settings_dep)):
    sm = _session_manager(settings)
    deleted = sm.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
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
    upload: UploadFile,
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
    return {"deleted": file}
