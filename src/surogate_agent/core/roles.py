"""
Role definitions and role-gated context for surogate-agent.

Roles control which skills are available and what the agent system prompt
communicates about permitted actions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Role(str, Enum):
    """Agent user roles.

    DEVELOPER
        Full access including the meta-skill for creating and editing skills.
        The agent exposes the write_file / edit_file tools for skill artifacts
        and is given explicit instructions for the skill-development workflow.

    USER
        Standard access.  Meta-skill is not loaded; skill-authoring tools are
        hidden.  The agent only has access to explicitly enabled skills.
    """

    DEVELOPER = "developer"
    USER = "user"


@dataclass
class RoleContext:
    """Runtime context attached to an agent invocation.

    Passed through ``configurable`` in the LangGraph config dict so that
    graph nodes can inspect the current role without thread-unsafe globals.

    Attributes
    ----------
    role:
        The resolved role for this session.
    user_id:
        Optional identifier for the human user — useful for audit logging.
    session_id:
        The ID of the current session workspace.  User files (inputs/outputs)
        live in ``sessions/<session_id>/``.  Empty string when not in a session.
    metadata:
        Arbitrary key-value pairs (tenant ID, department, etc.).
    """

    role: Role = Role.USER
    user_id: str = ""
    session_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    @property
    def is_developer(self) -> bool:
        return self.role == Role.DEVELOPER

    def to_configurable(self) -> dict[str, Any]:
        """Serialize for use as a LangGraph ``config["configurable"]`` value."""
        return {
            "role": self.role.value,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_configurable(cls, cfg: dict[str, Any]) -> "RoleContext":
        """Reconstruct from a ``config["configurable"]`` dict."""
        return cls(
            role=Role(cfg.get("role", Role.USER.value)),
            user_id=cfg.get("user_id", ""),
            session_id=cfg.get("session_id", ""),
            metadata=cfg.get("metadata", {}),
        )
