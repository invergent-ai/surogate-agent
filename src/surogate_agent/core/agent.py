"""
create_agent() — the main entry point for surogate-agent.

Wraps ``deepagents.create_deep_agent()`` with:
- Role-based skill selection (meta-skill is injected only for DEVELOPER)
- RoleGuardMiddleware so every invocation carries a RoleContext
- Configurable model, extra tools, and skill directories
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from surogate_agent.core.config import AgentConfig, _DEFAULT_SKILLS_DIR
from surogate_agent.core.logging import get_logger
from surogate_agent.core.roles import Role, RoleContext
from surogate_agent.core.session import Session, SessionManager

log = get_logger(__name__)

# Lazy import so that users without deepagents installed still get import errors
# at call time, not at module import time — friendlier for unit testing with mocks.
def _import_deepagents():
    try:
        from deepagents import create_deep_agent  # type: ignore
        return create_deep_agent
    except ImportError as exc:
        raise ImportError(
            "deepagents is required: pip install 'surogate-agent[anthropic]'"
        ) from exc


def _build_llm(model: str, api_key: str = "", openrouter_provider: dict | None = None):
    """Instantiate a LangChain chat model from a model-string shorthand.

    Parameters
    ----------
    model:
        LangChain model string.  Routing is determined by prefix/format:

        - ``"claude-*"`` → Anthropic (requires ``ANTHROPIC_API_KEY``)
        - ``"gpt-*"``, ``"o1-*"``, ``"o3-*"`` → OpenAI (requires ``OPENAI_API_KEY``)
        - ``"<provider>/<model>"`` (contains ``/``) → OpenRouter
          (requires ``OPENROUTER_API_KEY``).
          Examples: ``"minimax/MiniMax-M2.5"``, ``"anthropic/claude-3-5-sonnet"``

    api_key:
        API key supplied at request time (from the user's stored settings).
        The user-supplied key takes precedence over the server-side
        environment variable, allowing each user to use their own key.
    openrouter_provider:
        Optional OpenRouter provider routing object.  Passed verbatim as the
        ``provider`` field in the request body — only applied for OpenRouter
        (``"/"`` in the model string).
        Example: ``{"order": ["MiniMax"], "allow_fallbacks": False}``
    """
    log.debug("building LLM: model=%s has_key=%s", model, bool(api_key))
    if model.startswith("claude"):
        resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not resolved_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is not configured. Set it as a server "
                "environment variable, or enter your API key in Settings."
            )
        try:
            from langchain_anthropic import ChatAnthropic  # type: ignore
            log.debug("instantiated ChatAnthropic: %s", model)
            return ChatAnthropic(model=model, api_key=resolved_key)
        except ImportError:
            raise ImportError(
                "Install langchain-anthropic: pip install 'surogate-agent[anthropic]'"
            )
    if model.startswith("gpt") or model.startswith("o1") or model.startswith("o3"):
        resolved_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        if not resolved_key:
            raise ValueError(
                "OPENAI_API_KEY is not configured. Set it as a server "
                "environment variable, or enter your API key in Settings."
            )
        try:
            from langchain_openai import ChatOpenAI  # type: ignore
            log.debug("instantiated ChatOpenAI: %s", model)
            return ChatOpenAI(model=model, api_key=resolved_key)
        except ImportError:
            raise ImportError(
                "Install langchain-openai: pip install 'surogate-agent[openai]'"
            )
    if "/" in model:
        # OpenRouter: all models are identified as "provider/model-name".
        # Examples: "minimax/MiniMax-M2.5", "anthropic/claude-3-5-sonnet",
        #           "google/gemini-2.0-flash-001"
        # OpenRouter exposes an OpenAI-compatible API, so ChatOpenAI works.
        resolved_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        if not resolved_key:
            raise ValueError(
                "OPENROUTER_API_KEY is not configured. Set it as a server "
                "environment variable, or enter your API key in Settings."
            )
        try:
            from langchain_openai import ChatOpenAI  # type: ignore
            log.debug(
                "instantiated ChatOpenAI (OpenRouter): %s provider=%s",
                model, openrouter_provider,
            )
            kwargs: dict = dict(
                model=model,
                api_key=resolved_key,
                base_url="https://openrouter.ai/api/v1",
            )
            if openrouter_provider:
                # `provider` is an OpenRouter-specific request body field.
                # It must be passed via `extra_body` so the OpenAI client
                # merges it into the JSON payload rather than treating it
                # as a Python kwarg (which raises TypeError).
                kwargs["model_kwargs"] = {"extra_body": {"provider": openrouter_provider}}
            return ChatOpenAI(**kwargs)
        except ImportError:
            raise ImportError(
                "Install langchain-openai: pip install 'surogate-agent[openai]'"
            )
    raise ValueError(
        f"Unknown model '{model}'. "
        "Use a Claude model ('claude-sonnet-4-6'), an OpenAI model ('gpt-4o'), "
        "or an OpenRouter model in 'provider/model' format ('minimax/MiniMax-M2.5'). "
        "You can also set the SUROGATE_MODEL environment variable."
    )


def create_agent(
    role: Role = Role.USER,
    config: Optional[AgentConfig] = None,
    *,
    session: Optional[Session] = None,
    user_id: str = "",
    metadata: dict[str, Any] | None = None,
    checkpointer=None,
):
    """Create a role-aware surogate deep agent.

    Parameters
    ----------
    role:
        The role for this agent instance.  ``Role.DEVELOPER`` loads the
        meta-skill and exposes skill-authoring capabilities.
    config:
        Optional ``AgentConfig``.  Defaults are used when omitted.
    user_id:
        Optional user identifier, stored in ``RoleContext`` for audit trails.
    metadata:
        Arbitrary key/value pairs forwarded into ``RoleContext.metadata``.

    Returns
    -------
    A compiled LangGraph ``CompiledGraph`` (i.e. what ``create_deep_agent``
    returns), wrapped in a ``RoleGuardAgent`` shim that injects the
    ``RoleContext`` into every ``.invoke()`` / ``.stream()`` call.

    Examples
    --------
    >>> agent = create_agent(role=Role.DEVELOPER)
    >>> result = agent.invoke({
    ...     "messages": [{"role": "user", "content": "Create a Jira summariser skill"}]
    ... })
    """
    log.info(
        "create_agent: role=%s model=%s user_id=%r",
        role.value, config.model if config else AgentConfig().model, user_id,
    )

    if config is None:
        config = AgentConfig()

    # Auto-create a session when none is provided.
    if session is None:
        session = SessionManager(config.sessions_dir).new_session()

    log.debug("session_id=%s workspace=%s", session.session_id, session.workspace_dir)

    role_ctx = RoleContext(
        role=role,
        user_id=user_id,
        session_id=session.session_id,
        metadata=metadata or {},
    )

    # Build skill *source* directories for deepagents SkillsMiddleware.
    # SkillsMiddleware scans each source dir for subdirs that contain SKILL.md —
    # so we pass parent directories, not individual skill directories.
    # Role filtering is achieved by controlling which source directories are included:
    #   DEVELOPER → builtin/ (meta-skill) + user skills dir
    #   USER      → user skills dir only (no access to builtin meta-skill)
    skill_sources: list[str] = []
    if role == Role.DEVELOPER and _DEFAULT_SKILLS_DIR.exists():
        skill_sources.append(str(_DEFAULT_SKILLS_DIR))
        log.debug("skill source: builtin/ (developer role)")
    if config.user_skills_dir.exists():
        skill_sources.append(str(config.user_skills_dir))
        log.debug("skill source: user skills dir %s", config.user_skills_dir)
    # Also include any extra skills dirs from config
    for extra in config.skills_dirs:
        s = str(extra)
        if extra.exists() and s not in skill_sources and s != str(_DEFAULT_SKILLS_DIR):
            skill_sources.append(s)
            log.debug("skill source: extra dir %s", extra)
    log.debug("total skill sources: %d — %s", len(skill_sources), skill_sources)

    create_deep_agent = _import_deepagents()
    llm = _build_llm(config.model, api_key=config.api_key, openrouter_provider=config.openrouter_provider)

    # Choose backend based on whether shell execution is needed.
    #
    # LocalShellBackend is used when:
    #   (a) config.allow_execute is True (explicit consent, e.g. developer mode), OR
    #   (b) the user role is active AND at least one user skill declares 'execute'
    #       in its allowed-tools frontmatter — skill authors opt their skill in by
    #       listing execute, and the framework honours that automatically.
    #
    # FilesystemBackend (default) — file ops only (ls/read/write/edit/glob/grep).
    # The `execute` tool is present but returns a "not available" error.
    effective_allow_execute = config.allow_execute
    if not effective_allow_execute and role == Role.USER:
        # Collect all directories that are visible to user sessions — mirrors
        # the skill_sources logic above but without the developer-only builtin.
        user_skill_dirs: list[Path] = [config.user_skills_dir]
        for extra in config.skills_dirs:
            if extra != _DEFAULT_SKILLS_DIR and extra not in user_skill_dirs:
                user_skill_dirs.append(extra)
        effective_allow_execute = _user_skills_need_execute(user_skill_dirs)
        if effective_allow_execute:
            log.warning(
                "auto-activating LocalShellBackend: a user skill declared 'execute' in allowed-tools"
            )

    backend = None
    try:
        if effective_allow_execute:
            from deepagents.backends.local_shell import LocalShellBackend
            backend = LocalShellBackend(
                root_dir=Path.cwd(),
                virtual_mode=False,
                inherit_env=True,   # agent needs PATH, API keys, etc.
            )
            log.debug("backend: LocalShellBackend (allow_execute=%s)", config.allow_execute)
        else:
            from deepagents.backends.filesystem import FilesystemBackend
            backend = FilesystemBackend(root_dir=Path.cwd(), virtual_mode=False)
            log.debug("backend: FilesystemBackend")
    except ImportError:
        log.warning("could not import deepagents backend — falling back to deepagents default")
        backend = None  # fall back to deepagents default

    system_suffix = _build_system_suffix(role_ctx, config, session)
    log.trace("system prompt suffix length: %d chars", len(system_suffix))  # type: ignore[attr-defined]

    graph_kwargs: dict[str, Any] = dict(
        model=llm,
        tools=config.extra_tools,
        skills=skill_sources if skill_sources else None,
        system_prompt=system_suffix if system_suffix else None,
    )
    if backend is not None:
        graph_kwargs["backend"] = backend
    if checkpointer is not None:
        graph_kwargs["checkpointer"] = checkpointer

    graph = create_deep_agent(**graph_kwargs)
    log.debug("deepagents graph created")

    from surogate_agent.middleware.role_guard import RoleGuardAgent
    agent = RoleGuardAgent(graph=graph, role_context=role_ctx, config=config, session=session)
    log.info("agent ready: %r", agent)
    return agent


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_system_suffix(
    role_ctx: RoleContext,
    config: AgentConfig,
    session: Session,
) -> str:
    parts: list[str] = []
    skills_root = config.user_skills_dir.resolve()

    if role_ctx.is_developer:
        dev_workspace = config.dev_workspace_dir.resolve()
        workspace_snapshot = _snapshot_workspace(dev_workspace)
        execute_section = ""
        if config.allow_execute:
            execute_section = (
                "\n## Shell execution\n"
                "You have the `execute` tool available. Use it to:\n"
                "- Install packages: `execute pip install <pkg>` or `execute uv pip install <pkg>`\n"
                "- Install system packages: `execute apt-get install -y <pkg>`\n"
                "- Run scripts: `execute python workspace/<skill>/extract.py ...`\n"
                "- Any other shell command needed to build or test skills.\n"
                "Always prefer project-local installs (pip install, uv pip) over system-wide.\n"
                "The developer has consented to shell execution for this session.\n"
            )
        parts.append(
            f"You are operating in DEVELOPER mode.\n"
            f"You have access to the skill-development meta-skill.\n"
            f"{execute_section}\n"
            f"## File locations — keep these strictly separate\n\n"
            f"### 1. Skill definition files  →  {skills_root}/<skill-name>/\n"
            f"Files here ARE the skill — they ship with it and are accessible "
            f"to the agent when the skill is active.\n"
            f"Examples: SKILL.md, prompt.md, output-schema.json\n"
            f"Rules:\n"
            f"- Each skill's files are private to its own sub-directory.\n"
            f"- Never reference one skill's files from another skill.\n\n"
            f"### 2. Development workspace  →  {dev_workspace}/<skill-name>/\n"
            f"This is your persistent scratch area while BUILDING skills.\n"
            f"It mirrors the skill directory structure so you can work on "
            f"multiple skills in parallel without their files mixing.\n"
            f"Use it for: draft prompts, test inputs, experiment notes, "
            f"temporary scripts.\n"
            f"Files here are NOT part of any skill and NOT accessible to users.\n"
            f"Only copy a file from here into the skill directory when you "
            f"deliberately want it to ship as part of that skill.\n\n"
            f"### Current workspace contents (snapshot at session start)\n"
            f"{workspace_snapshot}"
        )
    else:
        user_workspace = session.workspace_dir.resolve()
        dev_workspace = config.dev_workspace_dir.resolve()
        session_snapshot = _snapshot_session(user_workspace)
        parts.append(
            f"You are operating in USER mode.\n\n"
            f"## Accessible file locations\n\n"
            f"You may ONLY read and write files in these two locations:\n\n"
            f"1. **Your session workspace** (read + write)\n"
            f"   Path: {user_workspace}\n"
            f"   This is the only place where user files exist.\n"
            f"   Always resolve a filename the user mentions as "
            f"`{user_workspace}/<filename>`.\n\n"
            f"2. **Skill files** (read-only)\n"
            f"   Helper files shipped with the active skill (templates, scripts, etc.).\n"
            f"   A skill's instructions will tell you the exact path when relevant.\n\n"
            f"### Files currently in your session workspace\n"
            f"{session_snapshot}\n"
            f"## FORBIDDEN paths — never access these under any circumstances\n\n"
            f"- {dev_workspace}  ← developer workspace, not accessible to users\n"
            f"- Any directory outside your session workspace or the skills directory\n\n"
            f"If the user asks you to process a file that is not listed above, "
            f"tell them to upload it to the session workspace first. "
            f"Do not search for it in other directories."
        )

    if config.system_prompt_suffix:
        parts.append(config.system_prompt_suffix)

    return "\n\n".join(parts)


def _user_skills_need_execute(skill_dirs: list[Path]) -> bool:
    """Return True if any skill in *skill_dirs* declares ``execute`` in its
    ``allowed-tools`` frontmatter.

    This is used by ``create_agent()`` to automatically activate
    ``LocalShellBackend`` for user sessions when at least one installed skill
    requires shell execution — without requiring explicit ``allow_execute=True``
    in the config.

    All user-visible skill directories are checked (user_skills_dir plus any
    extra dirs supplied via AgentConfig.skills_dirs).
    """
    from surogate_agent.skills.loader import SkillLoader
    for d in skill_dirs:
        if not d.is_dir():
            continue
        for skill in SkillLoader(d).load():
            if "execute" in skill.allowed_tools:
                return True
    return False


def _snapshot_session(session_workspace: Path) -> str:
    """Return a brief text listing of files currently in the user session workspace."""
    if not session_workspace.is_dir():
        return "(no files uploaded yet)\n"
    files = sorted(f for f in session_workspace.iterdir() if f.is_file())
    if not files:
        return "(no files uploaded yet)\n"
    lines = [f"  {f.name}  ({f.stat().st_size:,} bytes)  →  {f}" for f in files]
    return "\n".join(lines) + "\n"


def _snapshot_workspace(dev_workspace: Path) -> str:
    """Return a brief text listing of files currently in the dev workspace."""
    if not dev_workspace.is_dir():
        return "(workspace directory does not exist yet — it will be created when you first add a file)\n"

    skill_dirs = sorted(d for d in dev_workspace.iterdir() if d.is_dir())
    if not skill_dirs:
        return "(workspace is empty — add files with: surogate-agent workspace files add <skill> <file>)\n"

    lines: list[str] = []
    for skill_dir in skill_dirs:
        files = sorted(f for f in skill_dir.iterdir() if f.is_file())
        lines.append(f"  {dev_workspace.name}/{skill_dir.name}/  ({len(files)} file(s))")
        for f in files:
            lines.append(f"    {f.name}  ({f.stat().st_size:,} bytes)  →  {f}")
    return "\n".join(lines) + "\n"
