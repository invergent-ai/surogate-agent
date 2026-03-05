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
        if entry.transport == "sse":
            status = self._ping_http(entry)
            log.debug("MCPLifecycle.get_status: SSE server %r → %s", entry.name, status)
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
        for path in ("/sse", "/"):
            try:
                url = f"http://{entry.host}:{entry.port}{path}"
                log.debug("MCPLifecycle._ping_http: GET %s", url)
                with urllib.request.urlopen(
                    urllib.request.Request(url, method="GET"), timeout=1
                ):
                    pass
                log.debug("MCPLifecycle._ping_http: %s responded → running", url)
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
            raise ValueError(f"start_server is only for SSE servers; '{entry.name}' is stdio")

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
        """Start all registered SSE servers that aren't already running.
        stdio servers are not started as daemons — they are spawned on demand.
        """
        all_entries = registry.list()
        sse_entries = [e for e in all_entries if e.transport == "sse"]
        log.info("MCPLifecycle.start_all: %d total server(s), %d SSE", len(all_entries), len(sse_entries))
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
                url = f"http://{entry.host}:{entry.port}/sse"
                server_config = {entry.name: {"url": url, "transport": "sse"}}
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
