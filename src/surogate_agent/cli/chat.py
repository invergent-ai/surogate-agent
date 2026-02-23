"""
Interactive chat session — developer or user role.

DEVELOPER role loads the skill-developer meta-skill so the user can author
new skills purely through conversation.  USER role gets a clean agent with
only the skills explicitly available to them.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_DEBUG = os.environ.get("SUROGATE_DEBUG", "").lower() in ("1", "true", "yes")
from typing import Annotated, Optional

import typer
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.key_binding import KeyBindings
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text
from rich.theme import Theme

from surogate_agent.core.config import AgentConfig
from surogate_agent.core.roles import Role
from surogate_agent.core.session import SessionManager

# ---------------------------------------------------------------------------
# Console setup
# ---------------------------------------------------------------------------

_THEME = Theme(
    {
        "agent": "bold cyan",
        "user": "bold green",
        "meta": "dim",
        "warn": "bold yellow",
        "err": "bold red",
    }
)
console = Console(theme=_THEME)


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

def chat(
    role: Annotated[
        str,
        typer.Option(
            "--role", "-r",
            help="Session role: developer (meta-skill loaded) or user",
        ),
    ] = "developer",
    skill: Annotated[
        str,
        typer.Option(
            "--skill", "-k",
            help="Skill name to develop (developer mode). Resumes previous session if one exists.",
        ),
    ] = "",
    model: Annotated[
        str,
        typer.Option("--model", "-m", help="LangChain model string, e.g. claude-sonnet-4-6"),
    ] = "",
    skills_dir: Annotated[
        Optional[Path],
        typer.Option(
            "--skills-dir", "-s",
            help="Directory for user skills (default: ./skills)",
            exists=False,
        ),
    ] = None,
    dev_workspace: Annotated[
        Optional[Path],
        typer.Option(
            "--workspace", "-w",
            help="Developer scratch workspace root (default: ./workspace)",
            exists=False,
        ),
    ] = None,
    extra_skills: Annotated[
        Optional[Path],
        typer.Option(
            "--extra-skills",
            help="Additional directory to scan for existing skills",
            exists=False,
        ),
    ] = None,
    session_id: Annotated[
        str,
        typer.Option(
            "--session", "-t",
            help="Session ID to resume (user mode; creates a new session if omitted)",
        ),
    ] = "",
    user_id: Annotated[
        str,
        typer.Option("--user", "-u", help="User identifier stored in audit context"),
    ] = "",
) -> None:
    """[bold]Start an interactive chat session.[/bold]

    [green]developer[/green] role loads the [cyan]skill-developer[/cyan] meta-skill so
    you can create, edit, and manage skills through conversation.
    Developer sessions are persisted per skill — use [bold]--skill <name>[/bold] to
    resume where you left off.

    [green]user[/green] role starts a clean session with only the skills available
    to that role — no skill-authoring capabilities.

    [dim]Tip: use [bold]surogate-agent user[/bold] or [bold]surogate-agent developer[/bold]
    as convenient role-specific shortcuts.[/dim]

    [dim]Type  exit / quit / Ctrl-D  to end the session.[/dim]
    """
    try:
        resolved_role = Role(role.lower())
    except ValueError:
        console.print(f"[err]Unknown role '{role}'. Choose: developer, user[/err]")
        raise typer.Exit(1)

    resolved_model = model or os.environ.get("SUROGATE_MODEL", "claude-sonnet-4-6")
    resolved_skills_dir = skills_dir or Path(os.environ.get("SUROGATE_SKILLS_DIR", "") or Path.cwd() / "skills")
    resolved_skills_dir.mkdir(parents=True, exist_ok=True)

    cfg_kwargs: dict = dict(
        model=resolved_model,
        user_skills_dir=resolved_skills_dir,
    )
    if dev_workspace:
        cfg_kwargs["dev_workspace_dir"] = dev_workspace
    if extra_skills:
        cfg_kwargs["skills_dirs"] = [extra_skills]

    if resolved_role == Role.DEVELOPER:
        cfg_kwargs["allow_execute"] = True

    config = AgentConfig(**cfg_kwargs)

    # -----------------------------------------------------------------------
    # Developer: optional --skill flag enables persistent per-skill history
    # -----------------------------------------------------------------------
    checkpointer = None
    _checkpointer_ctx = None   # context manager to close on exit
    dev_skill_name: str = skill.strip()
    resuming = False

    if resolved_role == Role.DEVELOPER:
        config.dev_workspace_dir.mkdir(parents=True, exist_ok=True)

        if dev_skill_name:
            # --skill provided: persistent SQLite history keyed by skill name
            history_db = config.dev_workspace_dir / ".history.db"
            try:
                from langgraph.checkpoint.sqlite import SqliteSaver
                # from_conn_string is a @contextmanager — enter it to get the saver instance
                _checkpointer_ctx = SqliteSaver.from_conn_string(str(history_db))
                checkpointer = _checkpointer_ctx.__enter__()
            except ImportError:
                console.print("[warn]langgraph-checkpoint-sqlite not installed — session history will not persist.[/warn]")

            thread_id = f"dev:{dev_skill_name}"
            resuming = checkpointer is not None and _thread_has_history(checkpointer, thread_id)
            skill_workspace = config.dev_workspace_dir / dev_skill_name
        else:
            # No --skill: fresh session, workspace root
            import time as _time
            thread_id = f"dev:{int(_time.time())}"
            skill_workspace = config.dev_workspace_dir

        skill_workspace.mkdir(parents=True, exist_ok=True)
        from surogate_agent.core.session import Session
        session = Session(session_id=thread_id, workspace_dir=skill_workspace)
    else:
        sm = SessionManager(config.sessions_dir)
        session = sm.resume_or_create(session_id) if session_id else sm.new_session()
        thread_id = session.session_id

    # When no persistent checkpointer is available, fall back to an in-memory
    # one so LangGraph always owns conversation history.  This prevents the full
    # accumulated message list from being passed on every call (which causes the
    # graph to re-emit — and the CLI to re-render — all prior assistant messages).
    if checkpointer is None:
        try:
            from langgraph.checkpoint.memory import MemorySaver
            checkpointer = MemorySaver()
        except ImportError:
            pass  # genuine fallback to local_history if langgraph unavailable

    # For user sessions, check whether any installed skill needs execute so the
    # banner can report it accurately before the agent is created.
    user_execute_active = False
    if resolved_role == Role.USER:
        from surogate_agent.core.agent import _user_skills_need_execute
        from surogate_agent.core.config import _DEFAULT_SKILLS_DIR
        _user_dirs = [config.user_skills_dir] + [
            d for d in config.skills_dirs if d != _DEFAULT_SKILLS_DIR
        ]
        user_execute_active = _user_skills_need_execute(_user_dirs)

    _print_banner(resolved_model, resolved_skills_dir, resolved_role, session, config,
                  dev_skill_name=dev_skill_name, resuming=resuming,
                  user_execute_active=user_execute_active)

    try:
        from surogate_agent.core.agent import create_agent
    except ImportError as exc:
        console.print(f"[err]Import error:[/err] {exc}")
        raise typer.Exit(1) from exc

    try:
        agent = create_agent(
            role=resolved_role,
            config=config,
            session=session,
            user_id=user_id or f"cli-{resolved_role.value}",
            checkpointer=checkpointer,
        )
    except Exception as exc:
        console.print(f"[err]Failed to create agent:[/err] {exc}")
        raise typer.Exit(1) from exc

    if resuming:
        console.print(
            f"[meta]Resuming[/meta] [bold cyan]{dev_skill_name}[/bold cyan]  "
            f"[dim]thread: {thread_id}[/dim]\n"
        )

    # When a checkpointer is active the graph owns the conversation history.
    # We must pass ONLY the latest user message per call — passing the full
    # accumulated list would cause duplicates in the persisted state.
    # Without a checkpointer we maintain history locally so the graph has
    # full context each call.
    use_local_history = checkpointer is None
    local_history: list[dict] = []
    invoke_config = {"configurable": {"thread_id": thread_id}}
    # IDs of messages already rendered in previous turns.  LangGraph with a
    # checkpointer emits the full loaded state (including prior messages) as
    # the first chunk of every new turn.  We skip anything already seen.
    rendered_ids: set[str] = set()
    # current_dev_skill — the specific skill being worked on (or "").
    # meta_skill_active  — True once the developer engages skill-dev context;
    #                      stays True for the rest of the session (sticky).
    current_dev_skill = dev_skill_name
    meta_skill_active = bool(dev_skill_name)  # already in context if --skill given

    prompt_session = _make_prompt_session()

    try:
        while True:
            # --- Read user input ---
            try:
                user_input = prompt_session.prompt(
                    HTML("<ansigreen><b>You</b></ansigreen> (Alt+Enter to send)\n> "),
                    multiline=True,
                )
            except (EOFError, KeyboardInterrupt):
                console.print("\n[meta]Session ended.[/meta]")
                _print_session_summary(session)
                break

            stripped = user_input.strip()
            if not stripped:
                continue
            if stripped.lower() in {"exit", "quit", "q"}:
                console.print("[meta]Goodbye.[/meta]")
                _print_session_summary(session)
                break

            new_user_msg = {"role": "user", "content": stripped}
            if use_local_history:
                local_history.append(new_user_msg)
                invoke_input = {"messages": local_history}
            else:
                # Checkpointer holds history — pass only the new message
                invoke_input = {"messages": [new_user_msg]}

            # Update skill context from the user's message before each invoke.
            if resolved_role == Role.DEVELOPER:
                inferred = _infer_skill_from_message(stripped, resolved_skills_dir)
                if inferred:
                    current_dev_skill = inferred
                    meta_skill_active = True
                elif _is_skill_dev_context(stripped):
                    meta_skill_active = True

                if current_dev_skill:
                    active_skill = f"skill-developer  ·  {current_dev_skill}"
                elif meta_skill_active:
                    active_skill = "skill-developer"
                else:
                    active_skill = ""   # casual message, no skill context yet
            else:
                active_skill = ""

            # --- Invoke agent ---
            console.print()
            detected_skills: set[str] = set()
            try:
                reply = _invoke(agent, invoke_input, invoke_config,
                               active_skill=active_skill, rendered_ids=rendered_ids,
                               skills_dir=resolved_skills_dir if resolved_role == Role.DEVELOPER else None,
                               detected_skills=detected_skills)
            except KeyboardInterrupt:
                console.print("\n[warn]Interrupted.[/warn]")
                if use_local_history:
                    local_history.pop()
                continue
            except Exception as exc:
                console.print(f"[err]Agent error:[/err] {exc}")
                if use_local_history:
                    local_history.pop()
                continue

            # Update current_dev_skill from tool-call paths and reply text so
            # the next turn's header reflects the skill the agent worked on,
            # even when the user never named it explicitly.
            if resolved_role == Role.DEVELOPER:
                if detected_skills:
                    current_dev_skill = next(iter(detected_skills))
                    meta_skill_active = True
                elif reply:
                    reply_inferred = _infer_skill_from_message(reply, resolved_skills_dir)
                    if reply_inferred:
                        current_dev_skill = reply_inferred
                        meta_skill_active = True

            if use_local_history:
                local_history.append({"role": "assistant", "content": reply})
            console.print(Rule(style="dim"))
            console.print()
    finally:
        # Close the SQLite checkpointer connection if one was opened
        if _checkpointer_ctx is not None:
            try:
                _checkpointer_ctx.__exit__(None, None, None)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_prompt_session() -> PromptSession:
    """Build a PromptSession where Enter = newline, Alt+Enter = submit.

    In most terminal emulators, Ctrl+Enter and Enter send the same byte (\r),
    so they cannot be distinguished at the protocol level.  Alt+Enter (Escape
    then Enter) is reliably distinct and is prompt_toolkit's canonical submit
    key in multiline mode.
    """
    kb = KeyBindings()

    @kb.add("escape", "enter")   # Alt+Enter / Meta+Enter — submit
    def _submit(event):
        event.current_buffer.validate_and_handle()

    # NOTE: no custom "enter" binding — prompt_toolkit's default multiline
    # behaviour already inserts a newline on Enter.

    return PromptSession(key_bindings=kb)


def _invoke(
    agent,
    invoke_input: dict,
    invoke_config: dict,
    *,
    active_skill: str = "",
    rendered_ids: set[str] | None = None,
    skills_dir: Path | None = None,
    detected_skills: set[str] | None = None,
) -> str:
    """Stream the agent response, render tool calls in real time, return reply text.

    Shows a spinner while waiting for the first message-bearing chunk.
    Set env var SUROGATE_DEBUG=1 to print raw chunk keys for diagnosis.

    *rendered_ids* is a caller-owned set of message IDs already displayed in
    previous turns.  Messages whose ID is in the set are skipped (LangGraph
    emits the full loaded state as the first chunk on each new turn, so prior
    assistant messages would otherwise be re-rendered).  Newly rendered message
    IDs are added to the set so future turns know about them.

    *skills_dir* / *detected_skills*: if provided, skill names found in tool
    call path arguments are added to *detected_skills* during streaming so the
    caller can update the active-skill label for subsequent turns.
    """
    if rendered_ids is None:
        rendered_ids = set()

    reply_parts: list[str] = []
    stream_had_output = False
    header_printed = False

    def _ensure_header(status=None):
        nonlocal header_printed
        if not header_printed:
            header_printed = True
            if status is not None:
                status.stop()
            if active_skill:
                console.print(
                    Rule(
                        f"[dim cyan]● {active_skill}[/dim cyan]",
                        style="dim",
                        align="left",
                    )
                )

    try:
        with console.status("[dim]● thinking…[/dim]", spinner="dots") as status:
            for chunk in agent.stream(invoke_input, config=invoke_config):
                stream_had_output = True

                if _DEBUG:
                    _debug_chunk(chunk)

                for msg in _iter_messages(chunk):
                    _ensure_header(status)
                    text = _render_message(msg, rendered_ids=rendered_ids,
                                          skills_dir=skills_dir,
                                          detected_skills=detected_skills)
                    if text:
                        reply_parts.append(text)

    except NotImplementedError:
        pass  # stream not supported — fall through to invoke below

    # Only fall back to invoke when the stream produced absolutely nothing
    # (graph doesn't support streaming at all, e.g. in unit tests).
    if not stream_had_output:
        _ensure_header()
        result = agent.invoke(invoke_input, config=invoke_config)
        text = _extract_text_from_result(result)
        console.print(f"\n[agent]Agent[/agent]")
        console.print(Markdown(text))
        return text

    return "".join(reply_parts)


def _unwrap_messages(raw) -> list:
    """Unwrap a LangGraph state value into a plain list of messages.

    deepagents middleware nodes return ``Overwrite(value=[...])`` wrappers
    instead of plain lists.  We also accept plain lists directly.
    """
    if raw is None:
        return []
    # LangGraph Overwrite / Annotated wrappers expose their list via .value
    if hasattr(raw, "value"):
        raw = raw.value
    if isinstance(raw, list):
        return raw
    return []


def _iter_messages(chunk):
    """Yield message objects from a LangGraph stream chunk.

    Handles the two common LangGraph stream_mode formats:
    - "updates": {node_name: {"messages": <list|Overwrite>}, ...}
    - "values":  {"messages": <list|Overwrite>}  (top-level key)
    """
    if not isinstance(chunk, dict):
        # stream_mode="messages" yields (msg, metadata) tuples
        if isinstance(chunk, tuple) and chunk:
            item = chunk[0]
            if _looks_like_message(item):
                yield item
        return

    # "values" mode: messages is a top-level key
    if "messages" in chunk:
        msgs = _unwrap_messages(chunk["messages"])
        if msgs:
            # In "values" mode each chunk is the FULL state — only the last
            # message is new.  Yield only the final entry to avoid re-rendering.
            yield msgs[-1]
        return

    # "updates" mode: {node_name: state_delta, ...}
    for node_output in chunk.values():
        if isinstance(node_output, dict):
            for msg in _unwrap_messages(node_output.get("messages")):
                yield msg
        elif isinstance(node_output, list):
            # Defensive: some middleware might return a bare list of messages
            for item in node_output:
                if _looks_like_message(item):
                    yield item


def _looks_like_message(obj) -> bool:
    """True if obj appears to be a LangChain message object."""
    t = getattr(obj, "type", None)
    if isinstance(t, str):
        return True
    return isinstance(obj, dict) and "role" in obj


def _debug_chunk(chunk) -> None:
    """Print a compact debug line showing the raw chunk structure."""
    if isinstance(chunk, dict):
        parts = []
        for k, v in chunk.items():
            if isinstance(v, dict):
                msgs = v.get("messages", [])
                parts.append(
                    f"{k}={{messages:[{', '.join(_msg_summary(m) for m in msgs)}]}}"
                    if msgs else f"{k}={{keys:{list(v.keys())}}}"
                )
            else:
                parts.append(f"{k}={type(v).__name__}")
        console.print(f"[dim]  DEBUG chunk: {{{', '.join(parts)}}}[/dim]")
    else:
        console.print(f"[dim]  DEBUG chunk type={type(chunk).__name__}: {chunk!r:.120}[/dim]")


def _msg_summary(msg) -> str:
    t = getattr(msg, "type", msg.get("role", "?") if isinstance(msg, dict) else "?")
    content = getattr(msg, "content", msg.get("content", "") if isinstance(msg, dict) else "")
    tcs = getattr(msg, "tool_calls", [])
    tc_names = [tc.get("name", "?") if isinstance(tc, dict) else getattr(tc, "name", "?") for tc in (tcs or [])]
    content_len = len(content) if isinstance(content, str) else len(str(content))
    tc_str = f" tool_calls={tc_names}" if tc_names else ""
    return f"{t}(len={content_len}{tc_str})"


def _render_message(
    msg,
    rendered_ids: set[str] | None = None,
    skills_dir: Path | None = None,
    detected_skills: set[str] | None = None,
) -> str:
    """Render one message from a streamed chunk; return any assistant text.

    If *rendered_ids* is provided, messages whose ID is already in the set are
    skipped and the set is updated with IDs of newly rendered messages.

    If *skills_dir* and *detected_skills* are provided, skill names found in
    tool call path arguments are added to *detected_skills*.
    """
    # Deduplicate against messages rendered in prior turns.
    msg_id: str | None = (
        msg.get("id") if isinstance(msg, dict) else getattr(msg, "id", None)
    )
    if rendered_ids is not None and msg_id:
        if msg_id in rendered_ids:
            return ""
        rendered_ids.add(msg_id)

    # Support both dict messages and LangChain message objects
    msg_type = msg.get("role") if isinstance(msg, dict) else getattr(msg, "type", None)

    if msg_type in ("ai", "assistant"):
        content = (
            msg.get("content", "") if isinstance(msg, dict)
            else getattr(msg, "content", "")
        )
        tool_calls = (
            msg.get("tool_calls", []) if isinstance(msg, dict)
            else getattr(msg, "tool_calls", [])
        )

        # Show thinking blocks
        thinking = _extract_thinking(content)
        if thinking:
            console.print(
                Panel(
                    Text(thinking, style="dim italic"),
                    title="[dim]● thinking[/dim]",
                    border_style="dim",
                    padding=(0, 1),
                )
            )

        # Show tool calls; also sniff path args for skill directory names.
        for tc in tool_calls or []:
            name = tc.get("name", "?") if isinstance(tc, dict) else getattr(tc, "name", "?")
            args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
            console.print(f"[dim cyan]  ▶ {name}[/dim cyan][dim] {_fmt_args(args)}[/dim]")
            if skills_dir is not None and detected_skills is not None:
                skill = _skill_from_tool_args(args, skills_dir)
                if skill:
                    detected_skills.add(skill)

        # Show text content
        text = _extract_content_text(content)
        if text:
            console.print(f"\n[agent]Agent[/agent]")
            console.print(Markdown(text))
            console.print()
        return text

    if msg_type == "tool":
        name = (
            msg.get("name", "?") if isinstance(msg, dict)
            else getattr(msg, "name", getattr(msg, "tool_call_id", "?"))
        )
        content = (
            msg.get("content", "") if isinstance(msg, dict)
            else getattr(msg, "content", "")
        )
        snippet = str(content).replace("\n", " ")[:120]
        if len(str(content)) > 120:
            snippet += "…"
        console.print(f"[dim]    ✓ {name}: {snippet}[/dim]")

    return ""


def _extract_thinking(content) -> str:
    """Extract thinking text from content blocks (Claude extended thinking)."""
    if not isinstance(content, list):
        return ""
    parts = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "thinking":
            parts.append(block.get("thinking", ""))
        elif hasattr(block, "type") and getattr(block, "type", None) == "thinking":
            parts.append(getattr(block, "thinking", ""))
    return "\n\n".join(p for p in parts if p)


def _extract_content_text(content) -> str:
    """Extract plain text from a message content field (str or content-block list)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif hasattr(block, "type") and getattr(block, "type", None) == "text":
                parts.append(getattr(block, "text", ""))
        return "".join(parts)
    return ""


def _fmt_args(args: dict) -> str:
    """Compact one-liner of tool arguments."""
    if not args:
        return ""
    parts = []
    for k, v in list(args.items())[:3]:
        v_str = str(v)
        if len(v_str) > 50:
            v_str = v_str[:47] + "..."
        parts.append(f"{k}={v_str!r}")
    suffix = ", …" if len(args) > 3 else ""
    return "(" + ", ".join(parts) + suffix + ")"


def _extract_text_from_result(result: dict) -> str:
    messages = result.get("messages", [])
    if not messages:
        return ""
    last = messages[-1]
    if isinstance(last, dict):
        return last.get("content", "")
    return _extract_content_text(getattr(last, "content", ""))


def _print_banner(
    model: str,
    skills_dir: Path,
    role: Role,
    session,
    config,
    *,
    dev_skill_name: str = "",
    resuming: bool = False,
    user_execute_active: bool = False,
) -> None:
    role_colour = "yellow" if role == Role.DEVELOPER else "green"
    role_label = role.value

    if role == Role.DEVELOPER:
        execute_tag = (
            "  [bold yellow]⚡ shell execution enabled[/bold yellow]"
            if config.allow_execute
            else "  [dim]shell execution disabled[/dim]"
        )
        meta_note = (
            f"\n[dim]meta-skill active — create or manage skills through conversation[/dim]"
            f"{execute_tag}"
        )
        if dev_skill_name:
            resume_tag = "  [dim](resuming)[/dim]" if resuming else "  [dim](new session)[/dim]"
            workspace_line = (
                f"[meta]skill      :[/meta] [bold cyan]{dev_skill_name}[/bold cyan]{resume_tag}\n"
                f"[meta]workspace  :[/meta] [bold]{session.workspace_dir}[/bold]\n"
                f"[meta]history db :[/meta] [dim]{config.dev_workspace_dir / '.history.db'}[/dim]"
            )
        else:
            workspace_line = (
                f"[meta]workspace  :[/meta] [bold]{config.dev_workspace_dir}[/bold]\n"
                f"[dim]  Use [bold]--skill <name>[/bold] to resume a specific skill session.[/dim]"
            )
    else:
        execute_tag = (
            "  [bold green]⚡ shell execution enabled (skill-requested)[/bold green]"
            if user_execute_active
            else ""
        )
        meta_note = execute_tag
        workspace_line = (
            f"[meta]session workspace:[/meta] [bold]{session.workspace_dir}[/bold]\n"
            f"[dim]  session: {session.session_id}[/dim]"
        )

    console.print(
        Panel.fit(
            f"[bold cyan]surogate-agent[/bold cyan]  "
            f"[{role_colour}]{role_label}[/{role_colour}]{meta_note}\n"
            f"[meta]model  :[/meta] [bold]{model}[/bold]\n"
            f"[meta]skills :[/meta] [bold]{skills_dir}[/bold]\n"
            f"{workspace_line}\n\n"
            "[dim]Type [bold]exit[/bold] or press Ctrl-D to quit.[/dim]",
            border_style=role_colour,
        )
    )
    console.print()



def _thread_has_history(checkpointer, thread_id: str) -> bool:
    """Return True if the checkpointer has any saved state for this thread."""
    try:
        cp = checkpointer.get({"configurable": {"thread_id": thread_id}})
        return cp is not None
    except Exception:
        return False


def _skill_from_tool_args(args: dict, skills_dir: Path) -> str:
    """Return a known skill name found in any string-valued tool argument, or ''."""
    if not skills_dir.is_dir():
        return ""
    args_blob = " ".join(str(v) for v in args.values())
    for entry in skills_dir.iterdir():
        if entry.is_dir() and (entry / "SKILL.md").exists():
            # Match only when the name appears in a path context to avoid
            # false positives from short or common names.
            if f"skills/{entry.name}" in args_blob or f"workspace/{entry.name}" in args_blob:
                return entry.name
    return ""


_SKILL_DEV_WORDS = frozenset([
    "skill", "skills", "create", "develop", "build", "workspace",
    "prompt.md", "skill.md", "new skill", "make a skill",
])


def _is_skill_dev_context(message: str) -> bool:
    """Return True if the message signals skill-development intent."""
    msg_lower = message.lower()
    return any(w in msg_lower for w in _SKILL_DEV_WORDS)


def _infer_skill_from_message(message: str, skills_dir: Path) -> str:
    """Return the name of the first known skill mentioned in *message*, or ''.

    Matches both the kebab-case form (``generate-mandate``) and its
    space-separated equivalent (``generate mandate``) so natural language
    works without special syntax.
    """
    if not skills_dir.is_dir():
        return ""
    msg_lower = message.lower()
    for entry in sorted(skills_dir.iterdir()):
        if not entry.is_dir() or not (entry / "SKILL.md").exists():
            continue
        name = entry.name.lower()
        if name in msg_lower or name.replace("-", " ") in msg_lower:
            return entry.name
    return ""


def _print_session_summary(session) -> None:
    """Print the files present in the session workspace at end of session."""
    files = session.files
    if not files:
        return
    console.print()
    console.print(f"[meta]Session workspace:[/meta] [bold]{session.workspace_dir}[/bold]")
    for f in files:
        console.print(f"  [green]↳[/green] {f.name}  [dim]({f.stat().st_size:,} bytes)[/dim]")


# ---------------------------------------------------------------------------
# Role-specific shortcut commands
# ---------------------------------------------------------------------------

def user_cmd(
    model: Annotated[
        str,
        typer.Option("--model", "-m", help="LangChain model string, e.g. claude-sonnet-4-6"),
    ] = "",
    session_id: Annotated[
        str,
        typer.Option(
            "--session", "-t",
            help="Session ID to resume (creates a new session if omitted)",
        ),
    ] = "",
    skills_dir: Annotated[
        Optional[Path],
        typer.Option(
            "--skills-dir", "-s",
            help="Directory of available skills (default: ./skills)",
            exists=False,
        ),
    ] = None,
    extra_skills: Annotated[
        Optional[Path],
        typer.Option(
            "--extra-skills",
            help="Additional directory to scan for skills",
            exists=False,
        ),
    ] = None,
    user_id: Annotated[
        str,
        typer.Option("--user", "-u", help="User identifier stored in audit context"),
    ] = "",
) -> None:
    """[bold]Start a user-role chat session.[/bold]

    Runs with only the skills available to the [green]user[/green] role —
    no skill-authoring capabilities.

    [dim]Type  exit / quit / Ctrl-D  to end the session.[/dim]
    """
    chat(
        role="user",
        skill="",
        model=model,
        skills_dir=skills_dir,
        dev_workspace=None,
        extra_skills=extra_skills,
        session_id=session_id,
        user_id=user_id,
    )


def developer_cmd(
    skill: Annotated[
        str,
        typer.Option(
            "--skill", "-k",
            help="Skill name to develop. Resumes previous session if one exists.",
        ),
    ] = "",
    model: Annotated[
        str,
        typer.Option("--model", "-m", help="LangChain model string, e.g. claude-sonnet-4-6"),
    ] = "",
    skills_dir: Annotated[
        Optional[Path],
        typer.Option(
            "--skills-dir", "-s",
            help="Directory for user skills (default: ./skills)",
            exists=False,
        ),
    ] = None,
    dev_workspace: Annotated[
        Optional[Path],
        typer.Option(
            "--workspace", "-w",
            help="Developer scratch workspace root (default: ./workspace)",
            exists=False,
        ),
    ] = None,
    extra_skills: Annotated[
        Optional[Path],
        typer.Option(
            "--extra-skills",
            help="Additional directory to scan for existing skills",
            exists=False,
        ),
    ] = None,
    user_id: Annotated[
        str,
        typer.Option("--user", "-u", help="User identifier stored in audit context"),
    ] = "",
) -> None:
    """[bold]Start a developer-role chat session.[/bold]

    Loads the [cyan]skill-developer[/cyan] meta-skill so you can create, edit,
    and manage skills through conversation.
    Use [bold]--skill <name>[/bold] to resume a previous skill-development session.

    [dim]Type  exit / quit / Ctrl-D  to end the session.[/dim]
    """
    chat(
        role="developer",
        skill=skill,
        model=model,
        skills_dir=skills_dir,
        dev_workspace=dev_workspace,
        extra_skills=extra_skills,
        session_id="",
        user_id=user_id,
    )
