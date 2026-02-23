"""
SkillLoader — discovers and parses deepagents-compatible skill directories.

A *skill directory* is any directory that contains a ``SKILL.md`` file.
The SKILL.md must start with a YAML frontmatter block (delimited by ``---``).

Minimal valid SKILL.md
-----------------------
---
name: my-skill
description: Does something useful (max ~1024 chars)
---

The rest of the file is the skill body — markdown instructions the agent
reads when the skill is activated.

Optional frontmatter fields
----------------------------
role-restriction : "developer" | "user"
    If set, the skill is only loaded for agents with a matching role.
    Omit (or set to null) to load for all roles.
allowed-tools : list[str]
    Explicit tool whitelist forwarded to deepagents.
version : str
    Semver string for the skill.  Informational only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

# Matches YAML front-matter between two --- delimiters.
# Closing --- may be at end-of-file (no trailing newline required).
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", re.DOTALL)
_SKILL_FILENAME = "SKILL.md"


def _parse_allowed_tools(raw: object) -> list[str]:
    """Normalise the ``allowed-tools`` frontmatter value to a list of strings.

    The canonical format is a space-delimited string
    (``allowed-tools: read_file write_file execute``).  YAML lists are also
    accepted for backwards compatibility.  Any other value returns an empty list.
    """
    if isinstance(raw, str):
        return raw.split()
    if isinstance(raw, list):
        return [str(t) for t in raw]
    return []


@dataclass
class SkillInfo:
    """Parsed metadata for a single skill directory."""

    path: Path                          # Absolute path to skill directory
    name: str
    description: str
    role_restriction: Optional[str] = None   # "developer", "user", or None (all)
    allowed_tools: list[str] = field(default_factory=list)
    version: str = "0.1.0"
    raw_frontmatter: dict = field(default_factory=dict)

    @property
    def is_developer_only(self) -> bool:
        return self.role_restriction == "developer"

    @property
    def helper_files(self) -> list[Path]:
        """All files in the skill directory except SKILL.md, sorted by name.

        Both developer and user roles can place arbitrary helper files here
        (templates, prompts, schemas, examples, …).  The agent can reference
        them via ``read_file`` when the skill is active.
        """
        if not self.path.is_dir():
            return []
        return sorted(
            f for f in self.path.iterdir()
            if f.is_file() and f.name != _SKILL_FILENAME
        )


class SkillLoader:
    """Scans a root directory for skill sub-directories and parses them.

    Parameters
    ----------
    root:
        A directory that may contain one or more skill sub-directories.

    Usage
    -----
    >>> loader = SkillLoader(Path("./skills"))
    >>> skills = loader.load()
    >>> for s in skills:
    ...     print(s.name, s.path)
    """

    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()

    def load(self) -> list[SkillInfo]:
        """Return all valid skills found under ``self.root``."""
        skills: list[SkillInfo] = []
        if not self.root.is_dir():
            return skills

        for candidate in sorted(self.root.iterdir()):
            if not candidate.is_dir():
                continue
            skill_md = candidate / _SKILL_FILENAME
            if not skill_md.exists():
                continue
            try:
                info = _parse_skill(candidate, skill_md)
                skills.append(info)
            except Exception as exc:  # noqa: BLE001
                import warnings
                warnings.warn(
                    f"Could not load skill at {candidate}: {exc}",
                    stacklevel=2,
                )

        return skills


# ---------------------------------------------------------------------------
# Internal parsing helpers
# ---------------------------------------------------------------------------

def _normalize_skill_md(raw: str) -> str:
    """Return a normalized form of a SKILL.md file that the regex can always parse.

    LLMs commonly produce these malformed variants:
    - UTF-8 BOM at the start
    - One or more blank lines / a markdown heading before the opening ``---``
    - Indented ``---`` (spaces/tabs before the delimiter)
    - Missing trailing newline after the closing ``---``

    When frontmatter is present but not at the top (e.g. a ``# Heading`` was
    written first), the block is lifted to position 0.  Any content that
    appeared before the frontmatter (typically a misplaced heading) is dropped
    because SKILL.md's preamble is the frontmatter itself — there is nothing
    meaningful before it.
    """
    # Strip BOM then any leading whitespace/blank lines
    text = raw.lstrip("\ufeff").lstrip()
    # Guarantee a trailing newline so the closing --- delimiter always matches
    if not text.endswith("\n"):
        text += "\n"

    # Fast path: already starts correctly
    if text.startswith("---"):
        return text

    # Recovery: frontmatter exists but is not at position 0.
    # Find the first --- block and lift it to the top.
    fm_match = re.search(r"(?:^|\n)(---\s*\n.*?\n---\s*(?:\n|$))", text, re.DOTALL)
    if fm_match:
        frontmatter = fm_match.group(1)
        body_after = text[fm_match.end():]
        text = frontmatter + body_after

    return text


def _parse_skill(skill_dir: Path, skill_md: Path) -> SkillInfo:
    raw = skill_md.read_text(encoding="utf-8")
    text = _normalize_skill_md(raw)

    # Silently fix the file on disk when normalization was needed so future
    # reads (and the agent's own read_file verification step) see clean output.
    if text != raw:
        skill_md.write_text(text, encoding="utf-8")

    match = _FRONTMATTER_RE.match(text)
    if not match:
        first_line = text.split("\n")[0][:60]
        raise ValueError(
            f"SKILL.md at {skill_md} has no valid YAML frontmatter "
            f"(first line: {first_line!r}). "
            "File must start with --- on line 1."
        )

    raw = yaml.safe_load(match.group(1)) or {}

    name = raw.get("name")
    if not name:
        raise ValueError(f"SKILL.md at {skill_md} is missing 'name' in frontmatter")

    description = raw.get("description", "")
    if len(description) > 1024:
        description = description[:1021] + "..."

    return SkillInfo(
        path=skill_dir.resolve(),
        name=str(name),
        description=description,
        role_restriction=raw.get("role-restriction"),
        allowed_tools=_parse_allowed_tools(raw.get("allowed-tools")),
        version=str(raw.get("version", "0.1.0")),
        raw_frontmatter=raw,
    )
