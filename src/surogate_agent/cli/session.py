"""
Session management subcommands.

  surogate-agent session list                       List all past sessions
  surogate-agent session show <id>                  Show session details + files
  surogate-agent session files list <id>            List files in a session workspace
  surogate-agent session files add <id> <src>       Copy a file into a session workspace
  surogate-agent session files show <id> <file>     Print a file from the workspace
  surogate-agent session files remove <id> <file>   Delete a file from the workspace
  surogate-agent session clean <id>                 Delete an entire session workspace
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.syntax import Syntax
from rich.table import Table
from rich import box

from surogate_agent.core.session import SessionManager

console = Console()

app = typer.Typer(
    help="Manage chat session workspaces (user file inputs and outputs).",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

files_app = typer.Typer(
    help="Manage files inside a session workspace.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
app.add_typer(files_app, name="files")

# ---------------------------------------------------------------------------
# Shared option
# ---------------------------------------------------------------------------

_SessionsDirOpt = Annotated[
    Path,
    typer.Option(
        "--sessions-dir",
        help="Root directory containing session workspaces (default: ./sessions)",
    ),
]

_SessionIdArg = Annotated[str, typer.Argument(help="Session ID")]


def _manager(sessions_dir: Path) -> SessionManager:
    return SessionManager(sessions_dir)


def _resolve_session(session_id: str, sessions_dir: Path):
    sm = _manager(sessions_dir)
    session = sm.get_session(session_id)
    if session is None:
        console.print(f"[bold red]Session '{session_id}' not found.[/bold red]")
        raise typer.Exit(1)
    return session


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------

@app.command("list")
def list_sessions(
    sessions_dir: _SessionsDirOpt = Path("./sessions"),
) -> None:
    """List all session workspaces."""
    sessions = _manager(sessions_dir).list_sessions()
    if not sessions:
        console.print("[dim]No sessions found.[/dim]")
        raise typer.Exit()

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan")
    table.add_column("Session ID")
    table.add_column("Files", justify="right")
    table.add_column("Size", justify="right", style="dim")
    table.add_column("Workspace", style="dim")

    for s in sessions:
        files = s.files
        total = sum(f.stat().st_size for f in files)
        table.add_row(
            s.session_id,
            str(len(files)),
            f"{total:,} bytes" if files else "—",
            str(s.workspace_dir),
        )

    console.print(table)


# ---------------------------------------------------------------------------
# show
# ---------------------------------------------------------------------------

@app.command("show")
def show_session(
    session_id: _SessionIdArg,
    sessions_dir: _SessionsDirOpt = Path("./sessions"),
) -> None:
    """Show details and file listing for a session."""
    session = _resolve_session(session_id, sessions_dir)
    files = session.files

    file_lines = "\n".join(
        f"  {f.name}  ({f.stat().st_size:,} bytes)" for f in files
    ) or "  (empty)"

    console.print(
        Panel(
            f"[bold]Session ID:[/bold] {session.session_id}\n"
            f"[bold]Workspace :[/bold] {session.workspace_dir}\n\n"
            f"[bold]Files[/bold] ({len(files)}):\n{file_lines}",
            title=f"[bold cyan]{session.session_id}[/bold cyan]",
            border_style="cyan",
        )
    )


# ---------------------------------------------------------------------------
# clean
# ---------------------------------------------------------------------------

@app.command("clean")
def clean_session(
    session_id: _SessionIdArg,
    sessions_dir: _SessionsDirOpt = Path("./sessions"),
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Skip confirmation"),
    ] = False,
) -> None:
    """Delete a session workspace and all its files."""
    session = _resolve_session(session_id, sessions_dir)

    if not force:
        files = session.files
        confirmed = Confirm.ask(
            f"[bold red]Delete session '{session_id}'[/bold red] "
            f"({len(files)} file(s))?",
            default=False,
        )
        if not confirmed:
            console.print("[dim]Aborted.[/dim]")
            raise typer.Exit()

    _manager(sessions_dir).delete_session(session_id)
    console.print(f"[bold green]Deleted session:[/bold green] {session_id}")


# ---------------------------------------------------------------------------
# files sub-app
# ---------------------------------------------------------------------------

@files_app.command("list")
def files_list(
    session_id: _SessionIdArg,
    sessions_dir: _SessionsDirOpt = Path("./sessions"),
) -> None:
    """List all files in a session workspace."""
    session = _resolve_session(session_id, sessions_dir)
    files = session.files

    if not files:
        console.print(f"[dim]Session '{session_id}' workspace is empty.[/dim]")
        console.print(
            f"[dim]Add files with: "
            f"surogate-agent session files add {session_id} <path>[/dim]"
        )
        raise typer.Exit()

    table = Table(box=box.SIMPLE, show_header=True, header_style="bold cyan")
    table.add_column("File")
    table.add_column("Size", justify="right", style="dim")
    table.add_column("Path", style="dim")
    for f in files:
        table.add_row(f.name, f"{f.stat().st_size:,} bytes", str(f))
    console.print(table)


@files_app.command("add")
def files_add(
    session_id: _SessionIdArg,
    source: Annotated[Path, typer.Argument(help="Path to the file to add")],
    filename: Annotated[
        str,
        typer.Option("--filename", "-n", help="Override destination filename"),
    ] = "",
    sessions_dir: _SessionsDirOpt = Path("./sessions"),
) -> None:
    """Copy a file into a session workspace (creates the session if needed).

    Use this to place your input files ("file X") before starting a chat:

    [dim]  surogate-agent session files add my-session ./data.csv[/dim]
    [dim]  surogate-agent chat --role user --session my-session[/dim]
    """
    if not source.exists():
        console.print(f"[bold red]File not found:[/bold red] {source}")
        raise typer.Exit(1)

    # Auto-create the session workspace if it doesn't exist yet.
    sm = _manager(sessions_dir)
    session = sm.resume_or_create(session_id)

    dest = session.add_file(source, filename or None)
    console.print(f"[bold green]Added:[/bold green] {dest.name}  →  {dest}")


@files_app.command("show")
def files_show(
    session_id: _SessionIdArg,
    filename: Annotated[str, typer.Argument(help="Filename inside the workspace")],
    sessions_dir: _SessionsDirOpt = Path("./sessions"),
) -> None:
    """Print the contents of a file in a session workspace."""
    session = _resolve_session(session_id, sessions_dir)
    fpath = session.workspace_dir / filename

    if not fpath.exists():
        console.print(
            f"[bold red]'{filename}' not found in session '{session_id}'.[/bold red]"
        )
        raise typer.Exit(1)

    content = fpath.read_text(encoding="utf-8", errors="replace")
    lexer = _guess_lexer(filename)
    console.print(
        Panel(
            Syntax(content, lexer, theme="monokai", line_numbers=True),
            title=f"[bold cyan]{session_id}[/bold cyan] / [bold]{filename}[/bold]",
            border_style="cyan",
        )
    )


@files_app.command("remove")
def files_remove(
    session_id: _SessionIdArg,
    filename: Annotated[str, typer.Argument(help="Filename to delete")],
    sessions_dir: _SessionsDirOpt = Path("./sessions"),
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Skip confirmation"),
    ] = False,
) -> None:
    """Delete a file from a session workspace."""
    session = _resolve_session(session_id, sessions_dir)
    fpath = session.workspace_dir / filename

    if not fpath.exists():
        console.print(
            f"[bold red]'{filename}' not found in session '{session_id}'.[/bold red]"
        )
        raise typer.Exit(1)

    if not force:
        confirmed = Confirm.ask(
            f"[bold red]Remove '{filename}'[/bold red] from session '{session_id}'?",
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
