"""ArchAI CLI - Architecture-aware AI coding assistant.

Provides commands for MCP server integration and project initialization.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import typer

# Suppress noisy litellm pre-load warnings (archai doesn't use litellm directly)
os.environ.setdefault("LITELLM_LOG", "ERROR")

app = typer.Typer(name="archai", help="Architecture-aware AI coding assistant")


def _version_callback(value: bool) -> None:
    if value:
        from importlib.metadata import version

        typer.echo(f"archai-mcp v{version('archai-mcp')}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        help="Show version and exit",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """Architecture-aware AI coding assistant."""
    pass


@app.command()
def mcp():
    """Start ArchAI in MCP server mode (stdio, for AI agents)."""
    from archai.mcp_server import mcp as mcp_app

    mcp_app.run(transport="stdio")


@app.command()
def init(
    project_dir: str = typer.Argument(".", help="Project directory to configure"),
):
    """Initialize archai in a project for OpenCode MCP integration.

    Creates .opencode.json so OpenCode can discover and call
    archai's architecture tools in this project.
    """
    project_path = Path(project_dir).resolve()
    config_file = project_path / ".opencode.json"

    # Read existing config or start fresh
    existing = {}
    if config_file.exists():
        try:
            existing = json.loads(config_file.read_text())
        except (json.JSONDecodeError, OSError):
            existing = {}

    if config_file.exists():
        # Check if archai is already configured
        raw_mcp = existing.get("mcp")
        if raw_mcp is None:
            mcp_config = {}
        elif not isinstance(raw_mcp, dict):
            raise ValueError(
                f"Invalid type for 'mcp' in .opencode.json: expected dict, got {type(raw_mcp).__name__} ({raw_mcp!r})"
            )
        else:
            mcp_config = raw_mcp
        if "archai" in mcp_config:
            typer.echo(
                typer.style(
                    "✓ archai is already configured in this project.",
                    fg="green",
                )
            )
            raise typer.Exit(code=0)

    existing.setdefault("mcp", {})["archai"] = {
        "type": "local",
        "command": ["archai", "mcp"],
        "enabled": True,
    }

    config_file.write_text(json.dumps(existing, indent=2) + "\n")

    typer.echo(typer.style("✓ Configured archai MCP server in .opencode.json", fg="green"))


if __name__ == "__main__":
    app()
