"""
Session — per-invocation workspace for user files.

A *session* is an isolated directory where the user's input and output files
live for the duration of a chat interaction.  It is entirely separate from
skill directories (which hold skill definitions and their private helper files).

Filesystem layout
-----------------
sessions/
└── <session-id>/           ← one dir per chat session
    ├── data.csv            ← "file X" — user places input here
    └── report.md           ← "file Y" — agent writes output here

Skill helper files (prompt.md, schema.json, …) live in the *skill* directory
and are never accessible from the session workspace, and vice-versa.
"""

from __future__ import annotations

import datetime
import random
import string
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


_DEFAULT_SESSIONS_DIR = Path("./sessions")


def _new_session_id() -> str:
    """Generate a short, human-readable session ID."""
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"{ts}-{suffix}"


@dataclass
class Session:
    """A single user session with an isolated file workspace.

    Attributes
    ----------
    session_id:
        Unique identifier for this session (timestamp + random suffix).
    workspace_dir:
        Absolute path to the session's file workspace.
    created_at:
        UTC timestamp when the session was created.
    """

    session_id: str
    workspace_dir: Path
    created_at: datetime.datetime = field(
        default_factory=datetime.datetime.utcnow
    )

    @property
    def files(self) -> list[Path]:
        """All files currently in the workspace, sorted by name."""
        if not self.workspace_dir.is_dir():
            return []
        return sorted(f for f in self.workspace_dir.iterdir() if f.is_file())

    def add_file(self, source: Path, filename: Optional[str] = None) -> Path:
        """Copy *source* into the workspace, creating the directory if needed.

        Parameters
        ----------
        source:
            Existing file to copy.
        filename:
            Override the destination filename.  Uses ``source.name`` if omitted.

        Returns
        -------
        Path to the file inside the workspace.
        """
        import shutil
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        dest = self.workspace_dir / (filename or source.name)
        shutil.copy2(source, dest)
        return dest

    def __str__(self) -> str:
        return self.session_id


class SessionManager:
    """Creates and resolves sessions on disk.

    Parameters
    ----------
    sessions_dir:
        Root directory under which session subdirectories are created.
    """

    def __init__(self, sessions_dir: Path = _DEFAULT_SESSIONS_DIR) -> None:
        self.sessions_dir = Path(sessions_dir).resolve()

    def new_session(self, session_id: Optional[str] = None) -> Session:
        """Return a new Session.

        The workspace directory is **not** created here — it is created lazily
        the first time a file is written into it (by the agent or via
        ``Session.add_file``).  This prevents a proliferation of empty
        timestamped directories when sessions produce no output files.

        Parameters
        ----------
        session_id:
            Explicit ID.  A timestamped random ID is generated if omitted.
        """
        sid = session_id or _new_session_id()
        workspace = self.sessions_dir / sid
        return Session(session_id=sid, workspace_dir=workspace)

    def get_session(self, session_id: str) -> Optional[Session]:
        """Return an existing session by ID, or None if it does not exist."""
        workspace = self.sessions_dir / session_id
        if workspace.is_dir():
            return Session(session_id=session_id, workspace_dir=workspace)
        return None

    def resume_or_create(self, session_id: str) -> Session:
        """Return an existing session, or create it if it does not exist."""
        return self.get_session(session_id) or self.new_session(session_id)

    def list_sessions(self) -> list[Session]:
        """Return all existing sessions, sorted newest-first."""
        if not self.sessions_dir.is_dir():
            return []
        sessions = []
        for entry in self.sessions_dir.iterdir():
            if entry.is_dir():
                sessions.append(
                    Session(session_id=entry.name, workspace_dir=entry)
                )
        return sorted(sessions, key=lambda s: s.session_id, reverse=True)

    def delete_session(self, session_id: str) -> bool:
        """Delete a session workspace. Returns True if it existed."""
        import shutil
        workspace = self.sessions_dir / session_id
        if workspace.is_dir():
            shutil.rmtree(workspace)
            return True
        return False
