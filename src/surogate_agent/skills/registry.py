"""
SkillRegistry — central in-memory registry of loaded skills.

The registry:
1. Deduplicates by skill *name* (last-write-wins, so user skills can shadow
   built-in skills with the same name).
2. Filters by role on ``paths_for_role()`` so the agent only receives paths it
   is allowed to use.
3. Supports hot-registration of a single skill directory at runtime (useful for
   the meta-skill workflow: create → register → use immediately).
"""

from __future__ import annotations

from pathlib import Path

from surogate_agent.core.logging import get_logger
from surogate_agent.core.roles import Role
from surogate_agent.skills.loader import SkillInfo, SkillLoader

log = get_logger(__name__)


class SkillRegistry:
    """Manages a collection of SkillInfo objects.

    Usage
    -----
    >>> registry = SkillRegistry()
    >>> registry.scan(Path("./skills/builtin"))
    >>> registry.scan(Path("./skills"))           # user skills (may shadow)
    >>> paths = registry.paths_for_role(Role.DEVELOPER)
    """

    def __init__(self) -> None:
        # name → SkillInfo; insertion order preserved (Python 3.7+)
        self._skills: dict[str, SkillInfo] = {}

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def scan(self, root: Path) -> list[SkillInfo]:
        """Scan *root* for skill directories and register them.

        Returns the list of newly registered ``SkillInfo`` objects.
        """
        log.debug("registry scan: %s", root)
        loader = SkillLoader(root)
        found = loader.load()
        for info in found:
            shadowed = info.name in self._skills
            self._skills[info.name] = info
            if shadowed:
                log.debug("skill '%s' overrides a previously registered entry", info.name)
            else:
                log.debug("registered skill '%s' (role=%s)", info.name, info.role_restriction or "any")
        log.debug("registry scan complete: %d skill(s) found in %s", len(found), root)
        return found

    def register(self, skill_dir: Path) -> SkillInfo:
        """Register a single skill directory.

        Raises ``ValueError`` if the directory lacks a valid ``SKILL.md``.
        """
        from surogate_agent.skills.loader import _parse_skill
        skill_md = Path(skill_dir) / "SKILL.md"
        if not skill_md.exists():
            raise ValueError(f"No SKILL.md found in {skill_dir}")
        info = _parse_skill(Path(skill_dir), skill_md)
        self._skills[info.name] = info
        log.debug("hot-registered skill '%s' from %s", info.name, skill_dir)
        return info

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def paths_for_role(self, role: Role) -> list[Path]:
        """Return skill directory paths accessible to *role*.

        Developer role receives all skills.
        User role receives only skills without a ``role-restriction`` of
        ``"developer"``.
        """
        paths: list[Path] = []
        for info in self._skills.values():
            if role == Role.DEVELOPER:
                paths.append(info.path)
                log.trace("role=%s — including '%s'", role.value, info.name)  # type: ignore[attr-defined]
            elif not info.is_developer_only:
                paths.append(info.path)
                log.trace("role=%s — including '%s'", role.value, info.name)  # type: ignore[attr-defined]
            else:
                log.trace("role=%s — excluding developer-only skill '%s'", role.value, info.name)  # type: ignore[attr-defined]
        log.debug("paths_for_role(%s): %d skill(s)", role.value, len(paths))
        return paths

    def all_skills(self) -> list[SkillInfo]:
        return list(self._skills.values())

    def get(self, name: str) -> SkillInfo | None:
        return self._skills.get(name)

    def __len__(self) -> int:
        return len(self._skills)

    def __repr__(self) -> str:
        names = list(self._skills)
        return f"SkillRegistry({names})"
