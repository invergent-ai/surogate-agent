"""User CRUD and password utilities."""

from __future__ import annotations

import bcrypt
from sqlalchemy.orm import Session

from surogate_agent.auth.models import User
from surogate_agent.auth.schemas import RegisterRequest


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
    user = User(
        username=req.username,
        email=req.email,
        hashed_password=hash_password(req.password),
        role=req.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def authenticate_user(db: Session, username: str, password: str) -> User | None:
    """Return the user if credentials are valid, else None."""
    user = get_user_by_username(db, username)
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


# ---------------------------------------------------------------------------
# User settings
# ---------------------------------------------------------------------------

def update_user_settings(db: Session, user: User, model: str, api_key: str) -> User:
    """Persist the user's preferred LLM model and API key."""
    user.model = model.strip()
    user.api_key = api_key.strip()
    db.commit()
    db.refresh(user)
    return user
