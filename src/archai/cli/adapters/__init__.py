"""Agent adapters for `archai init` multi-CLI support."""

from __future__ import annotations

from pathlib import Path

import typer

from archai.cli.adapters.base import BaseAgentAdapter
from archai.cli.adapters.claude import ClaudeCodeAdapter
from archai.cli.adapters.cursor import CursorAdapter
from archai.cli.adapters.gemini import GeminiCliAdapter
from archai.cli.adapters.opencode import OpenCodeAdapter

__all__ = [
    "BaseAgentAdapter",
    "OpenCodeAdapter",
    "GeminiCliAdapter",
    "ClaudeCodeAdapter",
    "CursorAdapter",
]

AGENT_MAP: dict[str, type[BaseAgentAdapter]] = {
    "opencode": OpenCodeAdapter,
    "gemini": GeminiCliAdapter,
    "claude": ClaudeCodeAdapter,
    "cursor": CursorAdapter,
}


def resolve_adapters(agent: str, project_dir: Path) -> list[BaseAgentAdapter]:
    """Resolve agent name(s) to adapter instances."""
    if agent == "all":
        return [cls(project_dir) for cls in AGENT_MAP.values()]
    if agent not in AGENT_MAP:
        msg = f"Unknown agent: {agent!r}. Choose from {', '.join(AGENT_MAP)}"
        raise typer.BadParameter(msg)
    return [AGENT_MAP[agent](project_dir)]
