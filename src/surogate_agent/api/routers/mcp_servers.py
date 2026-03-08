"""
MCP server management router — /api/mcp-servers  (developer only)
"""

from __future__ import annotations

import io
import json
import shutil
import zipfile
from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

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
async def add_server(
    body: McpServerCreate,
    settings: ServerSettings = Depends(settings_dep),
    _user: User = Depends(_require_developer),
) -> McpServerResponse:
    from surogate_agent.mcp.lifecycle import probe_url

    transport = body.transport
    probed_tools: list = []

    # When a remote URL is provided, detect transport and fetch tools in one shot.
    if body.repo_url:
        try:
            transport, lc_tools = await probe_url(body.repo_url, name=body.name)
        except RuntimeError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        probed_tools = [
            {"name": t.name, "description": getattr(t, "description", "") or ""}
            for t in lc_tools
        ]
        log.info("probed %r: transport=%s, tools=%d", body.name, transport, len(probed_tools))

    entry = McpServerEntry(
        name=body.name,
        repo_url=body.repo_url,
        start_command=body.start_command,
        cwd=body.cwd,
        transport=transport,
        host=body.host,
        port=body.port,
        tools=probed_tools or [{"name": t.name, "description": t.description} for t in body.tools],
    )

    lifecycle = MCPLifecycle(settings.mcp_scripts_dir)

    registry = MCPRegistry(settings.mcp_scripts_dir)
    registry.add(entry)
    log.info("registered MCP server %r (transport=%s)", entry.name, entry.transport)

    if entry.transport == "stdio":
        # Auto-start: launch persistent session, persist tools, mark enabled.
        try:
            lc_tools = await lifecycle.start_stdio_server(entry)
            if lc_tools:
                entry.tools = [
                    {"name": t.name, "description": getattr(t, "description", "") or ""}
                    for t in lc_tools
                ]
        except Exception as exc:
            log.warning("could not start stdio server %r after registration: %s", entry.name, exc)
        entry.enabled = True
        registry.add(entry)
        status = lifecycle.get_status(entry)
    elif entry.transport == "sse" and not entry.repo_url:
        # Local SSE daemon: spawn process and wait.
        try:
            if lifecycle.get_status(entry) != "running":
                lifecycle.start_server(entry)
        except Exception as exc:
            log.warning("could not start MCP server %r after registration: %s", entry.name, exc)
        status = lifecycle.wait_for_running(entry)
    else:
        # Remote SSE / HTTP: enabled by default, status from HTTP ping.
        status = lifecycle.get_status(entry)

    return _to_response(entry, status)


@router.post("/{name}/start", response_model=McpServerResponse)
async def start_server(
    name: str,
    settings: ServerSettings = Depends(settings_dep),
    _user: User = Depends(_require_developer),
) -> McpServerResponse:
    registry = MCPRegistry(settings.mcp_scripts_dir)
    entry = registry.get(name)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"MCP server '{name}' not found")
    lifecycle = MCPLifecycle(settings.mcp_scripts_dir)

    if entry.transport == "stdio":
        # Start persistent session (or reuse if already running), persist tools.
        try:
            lc_tools = await lifecycle.start_stdio_server(entry)
            if lc_tools:
                entry.tools = [
                    {"name": t.name, "description": getattr(t, "description", "") or ""}
                    for t in lc_tools
                ]
        except Exception as exc:
            log.warning("could not start stdio server %r: %s", name, exc)
            raise HTTPException(status_code=500, detail=f"Failed to start stdio server: {exc}") from exc
        entry.enabled = True
        registry.add(entry)
        log.info("started stdio MCP server %r", name)
        return _to_response(entry, lifecycle.get_status(entry))

    if entry.repo_url or entry.transport == "http":
        # Remote / HTTP server: enable, cache tools, and report live status.
        entry.enabled = True
        registry.add(entry)
        try:
            lc_tools = await lifecycle._fetch_and_cache_http_tools(entry)
            if lc_tools:
                entry.tools = [
                    {"name": t.name, "description": getattr(t, "description", "") or ""}
                    for t in lc_tools
                ]
                registry.add(entry)
        except Exception as exc:
            log.warning("could not fetch tools for %s server %r: %s", entry.transport, name, exc)
        log.info("enabled %s MCP server %r", entry.transport, name)
        return _to_response(entry, lifecycle.get_status(entry))

    # Local SSE server: spawn process.
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
async def stop_server(
    name: str,
    settings: ServerSettings = Depends(settings_dep),
    _user: User = Depends(_require_developer),
) -> McpServerResponse:
    registry = MCPRegistry(settings.mcp_scripts_dir)
    entry = registry.get(name)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"MCP server '{name}' not found")
    lifecycle = MCPLifecycle(settings.mcp_scripts_dir)

    if entry.transport == "stdio":
        await lifecycle.stop_stdio_server(entry)
        entry.enabled = False
        registry.add(entry)
        log.info("stopped stdio MCP server %r", name)
    elif entry.repo_url or entry.transport == "http":
        entry.enabled = False
        registry.add(entry)
        from surogate_agent.mcp.lifecycle import _HTTP_TOOLS
        _HTTP_TOOLS.pop(name, None)
        log.info("disabled %s MCP server %r", entry.transport, name)
    else:
        # Local SSE daemon: kill process.
        from surogate_agent.mcp.lifecycle import _PROCESSES
        proc = _PROCESSES.pop(name, None)
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
        log.info("stopped local SSE MCP server %r", name)

    return _to_response(entry, lifecycle.get_status(entry))


@router.get("/{name}/export")
def export_server(
    name: str,
    settings: ServerSettings = Depends(settings_dep),
    _user: User = Depends(_require_developer),
) -> StreamingResponse:
    """Download a ZIP archive containing everything needed to replicate this MCP server."""
    registry = MCPRegistry(settings.mcp_scripts_dir)
    entry = registry.get(name)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"MCP server '{name}' not found")

    mcp_workspace = settings.mcp_workspace_dir.resolve()
    mcp_scripts = settings.mcp_scripts_dir.resolve()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # meta.json — registry entry + original paths so the importer can patch them
        meta = {
            "mcp_workspace_dir": str(mcp_workspace),
            "mcp_scripts_dir": str(mcp_scripts),
            "registry_entry": asdict(entry),
        }
        zf.writestr("meta.json", json.dumps(meta, indent=2))

        # Everything from mcp_scripts/<name>/
        scripts_dir = mcp_scripts / name
        if scripts_dir.exists():
            for fp in sorted(scripts_dir.rglob("*")):
                if fp.is_file():
                    zf.write(fp, "scripts/" + str(fp.relative_to(scripts_dir)))

        # Workspace probe scripts: mcp_workspace/<name>/
        ws_server_dir = mcp_workspace / name
        if ws_server_dir.exists():
            for fp in sorted(ws_server_dir.rglob("*")):
                if fp.is_file():
                    zf.write(fp, "workspace/" + name + "/" + str(fp.relative_to(ws_server_dir)))

        # Source repo: mcp_workspace/repos/<name>/  (skip .git, __pycache__, *.pyc)
        repo_dir = mcp_workspace / "repos" / name
        if repo_dir.exists():
            for fp in sorted(repo_dir.rglob("*")):
                if (
                    fp.is_file()
                    and ".git" not in fp.parts
                    and "__pycache__" not in fp.parts
                    and fp.suffix != ".pyc"
                ):
                    zf.write(fp, "workspace/repos/" + name + "/" + str(fp.relative_to(repo_dir)))

    buf.seek(0)
    log.info("exporting MCP server %r as ZIP", name)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{name}-mcp-export.zip"'},
    )


@router.post("/import", response_model=McpServerResponse, status_code=201)
async def import_server(
    file: UploadFile = File(...),
    settings: ServerSettings = Depends(settings_dep),
    _user: User = Depends(_require_developer),
) -> McpServerResponse:
    """Import an MCP server from a previously exported ZIP archive."""
    content = await file.read()
    try:
        buf = io.BytesIO(content)
        with zipfile.ZipFile(buf, "r") as zf:
            if "meta.json" not in zf.namelist():
                raise ValueError("missing meta.json — not a valid MCP export")
            meta = json.loads(zf.read("meta.json"))
    except (zipfile.BadZipFile, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid export file: {exc}") from exc

    old_workspace = meta["mcp_workspace_dir"]
    old_scripts = meta["mcp_scripts_dir"]
    new_workspace = str(settings.mcp_workspace_dir.resolve())
    new_scripts = str(settings.mcp_scripts_dir.resolve())

    registry_entry_dict: dict = meta["registry_entry"]
    name: str = registry_entry_dict["name"]

    _TEXT_SUFFIXES = {".sh", ".json", ".py", ".txt", ".md", ".toml", ".cfg", ".yml", ".yaml", ".env"}

    buf = io.BytesIO(content)
    with zipfile.ZipFile(buf, "r") as zf:
        for member in zf.namelist():
            if member == "meta.json" or member.endswith("/"):
                continue

            data = zf.read(member)

            # Patch absolute paths in text files so they point to this server's dirs
            if Path(member).suffix.lower() in _TEXT_SUFFIXES:
                text = data.decode("utf-8", errors="replace")
                text = text.replace(old_workspace, new_workspace)
                text = text.replace(old_scripts, new_scripts)
                data = text.encode("utf-8")

            if member.startswith("scripts/"):
                dest = settings.mcp_scripts_dir / name / member[len("scripts/"):]
            elif member.startswith("workspace/"):
                dest = settings.mcp_workspace_dir / member[len("workspace/"):]
            else:
                continue

            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            if dest.suffix == ".sh":
                dest.chmod(0o755)

    # Patch paths in the registry entry itself
    def _patch(s: str) -> str:
        return s.replace(old_workspace, new_workspace).replace(old_scripts, new_scripts)

    registry_entry_dict["start_command"] = _patch(registry_entry_dict.get("start_command", ""))
    registry_entry_dict["cwd"] = _patch(registry_entry_dict.get("cwd", ""))
    registry_entry_dict["enabled"] = True

    entry = McpServerEntry.from_dict(registry_entry_dict)

    registry = MCPRegistry(settings.mcp_scripts_dir)
    registry.add(entry)
    log.info("imported MCP server %r (transport=%s)", name, entry.transport)

    lifecycle = MCPLifecycle(settings.mcp_scripts_dir)

    if entry.transport == "stdio":
        try:
            lc_tools = await lifecycle.start_stdio_server(entry)
            if lc_tools:
                entry.tools = [
                    {"name": t.name, "description": getattr(t, "description", "") or ""}
                    for t in lc_tools
                ]
                registry.add(entry)
        except Exception as exc:
            log.warning("import: could not start stdio server %r: %s", name, exc)
        status = lifecycle.get_status(entry)
    elif entry.transport == "sse" and not entry.repo_url:
        try:
            if lifecycle.get_status(entry) != "running":
                lifecycle.start_server(entry)
        except Exception as exc:
            log.warning("import: could not start SSE server %r: %s", name, exc)
        status = lifecycle.wait_for_running(entry)
    else:
        # Remote SSE / HTTP: fetch and cache tools so they're available immediately.
        try:
            lc_tools = await lifecycle._fetch_and_cache_http_tools(entry)
            if lc_tools:
                entry.tools = [
                    {"name": t.name, "description": getattr(t, "description", "") or ""}
                    for t in lc_tools
                ]
                registry.add(entry)
        except Exception as exc:
            log.warning("import: could not fetch tools for %r: %s", name, exc)
        status = lifecycle.get_status(entry)

    return _to_response(entry, status)


@router.delete("/{name}")
async def remove_server(
    name: str,
    settings: ServerSettings = Depends(settings_dep),
    _user: User = Depends(_require_developer),
) -> dict:
    registry = MCPRegistry(settings.mcp_scripts_dir)
    entry = registry.get(name)
    if entry is None or not registry.remove(name):
        raise HTTPException(status_code=404, detail=f"MCP server '{name}' not found")

    lifecycle = MCPLifecycle(settings.mcp_scripts_dir)

    # Stop first
    if entry.transport == "stdio":
        await lifecycle.stop_stdio_server(entry)
    else:
        from surogate_agent.mcp.lifecycle import _PROCESSES, _HTTP_TOOLS
        proc = _PROCESSES.pop(name, None)
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
        _HTTP_TOOLS.pop(name, None)

    # Remove scripts directory (start.sh, manifest.json, …)
    script_dir = settings.mcp_scripts_dir / name
    if script_dir.exists():
        shutil.rmtree(script_dir, ignore_errors=True)
        log.debug("removed scripts dir for %r", name)

    # Remove workspace assets: mcp_workspace/<name>/, repos/<name>/, venvs/<name>/
    mcp_workspace = settings.mcp_workspace_dir.resolve()
    for ws_target in (
        mcp_workspace / name,
        mcp_workspace / "repos" / name,
        mcp_workspace / "venvs" / name,
    ):
        if ws_target.exists():
            try:
                shutil.rmtree(ws_target)
                log.info("removed workspace dir %s", ws_target)
            except Exception as exc:
                log.warning("could not remove workspace dir %s: %s", ws_target, exc)

    log.info("removed MCP server %r and all assets", name)
    return {"deleted": name}
