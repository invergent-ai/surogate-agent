"""
Workspace router — /workspace  (developer scratch area)
"""

from __future__ import annotations

import shutil

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from surogate_agent.api.deps import ServerSettings, settings_dep
from surogate_agent.api.models import FileInfo, WorkspaceResponse
from surogate_agent.auth.jwt import get_current_user
from surogate_agent.core.logging import get_logger

log = get_logger(__name__)

router = APIRouter(
    prefix="/workspace",
    tags=["workspace"],
    dependencies=[Depends(get_current_user)],
)


def _file_infos(directory) -> list[FileInfo]:
    from pathlib import Path
    d = Path(directory)
    if not d.is_dir():
        return []
    return [
        FileInfo(name=f.name, size_bytes=f.stat().st_size)
        for f in sorted(d.iterdir())
        if f.is_file()
    ]


# ---------------------------------------------------------------------------
# List all skill workspaces
# ---------------------------------------------------------------------------


@router.get("", response_model=list[WorkspaceResponse])
def list_workspaces(settings: ServerSettings = Depends(settings_dep)):
    log.debug("list_workspaces: root=%s", settings.workspace_dir)
    ws_root = settings.workspace_dir
    if not ws_root.is_dir():
        return []
    return [
        WorkspaceResponse(
            skill=entry.name,
            workspace_dir=str(entry),
            files=_file_infos(entry),
        )
        for entry in sorted(ws_root.iterdir())
        if entry.is_dir() and not entry.name.startswith(".")
    ]


# ---------------------------------------------------------------------------
# Get single skill workspace
# ---------------------------------------------------------------------------


@router.get("/{skill}", response_model=WorkspaceResponse)
def get_workspace(skill: str, settings: ServerSettings = Depends(settings_dep)):
    ws_dir = settings.workspace_dir / skill
    if not ws_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Workspace for skill '{skill}' not found")
    return WorkspaceResponse(
        skill=skill,
        workspace_dir=str(ws_dir),
        files=_file_infos(ws_dir),
    )


# ---------------------------------------------------------------------------
# Delete skill workspace
# ---------------------------------------------------------------------------


@router.delete("/{skill}")
def delete_workspace(skill: str, settings: ServerSettings = Depends(settings_dep)):
    log.debug("delete_workspace: %s", skill)
    ws_dir = settings.workspace_dir / skill
    if not ws_dir.is_dir():
        log.debug("delete_workspace: workspace '%s' not found", skill)
        raise HTTPException(status_code=404, detail=f"Workspace for skill '{skill}' not found")
    shutil.rmtree(ws_dir)
    log.info("workspace deleted: '%s'", skill)
    return {"deleted": skill}


# ---------------------------------------------------------------------------
# Files — list
# ---------------------------------------------------------------------------


@router.get("/{skill}/files", response_model=list[FileInfo])
def list_workspace_files(skill: str, settings: ServerSettings = Depends(settings_dep)):
    ws_dir = settings.workspace_dir / skill
    if not ws_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Workspace for skill '{skill}' not found")
    return _file_infos(ws_dir)


# ---------------------------------------------------------------------------
# Files — download
# ---------------------------------------------------------------------------


@router.get("/{skill}/files/{file}")
def download_workspace_file(
    skill: str,
    file: str,
    settings: ServerSettings = Depends(settings_dep),
):
    ws_dir = settings.workspace_dir / skill
    if not ws_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Workspace for skill '{skill}' not found")
    target = ws_dir / file
    if not target.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"File '{file}' not found in workspace '{skill}'",
        )
    return FileResponse(str(target), filename=file)


# ---------------------------------------------------------------------------
# Files — upload
# ---------------------------------------------------------------------------


@router.post("/{skill}/files", status_code=201)
async def upload_workspace_file(
    skill: str,
    upload: UploadFile = File(...),
    filename: str = Query("", description="Override destination filename"),
    settings: ServerSettings = Depends(settings_dep),
):
    ws_dir = settings.workspace_dir / skill
    ws_dir.mkdir(parents=True, exist_ok=True)
    dest_name = filename or upload.filename or "upload"
    target = ws_dir / dest_name
    content = await upload.read()
    target.write_bytes(content)
    log.debug("workspace '%s': uploaded '%s' (%d bytes)", skill, dest_name, len(content))
    return {"uploaded": dest_name, "skill": skill, "size_bytes": len(content)}


# ---------------------------------------------------------------------------
# Files — delete
# ---------------------------------------------------------------------------


@router.delete("/{skill}/files/{file}")
def delete_workspace_file(
    skill: str,
    file: str,
    settings: ServerSettings = Depends(settings_dep),
):
    ws_dir = settings.workspace_dir / skill
    if not ws_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Workspace for skill '{skill}' not found")
    target = ws_dir / file
    if not target.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"File '{file}' not found in workspace '{skill}'",
        )
    target.unlink()
    log.debug("workspace '%s': deleted '%s'", skill, file)
    return {"deleted": file}
