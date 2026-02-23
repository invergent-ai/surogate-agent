"""Tests for Session and SessionManager — no LLM calls required."""

import pytest
from pathlib import Path

from surogate_agent.core.session import Session, SessionManager


@pytest.fixture()
def sm(tmp_path: Path) -> SessionManager:
    return SessionManager(tmp_path / "sessions")


class TestSessionManager:
    def test_new_session_does_not_create_directory_eagerly(self, sm: SessionManager):
        """Workspace must not be created until files are actually written."""
        session = sm.new_session()
        assert not session.workspace_dir.exists()

    def test_new_session_generates_id(self, sm: SessionManager):
        session = sm.new_session()
        assert session.session_id
        assert len(session.session_id) > 8   # timestamp + suffix

    def test_new_session_explicit_id(self, sm: SessionManager):
        session = sm.new_session("my-session")
        assert session.session_id == "my-session"
        assert session.workspace_dir.name == "my-session"

    def test_get_existing_session(self, sm: SessionManager, tmp_path: Path):
        """get_session finds a session once its workspace directory exists on disk."""
        session = sm.new_session("abc123")
        session.workspace_dir.mkdir(parents=True, exist_ok=True)  # simulate file write
        found = sm.get_session("abc123")
        assert found is not None
        assert found.session_id == "abc123"

    def test_get_missing_session_returns_none(self, sm: SessionManager):
        assert sm.get_session("does-not-exist") is None

    def test_resume_or_create_existing(self, sm: SessionManager):
        """resume_or_create finds an existing session whose directory is on disk."""
        session = sm.new_session("existing")
        session.workspace_dir.mkdir(parents=True, exist_ok=True)
        resumed = sm.resume_or_create("existing")
        assert resumed.session_id == "existing"

    def test_resume_or_create_new(self, sm: SessionManager):
        """resume_or_create returns a session object; directory is not yet created."""
        session = sm.resume_or_create("brand-new")
        assert session.session_id == "brand-new"
        assert not session.workspace_dir.exists()

    def test_list_sessions(self, sm: SessionManager):
        """Only sessions whose workspace directories exist on disk are listed."""
        for name in ("a", "b", "c"):
            s = sm.new_session(name)
            s.workspace_dir.mkdir(parents=True, exist_ok=True)
        sessions = sm.list_sessions()
        assert len(sessions) == 3

    def test_list_sessions_empty(self, sm: SessionManager):
        assert sm.list_sessions() == []

    def test_delete_session(self, sm: SessionManager):
        session = sm.new_session("to-delete")
        session.workspace_dir.mkdir(parents=True, exist_ok=True)
        deleted = sm.delete_session("to-delete")
        assert deleted is True
        assert sm.get_session("to-delete") is None

    def test_delete_nonexistent_session(self, sm: SessionManager):
        assert sm.delete_session("ghost") is False


class TestSession:
    def test_files_empty_workspace(self, sm: SessionManager):
        session = sm.new_session()
        assert session.files == []

    def test_files_lists_workspace_files(self, sm: SessionManager):
        session = sm.new_session()
        session.workspace_dir.mkdir(parents=True, exist_ok=True)
        (session.workspace_dir / "input.csv").write_text("a,b,c")
        (session.workspace_dir / "output.md").write_text("# Result")
        files = session.files
        assert len(files) == 2
        names = {f.name for f in files}
        assert names == {"input.csv", "output.md"}

    def test_add_file_copies_into_workspace(self, sm: SessionManager, tmp_path: Path):
        src = tmp_path / "data.csv"
        src.write_text("x,y\n1,2")
        session = sm.new_session()
        dest = session.add_file(src)
        assert dest.name == "data.csv"
        assert dest.read_text() == "x,y\n1,2"

    def test_add_file_with_rename(self, sm: SessionManager, tmp_path: Path):
        src = tmp_path / "original.txt"
        src.write_text("hello")
        session = sm.new_session()
        dest = session.add_file(src, filename="renamed.txt")
        assert dest.name == "renamed.txt"

    def test_str_returns_session_id(self, sm: SessionManager):
        session = sm.new_session("s1")
        assert str(session) == "s1"


class TestSessionIsolation:
    """Sessions must not share files."""

    def test_two_sessions_have_separate_workspaces(self, sm: SessionManager):
        s1 = sm.new_session()
        s2 = sm.new_session()
        assert s1.workspace_dir != s2.workspace_dir

    def test_file_in_one_session_not_visible_in_another(
        self, sm: SessionManager, tmp_path: Path
    ):
        src = tmp_path / "secret.txt"
        src.write_text("private")
        s1 = sm.new_session()
        s1.add_file(src)

        s2 = sm.new_session()
        assert (s2.workspace_dir / "secret.txt").exists() is False
