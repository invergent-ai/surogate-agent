"""User CRUD and password utilities."""

from __future__ import annotations

import bcrypt
from sqlalchemy.orm import Session

from surogate_agent.auth.models import User
from surogate_agent.auth.schemas import RegisterRequest
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
    db.commit()
    db.refresh(user)
    return user
