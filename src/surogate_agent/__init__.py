"""
surogate-agent
==============

Role-aware deep agent built on deepagents/LangGraph with a meta-skill
for conversational skill development.

Quick start
-----------
>>> from surogate_agent import create_agent, Role
>>> agent = create_agent(role=Role.DEVELOPER)
>>> result = agent.invoke({"messages": [{"role": "user", "content": "Create a skill that summarises Jira tickets"}]})
"""

from surogate_agent.core.agent import create_agent
from surogate_agent.core.roles import Role, RoleContext
from surogate_agent.core.config import AgentConfig
from surogate_agent.core.session import Session, SessionManager
from surogate_agent.skills.registry import SkillRegistry

__all__ = [
    "create_agent",
    "Role",
    "RoleContext",
    "AgentConfig",
    "Session",
    "SessionManager",
    "SkillRegistry",
]
