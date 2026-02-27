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


DATABASE_URL: str = os.getenv(
    "SUROGATE_DATABASE_URL",
    "sqlite:///./surogate.db",  # override with SUROGATE_DATABASE_URL in production
)

# SQLite requires check_same_thread=False for multi-threaded FastAPI use.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=_connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


def get_sqlite_path() -> Path | None:
    """Return the resolved filesystem path of the SQLite database, or None.

    Used to point LangGraph's AsyncSqliteSaver at the same file as the main
    application DB, eliminating separate ``.history.db`` files.
    """
    if DATABASE_URL.startswith("sqlite:///"):
        raw = DATABASE_URL[len("sqlite:///"):]
        return Path(raw).resolve()
    return None


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


def create_tables() -> None:
    """Create all tables defined via :class:`Base`.

    Called once at application startup.  Safe to call repeatedly — existing
    tables are not modified by ``create_all``.  A lightweight column migration
    is run first to bring existing databases up to date.
    """
    from surogate_agent.auth import models as _models  # noqa: F401 — registers models
    _migrate_users_table()
    Base.metadata.create_all(bind=engine)
