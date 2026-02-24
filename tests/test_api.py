"""
Tests for the surogate-agent FastAPI layer.

All LLM calls are mocked — no real model is required.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from surogate_agent.api.app import create_app
from surogate_agent.api.deps import ServerSettings, get_settings


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_dirs(tmp_path):
    skills_dir = tmp_path / "skills"
    sessions_dir = tmp_path / "sessions"
    workspace_dir = tmp_path / "workspace"
    skills_dir.mkdir()
    sessions_dir.mkdir()
    workspace_dir.mkdir()
    return skills_dir, sessions_dir, workspace_dir


@pytest.fixture()
def settings(tmp_dirs):
    skills_dir, sessions_dir, workspace_dir = tmp_dirs
    return ServerSettings(
        skills_dir=skills_dir,
        sessions_dir=sessions_dir,
        workspace_dir=workspace_dir,
        model="claude-sonnet-4-6",
    )


@pytest.fixture()
def client(settings):
    from unittest.mock import MagicMock
    from surogate_agent.auth.jwt import get_current_user

    mock_user = MagicMock()
    mock_user.username = "testuser"
    mock_user.role = "developer"
    mock_user.is_active = True

    app = create_app()
    app.dependency_overrides[
        __import__("surogate_agent.api.deps", fromlist=["settings_dep"]).settings_dep
    ] = lambda: settings
    app.dependency_overrides[get_current_user] = lambda: mock_user
    get_settings.cache_clear()
    return TestClient(app)


def _make_skill(skills_dir: Path, name: str, *, role_restriction: str | None = None) -> Path:
    """Create a minimal skill directory for testing."""
    d = skills_dir / name
    d.mkdir(parents=True, exist_ok=True)
    lines = ["---", f"name: {name}", f"description: Test skill {name}", "version: 0.1.0"]
    if role_restriction:
        lines.append(f"role-restriction: {role_restriction}")
    lines.append("---")
    lines.append("")
    lines.append("Instructions for the skill.")
    (d / "SKILL.md").write_text("\n".join(lines))
    return d


# ---------------------------------------------------------------------------
# Skills — list
# ---------------------------------------------------------------------------


class TestSkillsList:
    def test_list_empty(self, client):
        resp = client.get("/api/skills")
        assert resp.status_code == 200
        # Only builtins (meta skill) may appear
        body = resp.json()
        assert isinstance(body, list)

    def test_list_user_skill(self, client, settings):
        _make_skill(settings.skills_dir, "my-skill")
        resp = client.get("/api/skills")
        assert resp.status_code == 200
        names = [s["name"] for s in resp.json()]
        assert "my-skill" in names

    def test_list_filter_user_role(self, client, settings):
        _make_skill(settings.skills_dir, "open-skill")
        _make_skill(settings.skills_dir, "dev-only", role_restriction="developer")
        resp = client.get("/api/skills?role=user")
        assert resp.status_code == 200
        names = [s["name"] for s in resp.json()]
        assert "open-skill" in names
        assert "dev-only" not in names

    def test_list_filter_developer_role(self, client, settings):
        _make_skill(settings.skills_dir, "open-skill")
        _make_skill(settings.skills_dir, "dev-only", role_restriction="developer")
        resp = client.get("/api/skills?role=developer")
        assert resp.status_code == 200
        names = [s["name"] for s in resp.json()]
        assert "open-skill" in names
        assert "dev-only" in names


# ---------------------------------------------------------------------------
# Skills — get
# ---------------------------------------------------------------------------


class TestSkillsGet:
    def test_get_existing(self, client, settings):
        _make_skill(settings.skills_dir, "my-skill")
        resp = client.get("/api/skills/my-skill")
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "my-skill"
        assert "skill_md_content" in body
        assert "helper_files" in body

    def test_get_missing(self, client):
        resp = client.get("/api/skills/nonexistent")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Skills — create
# ---------------------------------------------------------------------------


class TestSkillsCreate:
    def test_create_new_skill(self, client, settings):
        payload = {
            "name": "new-skill",
            "description": "A brand new skill",
            "version": "1.0.0",
        }
        resp = client.post("/api/skills", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "new-skill"
        assert (settings.skills_dir / "new-skill" / "SKILL.md").exists()

    def test_create_with_body(self, client, settings):
        payload = {
            "name": "with-body",
            "description": "Has body",
            "skill_md_body": "# Instructions\nDo something useful.",
        }
        resp = client.post("/api/skills", json=payload)
        assert resp.status_code == 201
        content = (settings.skills_dir / "with-body" / "SKILL.md").read_text()
        assert "Do something useful" in content

    def test_create_conflict(self, client, settings):
        _make_skill(settings.skills_dir, "existing")
        payload = {"name": "existing", "description": "dup"}
        resp = client.post("/api/skills", json=payload)
        assert resp.status_code == 409

    def test_create_with_role_restriction(self, client, settings):
        payload = {
            "name": "dev-skill",
            "description": "Developer only",
            "role_restriction": "developer",
        }
        resp = client.post("/api/skills", json=payload)
        assert resp.status_code == 201
        content = (settings.skills_dir / "dev-skill" / "SKILL.md").read_text()
        assert "role-restriction: developer" in content


# ---------------------------------------------------------------------------
# Skills — delete
# ---------------------------------------------------------------------------


class TestSkillsDelete:
    def test_delete_user_skill(self, client, settings):
        _make_skill(settings.skills_dir, "deletable")
        resp = client.delete("/api/skills/deletable")
        assert resp.status_code == 200
        assert not (settings.skills_dir / "deletable").exists()

    def test_delete_missing(self, client):
        resp = client.delete("/api/skills/ghost")
        assert resp.status_code == 404

    def test_delete_builtin_refused(self, client):
        # skill-developer is the builtin meta skill — cannot be deleted
        resp = client.delete("/api/skills/skill-developer")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Skills — validate
# ---------------------------------------------------------------------------


class TestSkillsValidate:
    def test_validate_valid_skill(self, client, settings):
        _make_skill(settings.skills_dir, "valid-skill")
        resp = client.post("/api/skills/valid-skill/validate")
        assert resp.status_code == 200
        body = resp.json()
        assert body["valid"] is True
        assert body["errors"] == []

    def test_validate_missing_skill(self, client):
        resp = client.post("/api/skills/no-such/validate")
        assert resp.status_code == 200
        body = resp.json()
        assert body["valid"] is False
        assert body["errors"]


# ---------------------------------------------------------------------------
# Skills — helper files
# ---------------------------------------------------------------------------


class TestSkillHelperFiles:
    def test_list_helper_files_empty(self, client, settings):
        _make_skill(settings.skills_dir, "no-helpers")
        resp = client.get("/api/skills/no-helpers/files")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_upload_and_list(self, client, settings):
        _make_skill(settings.skills_dir, "with-helpers")
        file_data = b"helper content"
        resp = client.post(
            "/api/skills/with-helpers/files/helper.txt",
            files={"upload": ("helper.txt", io.BytesIO(file_data), "text/plain")},
        )
        assert resp.status_code == 201

        resp = client.get("/api/skills/with-helpers/files")
        assert resp.status_code == 200
        names = [f["name"] for f in resp.json()]
        assert "helper.txt" in names

    def test_download_helper(self, client, settings):
        d = _make_skill(settings.skills_dir, "with-download")
        (d / "data.txt").write_text("hello")
        resp = client.get("/api/skills/with-download/files/data.txt")
        assert resp.status_code == 200
        assert resp.content == b"hello"

    def test_download_missing(self, client, settings):
        _make_skill(settings.skills_dir, "no-file")
        resp = client.get("/api/skills/no-file/files/nope.txt")
        assert resp.status_code == 404

    def test_delete_helper(self, client, settings):
        d = _make_skill(settings.skills_dir, "del-helper")
        (d / "remove.txt").write_text("bye")
        resp = client.delete("/api/skills/del-helper/files/remove.txt")
        assert resp.status_code == 200
        assert not (d / "remove.txt").exists()

    def test_delete_skill_md_refused(self, client, settings):
        _make_skill(settings.skills_dir, "protected")
        resp = client.delete("/api/skills/protected/files/SKILL.md")
        assert resp.status_code == 403

    def test_upload_conflict_without_force(self, client, settings):
        d = _make_skill(settings.skills_dir, "conflict")
        (d / "existing.txt").write_text("old")
        resp = client.post(
            "/api/skills/conflict/files/existing.txt",
            files={"upload": ("existing.txt", io.BytesIO(b"new"), "text/plain")},
        )
        assert resp.status_code == 409

    def test_upload_force_overwrite(self, client, settings):
        d = _make_skill(settings.skills_dir, "force-overwrite")
        (d / "existing.txt").write_text("old")
        resp = client.post(
            "/api/skills/force-overwrite/files/existing.txt?force=true",
            files={"upload": ("existing.txt", io.BytesIO(b"new"), "text/plain")},
        )
        assert resp.status_code == 201
        assert (d / "existing.txt").read_text() == "new"


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


class TestSessions:
    def _make_session(self, settings, session_id="test-session"):
        ws = settings.sessions_dir / session_id
        ws.mkdir(parents=True, exist_ok=True)
        return ws

    def test_list_sessions_empty(self, client):
        resp = client.get("/api/sessions")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_sessions(self, client, settings):
        self._make_session(settings, "s1")
        self._make_session(settings, "s2")
        resp = client.get("/api/sessions")
        assert resp.status_code == 200
        ids = [s["session_id"] for s in resp.json()]
        assert "s1" in ids
        assert "s2" in ids

    def test_get_session(self, client, settings):
        self._make_session(settings, "my-session")
        resp = client.get("/api/sessions/my-session")
        assert resp.status_code == 200
        assert resp.json()["session_id"] == "my-session"

    def test_get_session_missing(self, client):
        resp = client.get("/api/sessions/ghost")
        assert resp.status_code == 404

    def test_delete_session(self, client, settings):
        self._make_session(settings, "delete-me")
        resp = client.delete("/api/sessions/delete-me")
        assert resp.status_code == 200
        assert not (settings.sessions_dir / "delete-me").exists()

    def test_delete_session_missing(self, client):
        resp = client.delete("/api/sessions/no-such")
        assert resp.status_code == 404

    def test_session_file_upload_download_delete(self, client, settings):
        self._make_session(settings, "file-session")
        # Upload
        resp = client.post(
            "/api/sessions/file-session/files",
            files={"upload": ("data.csv", io.BytesIO(b"a,b\n1,2"), "text/csv")},
        )
        assert resp.status_code == 201
        # List
        resp = client.get("/api/sessions/file-session/files")
        assert resp.status_code == 200
        names = [f["name"] for f in resp.json()]
        assert "data.csv" in names
        # Download
        resp = client.get("/api/sessions/file-session/files/data.csv")
        assert resp.status_code == 200
        assert b"a,b" in resp.content
        # Delete
        resp = client.delete("/api/sessions/file-session/files/data.csv")
        assert resp.status_code == 200
        assert not (settings.sessions_dir / "file-session" / "data.csv").exists()

    def test_session_file_download_missing(self, client, settings):
        self._make_session(settings, "empty-session")
        resp = client.get("/api/sessions/empty-session/files/nope.txt")
        assert resp.status_code == 404

    def test_session_upload_creates_session(self, client, settings):
        # Upload to a session that doesn't exist yet
        resp = client.post(
            "/api/sessions/brand-new/files",
            files={"upload": ("hello.txt", io.BytesIO(b"hi"), "text/plain")},
        )
        assert resp.status_code == 201
        assert (settings.sessions_dir / "brand-new" / "hello.txt").exists()


# ---------------------------------------------------------------------------
# Workspace
# ---------------------------------------------------------------------------


class TestWorkspace:
    def _make_workspace(self, settings, skill="my-skill"):
        ws = settings.workspace_dir / skill
        ws.mkdir(parents=True, exist_ok=True)
        return ws

    def test_list_workspaces_empty(self, client):
        resp = client.get("/api/workspace")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_workspaces(self, client, settings):
        self._make_workspace(settings, "skill-a")
        self._make_workspace(settings, "skill-b")
        resp = client.get("/api/workspace")
        assert resp.status_code == 200
        skills = [w["skill"] for w in resp.json()]
        assert "skill-a" in skills
        assert "skill-b" in skills

    def test_get_workspace(self, client, settings):
        self._make_workspace(settings, "alpha")
        resp = client.get("/api/workspace/alpha")
        assert resp.status_code == 200
        assert resp.json()["skill"] == "alpha"

    def test_get_workspace_missing(self, client):
        resp = client.get("/api/workspace/no-such")
        assert resp.status_code == 404

    def test_delete_workspace(self, client, settings):
        self._make_workspace(settings, "remove-me")
        resp = client.delete("/api/workspace/remove-me")
        assert resp.status_code == 200
        assert not (settings.workspace_dir / "remove-me").exists()

    def test_workspace_file_upload_download_delete(self, client, settings):
        self._make_workspace(settings, "ws-skill")
        # Upload
        resp = client.post(
            "/api/workspace/ws-skill/files",
            files={"upload": ("notes.txt", io.BytesIO(b"my notes"), "text/plain")},
        )
        assert resp.status_code == 201
        # List
        resp = client.get("/api/workspace/ws-skill/files")
        assert resp.status_code == 200
        names = [f["name"] for f in resp.json()]
        assert "notes.txt" in names
        # Download
        resp = client.get("/api/workspace/ws-skill/files/notes.txt")
        assert resp.status_code == 200
        assert resp.content == b"my notes"
        # Delete
        resp = client.delete("/api/workspace/ws-skill/files/notes.txt")
        assert resp.status_code == 200
        assert not (settings.workspace_dir / "ws-skill" / "notes.txt").exists()

    def test_workspace_file_download_missing(self, client, settings):
        self._make_workspace(settings, "empty-ws")
        resp = client.get("/api/workspace/empty-ws/files/nope.txt")
        assert resp.status_code == 404

    def test_workspace_upload_creates_dir(self, client, settings):
        # Upload to workspace that does not exist yet
        resp = client.post(
            "/api/workspace/brand-new-skill/files",
            files={"upload": ("draft.md", io.BytesIO(b"# Draft"), "text/markdown")},
        )
        assert resp.status_code == 201
        assert (settings.workspace_dir / "brand-new-skill" / "draft.md").exists()


# ---------------------------------------------------------------------------
# Chat — SSE stream (mocked agent)
# ---------------------------------------------------------------------------


class TestChat:
    def _mock_agent(self):
        """Return a mock RoleGuardAgent that yields a simple text chunk."""

        async def _astream(input, config=None, **kwargs):
            yield {
                "agent": {
                    "messages": [
                        MagicMock(
                            type="ai",
                            id="msg1",
                            content="Hello from the agent!",
                            tool_calls=[],
                        )
                    ]
                }
            }

        mock = MagicMock()
        mock.astream = _astream
        mock.session = MagicMock()
        mock.session.session_id = "test-session-id"
        mock.session.files = []
        return mock

    @patch("surogate_agent.api.routers.chat.create_agent")
    def test_chat_returns_sse_stream(self, mock_create_agent, client, settings):
        mock_agent = self._mock_agent()
        mock_create_agent.return_value = mock_agent

        resp = client.post(
            "/api/chat",
            json={"message": "Hello", "role": "user"},
            headers={"Accept": "text/event-stream"},
        )
        assert resp.status_code == 200
        # SSE response should contain event data
        body = resp.text
        assert "data:" in body

    @patch("surogate_agent.api.routers.chat.create_agent")
    def test_chat_done_event_present(self, mock_create_agent, client, settings):
        mock_agent = self._mock_agent()
        mock_create_agent.return_value = mock_agent

        resp = client.post(
            "/api/chat",
            json={"message": "Hello", "role": "user"},
        )
        assert resp.status_code == 200
        body = resp.text
        # Done event must be yielded
        assert "done" in body

    @patch("surogate_agent.api.routers.chat.create_agent")
    def test_chat_invalid_role_falls_back_to_account_role(self, mock_create_agent, client):
        # An unrecognised role value in the request body is silently ignored;
        # the authenticated user's account role is used instead.
        mock_create_agent.return_value = self._mock_agent()
        resp = client.post("/api/chat", json={"message": "Hi", "role": "superuser"})
        assert resp.status_code == 200
        assert "done" in resp.text

    @patch("surogate_agent.api.routers.chat.create_agent")
    def test_chat_developer_can_downgrade_to_user_role(self, mock_create_agent, client):
        # A developer account may request role="user" explicitly (for "Test as User").
        # The request must succeed and use user-mode semantics.
        mock_create_agent.return_value = self._mock_agent()
        resp = client.post("/api/chat", json={"message": "Hi", "role": "user"})
        assert resp.status_code == 200
        assert "done" in resp.text
        # Verify create_agent was called with Role.USER
        from surogate_agent.core.roles import Role
        call_kwargs = mock_create_agent.call_args
        assert call_kwargs.kwargs.get("role") == Role.USER or (
            call_kwargs.args and call_kwargs.args[0] == Role.USER
        )

    @patch("surogate_agent.api.routers.chat.create_agent")
    def test_chat_developer_role(self, mock_create_agent, client, settings):
        mock_agent = self._mock_agent()
        mock_create_agent.return_value = mock_agent

        resp = client.post(
            "/api/chat",
            json={"message": "Create a skill", "role": "developer", "skill": "my-skill"},
        )
        assert resp.status_code == 200
        body = resp.text
        assert "done" in body

    @patch("surogate_agent.api.routers.chat.create_agent")
    def test_chat_thinking_event(self, mock_create_agent, client, settings):
        """An AI message with thinking content blocks yields a thinking event."""

        async def _astream_thinking(input, config=None, **kwargs):
            yield {
                "agent": {
                    "messages": [
                        MagicMock(
                            type="ai",
                            id="msg-think",
                            content=[{"type": "thinking", "thinking": "I am reasoning..."}],
                            tool_calls=[],
                        )
                    ]
                }
            }

        mock = MagicMock()
        mock.astream = _astream_thinking
        mock.session = MagicMock()
        mock.session.session_id = "think-session"
        mock.session.files = []
        mock_create_agent.return_value = mock

        resp = client.post("/api/chat", json={"message": "Think!", "role": "user"})
        assert resp.status_code == 200
        assert "thinking" in resp.text

    @patch("surogate_agent.api.routers.chat.create_agent")
    def test_chat_tool_call_event(self, mock_create_agent, client, settings):
        """Tool calls in AI messages yield tool_call events."""

        tc = MagicMock()
        tc.name = "write_file"
        tc.args = {"path": "/tmp/x.txt", "content": "hi"}

        async def _astream_tc(input, config=None, **kwargs):
            yield {
                "agent": {
                    "messages": [
                        MagicMock(
                            type="ai",
                            id="msg-tc",
                            content="",
                            tool_calls=[tc],
                        )
                    ]
                }
            }

        mock = MagicMock()
        mock.astream = _astream_tc
        mock.session = MagicMock()
        mock.session.session_id = "tc-session"
        mock.session.files = []
        mock_create_agent.return_value = mock

        resp = client.post("/api/chat", json={"message": "Write a file", "role": "developer"})
        assert resp.status_code == 200
        assert "tool_call" in resp.text
