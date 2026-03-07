"""
MCP server lifecycle — start/stop processes, probe status, fetch tools.
"""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from surogate_agent.core.logging import get_logger

if TYPE_CHECKING:
    from surogate_agent.mcp.registry import McpServerEntry, MCPRegistry

log = get_logger(__name__)

# Global process registry: name → Popen (SSE daemon processes only)
_PROCESSES: dict[str, subprocess.Popen] = {}


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
    import asyncio

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


class MCPLifecycle:
    def __init__(self, mcp_dir: Path) -> None:
        self._mcp_dir = Path(mcp_dir)

    def get_status(self, entry: "McpServerEntry") -> str:
        """Return 'running', 'stopped', or 'available'.

        - SSE servers: HTTP-ping the /sse endpoint.
        - stdio servers: 'available' if the start script exists, 'stopped' otherwise.
          (stdio has no persistent daemon to ping.)
        """
        if entry.transport in ("sse", "http"):
            status = self._ping_http(entry)
            log.debug("MCPLifecycle.get_status: %s server %r → %s", entry.transport, entry.name, status)
            return status
        # stdio — no persistent daemon; report available when start script exists
        script_path = self._mcp_dir / entry.name / "start.sh"
        status = "available" if script_path.exists() else "stopped"
        log.debug(
            "MCPLifecycle.get_status: stdio server %r → %s (start.sh %s)",
            entry.name, status, "found" if script_path.exists() else "missing",
        )
        return status

    def _ping_http(self, entry: "McpServerEntry") -> str:
        import urllib.request
        import urllib.error

        # Use repo_url as the canonical URL when available (exact URL, no path mangling).
        # Fall back to constructing from host/port with the correct scheme.
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
            # Any HTTP error (405, 404, …) still means the server is reachable.
            log.debug("MCPLifecycle._ping_http: %s HTTP error → running", url)
            return "running"
        except Exception as exc:
            log.debug("MCPLifecycle._ping_http: %s unreachable: %s", url, exc)
            return "stopped"

    def start_server(self, entry: "McpServerEntry") -> subprocess.Popen:
        """Start an SSE server process and track it.

        Only meaningful for SSE servers (stdio servers are spawned on demand).
        Raises ValueError for stdio transport.
        """
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

        log.info("starting MCP server %r: %s", entry.name, " ".join(cmd))
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
        log.debug("MCPLifecycle.wait_for_running: polling %r (attempts=%d, delay=%.1fs)", entry.name, attempts, delay)
        for i in range(attempts):
            status = self.get_status(entry)
            if status == "running":
                log.info("MCPLifecycle.wait_for_running: %r is running after %d poll(s)", entry.name, i + 1)
                return "running"
            log.debug("MCPLifecycle.wait_for_running: attempt %d/%d → %s, retrying…", i + 1, attempts, status)
            time.sleep(delay)
        final = self.get_status(entry)
        log.warning("MCPLifecycle.wait_for_running: %r still %r after %d attempts", entry.name, final, attempts)
        return final

    def start_all(self, registry: "MCPRegistry") -> None:
        """Start all registered local SSE servers that aren't already running.

        Remote servers (those with a repo_url set) and stdio servers are not
        started as daemons — remote ones are already running externally, and
        stdio ones are spawned on demand.
        """
        all_entries = registry.list()
        # Only local SSE servers need a daemon; remote ones (repo_url set) are external.
        sse_entries = [e for e in all_entries if e.transport == "sse" and not e.repo_url]
        log.info("MCPLifecycle.start_all: %d total server(s), %d local SSE", len(all_entries), len(sse_entries))
        for entry in sse_entries:
            status = self.get_status(entry)
            if status == "running":
                log.debug("MCPLifecycle.start_all: %r already running, skipping", entry.name)
                continue
            log.info("MCPLifecycle.start_all: starting SSE server %r (currently %s)", entry.name, status)
            try:
                self.start_server(entry)
            except Exception as exc:
                log.warning("MCPLifecycle.start_all: failed to start %r: %s", entry.name, exc)

    def stop_all(self) -> None:
        """Terminate all tracked SSE server processes."""
        log.info("MCPLifecycle.stop_all: stopping %d tracked process(es)", len(_PROCESSES))
        for name, proc in list(_PROCESSES.items()):
            if proc.poll() is None:
                log.info("MCPLifecycle.stop_all: terminating %r (pid=%d)", name, proc.pid)
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                    log.debug("MCPLifecycle.stop_all: %r terminated cleanly", name)
                except subprocess.TimeoutExpired:
                    log.warning("MCPLifecycle.stop_all: %r did not terminate, killing", name)
                    proc.kill()
            else:
                log.debug("MCPLifecycle.stop_all: %r was already dead (exit=%d)", name, proc.returncode)
            del _PROCESSES[name]

    async def get_tools(self, entry: "McpServerEntry") -> list:
        """Return LangChain tools for this MCP server (requires langchain-mcp-adapters).

        For SSE servers: connects to the running HTTP daemon.
        For stdio servers: spawns the process briefly, lists tools, then exits.
        """
        try:
            from langchain_mcp_adapters.client import MultiServerMCPClient

            if entry.transport == "sse":
                # For remote SSE servers use repo_url directly; for local ones construct from host:port.
                url = entry.repo_url if entry.repo_url else f"http://{entry.host}:{entry.port}/sse"
                server_config = {entry.name: {"url": url, "transport": "sse"}}
            elif entry.transport == "http":
                # Streamable HTTP transport — use repo_url if set, else construct from host:port.
                base_url = entry.repo_url if entry.repo_url else f"http://{entry.host}:{entry.port}"
                server_config = {entry.name: {"url": base_url, "transport": "streamable_http"}}
            else:
                # stdio — spawn via start.sh
                script_path = self._mcp_dir / entry.name / "start.sh"
                if script_path.exists():
                    cmd_parts = ["bash", str(script_path)]
                else:
                    cmd_parts = shlex.split(entry.start_command)
                server_config = {
                    entry.name: {
                        "command": cmd_parts[0],
                        "args": cmd_parts[1:],
                        "transport": "stdio",
                    }
                }

            log.debug("MCPLifecycle.get_tools: probing %r (transport=%s)", entry.name, entry.transport)
            # langchain-mcp-adapters >=0.1.0: no context manager; get_tools() is async.
            client = MultiServerMCPClient(server_config)
            tools = await client.get_tools()
            for tool in tools:
                _patch_mcp_tool(tool)
            log.info("MCPLifecycle.get_tools: %r → %d tool(s)", entry.name, len(tools))
            return tools

        except Exception as exc:
            log.warning("MCPLifecycle.get_tools: failed for %r: %s", entry.name, exc)
            return []
