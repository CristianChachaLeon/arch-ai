"""OpenCode adapter — writes .opencode/opencode.toml."""

from __future__ import annotations

from pathlib import Path

import tomli_w

from archai.cli.adapters.base import BaseAgentAdapter


class OpenCodeAdapter(BaseAgentAdapter):
    """Manages MCP config for OpenCode (.opencode/opencode.toml)."""

    def filename(self) -> str:
        return "opencode.toml"

    def config_dir(self) -> Path:
        return self.project_dir / ".opencode"

    def config_path(self) -> Path:
        return self.config_dir() / self.filename()

    def generate_config(self, mcp_command: list[str]) -> dict:
        return {
            "mcp": {
                "archai": {
                    "type": "local",
                    "command": list(mcp_command),
                    "enabled": True,
                }
            }
        }

    def serialize(self, config: dict) -> str:
        return tomli_w.dumps(config)

    def write(self, mcp_command: list[str] | None = None) -> Path | None:
        if mcp_command is None:
            mcp_command = ["archai", "serve"]

        path = self.config_path()
        import tomllib

        existing = {}
        if path.exists():
            try:
                existing = tomllib.loads(path.read_text())
            except Exception:
                existing = {}

        mcp_servers = existing.get("mcp", {})
        if "archai" in mcp_servers:
            return None  # already configured

        config = self.generate_config(mcp_command)
        if existing:
            existing.setdefault("mcp", {})["archai"] = config["mcp"]["archai"]
            content = self.serialize(existing)
        else:
            content = self.serialize(config)

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path
