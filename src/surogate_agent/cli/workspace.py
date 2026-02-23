"""
Developer workspace subcommands.

The workspace is a persistent scratch area for files used WHILE BUILDING skills.
It is NOT part of any skill definition and NOT accessible to users.

Each skill being developed gets its own sub-directory so multiple skills can
be developed in parallel without their files mixing:

  workspace/
  ├── jira-summariser/     ← working files for jira-summariser
  │   ├── draft-prompt.md
  │   └── test-tickets.json
  └── csv-to-report/       ← working files for csv-to-report
      └── sample.csv

Commands
--------
  surogate-agent workspace list                    List skills with workspace dirs
  surogate-agent workspace show <skill>            Show files for one skill
  surogate-agent workspace files add <skill> <src> Copy a file into workspace/<skill>/
  surogate-agent workspace files show <skill> <f>  Print a workspace file
  surogate-agent workspace files remove <skill> <f> Delete a workspace file
  surogate-agent workspace clean <skill>           Delete a skill's workspace dir
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.syntax import Syntax
from rich.table import Table
from rich import box

console = Console()

app = typer.Typer(
    help=(
        "Manage the developer workspace — scratch files used while building skills.\n\n"
        "workspace/<skill-name>/ is isolated per skill so multiple skills can be "
        "developed in parallel."
    ),
    no_args_is_help=True,
    rich_markup_mode="rich",
)

files_app = typer.Typer(
    help="Manage files inside a skill's workspace sub-directory.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
app.add_typer(files_app, name="files")

# ---------------------------------------------------------------------------
# Shared types
# ---------------------------------------------------------------------------

_WorkspaceDirOpt = Annotated[
    Path,
    typer.Option(
        "--workspace-dir", "-w",
        help="Root workspace directory (default: ./workspace)",
    ),
]
_SkillArg  = Annotated[str, typer.Argument(help="Skill name (kebab-case)")]
_FileArg   = Annotated[str, typer.Argument(help="Filename inside the workspace")]


def _skill_dir(skill: str, workspace_dir: Path) -> Path:
    return workspace_dir / skill


def _resolve_skill_dir(skill: str, workspace_dir: Path) -> Path:
    d = _skill_dir(skill, workspace_dir)
    if not d.is_dir():
        console.print(
            f"[bold red]No workspace for '{skill}'.[/bold red]  "
            f"Create it with: [bold]surogate-agent workspace files add {skill} <file>[/bold]"
        )
        raise typer.Exit(1)
    return d


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------

@app.command("list")
def list_workspaces(
    workspace_dir: _WorkspaceDirOpt = Path("./workspace"),
) -> None:
    """List all skill workspace directories and their file counts."""
    if not workspace_dir.is_dir():
        console.print("[dim]No workspace directory found.[/dim]")
        raise typer.Exit()

    entries = sorted(d for d in workspace_dir.iterdir() if d.is_dir())
    if not entries:
        console.print("[dim]No skill workspaces yet.[/dim]")
        raise typer.Exit()

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan")
    table.add_column("Skill")
    table.add_column("Files", justify="right")
    table.add_column("Size", justify="right", style="dim")
    table.add_column("Path", style="dim")

    for d in entries:
        files = [f for f in d.iterdir() if f.is_file()]
        total = sum(f.stat().st_size for f in files)
        table.add_row(
            d.name,
            str(len(files)),
            f"{total:,} bytes" if files else "—",
            str(d),
        )

    console.print(table)


# ---------------------------------------------------------------------------
# show
# ---------------------------------------------------------------------------

@app.command("show")
def show_workspace(
    skill: _SkillArg,
    workspace_dir: _WorkspaceDirOpt = Path("./workspace"),
) -> None:
    """Show all files in a skill's workspace directory."""
    d = _resolve_skill_dir(skill, workspace_dir)
    files = sorted(f for f in d.iterdir() if f.is_file())

    file_lines = "\n".join(
        f"  {f.name}  ({f.stat().st_size:,} bytes)" for f in files
    ) or "  (empty)"

    console.print(
        Panel(
            f"[bold]Skill    :[/bold] {skill}\n"
            f"[bold]Directory:[/bold] {d}\n\n"
            f"[bold]Files[/bold] ({len(files)}):\n{file_lines}",
            title=f"[bold cyan]workspace / {skill}[/bold cyan]",
            border_style="cyan",
        )
    )


# ---------------------------------------------------------------------------
# clean
# ---------------------------------------------------------------------------

@app.command("clean")
def clean_workspace(
    skill: _SkillArg,
    workspace_dir: _WorkspaceDirOpt = Path("./workspace"),
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Skip confirmation")
    ] = False,
) -> None:
    """Delete a skill's workspace directory and all its files."""
    d = _resolve_skill_dir(skill, workspace_dir)
    files = [f for f in d.iterdir() if f.is_file()]

    if not force:
        confirmed = Confirm.ask(
            f"[bold red]Delete workspace for '{skill}'[/bold red] "
            f"({len(files)} file(s))?",
            default=False,
        )
        if not confirmed:
            console.print("[dim]Aborted.[/dim]")
            raise typer.Exit()

    shutil.rmtree(d)
    console.print(f"[bold green]Deleted workspace:[/bold green] {d}")


# ---------------------------------------------------------------------------
# files sub-app
# ---------------------------------------------------------------------------

@files_app.command("add")
def files_add(
    skill: _SkillArg,
    source: Annotated[Path, typer.Argument(help="File to copy into the workspace")],
    filename: Annotated[
        str,
        typer.Option("--filename", "-n", help="Override destination filename"),
    ] = "",
    workspace_dir: _WorkspaceDirOpt = Path("./workspace"),
) -> None:
    """Copy a file into a skill's workspace directory (creates it if needed).

    Use this to add test inputs, draft prompts, or experiment files:

    [dim]  surogate-agent workspace files add csv-to-report ./sample.csv[/dim]
    """
    if not source.exists():
        console.print(f"[bold red]File not found:[/bold red] {source}")
        raise typer.Exit(1)

    dest_dir = _skill_dir(skill, workspace_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest = dest_dir / (filename or source.name)
    shutil.copy2(source, dest)
    console.print(f"[bold green]Added:[/bold green] {dest.name}  →  {dest}")


@files_app.command("show")
def files_show(
    skill: _SkillArg,
    filename: _FileArg,
    workspace_dir: _WorkspaceDirOpt = Path("./workspace"),
) -> None:
    """Print the contents of a file in a skill's workspace."""
    d = _resolve_skill_dir(skill, workspace_dir)
    fpath = d / filename

    if not fpath.exists():
        console.print(
            f"[bold red]'{filename}' not found in workspace for '{skill}'.[/bold red]"
        )
        raise typer.Exit(1)

    content = fpath.read_text(encoding="utf-8", errors="replace")
    lexer = _guess_lexer(filename)
    console.print(
        Panel(
            Syntax(content, lexer, theme="monokai", line_numbers=True),
            title=f"[bold cyan]workspace / {skill}[/bold cyan] / [bold]{filename}[/bold]",
            border_style="cyan",
        )
    )


@files_app.command("list")
def files_list(
    skill: _SkillArg,
    workspace_dir: _WorkspaceDirOpt = Path("./workspace"),
) -> None:
    """List all files in a skill's workspace directory."""
    d = _resolve_skill_dir(skill, workspace_dir)
    files = sorted(f for f in d.iterdir() if f.is_file())

    if not files:
        console.print(f"[dim]Workspace for '{skill}' is empty.[/dim]")
        raise typer.Exit()

    table = Table(box=box.SIMPLE, show_header=True, header_style="bold cyan")
    table.add_column("File")
    table.add_column("Size", justify="right", style="dim")
    table.add_column("Path", style="dim")
    for f in files:
        table.add_row(f.name, f"{f.stat().st_size:,} bytes", str(f))
    console.print(table)


@files_app.command("remove")
def files_remove(
    skill: _SkillArg,
    filename: _FileArg,
    workspace_dir: _WorkspaceDirOpt = Path("./workspace"),
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Skip confirmation")
    ] = False,
) -> None:
    """Delete a file from a skill's workspace directory."""
    d = _resolve_skill_dir(skill, workspace_dir)
    fpath = d / filename

    if not fpath.exists():
        console.print(
            f"[bold red]'{filename}' not found in workspace for '{skill}'.[/bold red]"
        )
        raise typer.Exit(1)

    if not force:
        confirmed = Confirm.ask(
            f"[bold red]Remove '{filename}'[/bold red] from workspace '{skill}'?",
            default=False,
        )
        if not confirmed:
            console.print("[dim]Aborted.[/dim]")
            raise typer.Exit()

    fpath.unlink()
    console.print(f"[bold green]Removed:[/bold green] {fpath}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _guess_lexer(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return {
        ".md": "markdown", ".json": "json", ".yaml": "yaml", ".yml": "yaml",
        ".py": "python", ".sh": "bash", ".csv": "text", ".txt": "text",
        ".jinja2": "jinja2", ".j2": "jinja2", ".sql": "sql", ".xml": "xml",
    }.get(ext, "text")
