"""ORM models for the auth module."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from surogate_agent.auth.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    # Per-user LLM configuration (nullable for backward compat with existing DBs)
    model: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, default="", server_default=""
    )
    api_key: Mapped[Optional[str]] = mapped_column(
        String(1000), nullable=True, default="", server_default=""
    )
    # OpenRouter provider preference — comma-separated provider name(s), e.g. "MiniMax"
    # or "MiniMax,Fireworks".  Blank means no preference (OpenRouter default routing).
    openrouter_provider: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, default="", server_default=""
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r} role={self.role!r}>"


class SessionMetadata(Base):
    """Per-user session metadata (name, creation date)."""

    __tablename__ = "session_metadata"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<SessionMetadata session_id={self.session_id!r} user={self.user_id!r} name={self.name!r}>"


class ChatHistory(Base):
    """Stores the rendered chat messages (JSON) for a user session."""

    __tablename__ = "chat_history"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    messages_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<ChatHistory session_id={self.session_id!r} user={self.user_id!r}>"
