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


def _synthesize_frontmatter(skill_dir: Path, body: str) -> str:
    """Prepend a minimal frontmatter block derived from the directory name.

    Called when SKILL.md exists but has no parseable frontmatter at all.
    The synthesized block is written back to disk so the skill is valid on the
    next load without any manual intervention.
    """
    import warnings

    dir_name = skill_dir.name
    # Use the first markdown heading as the description, if present.
    heading_match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
    description = heading_match.group(1).strip() if heading_match else dir_name

    # Use yaml.dump so values containing YAML special characters (`:`, `#`, …)
    # are automatically quoted rather than producing invalid YAML.
    fm_text = yaml.dump(
        {"name": dir_name, "description": description, "version": "0.1.0"},
        default_flow_style=False,
        allow_unicode=True,
    )
    synthesized = f"---\n{fm_text}---\n\n" + body
    warnings.warn(
        f"SKILL.md in '{dir_name}' had no frontmatter — "
        f"synthesized name='{dir_name}' from directory name and rewrote the file. "
        "Add a proper frontmatter block to suppress this warning.",
        stacklevel=4,
    )
    return synthesized


def _parse_skill(skill_dir: Path, skill_md: Path) -> SkillInfo:
    raw = skill_md.read_text(encoding="utf-8")
    text = _normalize_skill_md(raw)

    match = _FRONTMATTER_RE.match(text)
    if not match:
        # No frontmatter at all — synthesize one from the directory name so the
        # skill is still usable and appears in the registry / frontend.
        text = _synthesize_frontmatter(skill_dir, text)
        match = _FRONTMATTER_RE.match(text)

    # Rewrite the file on disk whenever the content changed (normalization or
    # synthesis) so future reads always see a clean, valid SKILL.md.
    if text != raw:
        skill_md.write_text(text, encoding="utf-8")

    fm_text = match.group(1)  # type: ignore[union-attr]
    try:
        fm = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError:
        # Invalid YAML in the frontmatter (e.g. unquoted colon in a value).
        # Fall back to line-by-line regex extraction so the skill still loads.
        import warnings
        warnings.warn(
            f"SKILL.md in '{skill_dir.name}' has invalid YAML frontmatter — "
            "loading with partial field extraction. Fix the frontmatter to suppress this.",
            stacklevel=2,
        )
        fm = _extract_frontmatter_fields(fm_text)

    # Fall back to directory name when 'name' is missing from the frontmatter.
    name: str = fm.get("name") or skill_dir.name
    if not fm.get("name"):
        import warnings
        warnings.warn(
            f"SKILL.md in '{skill_dir.name}' has no 'name' field — "
            f"using directory name '{name}'.",
            stacklevel=2,
        )

    description = str(fm.get("description", ""))
    if len(description) > 1024:
        description = description[:1021] + "..."

    return SkillInfo(
        path=skill_dir.resolve(),
        name=name,
        description=description,
        role_restriction=fm.get("role-restriction"),
        allowed_tools=_parse_allowed_tools(fm.get("allowed-tools")),
        version=str(fm.get("version", "0.1.0")),
        raw_frontmatter=fm,
    )
