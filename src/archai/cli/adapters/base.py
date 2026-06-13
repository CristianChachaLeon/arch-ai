"""Abstract base class for agent adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class BaseAgentAdapter(ABC):
    """Generates and writes MCP configuration for a specific AI coding agent."""

    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir

    @abstractmethod
    def config_path(self) -> Path:
        """Full path to the config file this adapter manages."""

    @abstractmethod
    def generate_config(self, mcp_command: list[str]) -> dict:
        """Return the full config dict for this agent."""

    @abstractmethod
    def serialize(self, config: dict) -> str:
        """Serialize config dict to the agent's config format (JSON, TOML, etc)."""

    def write(self, mcp_command: list[str] | None = None) -> Path | None:
        """Generate, merge, and write config. Returns path or None if skipped."""
        raise NotImplementedError
