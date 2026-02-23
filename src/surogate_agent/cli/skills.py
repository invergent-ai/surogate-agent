"""
Skills management subcommands.

  surogate-agent skills list                    List all discovered skills
  surogate-agent skills show <name>             Print SKILL.md + helper files
  surogate-agent skills validate <path>         Validate a skill directory
  surogate-agent skills new <name>              Scaffold a blank skill interactively
  surogate-agent skills delete <name>           Delete a skill directory
  surogate-agent skills files list <name>       List helper files for a skill
  surogate-agent skills files add <name> <file> Create/overwrite a helper file
  surogate-agent skills files show <name> <file>Print a helper file's content
  surogate-agent skills files remove <name> <file> Delete a helper file
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.syntax import Syntax
from rich.table import Table
from rich import box

from surogate_agent.core.config import AgentConfig, _DEFAULT_SKILLS_DIR
from surogate_agent.core.roles import Role
from surogate_agent.skills.loader import SkillInfo, _parse_skill
from surogate_agent.skills.registry import SkillRegistry

console = Console()

app = typer.Typer(
    help="Manage agent skills.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

files_app = typer.Typer(
    help="Manage helper files inside a skill directory.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
app.add_typer(files_app, name="files")

# ---------------------------------------------------------------------------
# Shared option
# ---------------------------------------------------------------------------

_SkillsDirOpt = Annotated[
    Path,
    typer.Option(
        "--skills-dir", "-s",
        help="Root directory to scan for user skills (default: ./skills)",
    ),
]


def _build_registry(skills_dir: Path) -> SkillRegistry:
    reg = SkillRegistry()
    reg.scan(_DEFAULT_SKILLS_DIR)       # built-in skills
    if skills_dir.exists():
        reg.scan(skills_dir)            # user skills
    return reg


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------

@app.command("list")
def list_skills(
    skills_dir: _SkillsDirOpt = Path("./skills"),
    role: Annotated[
        str,
        typer.Option("--role", "-r", help="Filter by role: developer | user | all"),
    ] = "all",
) -> None:
    """List all discovered skills."""
    reg = _build_registry(skills_dir)

    filter_role: Optional[Role] = None
    if role == "developer":
        filter_role = Role.DEVELOPER
    elif role == "user":
        filter_role = Role.USER

    skills = reg.all_skills()
    if filter_role is not None:
        paths = {str(p) for p in reg.paths_for_role(filter_role)}
        skills = [s for s in skills if str(s.path) in paths]

    if not skills:
        console.print("[dim]No skills found.[/dim]")
        raise typer.Exit()

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan")
    table.add_column("Name", style="bold")
    table.add_column("Version", justify="center")
    table.add_column("Role", justify="center")
    table.add_column("Description")
    table.add_column("Path", style="dim")

    for s in sorted(skills, key=lambda x: x.name):
        role_label = s.role_restriction or "all"
        role_style = "yellow" if s.is_developer_only else "green"
        table.add_row(
            s.name,
            s.version,
            f"[{role_style}]{role_label}[/{role_style}]",
            s.description[:60] + ("…" if len(s.description) > 60 else ""),
            str(s.path),
        )

    console.print(table)


# ---------------------------------------------------------------------------
# show
# ---------------------------------------------------------------------------

@app.command("show")
def show_skill(
    name: Annotated[str, typer.Argument(help="Skill name (kebab-case)")],
    skills_dir: _SkillsDirOpt = Path("./skills"),
) -> None:
    """Print the SKILL.md and list any helper files for a skill."""
    reg = _build_registry(skills_dir)
    info = reg.get(name)
    if info is None:
        console.print(f"[bold red]Skill '{name}' not found.[/bold red]")
        raise typer.Exit(1)

    skill_md = info.path / "SKILL.md"
    content = skill_md.read_text(encoding="utf-8")
    console.print(
        Panel(
            content,
            title=f"[bold cyan]{name}[/bold cyan]  [dim]{info.path}[/dim]",
            border_style="cyan",
        )
    )

    helpers = info.helper_files
    if helpers:
        table = Table(box=box.SIMPLE, show_header=True, header_style="bold")
        table.add_column("Helper file")
        table.add_column("Size", justify="right", style="dim")
        for f in helpers:
            table.add_row(f.name, f"{f.stat().st_size:,} bytes")
        console.print(table)
        console.print(
            f"[dim]Use [bold]surogate-agent skills files show {name} <file>[/bold] "
            "to view a file.[/dim]"
        )
    else:
        console.print("[dim]No helper files. Add them with: "
                      f"surogate-agent skills files add {name} <filename>[/dim]")


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------

@app.command("validate")
def validate_skill(
    path: Annotated[Path, typer.Argument(help="Path to skill directory")],
) -> None:
    """Validate a skill directory (checks SKILL.md frontmatter)."""
    path = path.resolve()
    skill_md = path / "SKILL.md"

    errors: list[str] = []
    warnings: list[str] = []

    if not path.is_dir():
        console.print(f"[bold red]Not a directory:[/bold red] {path}")
        raise typer.Exit(1)

    if not skill_md.exists():
        errors.append("Missing SKILL.md")
    else:
        try:
            info = _parse_skill(path, skill_md)
        except Exception as exc:
            errors.append(str(exc))
            info = None

        if info is not None:
            if not info.name:
                errors.append("'name' is empty")
            elif "-" not in info.name and "_" in info.name:
                warnings.append(f"name '{info.name}' uses underscores; prefer kebab-case")
            if not info.description:
                warnings.append("'description' is empty")
            elif len(info.description) > 1024:
                errors.append(f"'description' exceeds 1024 chars ({len(info.description)})")
            if info.role_restriction and info.role_restriction not in ("developer", "user"):
                errors.append(
                    f"unknown role-restriction '{info.role_restriction}'; "
                    "use 'developer', 'user', or omit"
                )

    if errors:
        for e in errors:
            console.print(f"[bold red]  ✗  {e}[/bold red]")
        console.print(f"\n[bold red]Validation FAILED[/bold red] — {path.name}")
        raise typer.Exit(1)

    for w in warnings:
        console.print(f"[yellow]  ⚠  {w}[/yellow]")

    console.print(f"[bold green]  ✓  {path.name} is valid[/bold green]")


# ---------------------------------------------------------------------------
# new
# ---------------------------------------------------------------------------

@app.command("new")
def new_skill(
    name: Annotated[
        str,
        typer.Argument(help="Skill name in kebab-case, e.g. jira-summariser"),
    ] = "",
    skills_dir: _SkillsDirOpt = Path("./skills"),
) -> None:
    """Scaffold a blank skill directory interactively.

    Useful when you prefer to write the SKILL.md yourself rather than asking
    the agent to do it.  For the full conversational workflow, use [bold]chat[/bold].
    """
    if not name:
        name = Prompt.ask("Skill name (kebab-case)")

    name = name.strip().lower().replace(" ", "-").replace("_", "-")
    skill_dir = skills_dir / name

    if skill_dir.exists():
        console.print(f"[bold red]Directory already exists:[/bold red] {skill_dir}")
        raise typer.Exit(1)

    description = Prompt.ask("One-line description")
    role_raw = Prompt.ask(
        "Available to",
        choices=["all", "developer"],
        default="all",
    )
    role_restriction = None if role_raw == "all" else role_raw

    skill_dir.mkdir(parents=True)
    _write_skill_md(skill_dir, name, description, role_restriction)

    # Offer to scaffold common helper files
    created_helpers: list[str] = []
    if Confirm.ask("Add helper files now?", default=False):
        console.print(
            "[dim]Enter one filename per line (e.g. prompt.md, schema.json). "
            "Empty line to finish.[/dim]"
        )
        while True:
            fname = Prompt.ask("  Filename", default="").strip()
            if not fname:
                break
            fpath = skill_dir / fname
            fpath.write_text(
                _helper_template(fname, name), encoding="utf-8"
            )
            created_helpers.append(fname)
            console.print(f"  [green]created[/green] {fname}")

    files_summary = (
        "\n" + "\n".join(f"  {skill_dir / f}" for f in created_helpers)
        if created_helpers else ""
    )
    console.print(
        Panel.fit(
            f"[bold green]Skill created:[/bold green] {skill_dir}\n"
            f"  {skill_dir / 'SKILL.md'}{files_summary}\n\n"
            "[dim]Add more helper files any time with:\n"
            f"  surogate-agent skills files add {name} <filename>[/dim]",
            border_style="green",
        )
    )


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------

@app.command("delete")
def delete_skill(
    name: Annotated[str, typer.Argument(help="Skill name to delete")],
    skills_dir: _SkillsDirOpt = Path("./skills"),
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Skip confirmation prompt"),
    ] = False,
) -> None:
    """Delete a skill directory (only user skills; built-ins are protected)."""
    # Only allow deletion from user skills dir, never from built-ins.
    skill_dir = (skills_dir / name).resolve()
    builtin = _DEFAULT_SKILLS_DIR.resolve()

    if str(skill_dir).startswith(str(builtin)):
        console.print("[bold red]Cannot delete a built-in skill.[/bold red]")
        raise typer.Exit(1)

    if not skill_dir.exists():
        console.print(f"[bold red]Skill directory not found:[/bold red] {skill_dir}")
        raise typer.Exit(1)

    if not force:
        confirmed = Confirm.ask(
            f"[bold red]Delete '{name}'[/bold red] at {skill_dir}?",
            default=False,
        )
        if not confirmed:
            console.print("[dim]Aborted.[/dim]")
            raise typer.Exit()

    shutil.rmtree(skill_dir)
    console.print(f"[bold green]Deleted:[/bold green] {skill_dir}")


# ---------------------------------------------------------------------------
# files sub-app  (surogate-agent skills files ...)
# ---------------------------------------------------------------------------

_FilesSkillArg = Annotated[str, typer.Argument(help="Skill name")]
_FilesFileArg  = Annotated[str, typer.Argument(help="Helper filename")]


def _resolve_skill(name: str, skills_dir: Path) -> "SkillInfo":
    reg = _build_registry(skills_dir)
    info = reg.get(name)
    if info is None:
        console.print(f"[bold red]Skill '{name}' not found.[/bold red]")
        raise typer.Exit(1)
    return info


@files_app.command("list")
def files_list(
    name: _FilesSkillArg,
    skills_dir: _SkillsDirOpt = Path("./skills"),
) -> None:
    """List all helper files inside a skill directory."""
    info = _resolve_skill(name, skills_dir)
    helpers = info.helper_files
    if not helpers:
        console.print(f"[dim]No helper files in '{name}'.[/dim]")
        raise typer.Exit()

    table = Table(box=box.SIMPLE, show_header=True, header_style="bold cyan")
    table.add_column("File")
    table.add_column("Size", justify="right", style="dim")
    table.add_column("Path", style="dim")
    for f in helpers:
        table.add_row(f.name, f"{f.stat().st_size:,} bytes", str(f))
    console.print(table)


@files_app.command("show")
def files_show(
    name: _FilesSkillArg,
    filename: _FilesFileArg,
    skills_dir: _SkillsDirOpt = Path("./skills"),
) -> None:
    """Print the contents of a helper file."""
    info = _resolve_skill(name, skills_dir)
    fpath = info.path / filename
    if not fpath.exists():
        console.print(f"[bold red]File '{filename}' not found in skill '{name}'.[/bold red]")
        raise typer.Exit(1)

    content = fpath.read_text(encoding="utf-8")
    lexer = _guess_lexer(filename)
    console.print(
        Panel(
            Syntax(content, lexer, theme="monokai", line_numbers=True),
            title=f"[bold cyan]{name}[/bold cyan] / [bold]{filename}[/bold]",
            border_style="cyan",
        )
    )


@files_app.command("add")
def files_add(
    name: _FilesSkillArg,
    filename: _FilesFileArg,
    skills_dir: _SkillsDirOpt = Path("./skills"),
    content: Annotated[
        str,
        typer.Option("--content", "-c", help="File content (reads stdin if omitted)"),
    ] = "",
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Overwrite if the file already exists"),
    ] = False,
) -> None:
    """Create or update a helper file inside a skill.

    Content is read from [bold]--content[/bold] or piped via stdin:

    [dim]  echo 'summarise in 3 bullets' | surogate-agent skills files add my-skill prompt.md[/dim]

    Available to both developer and user roles.
    """
    info = _resolve_skill(name, skills_dir)
    fpath = info.path / filename

    if fpath.exists() and not force:
        console.print(
            f"[bold yellow]'{filename}' already exists.[/bold yellow]  "
            "Use [bold]--force[/bold] to overwrite."
        )
        raise typer.Exit(1)

    if content:
        text = content
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        # Interactive: open a simple prompt
        console.print(
            f"[dim]Enter content for [bold]{filename}[/bold]. "
            "Finish with Ctrl-D (Unix) or Ctrl-Z Enter (Windows).[/dim]"
        )
        lines: list[str] = []
        try:
            while True:
                lines.append(input())
        except EOFError:
            pass
        text = "\n".join(lines) + "\n"

    fpath.write_text(text, encoding="utf-8")
    action = "updated" if fpath.exists() else "created"
    console.print(f"[bold green]{action}:[/bold green] {fpath}")


@files_app.command("remove")
def files_remove(
    name: _FilesSkillArg,
    filename: _FilesFileArg,
    skills_dir: _SkillsDirOpt = Path("./skills"),
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Skip confirmation"),
    ] = False,
) -> None:
    """Delete a helper file from a skill directory."""
    info = _resolve_skill(name, skills_dir)
    fpath = info.path / filename

    if filename == "SKILL.md":
        console.print("[bold red]Cannot remove SKILL.md — delete the whole skill instead.[/bold red]")
        raise typer.Exit(1)

    if not fpath.exists():
        console.print(f"[bold red]'{filename}' not found in skill '{name}'.[/bold red]")
        raise typer.Exit(1)

    if not force:
        confirmed = Confirm.ask(
            f"[bold red]Remove '{filename}'[/bold red] from '{name}'?",
            default=False,
        )
        if not confirmed:
            console.print("[dim]Aborted.[/dim]")
            raise typer.Exit()

    fpath.unlink()
    console.print(f"[bold green]Removed:[/bold green] {fpath}")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _write_skill_md(
    skill_dir: Path,
    name: str,
    description: str,
    role_restriction: Optional[str],
) -> None:
    restriction_line = (
        f"role-restriction: {role_restriction}\n" if role_restriction else ""
    )
    content = (
        f"---\n"
        f"name: {name}\n"
        f"description: {description}\n"
        f"{restriction_line}"
        f"version: 0.1.0\n"
        f"---\n\n"
        f"# {name.replace('-', ' ').title()}\n\n"
        f"<!-- Describe what the agent should do when this skill is active. -->\n"
        f"<!-- Helper files in this directory can be referenced via read_file. -->\n"
    )
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")


def _helper_template(filename: str, skill_name: str) -> str:
    """Return a sensible starter template based on the file extension."""
    ext = Path(filename).suffix.lower()
    if ext in (".md", ".txt", ""):
        return f"# {filename}\n\n<!-- Helper file for the '{skill_name}' skill. -->\n"
    if ext == ".json":
        return '{\n  "skill": "' + skill_name + '"\n}\n'
    if ext in (".yaml", ".yml"):
        return f"# Helper config for {skill_name}\nskill: {skill_name}\n"
    if ext == ".jinja2" or ext == ".j2":
        return f"{{# Jinja2 template for {skill_name} #}}\n"
    return f"# {filename} — helper file for {skill_name}\n"


def _guess_lexer(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return {
        ".md": "markdown",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".py": "python",
        ".sh": "bash",
        ".jinja2": "jinja2",
        ".j2": "jinja2",
        ".txt": "text",
    }.get(ext, "text")
