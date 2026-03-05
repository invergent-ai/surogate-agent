"""
MCP server registry — persists registered server entries to registry.json.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from surogate_agent.core.logging import get_logger

log = get_logger(__name__)


@dataclass
class McpServerEntry:
    name: str
    repo_url: str
    start_command: str
    cwd: str
    transport: str  # "sse" | "stdio"
    host: str
    port: int
    tools: list[dict] = field(default_factory=list)  # [{"name": ..., "description": ...}]
    registered_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @classmethod
    def from_dict(cls, d: dict) -> "McpServerEntry":
        return cls(
            name=d["name"],
            repo_url=d.get("repo_url", ""),
            start_command=d.get("start_command", ""),
            cwd=d.get("cwd", ""),
            transport=d.get("transport", "sse"),
            host=d.get("host", "localhost"),
            port=int(d.get("port", 8101)),
            tools=d.get("tools", []),
            registered_at=d.get("registered_at", datetime.now(timezone.utc).isoformat()),
        )


class MCPRegistry:
    """Read/write MCP server entries from/to registry.json."""

    def __init__(self, mcp_dir: Path) -> None:
        self._mcp_dir = Path(mcp_dir)
        self._registry_path = self._mcp_dir / "registry.json"

    def _load(self) -> list[McpServerEntry]:
        if not self._registry_path.exists():
            log.debug("MCPRegistry: registry.json not found at %s", self._registry_path)
            return []
        try:
            data = json.loads(self._registry_path.read_text())
            entries = [McpServerEntry.from_dict(d) for d in data]
            log.debug("MCPRegistry: loaded %d server(s) from %s", len(entries), self._registry_path)
            return entries
        except Exception as exc:
            log.warning("MCPRegistry: failed to parse registry.json: %s", exc)
            return []

    def _save(self, entries: list[McpServerEntry]) -> None:
        self._mcp_dir.mkdir(parents=True, exist_ok=True)
        self._registry_path.write_text(
            json.dumps([asdict(e) for e in entries], indent=2)
        )
        log.debug("MCPRegistry: saved %d server(s) to %s", len(entries), self._registry_path)

    def list(self) -> list[McpServerEntry]:
        entries = self._load()
        log.debug("MCPRegistry.list: returning %d server(s)", len(entries))
        return entries

    def get(self, name: str) -> Optional[McpServerEntry]:
        entry = next((e for e in self._load() if e.name == name), None)
        if entry is None:
            log.debug("MCPRegistry.get: server %r not found", name)
        else:
            log.debug("MCPRegistry.get: found server %r (transport=%s)", name, entry.transport)
        return entry

    def add(self, entry: McpServerEntry) -> None:
        """Upsert by name."""
        entries = [e for e in self._load() if e.name != entry.name]
        entries.append(entry)
        self._save(entries)
        log.info("MCPRegistry.add: upserted server %r (transport=%s, tools=%d)", entry.name, entry.transport, len(entry.tools))

    def remove(self, name: str) -> bool:
        entries = self._load()
        filtered = [e for e in entries if e.name != name]
        if len(filtered) == len(entries):
            log.debug("MCPRegistry.remove: server %r not found", name)
            return False
        self._save(filtered)
        log.info("MCPRegistry.remove: removed server %r", name)
        return True
