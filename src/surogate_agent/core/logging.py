"""
Centralised logging for surogate-agent.

Log levels (low → high)
-----------------------
TRACE   (5)   — very verbose: every SSE event, every stream chunk, raw config
                details, individual field extraction.
DEBUG  (10)   — operational: skill loading, session lifecycle, backend
                selection, HTTP handler entry/exit.
INFO   (20)   — key lifecycle events: server start, agent created, user
                registered, skill created/deleted, chat request completed.
WARNING(30)   — recoverable issues: malformed SKILL.md, invalid YAML,
                fallback behaviour, failed login attempts, invalid tokens.
ERROR  (40)   — failures: unhandled exceptions in the chat stream,
                auth-table creation failure, fatal configuration errors.

Configuration
-------------
Call ``setup_logging(level)`` once at application startup (CLI main, API
server main), or set the ``SUROGATE_LOG_LEVEL`` environment variable to one
of the names above.  The default level is WARNING so production is quiet
unless explicitly configured.

Output format
-------------
Matches uvicorn's default formatter exactly::

    INFO:     agent ready: RoleGuardAgent(role='developer', ...)
    WARNING:  malformed SKILL.md in 'my-skill' ...
    ERROR:    unhandled exception in chat stream

The level prefix is colourised when writing to a TTY (green=INFO,
yellow=WARNING, red=ERROR, cyan=DEBUG, blue=TRACE).

Usage
-----
    from surogate_agent.core.logging import get_logger

    log = get_logger(__name__)

    log.info("agent ready: %r", agent)
    log.debug("skill sources: %s", skill_sources)
    log.trace("raw chunk keys: %s", list(chunk))   # type: ignore[attr-defined]
"""

from __future__ import annotations

import logging
import os
import sys
from copy import copy

# ---------------------------------------------------------------------------
# TRACE level — numeric value below DEBUG so it really is the noisiest tier
# ---------------------------------------------------------------------------

TRACE: int = 5
logging.addLevelName(TRACE, "TRACE")


def _trace(
    self: logging.Logger,
    message: object,
    *args: object,
    **kwargs: object,
) -> None:
    if self.isEnabledFor(TRACE):
        self._log(TRACE, message, args, **kwargs)  # type: ignore[arg-type]


logging.Logger.trace = _trace  # type: ignore[attr-defined]

# ---------------------------------------------------------------------------
# Formatter — matches uvicorn's ColourizedFormatter / DefaultFormatter
# ---------------------------------------------------------------------------

_LEVEL_COLORS = {
    TRACE:            "blue",
    logging.DEBUG:    "cyan",
    logging.INFO:     "green",
    logging.WARNING:  "yellow",
    logging.ERROR:    "red",
    logging.CRITICAL: "bright_red",
}


class _UvicornFormatter(logging.Formatter):
    """Replicates uvicorn's ``DefaultFormatter``.

    Format:  ``LEVELNAME:   message``
    The level name is padded with spaces after the colon so that messages
    from all levels start in the same column (``CRITICAL`` is the longest
    at 8 characters).  The level prefix is colourised when stderr is a TTY,
    using the same colours as uvicorn.
    """

    def __init__(self, use_colors: bool | None = None) -> None:
        # The format string is identical to uvicorn's.
        super().__init__(fmt="%(levelprefix)s %(message)s")
        if use_colors is None:
            self._use_colors = hasattr(sys.stderr, "isatty") and sys.stderr.isatty()
        else:
            self._use_colors = use_colors

    def _colorize(self, levelname: str, levelno: int) -> str:
        try:
            import click  # click is a transitive dep of typer, always present
            color = _LEVEL_COLORS.get(levelno)
            if color:
                return click.style(levelname, fg=color)
        except ImportError:
            pass
        return levelname

    def formatMessage(self, record: logging.LogRecord) -> str:
        rec = copy(record)
        levelname = rec.levelname
        # Pad so the message column is always aligned.
        # "CRITICAL" is 8 chars — the longest standard level name.
        sep = " " * (8 - len(levelname))
        if self._use_colors:
            levelname = self._colorize(levelname, rec.levelno)
        rec.__dict__["levelprefix"] = levelname + ":" + sep
        return super().formatMessage(rec)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

_ROOT = "surogate_agent"


def get_logger(name: str) -> logging.Logger:
    """Return a child logger scoped under the ``surogate_agent`` namespace.

    Pass ``__name__`` from the calling module::

        from surogate_agent.core.logging import get_logger
        log = get_logger(__name__)

    If *name* already starts with ``surogate_agent`` it is used as-is,
    otherwise it is prefixed with the root namespace.
    """
    if name.startswith(_ROOT):
        return logging.getLogger(name)
    return logging.getLogger(f"{_ROOT}.{name}")


def setup_logging(level: str | int | None = None) -> None:
    """Configure the ``surogate_agent`` root logger.

    Parameters
    ----------
    level:
        An integer log level or a level-name string (``"TRACE"``,
        ``"DEBUG"``, ``"INFO"``, ``"WARNING"``, ``"ERROR"``).
        Falls back to the ``SUROGATE_LOG_LEVEL`` environment variable,
        then ``"WARNING"``.

    When *level* is ``None`` (the default), this function acts as a
    "configure-if-not-already-configured" guard: if a handler has already
    been added (e.g. by the CLI entry point), the call is a no-op so that
    an explicitly requested level is never silently reset to the default.
    Pass an explicit level string or integer to always apply that level.
    """
    root_log = logging.getLogger(_ROOT)

    if level is None:
        # No explicit level — only configure if nothing is set up yet.
        # This lets the lifespan / factory call setup_logging() as a
        # safety net for direct-uvicorn usage without stomping over a
        # --log-level flag that was already applied by the CLI or server
        # entry point.
        if root_log.handlers:
            return
        env = os.environ.get("SUROGATE_LOG_LEVEL", "").strip().upper()
        level = env or "WARNING"

    if isinstance(level, str):
        # getLevelName returns an int for known names (including "TRACE"
        # because we registered it above).
        numeric = logging.getLevelName(level)
        if not isinstance(numeric, int):
            numeric = logging.WARNING
        level = numeric

    root_log.setLevel(level)

    if not root_log.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(level)
        handler.setFormatter(_UvicornFormatter())
        root_log.addHandler(handler)
    else:
        for handler in root_log.handlers:
            handler.setLevel(level)
