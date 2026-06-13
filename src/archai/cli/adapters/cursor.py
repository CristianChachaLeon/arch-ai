"""Cursor adapter — writes .cursor/mcp.json with mcpServers."""

from __future__ import annotations

import json
from pathlib import Path

from archai.cli.adapters.base import BaseAgentAdapter


class CursorAdapter(BaseAgentAdapter):
    """Manages MCP config for Cursor (.cursor/mcp.json)."""

    def filename(self) -> str:
        return "mcp.json"

    def config_dir(self) -> Path:
        return self.project_dir / ".cursor"

    def config_path(self) -> Path:
        return self.config_dir() / self.filename()

    def generate_config(self, mcp_command: list[str]) -> dict:
        return {
            "mcpServers": {
                "archai": {
                    "command": mcp_command[0],
                    "args": list(mcp_command[1:]),
                }
            }
        }

    def serialize(self, config: dict) -> str:
        return json.dumps(config, indent=2) + "\n"

    def write(self, mcp_command: list[str] | None = None) -> Path | None:
        if mcp_command is None:
            mcp_command = ["archai", "serve"]

        path = self.config_path()
        existing: dict = {}
        if path.exists():
            try:
                existing = json.loads(path.read_text())
            except (json.JSONDecodeError, OSError):
                existing = {}

        existing.setdefault("mcpServers", {})["archai"] = {
            "command": mcp_command[0],
            "args": list(mcp_command[1:]),
        }

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.serialize(existing))
        return path
