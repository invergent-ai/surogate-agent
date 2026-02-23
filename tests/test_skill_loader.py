"""Tests for SkillLoader and SkillRegistry — no LLM calls required."""

import textwrap
import pytest
from pathlib import Path

from surogate_agent.skills.loader import SkillLoader, SkillInfo
from surogate_agent.skills.registry import SkillRegistry
from surogate_agent.core.roles import Role


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def skills_root(tmp_path: Path) -> Path:
    """Create a temp skills directory with two sample skills."""

    # Skill 1 — available to all roles
    s1 = tmp_path / "jira-summariser"
    s1.mkdir()
    (s1 / "SKILL.md").write_text(textwrap.dedent("""\
        ---
        name: jira-summariser
        description: Summarises Jira tickets into bullet points.
        version: 1.0.0
        ---
        # Jira Summariser
        When the user provides a Jira ticket, summarise it.
    """))

    # Skill 2 — developer-only
    s2 = tmp_path / "skill-author"
    s2.mkdir()
    (s2 / "SKILL.md").write_text(textwrap.dedent("""\
        ---
        name: skill-author
        description: Helps developers write new skills.
        role-restriction: developer
        allowed-tools:
          - write_file
          - edit_file
        ---
        # Skill Author
        Help the developer scaffold a new skill.
    """))

    # Non-skill directory (no SKILL.md) — should be ignored
    (tmp_path / "not-a-skill").mkdir()

    return tmp_path


@pytest.fixture()
def loader(skills_root: Path) -> SkillLoader:
    return SkillLoader(skills_root)


# ---------------------------------------------------------------------------
# SkillLoader tests
# ---------------------------------------------------------------------------

class TestSkillLoader:
    def test_finds_two_skills(self, loader: SkillLoader):
        skills = loader.load()
        assert len(skills) == 2

    def test_ignores_non_skill_dirs(self, loader: SkillLoader):
        names = {s.name for s in loader.load()}
        assert "not-a-skill" not in names

    def test_parses_name_and_description(self, loader: SkillLoader):
        skills = {s.name: s for s in loader.load()}
        s = skills["jira-summariser"]
        assert s.description.startswith("Summarises")
        assert s.version == "1.0.0"

    def test_parses_role_restriction(self, loader: SkillLoader):
        skills = {s.name: s for s in loader.load()}
        assert skills["skill-author"].is_developer_only
        assert not skills["jira-summariser"].is_developer_only

    def test_parses_allowed_tools(self, loader: SkillLoader):
        skills = {s.name: s for s in loader.load()}
        assert "write_file" in skills["skill-author"].allowed_tools

    def test_allowed_tools_is_always_a_list(self, loader: SkillLoader):
        """allowed_tools must be list[str] regardless of YAML source format."""
        for s in loader.load():
            assert isinstance(s.allowed_tools, list)

    def test_parses_allowed_tools_string_format(self, tmp_path: Path):
        """Space-delimited string is the canonical SKILL.md format."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(textwrap.dedent("""\
            ---
            name: my-skill
            description: A skill that needs execute.
            allowed-tools: read_file execute write_file
            ---
            # My Skill
        """))
        loader = SkillLoader(tmp_path)
        skills = {s.name: s for s in loader.load()}
        assert "execute" in skills["my-skill"].allowed_tools
        assert "read_file" in skills["my-skill"].allowed_tools
        assert isinstance(skills["my-skill"].allowed_tools, list)

    def test_path_is_absolute(self, loader: SkillLoader, skills_root: Path):
        for s in loader.load():
            assert s.path.is_absolute()

    def test_missing_name_raises(self, tmp_path: Path):
        bad = tmp_path / "bad-skill"
        bad.mkdir()
        (bad / "SKILL.md").write_text("---\ndescription: oops\n---\n# Bad\n")
        loader = SkillLoader(tmp_path)
        skills = loader.load()   # warning is emitted, skill is skipped
        assert not any(s.name == "bad-skill" for s in skills)

    def test_loads_skill_with_leading_blank_line(self, tmp_path: Path):
        """A blank line before --- should be stripped and the skill should load."""
        skill_dir = tmp_path / "blank-leader"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "\n---\nname: blank-leader\ndescription: Leading blank.\n---\n# Body\n"
        )
        loader = SkillLoader(tmp_path)
        skills = {s.name: s for s in loader.load()}
        assert "blank-leader" in skills

    def test_loads_skill_with_heading_before_frontmatter(self, tmp_path: Path):
        """A markdown heading written before --- should be stripped and skill loaded."""
        skill_dir = tmp_path / "heading-first"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "# heading-first\n"
            "---\n"
            "name: heading-first\n"
            "description: Heading came first.\n"
            "version: 0.1.0\n"
            "---\n"
            "\n# Body\n"
        )
        loader = SkillLoader(tmp_path)
        skills = {s.name: s for s in loader.load()}
        assert "heading-first" in skills

    def test_loads_skill_without_trailing_newline(self, tmp_path: Path):
        """Missing trailing newline after closing --- should not prevent loading."""
        skill_dir = tmp_path / "no-newline"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: no-newline\ndescription: No trailing newline.\n---"
        )
        loader = SkillLoader(tmp_path)
        skills = {s.name: s for s in loader.load()}
        assert "no-newline" in skills

    def test_missing_frontmatter_raises(self, tmp_path: Path):
        bad = tmp_path / "no-fm"
        bad.mkdir()
        (bad / "SKILL.md").write_text("# No frontmatter here\n")
        loader = SkillLoader(tmp_path)
        skills = loader.load()
        assert len(skills) == 0

    def test_nonexistent_root_returns_empty(self, tmp_path: Path):
        loader = SkillLoader(tmp_path / "does-not-exist")
        assert loader.load() == []


# ---------------------------------------------------------------------------
# SkillRegistry tests
# ---------------------------------------------------------------------------

class TestSkillRegistry:
    def test_scan_populates_registry(self, skills_root: Path):
        reg = SkillRegistry()
        reg.scan(skills_root)
        assert len(reg) == 2

    def test_paths_for_user_excludes_developer_skill(self, skills_root: Path):
        reg = SkillRegistry()
        reg.scan(skills_root)
        paths = reg.paths_for_role(Role.USER)
        names = [p.name for p in paths]
        assert "jira-summariser" in names
        assert "skill-author" not in names

    def test_paths_for_developer_includes_all(self, skills_root: Path):
        reg = SkillRegistry()
        reg.scan(skills_root)
        paths = reg.paths_for_role(Role.DEVELOPER)
        assert len(paths) == 2

    def test_register_single_skill(self, tmp_path: Path):
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(textwrap.dedent("""\
            ---
            name: my-skill
            description: A dynamically registered skill.
            ---
            # My Skill
        """))
        reg = SkillRegistry()
        info = reg.register(skill_dir)
        assert info.name == "my-skill"
        assert len(reg) == 1

    def test_register_missing_skill_md_raises(self, tmp_path: Path):
        skill_dir = tmp_path / "empty"
        skill_dir.mkdir()
        reg = SkillRegistry()
        with pytest.raises(ValueError, match="No SKILL.md"):
            reg.register(skill_dir)

    def test_user_skill_shadows_builtin(self, tmp_path: Path):
        # Simulate a user skill overriding a builtin with the same name
        builtin_dir = tmp_path / "builtin"
        builtin_dir.mkdir()
        s = builtin_dir / "shared-skill"
        s.mkdir()
        (s / "SKILL.md").write_text(
            "---\nname: shared-skill\ndescription: Builtin version.\n---\n# V1\n"
        )

        user_dir = tmp_path / "user"
        user_dir.mkdir()
        s2 = user_dir / "shared-skill"
        s2.mkdir()
        (s2 / "SKILL.md").write_text(
            "---\nname: shared-skill\ndescription: User version.\n---\n# V2\n"
        )

        reg = SkillRegistry()
        reg.scan(builtin_dir)
        reg.scan(user_dir)       # user scan wins
        assert len(reg) == 1
        assert reg.get("shared-skill").description == "User version."

    def test_builtin_meta_skill_is_developer_only(self):
        """The bundled meta-skill must have role-restriction: developer."""
        from surogate_agent.core.config import _DEFAULT_SKILLS_DIR
        reg = SkillRegistry()
        reg.scan(_DEFAULT_SKILLS_DIR)
        meta = reg.get("skill-developer")
        assert meta is not None, "Built-in meta-skill not found"
        assert meta.is_developer_only
