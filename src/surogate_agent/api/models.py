"""
Pydantic request/response models for the surogate-agent REST API.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    message: str
    images: list[str] = Field(default_factory=list)  # base64 data URIs for multimodal input
    role: str = "user"
    session_id: str = ""
    skill: str = ""
    model: str = ""
    user_id: str = ""
    allow_execute: bool = False
    api_key: str = ""  # client-supplied key; used only when server env var is absent
    openrouter_provider: str = ""  # comma-separated OpenRouter provider name(s), e.g. "MiniMax"
    vllm_url: str = ""  # vLLM / self-hosted OpenAI-compatible endpoint URL
    vllm_tool_calling: bool = True
    vllm_temperature: Optional[float] = None
    vllm_top_k: Optional[int] = None
    vllm_top_p: Optional[float] = None
    vllm_min_p: Optional[float] = None
    vllm_presence_penalty: Optional[float] = None
    vllm_context_length: Optional[int] = None
    thinking_enabled: Optional[bool] = None   # None = not specified; use DB setting as fallback
    thinking_budget: Optional[int] = None     # None = not specified; use DB setting as fallback


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
    experts: list[str]
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


# ---------------------------------------------------------------------------
# Session metadata models
# ---------------------------------------------------------------------------


class SessionMetaCreate(BaseModel):
    session_id: str
    name: str


class SessionMetaUpdate(BaseModel):
    name: str


class SessionMetaResponse(BaseModel):
    session_id: str
    name: str
    created_at: str  # ISO datetime string


# ---------------------------------------------------------------------------
# Chat history models
# ---------------------------------------------------------------------------


class ChatHistorySaveRequest(BaseModel):
    messages: list[Any]


class ChatHistoryResponse(BaseModel):
    session_id: str
    messages: list[Any]


class InputHistorySaveRequest(BaseModel):
    entries: list[str]


class InputHistoryResponse(BaseModel):
    session_id: str
    entries: list[str]


class InputFilesResponse(BaseModel):
    session_id: str
    input_files: list[str]


# ---------------------------------------------------------------------------
# Human-in-the-loop (HITL) task models
# ---------------------------------------------------------------------------


class HumanTaskResponse(BaseModel):
    id: str
    task_type: str          # "approval" | "report"
    status: str             # "pending" | "completed" | "cancelled"
    title: str
    description: str
    context: dict
    assigned_to: str
    assigned_by: str
    created_at: str
    responded_at: Optional[str]
    response: Optional[dict]


class TaskRespondRequest(BaseModel):
    decision: Optional[str] = None      # "approved" | "rejected" — for approval tasks
    acknowledged: Optional[bool] = None  # for report tasks
    feedback: str = ""


class SessionLockResponse(BaseModel):
    locked: bool
    task_id: Optional[str]
    task_type: Optional[str]  # "approval" | "report" — for frontend routing


# ---------------------------------------------------------------------------
# Skill import/export models
# ---------------------------------------------------------------------------


class SkillImportResponse(BaseModel):
    imported: list[str]
    skipped: list[str]


# ---------------------------------------------------------------------------
# MCP server models
# ---------------------------------------------------------------------------


class McpToolInfo(BaseModel):
    name: str
    description: str


class McpServerCreate(BaseModel):
    name: str
    repo_url: str = ""
    start_command: str = ""
    cwd: str = ""
    transport: str = "sse"
    host: str = "localhost"
    port: int = 8101
    tools: list[McpToolInfo] = Field(default_factory=list)


class McpServerResponse(BaseModel):
    name: str
    repo_url: str
    start_command: str
    cwd: str
    transport: str
    host: str
    port: int
    tools: list[McpToolInfo]
    registered_at: str
    status: str
