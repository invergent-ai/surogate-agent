"""User CRUD and password utilities."""

from __future__ import annotations

import json

import bcrypt
from sqlalchemy.orm import Session

from surogate_agent.auth.models import Expert, User
from surogate_agent.auth.schemas import ExpertCreate, ExpertUpdate, RegisterRequest
from surogate_agent.core.logging import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


# ---------------------------------------------------------------------------
# User queries
# ---------------------------------------------------------------------------

def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == username).first()


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


# ---------------------------------------------------------------------------
# User creation
# ---------------------------------------------------------------------------

def create_user(db: Session, req: RegisterRequest) -> User:
    log.debug("creating user: username=%r role=%s", req.username, req.role)
    user = User(
        username=req.username,
        email=req.email,
        hashed_password=hash_password(req.password),
        role=req.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    log.debug("user created: id=%d username=%r", user.id, user.username)
    return user


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def authenticate_user(db: Session, username: str, password: str) -> User | None:
    """Return the user if credentials are valid, else None."""
    log.debug("authenticate_user: %r", username)
    user = get_user_by_username(db, username)
    if user is None or not user.is_active:
        log.warning("authentication failed: user '%s' not found or inactive", username)
        return None
    if not verify_password(password, user.hashed_password):
        log.warning("authentication failed: wrong password for '%s'", username)
        return None
    log.debug("authentication successful: %r", username)
    return user


# ---------------------------------------------------------------------------
# User settings
# ---------------------------------------------------------------------------

def update_user_settings(
    db: Session,
    user: User,
    model: str,
    api_key: str,
    openrouter_provider: str = "",
    vllm_url: str = "",
    vllm_tool_calling: bool = True,
    vllm_temperature=None,
    vllm_top_k=None,
    vllm_top_p=None,
    vllm_min_p=None,
    vllm_presence_penalty=None,
    vllm_context_length=None,
    thinking_enabled: bool = False,
    thinking_budget: int = 10000,
    expert_lookup_enabled: bool = False,
) -> User:
    """Persist the user's preferred LLM model, API key, and vLLM settings."""
    user.model = model.strip()
    user.api_key = api_key.strip()
    user.openrouter_provider = openrouter_provider.strip()
    user.vllm_url = vllm_url.strip()
    user.vllm_tool_calling = vllm_tool_calling
    user.vllm_temperature = vllm_temperature
    user.vllm_top_k = vllm_top_k
    user.vllm_top_p = vllm_top_p
    user.vllm_min_p = vllm_min_p
    user.vllm_presence_penalty = vllm_presence_penalty
    user.vllm_context_length = vllm_context_length
    user.thinking_enabled = thinking_enabled
    user.thinking_budget = thinking_budget
    user.expert_lookup_enabled = expert_lookup_enabled
    db.commit()
    db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Expert CRUD
# ---------------------------------------------------------------------------

def list_experts(db: Session, user_id: int) -> list[Expert]:
    return db.query(Expert).filter(Expert.user_id == user_id).all()


def get_expert(db: Session, user_id: int, expert_id: int) -> Expert | None:
    return db.query(Expert).filter(Expert.user_id == user_id, Expert.id == expert_id).first()


def get_expert_by_name(db: Session, user_id: int, name: str) -> Expert | None:
    return db.query(Expert).filter(Expert.user_id == user_id, Expert.name == name).first()


def create_expert(db: Session, user_id: int, req: ExpertCreate) -> Expert:
    expert = Expert(
        user_id=user_id,
        name=req.name.strip(),
        description=req.description.strip(),
        model=req.model.strip(),
        api_key=req.api_key.strip(),
        openrouter_provider=req.openrouter_provider.strip(),
        vllm_url=req.vllm_url.strip(),
        vllm_tool_calling=req.vllm_tool_calling,
        vllm_temperature=req.vllm_temperature,
        vllm_top_k=req.vllm_top_k,
        vllm_top_p=req.vllm_top_p,
        vllm_min_p=req.vllm_min_p,
        vllm_presence_penalty=req.vllm_presence_penalty,
        vllm_context_length=req.vllm_context_length,
        thinking_enabled=req.thinking_enabled,
        thinking_budget=req.thinking_budget,
        available_tools=json.dumps(req.available_tools),
        available_skills=json.dumps(req.available_skills),
        available_mcp_servers=json.dumps(req.available_mcp_servers),
    )
    db.add(expert)
    db.commit()
    db.refresh(expert)
    return expert


def update_expert(db: Session, expert: Expert, req: ExpertUpdate) -> Expert:
    if req.name is not None:
        expert.name = req.name.strip()
    if req.description is not None:
        expert.description = req.description.strip()
    if req.model is not None:
        expert.model = req.model.strip()
    if req.api_key is not None:
        expert.api_key = req.api_key.strip()
    if req.openrouter_provider is not None:
        expert.openrouter_provider = req.openrouter_provider.strip()
    if req.vllm_url is not None:
        expert.vllm_url = req.vllm_url.strip()
    if req.vllm_tool_calling is not None:
        expert.vllm_tool_calling = req.vllm_tool_calling
    if req.vllm_temperature is not None:
        expert.vllm_temperature = req.vllm_temperature
    if req.vllm_top_k is not None:
        expert.vllm_top_k = req.vllm_top_k
    if req.vllm_top_p is not None:
        expert.vllm_top_p = req.vllm_top_p
    if req.vllm_min_p is not None:
        expert.vllm_min_p = req.vllm_min_p
    if req.vllm_presence_penalty is not None:
        expert.vllm_presence_penalty = req.vllm_presence_penalty
    if req.vllm_context_length is not None:
        expert.vllm_context_length = req.vllm_context_length
    if req.thinking_enabled is not None:
        expert.thinking_enabled = req.thinking_enabled
    if req.thinking_budget is not None:
        expert.thinking_budget = req.thinking_budget
    if req.available_tools is not None:
        expert.available_tools = json.dumps(req.available_tools)
    if req.available_skills is not None:
        expert.available_skills = json.dumps(req.available_skills)
    if req.available_mcp_servers is not None:
        expert.available_mcp_servers = json.dumps(req.available_mcp_servers)
    db.commit()
    db.refresh(expert)
    return expert


def delete_expert(db: Session, expert: Expert) -> None:
    db.delete(expert)
    db.commit()
