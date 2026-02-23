"""
Dependency injection for the surogate-agent FastAPI server.

All server-level configuration is read from environment variables so
individual requests do not need to carry filesystem paths.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from fastapi import Depends


@dataclass
class ServerSettings:
    skills_dir: Path
    sessions_dir: Path
    workspace_dir: Path
    model: str


@lru_cache(maxsize=1)
def get_settings() -> ServerSettings:
    return ServerSettings(
        skills_dir=Path(os.environ.get("SUROGATE_SKILLS_DIR", "./skills")),
        sessions_dir=Path(os.environ.get("SUROGATE_SESSIONS_DIR", "./sessions")),
        workspace_dir=Path(os.environ.get("SUROGATE_WORKSPACE_DIR", "./workspace")),
        model=os.environ.get("SUROGATE_MODEL", "claude-sonnet-4-6"),
    )


def settings_dep() -> ServerSettings:
    return get_settings()


Settings = Depends(settings_dep)
