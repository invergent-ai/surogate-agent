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


def get_checkpointer_path() -> Path:
    """Return the path to the LangGraph checkpointer SQLite database.

    Reads ``SUROGATE_CHECKPOINTER_DB`` env var.  When not set, derives the
    path from ``SUROGATE_SESSIONS_DIR`` so the file lands next to the other
    data directories rather than wherever the process CWD happens to be.
    This keeps both databases in one place (e.g. ``/data/``) without
    requiring an explicit env var in most deployments.

    This database is intentionally separate from ``SUROGATE_DATABASE_URL``
    (auth/users) so the two can be backed up and migrated independently.
    """
    if "SUROGATE_CHECKPOINTER_DB" in os.environ:
        return Path(os.environ["SUROGATE_CHECKPOINTER_DB"]).resolve()
    sessions_env = os.environ.get("SUROGATE_SESSIONS_DIR", "")
    if sessions_env:
        data_dir = Path(sessions_env).resolve().parent
    else:
        data_dir = Path(".").resolve()
    return data_dir / "checkpoints.db"


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
    user_skills_dir: Path = field(default_factory=lambda: Path(os.environ.get("SUROGATE_SKILLS_DIR", "") or Path.cwd() / "skills"))
    # Developer's persistent scratch area — separate from skill definition files.
    # Survives across development sessions; never mixed into skill directories.
    dev_workspace_dir: Path = field(default_factory=lambda: Path(os.environ.get("SUROGATE_WORKSPACE_DIR", "") or Path.cwd() / "workspace"))
    mcp_workspace_dir: Path = field(default_factory=lambda: Path(os.environ.get("SUROGATE_MCP_WORKSPACE_DIR", "") or Path.cwd() / "mcp-workspace"))
    # Production registry dir — registry.json and final start.sh files read by MCPLifecycle.
    mcp_scripts_dir: Path = field(default_factory=lambda: Path(os.environ.get("SUROGATE_MCP_DIR", "") or Path.cwd() / "mcp_scripts"))
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
    # OpenRouter provider routing object, passed verbatim as the ``provider`` field in
    # the request body.  Only used when the model string contains ``/`` (OpenRouter).
    # Example: {"order": ["MiniMax"], "allow_fallbacks": False}
    # See https://openrouter.ai/docs for available fields.
    openrouter_provider: dict | None = None
    # vLLM / self-hosted OpenAI-compatible endpoint base URL, e.g. "http://localhost:8000".
    # When set, the agent routes to this endpoint instead of cloud providers.
    # API key is not required (defaults to "EMPTY" for vLLM compatibility).
    vllm_base_url: str = ""
    # When True (default), tool definitions are forwarded to vLLM (requires
    # --enable-auto-tool-choice on the server). When False, tools are stripped
    # so the model runs as a plain chat endpoint without function calling.
    vllm_tool_calling: bool = True
    # Sampling parameters — only applied when vllm_base_url is set.
    vllm_temperature: Optional[float] = None
    vllm_top_k: Optional[int] = None
    vllm_top_p: Optional[float] = None
    vllm_min_p: Optional[float] = None
    vllm_presence_penalty: Optional[float] = None
    # Max context length of the model in tokens. When set, the user message is
    # truncated (with a ~2000-token overhead reserve) so the request fits in the
    # model's context window.  Uses a 4 chars-per-token approximation.
    vllm_context_length: Optional[int] = None
    # Thinking / extended reasoning.  When True, extended thinking is requested
    # from the model where the API supports it:
    #   - Claude  → thinking={"type":"enabled","budget_tokens":thinking_budget}
    #   - vLLM    → enable_thinking=True injected into the request body
    #   - OpenRouter → include=["reasoning"] injected into the request body
    #   - OpenAI  → no effect (Chat Completions API does not expose reasoning)
    thinking_enabled: bool = False
    thinking_budget: int = 10000  # token budget; primarily used by Claude

    def __post_init__(self) -> None:
        # Always include the bundled builtin skills directory.
        builtin = _DEFAULT_SKILLS_DIR
        if builtin not in self.skills_dirs:
            self.skills_dirs.insert(0, builtin)

        # Coerce any str paths to Path.
        self.skills_dirs = [Path(p) for p in self.skills_dirs]
        self.user_skills_dir = Path(self.user_skills_dir)
        self.dev_workspace_dir = Path(self.dev_workspace_dir)
        self.mcp_workspace_dir = Path(self.mcp_workspace_dir)
        self.mcp_scripts_dir = Path(self.mcp_scripts_dir)
        self.sessions_dir = Path(self.sessions_dir)

    @property
    def all_skill_roots(self) -> list[Path]:
        """All directories (builtin + user) to scan for skills."""
        roots = list(self.skills_dirs)
        if self.user_skills_dir not in roots:
            roots.append(self.user_skills_dir)
        return roots
