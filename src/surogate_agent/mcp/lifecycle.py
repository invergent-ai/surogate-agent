"""
MCP server lifecycle — start/stop processes, probe status, fetch tools.
"""

from __future__ import annotations

import asyncio
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from surogate_agent.core.logging import get_logger

if TYPE_CHECKING:
    from surogate_agent.mcp.registry import McpServerEntry, MCPRegistry

log = get_logger(__name__)

# Global process registry: name → Popen (local SSE daemon processes only)
_PROCESSES: dict[str, subprocess.Popen] = {}


@dataclass
class _StdioServer:
    """Tracks a running persistent stdio MCP session."""
    task: asyncio.Task
    tools: list = field(default_factory=list)  # cached LangChain tools
    stop_event: asyncio.Event = field(default_factory=asyncio.Event)


# Global stdio session registry: name → _StdioServer
_STDIO_SERVERS: dict[str, _StdioServer] = {}


def _unwrap_exc(exc: BaseException | None) -> str:
    """Return a human-readable string from a possibly-wrapped exception.

    ExceptionGroup (raised by anyio TaskGroup) buries the real error one level
    deep.  Unwrap recursively to find the first leaf message.
    """
    if exc is None:
        return "unknown error"
    if isinstance(exc, BaseExceptionGroup) and exc.exceptions:
        return _unwrap_exc(exc.exceptions[0])
    return str(exc)


async def _stdio_session_task(
    name: str,
    client,
    ready_event: asyncio.Event,
    stop_event: asyncio.Event,
    tools_holder: list,
    error_holder: list,
) -> None:
    """Background task that keeps a stdio MCP server process alive via a persistent session.

    Opens ``client.session(name)`` (which spawns the process and holds stdin/stdout open),
    loads LangChain tools, signals ready, then waits until ``stop_event`` is set or the
    task is cancelled — whichever comes first.
    """
    from langchain_mcp_adapters.tools import load_mcp_tools
    try:
        async with client.session(name) as session:
            tools = await load_mcp_tools(session)
            for t in tools:
                _patch_mcp_tool(t)
            tools_holder.extend(tools)
            log.info("stdio session %r ready — %d tool(s)", name, len(tools))
            ready_event.set()
            await stop_event.wait()
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        log.warning("stdio session %r failed: %s", name, _unwrap_exc(exc))
        error_holder.append(exc)
        if not ready_event.is_set():
            ready_event.set()


async def probe_url(url: str, name: str = "probe", timeout: float = 8.0) -> tuple[str, list]:
    """Auto-detect MCP transport for a URL by sequentially probing each transport.

    Always probes streamable HTTP first, then SSE — regardless of URL shape.

    SSE gets a 2× timeout budget because it requires two round-trips (GET to
    establish the event stream, then POST initialize + list_tools over that
    stream).  When the HTTP probe opens a streaming connection that doesn't
    cleanly close, a 1 s drain gives the event loop time to flush close
    handlers before the SSE probe starts.

    Returns ``(transport, tools)`` — transport is ``'http'`` or ``'sse'``,
    tools is the list of patched LangChain tool objects.
    """
    # (transport_key, langchain_transport, per-probe timeout)
    probes = [
        ("http", "streamable_http", timeout),
        ("sse", "sse", timeout * 2),
    ]

    last_error: Exception | None = None

    for i, (transport_key, lc_transport, probe_timeout) in enumerate(probes):
        if i > 0:
            # Give the event loop time to flush close-handlers from any
            # streaming connection opened by the previous probe (SSE or
            # chunked HTTP).  0.2 s is too tight when the server keeps the
            # stream open until the client drops it.
            await asyncio.sleep(1.0)
        try:
            from langchain_mcp_adapters.client import MultiServerMCPClient
            client = MultiServerMCPClient({name: {"url": url, "transport": lc_transport}})
            tools = await asyncio.wait_for(client.get_tools(), timeout=probe_timeout)
            for t in tools:
                _patch_mcp_tool(t)
            if tools:
                log.info("probe_url: %r → %s (%d tool(s))", url, transport_key, len(tools))
                return transport_key, tools
            # 0 tools is treated as a failed probe — the endpoint is reachable
            # but not speaking the expected MCP protocol (e.g. streamable HTTP
            # hitting a plain SSE endpoint).  Keep trying the next transport.
            log.debug("probe_url: %r %s returned 0 tools — treating as failure", url, transport_key)
            last_error = RuntimeError(f"{transport_key}: connected but returned 0 tools")
        except asyncio.TimeoutError as exc:
            log.debug("probe_url: %r %s timed out after %.1fs", url, transport_key, probe_timeout)
            last_error = exc
        except Exception as exc:
            log.debug("probe_url: %r %s failed: %s", url, transport_key, _unwrap_exc(exc))
            last_error = exc

    cause = _unwrap_exc(last_error) if last_error else "all transports failed"
    msg = f"Could not retrieve tools from {url!r}: {cause}"
    log.warning("probe_url: %s", msg)
    raise RuntimeError(msg) from last_error


def _patch_mcp_tool(tool) -> None:
    """Patch an MCP tool in-place to strip None kwargs before sending to the MCP server.

    The LLM frequently emits `null` for optional parameters.  The MCP server
    validates arguments server-side (e.g. FastMCP/Pydantic) and rejects None
    for fields it considers required, raising a ToolException.  Stripping None
    values before the call reaches the server prevents the error entirely and
    avoids the retry loop that `handle_tool_error=True` would otherwise trigger.
    """
    original_coroutine = tool.coroutine
    if original_coroutine is None:
        return

    async def _none_stripped_coroutine(**kwargs):
        clean = {k: v for k, v in kwargs.items() if v is not None}
        log.debug("MCP tool %r: stripped %d None arg(s)", tool.name, len(kwargs) - len(clean))
        return await original_coroutine(**clean)

    tool.coroutine = _none_stripped_coroutine


def _stdio_cmd(mcp_dir: Path, entry: "McpServerEntry") -> list[str]:
    """Return the command parts for a stdio MCP server."""
    script_path = mcp_dir / entry.name / "start.sh"
    if script_path.exists():
        return ["bash", str(script_path)]
    if entry.start_command:
        return shlex.split(entry.start_command)
    raise ValueError(f"No start.sh and no start_command for stdio server '{entry.name}'")


class MCPLifecycle:
    def __init__(self, mcp_dir: Path) -> None:
        self._mcp_dir = Path(mcp_dir)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self, entry: "McpServerEntry") -> str:
        """Return 'running' or 'stopped'.

        - stdio: 'running' when a persistent session task is alive.
        - local SSE (no repo_url): HTTP-ping the daemon.
        - remote SSE / HTTP: 'stopped' when disabled; HTTP-ping otherwise.
        """
        if entry.transport == "stdio":
            server = _STDIO_SERVERS.get(entry.name)
            running = server is not None and not server.task.done()
            status = "running" if running else "stopped"
            log.debug("MCPLifecycle.get_status: stdio %r → %s", entry.name, status)
            return status
        # sse or http
        if not entry.enabled:
            log.debug("MCPLifecycle.get_status: %s %r → stopped (disabled)", entry.transport, entry.name)
            return "stopped"
        status = self._ping_http(entry)
        log.debug("MCPLifecycle.get_status: %s %r → %s", entry.transport, entry.name, status)
        return status

    def _ping_http(self, entry: "McpServerEntry") -> str:
        import urllib.request
        import urllib.error

        if entry.repo_url:
            url = entry.repo_url
        else:
            scheme = "https" if entry.port == 443 else "http"
            port_suffix = f":{entry.port}" if entry.port not in (80, 443) else ""
            url = f"{scheme}://{entry.host}{port_suffix}"

        try:
            log.debug("MCPLifecycle._ping_http: GET %s", url)
            with urllib.request.urlopen(
                urllib.request.Request(url, method="GET"), timeout=2
            ):
                pass
            log.debug("MCPLifecycle._ping_http: %s responded → running", url)
            return "running"
        except urllib.error.HTTPError:
            log.debug("MCPLifecycle._ping_http: %s HTTP error → running", url)
            return "running"
        except Exception as exc:
            log.debug("MCPLifecycle._ping_http: %s unreachable: %s", url, exc)
            return "stopped"

    # ------------------------------------------------------------------
    # stdio persistent sessions
    # ------------------------------------------------------------------

    async def start_stdio_server(self, entry: "McpServerEntry") -> list:
        """Start a persistent stdio MCP session and return LangChain tools.

        If an existing live session is already running, returns its cached tools
        without spawning a new process.  On success the process stays alive for
        the lifetime of the server (or until ``stop_stdio_server`` is called).
        """
        existing = _STDIO_SERVERS.get(entry.name)
        if existing and not existing.task.done():
            log.debug("start_stdio_server: %r already running", entry.name)
            return list(existing.tools)

        # Clean up dead entry if present
        if entry.name in _STDIO_SERVERS:
            del _STDIO_SERVERS[entry.name]

        try:
            from langchain_mcp_adapters.client import MultiServerMCPClient
        except ImportError as exc:
            raise RuntimeError("langchain-mcp-adapters is not installed") from exc

        cmd_parts = _stdio_cmd(self._mcp_dir, entry)
        client = MultiServerMCPClient({
            entry.name: {
                "command": cmd_parts[0],
                "args": cmd_parts[1:],
                "transport": "stdio",
            }
        })

        ready_event: asyncio.Event = asyncio.Event()
        stop_event: asyncio.Event = asyncio.Event()
        tools_holder: list = []
        error_holder: list = []

        log.info("start_stdio_server: launching %r — %s", entry.name, " ".join(cmd_parts))
        task = asyncio.create_task(
            _stdio_session_task(entry.name, client, ready_event, stop_event, tools_holder, error_holder)
        )

        try:
            await asyncio.wait_for(asyncio.shield(ready_event.wait()), timeout=30)
        except asyncio.TimeoutError:
            task.cancel()
            raise RuntimeError(f"stdio server '{entry.name}' did not start within 30 s")

        if error_holder:
            task.cancel()
            raise error_holder[0]

        _STDIO_SERVERS[entry.name] = _StdioServer(
            task=task,
            tools=list(tools_holder),
            stop_event=stop_event,
        )
        return list(tools_holder)

    async def stop_stdio_server(self, entry: "McpServerEntry") -> None:
        """Shut down the persistent stdio session for ``entry``."""
        server = _STDIO_SERVERS.pop(entry.name, None)
        if server is None:
            log.debug("stop_stdio_server: %r was not running", entry.name)
            return
        log.info("stop_stdio_server: stopping %r", entry.name)
        server.stop_event.set()
        server.task.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(server.task), timeout=5)
        except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
            pass

    # ------------------------------------------------------------------
    # SSE daemon (local process)
    # ------------------------------------------------------------------

    def start_server(self, entry: "McpServerEntry") -> subprocess.Popen:
        """Start a local SSE daemon process and track it."""
        if entry.transport != "sse":
            raise ValueError(f"start_server is only for SSE servers; '{entry.name}' is {entry.transport}")

        script_path = self._mcp_dir / entry.name / "start.sh"
        cwd = entry.cwd or str(self._mcp_dir / entry.name)
        if script_path.exists():
            cmd = ["bash", str(script_path)]
        elif entry.start_command:
            cmd = shlex.split(entry.start_command)
        else:
            raise ValueError(f"No start.sh and no start_command for MCP server '{entry.name}'")

        log.info("starting SSE MCP server %r: %s", entry.name, " ".join(cmd))
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _PROCESSES[entry.name] = proc
        return proc

    def wait_for_running(self, entry: "McpServerEntry", attempts: int = 8, delay: float = 0.5) -> str:
        """Poll status after start, retrying until running or exhausted."""
        import time
        log.debug("MCPLifecycle.wait_for_running: polling %r", entry.name)
        for i in range(attempts):
            status = self.get_status(entry)
            if status == "running":
                log.info("MCPLifecycle.wait_for_running: %r running after %d poll(s)", entry.name, i + 1)
                return "running"
            log.debug("wait_for_running: attempt %d/%d → %s", i + 1, attempts, status)
            time.sleep(delay)
        final = self.get_status(entry)
        log.warning("wait_for_running: %r still %r after %d attempts", entry.name, final, attempts)
        return final

    # ------------------------------------------------------------------
    # Bulk start / stop (called from app lifespan)
    # ------------------------------------------------------------------

    async def start_all(self, registry: "MCPRegistry") -> None:
        """Start all servers that should be running at server boot.

        - Local SSE servers (transport=sse, no repo_url, enabled): spawn daemon.
        - stdio servers (enabled): start persistent session.
        - Remote SSE / HTTP: no action — availability determined by HTTP ping.
        """
        all_entries = registry.list()
        sse_entries = [e for e in all_entries if e.transport == "sse" and not e.repo_url and e.enabled]
        stdio_entries = [e for e in all_entries if e.transport == "stdio" and e.enabled]
        log.info(
            "MCPLifecycle.start_all: %d total — %d local SSE, %d stdio to start",
            len(all_entries), len(sse_entries), len(stdio_entries),
        )

        for entry in sse_entries:
            if self.get_status(entry) == "running":
                log.debug("start_all: SSE %r already running", entry.name)
                continue
            log.info("start_all: starting SSE server %r", entry.name)
            try:
                self.start_server(entry)
            except Exception as exc:
                log.warning("start_all: failed to start SSE %r: %s", entry.name, exc)

        for entry in stdio_entries:
            if entry.name in _STDIO_SERVERS and not _STDIO_SERVERS[entry.name].task.done():
                log.debug("start_all: stdio %r already running", entry.name)
                continue
            log.info("start_all: starting stdio server %r", entry.name)
            try:
                await self.start_stdio_server(entry)
            except Exception as exc:
                log.warning("start_all: failed to start stdio %r: %s", entry.name, exc)

    async def stop_all(self) -> None:
        """Terminate all tracked SSE daemon processes and stdio sessions."""
        log.info(
            "MCPLifecycle.stop_all: %d SSE process(es), %d stdio session(s)",
            len(_PROCESSES), len(_STDIO_SERVERS),
        )

        # SSE daemon processes
        for name, proc in list(_PROCESSES.items()):
            if proc.poll() is None:
                log.info("stop_all: terminating SSE %r (pid=%d)", name, proc.pid)
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    log.warning("stop_all: %r did not terminate, killing", name)
                    proc.kill()
            del _PROCESSES[name]

        # stdio persistent sessions
        stop_tasks = []
        for name, server in list(_STDIO_SERVERS.items()):
            log.info("stop_all: stopping stdio session %r", name)
            server.stop_event.set()
            server.task.cancel()
            stop_tasks.append(server.task)
        _STDIO_SERVERS.clear()

        if stop_tasks:
            await asyncio.gather(*stop_tasks, return_exceptions=True)

    # ------------------------------------------------------------------
    # Tool retrieval (for chat injection)
    # ------------------------------------------------------------------

    async def get_tools(self, entry: "McpServerEntry") -> list:
        """Return LangChain tools for this MCP server.

        - stdio: returns tools from the live persistent session (no new process).
        - SSE / HTTP: connects to the running daemon / URL.
        """
        try:
            if entry.transport == "stdio":
                server = _STDIO_SERVERS.get(entry.name)
                if server and not server.task.done():
                    log.debug("get_tools: %r — returning %d cached tool(s) from live session", entry.name, len(server.tools))
                    return list(server.tools)
                log.debug("get_tools: stdio %r has no live session — returning empty", entry.name)
                return []

            from langchain_mcp_adapters.client import MultiServerMCPClient

            if entry.transport == "sse":
                url = entry.repo_url if entry.repo_url else f"http://{entry.host}:{entry.port}/sse"
                server_config = {entry.name: {"url": url, "transport": "sse"}}
            else:  # http
                base_url = entry.repo_url if entry.repo_url else f"http://{entry.host}:{entry.port}"
                server_config = {entry.name: {"url": base_url, "transport": "streamable_http"}}

            log.debug("MCPLifecycle.get_tools: connecting to %r (transport=%s)", entry.name, entry.transport)
            client = MultiServerMCPClient(server_config)
            tools = await client.get_tools()
            for tool in tools:
                _patch_mcp_tool(tool)
            log.info("MCPLifecycle.get_tools: %r → %d tool(s)", entry.name, len(tools))
            return tools

        except Exception as exc:
            log.warning("MCPLifecycle.get_tools: failed for %r: %s", entry.name, exc)
            return []
