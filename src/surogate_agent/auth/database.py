"""SQLAlchemy engine and session factory.

Supports SQLite (dev, default) and PostgreSQL (prod) via the
``SUROGATE_DATABASE_URL`` environment variable.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


def _default_database_url() -> str:
    """Compute a CWD-independent default database URL.

    Derives the path from ``SUROGATE_SESSIONS_DIR`` so the database lands
    in the same parent directory as the data directories (sessions/, skills/,
    workspace/).  Without this, SQLAlchemy creates ``./surogate.db`` relative
    to the process CWD at import time, which produces duplicate DB files when
    the server is launched from different directories.

    In Docker the ``SUROGATE_DATABASE_URL`` env var is always set explicitly
    to ``sqlite:////data/surogate.db``, so this function is only reached in
    local development.
    """
    sessions_env = os.getenv("SUROGATE_SESSIONS_DIR", "")
    if sessions_env:
        data_dir = Path(sessions_env).resolve().parent
    else:
        data_dir = Path(".").resolve()
    return f"sqlite:///{data_dir}/surogate.db"


DATABASE_URL: str = os.getenv("SUROGATE_DATABASE_URL") or _default_database_url()

# SQLite requires check_same_thread=False for multi-threaded FastAPI use.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=_connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _migrate_users_table() -> None:
    """Add model/api_key columns to the users table if they don't exist.

    SQLAlchemy's ``create_all`` only creates *new* tables; it never alters
    existing ones.  This function handles forward-migration for deployments
    that already have a ``users`` table without the new columns.
    """
    try:
        cols = {c["name"] for c in inspect(engine).get_columns("users")}
    except Exception:
        return  # Table doesn't exist yet — create_all will handle it

    with engine.begin() as conn:
        if "model" not in cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN model VARCHAR(255) DEFAULT ''"))
        if "api_key" not in cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN api_key VARCHAR(1000) DEFAULT ''"))
        if "openrouter_provider" not in cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN openrouter_provider VARCHAR(255) DEFAULT ''"))
        if "vllm_url" not in cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN vllm_url VARCHAR(2048) DEFAULT ''"))
        if "vllm_tool_calling" not in cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN vllm_tool_calling BOOLEAN DEFAULT 1"))
        if "vllm_temperature" not in cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN vllm_temperature FLOAT"))
        if "vllm_top_k" not in cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN vllm_top_k INTEGER"))
        if "vllm_top_p" not in cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN vllm_top_p FLOAT"))
        if "vllm_min_p" not in cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN vllm_min_p FLOAT"))
        if "vllm_presence_penalty" not in cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN vllm_presence_penalty FLOAT"))
        if "vllm_context_length" not in cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN vllm_context_length INTEGER"))
        if "thinking_enabled" not in cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN thinking_enabled BOOLEAN DEFAULT 0"))
        if "thinking_budget" not in cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN thinking_budget INTEGER DEFAULT 10000"))


def create_tables() -> None:
    """Create all tables defined via :class:`Base`.

    Called once at application startup.  Safe to call repeatedly — existing
    tables are not modified by ``create_all``.  A lightweight column migration
    is run first to bring existing databases up to date.
    """
    from surogate_agent.auth import models as _models  # noqa: F401 — registers models
    _migrate_users_table()
    Base.metadata.create_all(bind=engine)
