"""
PermissionGuardMixin — enforce per-path read/write rules on deepagents backends.

Wraps FilesystemBackend and LocalShellBackend so that every file operation is
checked against declared allowed paths before being delegated to the real
backend.  Used by create_agent() to enforce role-based file access at the
backend level, complementing the system-prompt instructions.

Access levels
-------------
rw_paths  — directories the agent may read AND write/edit/create files in.
ro_paths  — directories the agent may read but NOT modify.
(anything else) — denied for both read and write.

Note on execute()
-----------------
LocalShellBackend.execute() runs arbitrary shell commands (e.g. ``rm``) and
cannot be path-sandboxed at the Python method level.  The system prompt and
developer-consent gate (allow_execute=True) are the applicable controls there.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from surogate_agent.core.logging import get_logger

log = get_logger(__name__)


class PermissionGuardMixin:
    """Mixin that enforces per-path read/write rules on deepagents backends.

    Must appear before the deepagents backend class in the MRO so that its
    method overrides fire first.  Use the factory functions below rather than
    subclassing directly — they build the correct MRO with a lazy import::

        backend = make_guarded_filesystem_backend(
            root_dir=Path.cwd(),
            virtual_mode=False,
            rw_paths=[skills_dir, workspace_dir],
            ro_paths=[builtin_dir, sessions_dir],
        )

    Parameters (keyword-only, consumed by this mixin)
    --------------------------------------------------
    rw_paths : list[Path]
        Directories the agent may read AND write.
    ro_paths : list[Path]
        Directories the agent may read but NOT write.
    """

    def __init__(
        self,
        *args: Any,
        rw_paths: list[Path],
        ro_paths: list[Path],
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        # Capture root_dir so relative paths are resolved the same way the
        # backend resolves them (not against Python's CWD, which may differ
        # from the configured data directory, e.g. in Docker /app vs /data).
        self._root_dir: Path = Path(kwargs.get("root_dir", Path.cwd())).resolve()
        self._rw_paths: list[Path] = [p.resolve() for p in rw_paths]
        self._ro_paths: list[Path] = [p.resolve() for p in ro_paths]
        log.debug(
            "PermissionGuardMixin active: root=%s rw=%s ro=%s",
            self._root_dir,
            [str(p) for p in self._rw_paths],
            [str(p) for p in self._ro_paths],
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _permission_for(self, path: str | Path) -> str:
        """Return ``'rw'``, ``'ro'``, or ``'deny'`` for *path*."""
        p = Path(path)
        # Resolve relative paths against root_dir (same as the backend does),
        # NOT against Python's CWD.  This is critical in deployments where the
        # process CWD differs from the configured data directory (e.g. Docker
        # where CWD=/app but data lives under /data/).
        resolved = (self._root_dir / p).resolve() if not p.is_absolute() else p.resolve()
        for base in self._rw_paths:
            try:
                resolved.relative_to(base)
                return "rw"
            except ValueError:
                pass
        for base in self._ro_paths:
            try:
                resolved.relative_to(base)
                return "ro"
            except ValueError:
                pass
        return "deny"

    def _read_error(self, path: str) -> str | None:
        """Return an error string if reading *path* is denied, else ``None``."""
        if self._permission_for(path) == "deny":
            log.warning("backend read blocked: %s", path)
            return (
                f"Error: Access denied — '{path}' is outside all allowed paths. "
                "Only paths within the designated skill, workspace, or session "
                "directories are accessible."
            )
        return None

    def _write_error(self, path: str) -> str | None:
        """Return an error string if writing *path* is denied, else ``None``."""
        perm = self._permission_for(path)
        if perm == "ro":
            log.warning("backend write blocked (read-only path): %s", path)
            return (
                f"Error: Write access denied — '{path}' is read-only in this "
                "context. Built-in skills and session files must not be modified."
            )
        if perm == "deny":
            log.warning("backend write blocked (out-of-bounds): %s", path)
            return (
                f"Error: Write access denied — '{path}' is outside all allowed "
                "paths. Only the skill definitions directory and the development "
                "workspace may be written to."
            )
        return None

    # ------------------------------------------------------------------
    # Write operations — intercepted before reaching the real backend
    # ------------------------------------------------------------------

    def write(self, file_path: str, content: str):  # type: ignore[override]
        if err := self._write_error(file_path):
            from deepagents.backends.protocol import WriteResult
            return WriteResult(error=err)
        return super().write(file_path, content)  # type: ignore[misc]

    def edit(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ):  # type: ignore[override]
        if err := self._write_error(file_path):
            from deepagents.backends.protocol import EditResult
            return EditResult(error=err)
        return super().edit(file_path, old_string, new_string, replace_all)  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Read operations — intercepted before reaching the real backend
    # ------------------------------------------------------------------

    def read(self, file_path: str, offset: int = 0, limit: int = 2000) -> str:  # type: ignore[override]
        if err := self._read_error(file_path):
            return err
        return super().read(file_path, offset, limit)  # type: ignore[misc]

    def ls_info(self, path: str):  # type: ignore[override]
        if self._read_error(path):
            return []
        return super().ls_info(path)  # type: ignore[misc]

    def glob_info(self, pattern: str, path: str = "/"):  # type: ignore[override]
        if path and self._read_error(path):
            return []
        return super().glob_info(pattern, path)  # type: ignore[misc]

    def grep_raw(
        self,
        pattern: str,
        path: str | None = None,
        glob: str | None = None,
    ):  # type: ignore[override]
        if path and self._read_error(path):
            return []
        return super().grep_raw(pattern, path, glob)  # type: ignore[misc]


# ------------------------------------------------------------------
# Factory functions — build the correct MRO with a lazy deepagents import
# ------------------------------------------------------------------

def make_guarded_filesystem_backend(
    rw_paths: list[Path],
    ro_paths: list[Path],
    **kwargs: Any,
):
    """Return a ``FilesystemBackend`` instance guarded by *rw_paths*/*ro_paths*."""
    from deepagents.backends.filesystem import FilesystemBackend

    class _GuardedFilesystemBackend(PermissionGuardMixin, FilesystemBackend):
        pass

    return _GuardedFilesystemBackend(rw_paths=rw_paths, ro_paths=ro_paths, **kwargs)


def make_guarded_local_shell_backend(
    rw_paths: list[Path],
    ro_paths: list[Path],
    **kwargs: Any,
):
    """Return a ``LocalShellBackend`` instance guarded by *rw_paths*/*ro_paths*.

    Note: ``execute()`` is not path-sandboxed — see module docstring.
    """
    from deepagents.backends.local_shell import LocalShellBackend

    class _GuardedLocalShellBackend(PermissionGuardMixin, LocalShellBackend):
        pass

    return _GuardedLocalShellBackend(rw_paths=rw_paths, ro_paths=ro_paths, **kwargs)
