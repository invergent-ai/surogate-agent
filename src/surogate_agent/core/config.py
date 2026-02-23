"""
AgentConfig — central configuration for surogate-agent.

All fields have sensible defaults so that ``create_agent()`` works out of the
box (model is read from the SUROGATE_MODEL env-var or falls back to
``claude-sonnet-4-6``).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


_DEFAULT_MODEL = "claude-sonnet-4-6"
_DEFAULT_SKILLS_DIR = Path(__file__).parent.parent / "skills" / "builtin"


@dataclass
class AgentConfig:
    """Configuration for a surogate-agent instance.

    Parameters
    ----------
    model:
        LangChain model identifier string, e.g. ``"claude-sonnet-4-6"`` or
        ``"gpt-4o"``.  Defaults to the ``SUROGATE_MODEL`` env-var or
        ``claude-sonnet-4-6``.
    skills_dirs:
        List of directories to scan for skill folders.  Each directory may
        contain multiple skill sub-folders, each with a ``SKILL.md``.
        The built-in skills directory (containing the meta-skill) is always
        included.
    user_skills_dir:
        Directory where newly created (developer-authored) skills are saved.
        Defaults to ``./skills`` relative to the current working directory.
    extra_tools:
        Additional LangChain ``BaseTool`` instances to inject into the agent.
    max_iterations:
        Hard limit on agent reasoning steps per invocation.
    system_prompt_suffix:
        Text appended to the base system prompt — useful for tenant-specific
        instructions or compliance notes.
    """

    model: str = field(
        default_factory=lambda: os.environ.get("SUROGATE_MODEL", _DEFAULT_MODEL)
    )
    skills_dirs: list[Path] = field(default_factory=list)
    user_skills_dir: Path = field(default_factory=lambda: Path.cwd() / "skills")
    # Developer's persistent scratch area — separate from skill definition files.
    # Survives across development sessions; never mixed into skill directories.
    dev_workspace_dir: Path = field(default_factory=lambda: Path(os.environ.get("SUROGATE_WORKSPACE_DIR", "") or Path.cwd() / "workspace"))
    sessions_dir: Path = field(default_factory=lambda: Path(os.environ.get("SUROGATE_SESSIONS_DIR", "") or Path.cwd() / "sessions"))
    extra_tools: list = field(default_factory=list)
    max_iterations: int = 50
    system_prompt_suffix: str = ""
    # When True the agent backend gains shell execution capability (execute tool).
    # Only set this after explicit user consent — it allows arbitrary commands on
    # the local machine.  Developer mode prompts for consent at session start.
    allow_execute: bool = False
    # Optional API key supplied at request time (e.g. from the browser settings panel).
    # Takes effect when the corresponding env var (ANTHROPIC_API_KEY / OPENAI_API_KEY)
    # is not set in the server environment.
    api_key: str = ""

    def __post_init__(self) -> None:
        # Always include the bundled builtin skills directory.
        builtin = _DEFAULT_SKILLS_DIR
        if builtin not in self.skills_dirs:
            self.skills_dirs.insert(0, builtin)

        # Coerce any str paths to Path.
        self.skills_dirs = [Path(p) for p in self.skills_dirs]
        self.user_skills_dir = Path(self.user_skills_dir)
        self.dev_workspace_dir = Path(self.dev_workspace_dir)
        self.sessions_dir = Path(self.sessions_dir)

    @property
    def all_skill_roots(self) -> list[Path]:
        """All directories (builtin + user) to scan for skills."""
        roots = list(self.skills_dirs)
        if self.user_skills_dir not in roots:
            roots.append(self.user_skills_dir)
        return roots
