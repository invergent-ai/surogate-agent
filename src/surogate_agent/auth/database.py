"""SQLAlchemy engine and session factory.

Supports SQLite (dev, default) and PostgreSQL (prod) via the
``SUROGATE_DATABASE_URL`` environment variable.
"""

from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import create_engine
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


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables() -> None:
    """Create all tables defined via :class:`Base`.

    Called once at application startup.  Safe to call repeatedly — existing
    tables are not modified.
    """
    from surogate_agent.auth import models as _models  # noqa: F401 — registers models
    Base.metadata.create_all(bind=engine)
