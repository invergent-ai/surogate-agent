"""
MCP server management router — /api/mcp-servers  (developer only)
"""

from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from surogate_agent.api.deps import ServerSettings, settings_dep
from surogate_agent.api.models import McpServerCreate, McpServerResponse, McpToolInfo
from surogate_agent.auth.jwt import get_current_user
from surogate_agent.auth.models import User
from surogate_agent.core.logging import get_logger
from surogate_agent.mcp.lifecycle import MCPLifecycle
from surogate_agent.mcp.registry import MCPRegistry, McpServerEntry

log = get_logger(__name__)

router = APIRouter(prefix="/mcp-servers", tags=["mcp-servers"])


def _require_developer(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "developer":
        raise HTTPException(status_code=403, detail="Developer role required")
    return current_user


def _to_response(entry: McpServerEntry, status: str) -> McpServerResponse:
    return McpServerResponse(
        name=entry.name,
        repo_url=entry.repo_url,
        start_command=entry.start_command,
        cwd=entry.cwd,
        transport=entry.transport,
        host=entry.host,
        port=entry.port,
        tools=[McpToolInfo(name=t.get("name", ""), description=t.get("description", "")) for t in entry.tools],
        registered_at=entry.registered_at,
        status=status,
    )


@router.get("", response_model=list[McpServerResponse])
def list_servers(
    settings: ServerSettings = Depends(settings_dep),
    _user: User = Depends(_require_developer),
) -> list[McpServerResponse]:
    registry = MCPRegistry(settings.mcp_scripts_dir)
    lifecycle = MCPLifecycle(settings.mcp_scripts_dir)
    return [_to_response(e, lifecycle.get_status(e)) for e in registry.list()]


@router.get("/{name}", response_model=McpServerResponse)
def get_server(
    name: str,
    settings: ServerSettings = Depends(settings_dep),
    _user: User = Depends(_require_developer),
) -> McpServerResponse:
    registry = MCPRegistry(settings.mcp_scripts_dir)
    entry = registry.get(name)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"MCP server '{name}' not found")
    lifecycle = MCPLifecycle(settings.mcp_scripts_dir)
    return _to_response(entry, lifecycle.get_status(entry))


@router.post("", response_model=McpServerResponse, status_code=201)
def add_server(
    body: McpServerCreate,
    settings: ServerSettings = Depends(settings_dep),
    _user: User = Depends(_require_developer),
) -> McpServerResponse:
    registry = MCPRegistry(settings.mcp_scripts_dir)
    entry = McpServerEntry(
        name=body.name,
        repo_url=body.repo_url,
        start_command=body.start_command,
        cwd=body.cwd,
        transport=body.transport,
        host=body.host,
        port=body.port,
        tools=[{"name": t.name, "description": t.description} for t in body.tools],
    )
    registry.add(entry)
    log.info("registered MCP server %r", entry.name)

    # Attempt to auto-start SSE servers (stdio are spawned on demand — no daemon needed)
    lifecycle = MCPLifecycle(settings.mcp_scripts_dir)
    if entry.transport == "sse":
        try:
            if lifecycle.get_status(entry) != "running":
                lifecycle.start_server(entry)
        except Exception as exc:
            log.warning("could not start MCP server %r after registration: %s", entry.name, exc)

    status = lifecycle.wait_for_running(entry) if entry.transport == "sse" else lifecycle.get_status(entry)
    return _to_response(entry, status)


@router.post("/{name}/start", response_model=McpServerResponse)
def start_server(
    name: str,
    settings: ServerSettings = Depends(settings_dep),
    _user: User = Depends(_require_developer),
) -> McpServerResponse:
    registry = MCPRegistry(settings.mcp_scripts_dir)
    entry = registry.get(name)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"MCP server '{name}' not found")
    lifecycle = MCPLifecycle(settings.mcp_scripts_dir)

    # stdio servers are spawned on demand — no persistent daemon to start
    if entry.transport != "sse":
        return _to_response(entry, lifecycle.get_status(entry))

    if lifecycle.get_status(entry) == "running":
        return _to_response(entry, "running")
    try:
        lifecycle.start_server(entry)
    except Exception as exc:
        log.warning("could not start MCP server %r: %s", name, exc)
        raise HTTPException(status_code=500, detail=f"Failed to start server: {exc}") from exc
    status = lifecycle.wait_for_running(entry)
    return _to_response(entry, status)


@router.post("/{name}/stop", response_model=McpServerResponse)
def stop_server(
    name: str,
    settings: ServerSettings = Depends(settings_dep),
    _user: User = Depends(_require_developer),
) -> McpServerResponse:
    registry = MCPRegistry(settings.mcp_scripts_dir)
    entry = registry.get(name)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"MCP server '{name}' not found")

    from surogate_agent.mcp.lifecycle import _PROCESSES
    proc = _PROCESSES.pop(name, None)
    if proc is not None and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        log.info("stopped MCP server %r", name)

    lifecycle = MCPLifecycle(settings.mcp_scripts_dir)
    status = lifecycle.get_status(entry)
    return _to_response(entry, status)


@router.delete("/{name}")
def remove_server(
    name: str,
    settings: ServerSettings = Depends(settings_dep),
    _user: User = Depends(_require_developer),
) -> dict:
    registry = MCPRegistry(settings.mcp_scripts_dir)
    if not registry.remove(name):
        raise HTTPException(status_code=404, detail=f"MCP server '{name}' not found")

    # Stop the process if running
    from surogate_agent.mcp.lifecycle import _PROCESSES
    proc = _PROCESSES.pop(name, None)
    if proc is not None and proc.poll() is None:
        proc.terminate()

    # Remove scripts directory
    script_dir = settings.mcp_scripts_dir / name
    if script_dir.exists():
        shutil.rmtree(script_dir, ignore_errors=True)

    log.info("removed MCP server %r", name)
    return {"deleted": name}
