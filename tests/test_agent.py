"""Tests for create_agent() and RoleGuardAgent — graph is mocked."""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from surogate_agent.core.roles import Role, RoleContext
from surogate_agent.core.config import AgentConfig
from surogate_agent.middleware.role_guard import RoleGuardAgent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_agent(role: Role = Role.USER, **cfg_kwargs) -> RoleGuardAgent:
    """Build a RoleGuardAgent with a mock underlying graph."""
    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {"messages": [{"role": "assistant", "content": "ok"}]}
    mock_graph.stream.return_value = iter([{"messages": []}])

    config = AgentConfig(**cfg_kwargs)
    ctx = RoleContext(role=role)
    return RoleGuardAgent(graph=mock_graph, role_context=ctx, config=config)


# ---------------------------------------------------------------------------
# RoleGuardAgent tests
# ---------------------------------------------------------------------------

class TestRoleGuardAgent:
    def test_invoke_passes_role_context_in_configurable(self):
        agent = _make_agent(role=Role.DEVELOPER)
        agent.invoke({"messages": []})

        call_args = agent._graph.invoke.call_args
        cfg = call_args.kwargs.get("config") or call_args.args[1]
        assert cfg["configurable"]["role"] == "developer"

    def test_invoke_merges_caller_config(self):
        agent = _make_agent()
        agent.invoke({"messages": []}, config={"configurable": {"thread_id": "t1"}})

        cfg = agent._graph.invoke.call_args.kwargs["config"]
        assert cfg["configurable"]["thread_id"] == "t1"
        assert cfg["configurable"]["role"] == "user"

    def test_role_property(self):
        agent = _make_agent(role=Role.DEVELOPER)
        assert agent.role == Role.DEVELOPER

    def test_repr_contains_role(self):
        agent = _make_agent(role=Role.DEVELOPER)
        assert "developer" in repr(agent)

    def test_stream_yields_from_graph(self):
        agent = _make_agent()
        chunks = list(agent.stream({"messages": []}))
        assert isinstance(chunks, list)

    def test_role_context_exposed(self):
        # user_id lives on RoleContext, not AgentConfig — build directly
        mock_graph = MagicMock()
        ctx = RoleContext(role=Role.USER, user_id="carol")
        config = AgentConfig()
        agent = RoleGuardAgent(graph=mock_graph, role_context=ctx, config=config)
        assert agent.role_context.user_id == "carol"
        assert agent.role_context.role == Role.USER


# ---------------------------------------------------------------------------
# create_agent integration (mocked deepagents + LLM)
# ---------------------------------------------------------------------------

class TestCreateAgent:
    @patch("surogate_agent.core.agent._import_deepagents")
    @patch("surogate_agent.core.agent._build_llm")
    def test_developer_gets_meta_skill(self, mock_llm, mock_import, tmp_path):
        """Developer role must include the meta-skill path."""
        mock_llm.return_value = MagicMock()
        mock_create = MagicMock(return_value=MagicMock())
        mock_import.return_value = mock_create

        from surogate_agent.core.agent import create_agent
        create_agent(role=Role.DEVELOPER, config=AgentConfig(user_skills_dir=tmp_path))

        call_kwargs = mock_create.call_args.kwargs
        skill_paths = call_kwargs.get("skills", [])
        assert any("meta" in p for p in skill_paths), (
            f"meta skill not found in {skill_paths}"
        )

    @patch("surogate_agent.core.agent._import_deepagents")
    @patch("surogate_agent.core.agent._build_llm")
    def test_user_does_not_get_meta_skill(self, mock_llm, mock_import, tmp_path):
        """User role must NOT include the builtin meta-skill directory."""
        mock_llm.return_value = MagicMock()
        mock_create = MagicMock(return_value=MagicMock())
        mock_import.return_value = mock_create

        from surogate_agent.core.agent import create_agent
        from surogate_agent.core.config import _DEFAULT_SKILLS_DIR
        create_agent(role=Role.USER, config=AgentConfig(user_skills_dir=tmp_path))

        call_kwargs = mock_create.call_args.kwargs
        skill_paths = call_kwargs.get("skills", [])
        builtin = str(_DEFAULT_SKILLS_DIR)
        assert not any(p == builtin for p in skill_paths), (
            f"builtin meta-skill dir should not be present for USER role but found in {skill_paths}"
        )

    @patch("surogate_agent.core.agent._import_deepagents")
    @patch("surogate_agent.core.agent._build_llm")
    def test_returns_role_guard_agent(self, mock_llm, mock_import, tmp_path):
        mock_llm.return_value = MagicMock()
        mock_import.return_value = MagicMock(return_value=MagicMock())

        from surogate_agent.core.agent import create_agent
        agent = create_agent(config=AgentConfig(user_skills_dir=tmp_path))
        assert isinstance(agent, RoleGuardAgent)

    @patch("surogate_agent.core.agent._import_deepagents")
    @patch("surogate_agent.core.agent._build_llm")
    def test_system_prompt_contains_user_skills_dir(self, mock_llm, mock_import, tmp_path):
        mock_llm.return_value = MagicMock()
        mock_create = MagicMock(return_value=MagicMock())
        mock_import.return_value = mock_create

        from surogate_agent.core.agent import create_agent
        user_dir = tmp_path / "my-skills"
        create_agent(role=Role.DEVELOPER, config=AgentConfig(user_skills_dir=user_dir))

        call_kwargs = mock_create.call_args.kwargs
        system_prompt = call_kwargs.get("system_prompt", "")
        assert str(user_dir.resolve()) in system_prompt

    @patch("surogate_agent.core.agent._import_deepagents")
    @patch("surogate_agent.core.agent._build_llm")
    def test_system_prompt_contains_session_workspace(self, mock_llm, mock_import, tmp_path):
        mock_llm.return_value = MagicMock()
        mock_create = MagicMock(return_value=MagicMock())
        mock_import.return_value = mock_create

        from surogate_agent.core.agent import create_agent
        from surogate_agent.core.session import SessionManager
        sm = SessionManager(tmp_path / "sessions")
        session = sm.new_session("test-session")

        create_agent(
            role=Role.USER,
            config=AgentConfig(user_skills_dir=tmp_path / "skills"),
            session=session,
        )

        call_kwargs = mock_create.call_args.kwargs
        system_prompt = call_kwargs.get("system_prompt", "")
        assert str(session.workspace_dir) in system_prompt
        assert "test-session" in system_prompt

    @patch("surogate_agent.core.agent._import_deepagents")
    @patch("surogate_agent.core.agent._build_llm")
    def test_role_context_carries_session_id(self, mock_llm, mock_import, tmp_path):
        mock_llm.return_value = MagicMock()
        mock_import.return_value = MagicMock(return_value=MagicMock())

        from surogate_agent.core.agent import create_agent
        from surogate_agent.core.session import SessionManager
        session = SessionManager(tmp_path / "sessions").new_session("sid-42")

        agent = create_agent(
            config=AgentConfig(user_skills_dir=tmp_path / "skills"),
            session=session,
        )
        assert agent.role_context.session_id == "sid-42"


# ---------------------------------------------------------------------------
# _build_llm unit tests
# ---------------------------------------------------------------------------

class TestBuildLlm:
    """Tests for _build_llm() — langchain_openai is not installed in the test
    environment so we inject a mock via sys.modules."""

    def _mock_openai(self):
        """Return (mock_module, mock_ChatOpenAI_cls)."""
        mock_cls = MagicMock()
        mock_module = MagicMock()
        mock_module.ChatOpenAI = mock_cls
        return mock_module, mock_cls

    def test_openrouter_no_provider(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
        mock_module, mock_cls = self._mock_openai()
        with patch.dict("sys.modules", {"langchain_openai": mock_module}):
            from surogate_agent.core.agent import _build_llm
            _build_llm("minimax/MiniMax-M2.5")
        mock_cls.assert_called_once()
        kw = mock_cls.call_args.kwargs
        assert kw["model"] == "minimax/MiniMax-M2.5"
        assert kw["base_url"] == "https://openrouter.ai/api/v1"
        assert "model_kwargs" not in kw

    def test_openrouter_with_provider_order(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
        mock_module, mock_cls = self._mock_openai()
        provider = {"order": ["MiniMax"], "allow_fallbacks": False}
        with patch.dict("sys.modules", {"langchain_openai": mock_module}):
            from surogate_agent.core.agent import _build_llm
            _build_llm("minimax/MiniMax-M2.5", openrouter_provider=provider)
        mock_cls.assert_called_once()
        kw = mock_cls.call_args.kwargs
        assert kw["model_kwargs"] == {"extra_body": {"provider": provider}}

    def test_openrouter_api_key_from_arg(self, monkeypatch):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        mock_module, mock_cls = self._mock_openai()
        with patch.dict("sys.modules", {"langchain_openai": mock_module}):
            from surogate_agent.core.agent import _build_llm
            _build_llm("google/gemini-2.0-flash-001", api_key="explicit-key")
        kw = mock_cls.call_args.kwargs
        assert kw["api_key"] == "explicit-key"
        assert kw["base_url"] == "https://openrouter.ai/api/v1"

    def test_openrouter_missing_key_raises(self, monkeypatch):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        from surogate_agent.core.agent import _build_llm
        with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
            _build_llm("minimax/MiniMax-M2.5")


# ---------------------------------------------------------------------------
# _user_skills_need_execute unit tests
# ---------------------------------------------------------------------------

import textwrap

class TestUserSkillsNeedExecute:
    def test_returns_true_when_skill_declares_execute(self, tmp_path):
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(textwrap.dedent("""\
            ---
            name: my-skill
            description: A skill that runs scripts.
            allowed-tools: read_file execute write_file
            ---
            # My Skill
        """))
        from surogate_agent.core.agent import _user_skills_need_execute
        assert _user_skills_need_execute([tmp_path]) is True

    def test_returns_false_when_no_skill_declares_execute(self, tmp_path):
        skill_dir = tmp_path / "read-only-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(textwrap.dedent("""\
            ---
            name: read-only-skill
            description: A read-only skill.
            allowed-tools: read_file write_file
            ---
            # Read-Only Skill
        """))
        from surogate_agent.core.agent import _user_skills_need_execute
        assert _user_skills_need_execute([tmp_path]) is False

    def test_returns_false_for_nonexistent_dir(self, tmp_path):
        from surogate_agent.core.agent import _user_skills_need_execute
        assert _user_skills_need_execute([tmp_path / "does-not-exist"]) is False

    def test_returns_false_when_no_allowed_tools_field(self, tmp_path):
        skill_dir = tmp_path / "bare-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(textwrap.dedent("""\
            ---
            name: bare-skill
            description: No allowed-tools declared.
            ---
            # Bare Skill
        """))
        from surogate_agent.core.agent import _user_skills_need_execute
        assert _user_skills_need_execute([tmp_path]) is False

    def test_checks_extra_dirs(self, tmp_path):
        """Skills in extra dirs (--extra-skills) are also scanned."""
        main_dir = tmp_path / "main"
        extra_dir = tmp_path / "extra"
        main_dir.mkdir()
        extra_dir.mkdir()
        # Only the extra dir has a skill with execute
        skill_dir = extra_dir / "exec-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(textwrap.dedent("""\
            ---
            name: exec-skill
            description: Lives in extra dir.
            allowed-tools: read_file execute
            ---
            # Exec Skill
        """))
        from surogate_agent.core.agent import _user_skills_need_execute
        assert _user_skills_need_execute([main_dir, extra_dir]) is True
        assert _user_skills_need_execute([main_dir]) is False
