"""
surogate-agent CLI — entry point.

Commands
--------
  surogate-agent user          Start a user-role chat session
  surogate-agent developer     Start a developer-role chat session (skill authoring)
  surogate-agent chat          Generic chat (--role developer|user)
  surogate-agent skills list   List all discovered skills
  surogate-agent skills show   Print a skill's SKILL.md
  surogate-agent skills validate  Validate a skill directory
  surogate-agent skills delete    Delete a skill directory
"""

from typing import Annotated, Optional

import typer
from surogate_agent.cli import chat as chat_module
from surogate_agent.cli import skills as skills_module
from surogate_agent.cli import session as session_module
from surogate_agent.cli import workspace as workspace_module

app = typer.Typer(
    name="surogate-agent",
    help="Role-aware deep agent with meta-skill for conversational skill development.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


@app.callback()
def _main(
    log_level: Annotated[
        Optional[str],
        typer.Option(
            "--log-level",
            "-L",
            help="Log level: TRACE, DEBUG, INFO, WARNING, ERROR",
            envvar="SUROGATE_LOG_LEVEL",
            show_default=False,
        ),
    ] = None,
) -> None:
    """Role-aware deep agent with meta-skill for conversational skill development."""
    from surogate_agent.core.logging import setup_logging
    setup_logging(log_level.upper() if log_level else None)

app.command("chat")(chat_module.chat)
app.command("user")(chat_module.user_cmd)
app.command("developer")(chat_module.developer_cmd)
app.add_typer(skills_module.app, name="skills")
app.add_typer(session_module.app, name="session")
app.add_typer(workspace_module.app, name="workspace")


@app.command("serve")
def serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Bind host"),
    port: int = typer.Option(8000, "--port", help="Bind port"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload (development)"),
) -> None:
    """Start the surogate-agent FastAPI server."""
    try:
        import uvicorn
    except ImportError:
        typer.echo(
            "API dependencies are not installed. Run:\n"
            "  uv sync --extra api\n"
            "or: pip install 'surogate-agent[api]'",
            err=True,
        )
        raise typer.Exit(1)
    uvicorn.run("surogate_agent.api.app:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()
