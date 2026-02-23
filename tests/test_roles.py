"""Tests for Role and RoleContext — no LLM calls required."""

import pytest
from surogate_agent.core.roles import Role, RoleContext


def test_role_values():
    assert Role.DEVELOPER.value == "developer"
    assert Role.USER.value == "user"


def test_role_is_string_enum():
    # Role can be compared to plain strings
    assert Role.DEVELOPER == "developer"


def test_role_context_defaults():
    ctx = RoleContext()
    assert ctx.role == Role.USER
    assert ctx.user_id == ""
    assert ctx.session_id == ""
    assert ctx.metadata == {}
    assert not ctx.is_developer


def test_role_context_developer():
    ctx = RoleContext(role=Role.DEVELOPER, user_id="alice")
    assert ctx.is_developer
    assert ctx.user_id == "alice"


def test_role_context_round_trip():
    original = RoleContext(
        role=Role.DEVELOPER,
        user_id="bob",
        session_id="20260221-143022-abc123",
        metadata={"tenant": "acme"},
    )
    serialized = original.to_configurable()
    restored = RoleContext.from_configurable(serialized)

    assert restored.role == original.role
    assert restored.user_id == original.user_id
    assert restored.session_id == original.session_id
    assert restored.metadata == original.metadata


def test_role_context_from_empty_configurable():
    ctx = RoleContext.from_configurable({})
    assert ctx.role == Role.USER


def test_role_context_from_unknown_role_raises():
    with pytest.raises(ValueError):
        RoleContext.from_configurable({"role": "superadmin"})
