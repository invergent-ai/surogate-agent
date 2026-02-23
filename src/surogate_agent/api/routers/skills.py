"""
Skills CRUD router — /skills
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from surogate_agent.api.deps import ServerSettings, settings_dep
from surogate_agent.api.models import (
    FileInfo,
    SkillCreateRequest,
    SkillListItem,
    SkillResponse,
    ValidationResult,
)
from surogate_agent.core.config import _DEFAULT_SKILLS_DIR
from surogate_agent.core.roles import Role
from surogate_agent.skills.loader import SkillLoader, _parse_skill
from surogate_agent.skills.registry import SkillRegistry

router = APIRouter(prefix="/skills", tags=["skills"])

_SKILL_FILENAME = "SKILL.md"


def _build_registry(settings: ServerSettings) -> SkillRegistry:
    registry = SkillRegistry()
    if _DEFAULT_SKILLS_DIR.exists():
        registry.scan(_DEFAULT_SKILLS_DIR)
    if settings.skills_dir.exists():
        registry.scan(settings.skills_dir)
    return registry


def _skill_md_content(skill_path: Path) -> str:
    skill_md = skill_path / _SKILL_FILENAME
    if skill_md.exists():
        return skill_md.read_text(encoding="utf-8")
    return ""


def _helper_files(skill_path: Path) -> list[FileInfo]:
    if not skill_path.is_dir():
        return []
    return [
        FileInfo(name=f.name, size_bytes=f.stat().st_size)
        for f in sorted(skill_path.iterdir())
        if f.is_file() and f.name != _SKILL_FILENAME
    ]


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


@router.get("", response_model=list[SkillListItem])
def list_skills(
    role: str = Query("all", description="Filter by role: all | developer | user"),
    settings: ServerSettings = Depends(settings_dep),
):
    registry = _build_registry(settings)
    if role == "developer":
        infos = [s for s in registry.all_skills()]
        paths = registry.paths_for_role(Role.DEVELOPER)
        infos = [s for s in registry.all_skills() if s.path in paths]
    elif role == "user":
        paths = registry.paths_for_role(Role.USER)
        infos = [s for s in registry.all_skills() if s.path in paths]
    else:
        infos = registry.all_skills()

    return [
        SkillListItem(
            name=s.name,
            description=s.description,
            version=s.version,
            role_restriction=s.role_restriction,
            path=str(s.path),
        )
        for s in infos
    ]


# ---------------------------------------------------------------------------
# Get
# ---------------------------------------------------------------------------


@router.get("/{name}", response_model=SkillResponse)
def get_skill(name: str, settings: ServerSettings = Depends(settings_dep)):
    registry = _build_registry(settings)
    info = registry.get(name)
    if info is None:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")
    return SkillResponse(
        name=info.name,
        description=info.description,
        version=info.version,
        role_restriction=info.role_restriction,
        allowed_tools=info.allowed_tools,
        path=str(info.path),
        skill_md_content=_skill_md_content(info.path),
        helper_files=_helper_files(info.path),
    )


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


@router.post("", response_model=SkillResponse, status_code=201)
def create_skill(
    req: SkillCreateRequest,
    settings: ServerSettings = Depends(settings_dep),
):
    skill_dir = settings.skills_dir / req.name
    if skill_dir.exists():
        raise HTTPException(status_code=409, detail=f"Skill '{req.name}' already exists")

    # Build SKILL.md content
    frontmatter_lines = [
        "---",
        f"name: {req.name}",
        f"description: {req.description}",
    ]
    if req.role_restriction:
        frontmatter_lines.append(f"role-restriction: {req.role_restriction}")
    if req.allowed_tools:
        frontmatter_lines.append(f"allowed-tools: {' '.join(req.allowed_tools)}")
    frontmatter_lines.append(f"version: {req.version}")
    frontmatter_lines.append("---")

    body = req.skill_md_body.strip()
    if body:
        skill_md_text = "\n".join(frontmatter_lines) + "\n\n" + body + "\n"
    else:
        skill_md_text = "\n".join(frontmatter_lines) + "\n"

    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / _SKILL_FILENAME).write_text(skill_md_text, encoding="utf-8")

    info = _parse_skill(skill_dir, skill_dir / _SKILL_FILENAME)
    return SkillResponse(
        name=info.name,
        description=info.description,
        version=info.version,
        role_restriction=info.role_restriction,
        allowed_tools=info.allowed_tools,
        path=str(info.path),
        skill_md_content=skill_md_text,
        helper_files=[],
    )


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


@router.delete("/{name}")
def delete_skill(name: str, settings: ServerSettings = Depends(settings_dep)):
    # Refuse to delete builtin skills
    builtin_registry = SkillRegistry()
    if _DEFAULT_SKILLS_DIR.exists():
        builtin_registry.scan(_DEFAULT_SKILLS_DIR)
    if builtin_registry.get(name):
        raise HTTPException(
            status_code=403,
            detail=f"Cannot delete builtin skill '{name}'",
        )

    skill_dir = settings.skills_dir / name
    if not skill_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")

    shutil.rmtree(skill_dir)
    return {"deleted": name}


# ---------------------------------------------------------------------------
# Validate
# ---------------------------------------------------------------------------


@router.post("/{name}/validate", response_model=ValidationResult)
def validate_skill(name: str, settings: ServerSettings = Depends(settings_dep)):
    registry = _build_registry(settings)
    info = registry.get(name)
    errors: list[str] = []
    warnings: list[str] = []

    if info is None:
        errors.append(f"Skill '{name}' not found")
        return ValidationResult(valid=False, errors=errors, warnings=warnings)

    skill_md = info.path / _SKILL_FILENAME
    if not skill_md.exists():
        errors.append("SKILL.md is missing")
    else:
        if not info.description:
            warnings.append("description is empty")
        if len(info.description) > 1024:
            warnings.append("description exceeds 1024 characters (will be truncated)")
        if info.role_restriction not in (None, "developer", "user"):
            errors.append(
                f"Invalid role-restriction '{info.role_restriction}'. "
                "Must be 'developer', 'user', or omitted."
            )

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Helper files — list
# ---------------------------------------------------------------------------


@router.get("/{name}/files", response_model=list[FileInfo])
def list_skill_files(name: str, settings: ServerSettings = Depends(settings_dep)):
    registry = _build_registry(settings)
    info = registry.get(name)
    if info is None:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")
    return _helper_files(info.path)


# ---------------------------------------------------------------------------
# Helper files — download
# ---------------------------------------------------------------------------


@router.get("/{name}/files/{file}")
def download_skill_file(
    name: str,
    file: str,
    settings: ServerSettings = Depends(settings_dep),
):
    registry = _build_registry(settings)
    info = registry.get(name)
    if info is None:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")
    target = info.path / file
    if not target.is_file():
        raise HTTPException(status_code=404, detail=f"File '{file}' not found in skill '{name}'")
    return FileResponse(str(target), filename=file)


# ---------------------------------------------------------------------------
# Helper files — upload
# ---------------------------------------------------------------------------


@router.post("/{name}/files/{file}", status_code=201)
async def upload_skill_file(
    name: str,
    file: str,
    upload: UploadFile,
    force: bool = Query(False),
    settings: ServerSettings = Depends(settings_dep),
):
    registry = _build_registry(settings)
    info = registry.get(name)
    if info is None:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")

    target = info.path / file
    if target.exists() and not force:
        raise HTTPException(
            status_code=409,
            detail=f"File '{file}' already exists. Use ?force=true to overwrite.",
        )

    content = await upload.read()
    target.write_bytes(content)
    return {"uploaded": file, "size_bytes": len(content)}


# ---------------------------------------------------------------------------
# Helper files — delete
# ---------------------------------------------------------------------------


@router.delete("/{name}/files/{file}")
def delete_skill_file(
    name: str,
    file: str,
    settings: ServerSettings = Depends(settings_dep),
):
    if file == _SKILL_FILENAME:
        raise HTTPException(status_code=403, detail="Cannot delete SKILL.md")

    registry = _build_registry(settings)
    info = registry.get(name)
    if info is None:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")

    target = info.path / file
    if not target.is_file():
        raise HTTPException(status_code=404, detail=f"File '{file}' not found in skill '{name}'")

    target.unlink()
    return {"deleted": file}
