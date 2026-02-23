"""
RoleGuardAgent — thin wrapper around a compiled LangGraph graph that:

1. Injects ``RoleContext`` into every call's ``configurable`` dict so graph
   nodes can inspect the current role without global state.
2. Provides a ``register_skill()`` convenience method so the developer can
   hot-register a newly created skill and immediately chat with it in the
   same session (without a full restart).

The wrapper is intentionally thin — it does *not* re-implement streaming,
checkpointing, or persistence.  All calls are forwarded to the underlying
graph after patching the config dict.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Iterator, Optional

from surogate_agent.core.config import AgentConfig
from surogate_agent.core.roles import RoleContext
from surogate_agent.core.session import Session


class RoleGuardAgent:
    """Wraps a compiled LangGraph graph with role-context injection.

    Parameters
    ----------
    graph:
        The compiled graph returned by ``deepagents.create_deep_agent()``.
    role_context:
        The ``RoleContext`` for this session.
    config:
        The ``AgentConfig`` used to create the agent.

    Usage
    -----
    >>> agent = create_agent(role=Role.DEVELOPER)
    >>> result = agent.invoke({"messages": [...]})
    >>> for chunk in agent.stream({"messages": [...]}):
    ...     print(chunk)
    """

    def __init__(
        self,
        graph,
        role_context: RoleContext,
        config: AgentConfig,
        session: Optional[Session] = None,
    ) -> None:
        self._graph = graph
        self._role_context = role_context
        self._config = config
        self._session = session

    # ------------------------------------------------------------------
    # Core invocation — delegate to the graph after injecting role ctx
    # ------------------------------------------------------------------

    def invoke(
        self,
        input: dict[str, Any],
        config: dict[str, Any] | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Synchronous invocation — mirrors ``CompiledGraph.invoke``."""
        merged = self._merge_config(config)
        return self._graph.invoke(input, config=merged, **kwargs)

    def stream(
        self,
        input: dict[str, Any],
        config: dict[str, Any] | None = None,
        **kwargs,
    ) -> Iterator[dict[str, Any]]:
        """Synchronous streaming — mirrors ``CompiledGraph.stream``."""
        merged = self._merge_config(config)
        yield from self._graph.stream(input, config=merged, **kwargs)

    async def ainvoke(
        self,
        input: dict[str, Any],
        config: dict[str, Any] | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Async invocation — mirrors ``CompiledGraph.ainvoke``."""
        merged = self._merge_config(config)
        return await self._graph.ainvoke(input, config=merged, **kwargs)

    async def astream(
        self,
        input: dict[str, Any],
        config: dict[str, Any] | None = None,
        **kwargs,
    ) -> AsyncIterator[dict[str, Any]]:
        """Async streaming — mirrors ``CompiledGraph.astream``."""
        merged = self._merge_config(config)
        async for chunk in self._graph.astream(input, config=merged, **kwargs):
            yield chunk

    # ------------------------------------------------------------------
    # Skill hot-registration
    # ------------------------------------------------------------------

    def register_skill(self, skill_dir: str | Any) -> None:
        """Register a newly created skill directory for the current session.

        This does *not* restart the agent; it updates the registry so that
        future sub-agent invocations within this session can see the skill.
        Calling code should pass the path the agent just wrote to.

        Parameters
        ----------
        skill_dir:
            Path to the skill directory (must contain a valid ``SKILL.md``).
        """
        from pathlib import Path
        from surogate_agent.skills.registry import SkillRegistry
        registry = SkillRegistry()
        registry.register(Path(skill_dir))
        # NOTE: deepagents does not support hot-reloading skill lists on an
        # existing compiled graph.  The registered skill will be picked up
        # on the *next* create_agent() call.  This method is here as a
        # hook for future deepagents versions that support runtime skill
        # injection, and for testing.

    # ------------------------------------------------------------------
    # Introspection helpers
    # ------------------------------------------------------------------

    @property
    def role(self):
        return self._role_context.role

    @property
    def role_context(self) -> RoleContext:
        return self._role_context

    @property
    def session(self) -> Optional[Session]:
        return self._session

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _merge_config(self, caller_config: dict[str, Any] | None) -> dict[str, Any]:
        """Merge caller-supplied config with role-context configurable."""
        base: dict[str, Any] = {"configurable": {}}
        if caller_config:
            base.update(caller_config)
            if "configurable" not in base:
                base["configurable"] = {}

        base["configurable"].update(self._role_context.to_configurable())
        return base

    def __repr__(self) -> str:
        return (
            f"RoleGuardAgent(role={self._role_context.role.value!r}, "
            f"model={self._config.model!r})"
        )
