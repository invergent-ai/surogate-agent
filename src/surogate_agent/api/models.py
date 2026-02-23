"""
Pydantic request/response models for the surogate-agent REST API.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    message: str
    role: str = "user"
    session_id: str = ""
    skill: str = ""
    model: str = ""
    user_id: str = ""
    allow_execute: bool = False
    api_key: str = ""  # client-supplied key; used only when server env var is absent


class SkillCreateRequest(BaseModel):
    name: str
    description: str
    role_restriction: Optional[str] = None
    allowed_tools: list[str] = Field(default_factory=list)
    version: str = "0.1.0"
    skill_md_body: str = ""


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class FileInfo(BaseModel):
    name: str
    size_bytes: int


class SkillListItem(BaseModel):
    name: str
    description: str
    version: str
    role_restriction: Optional[str]
    path: str


class SkillResponse(BaseModel):
    name: str
    description: str
    version: str
    role_restriction: Optional[str]
    allowed_tools: list[str]
    path: str
    skill_md_content: str
    helper_files: list[FileInfo]


class ValidationResult(BaseModel):
    valid: bool
    errors: list[str]
    warnings: list[str]


class SessionResponse(BaseModel):
    session_id: str
    workspace_dir: str
    files: list[FileInfo]


class WorkspaceResponse(BaseModel):
    skill: str
    workspace_dir: str
    files: list[FileInfo]
