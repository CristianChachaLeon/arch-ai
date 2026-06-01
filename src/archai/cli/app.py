"""ArchAI CLI - Architecture-aware AI coding assistant.

Provides commands for processing repositories, querying architecture context,
and validating changes.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import typer

app = typer.Typer(name="archai", help="Architecture-aware AI coding assistant")


def _run_async(coro):
    """Run an async coroutine from a sync context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


@app.command()
def start(
    repo_path: str = typer.Argument(None, help="Repository path (default: cwd)"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Process a repository through the full ArchAI pipeline."""
    from archai.cli.output import format_process_result
    from archai.config import detect_repo_root
    from archai.inference.llm.litellm_provider import LiteLLMProvider
    from archai.middleware.pipeline import ArchaiMiddleware

    resolved = repo_path or detect_repo_root()

    model = os.environ.get("ARCHAI_LLM_MODEL")
    api_base = os.environ.get("ARCHAI_LLM_API_BASE")
    api_key = os.environ.get("ARCHAI_LLM_API_KEY")
    llm_provider = (
        LiteLLMProvider(model=model, api_base=api_base, api_key=api_key) if model else None
    )

    middleware = ArchaiMiddleware(llm_provider=llm_provider)

    async def _process():
        result = await middleware.process(resolved)
        return result.to_dict()

    try:
        data = _run_async(_process())
        output = format_process_result(data, json_output)
        if output:
            typer.echo(output)
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)


@app.command()
def ask(
    query: str = typer.Argument(..., help="Question about the architecture"),
    repo_path: str = typer.Argument(None, help="Repository path (default: cwd)"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Ask a question about the repository architecture."""
    from archai.cli.output import format_context_packet
    from archai.config import detect_repo_root
    from archai.inference.llm.litellm_provider import LiteLLMProvider
    from archai.middleware.pipeline import ArchaiMiddleware
    from archai.orchestrator.orchestrator import ArchaiOrchestrator

    resolved = repo_path or detect_repo_root()

    model = os.environ.get("ARCHAI_LLM_MODEL")
    api_base = os.environ.get("ARCHAI_LLM_API_BASE")
    api_key = os.environ.get("ARCHAI_LLM_API_KEY")
    llm_provider = (
        LiteLLMProvider(model=model, api_base=api_base, api_key=api_key) if model else None
    )

    middleware = ArchaiMiddleware(llm_provider=llm_provider)
    orchestrator = ArchaiOrchestrator(middleware)

    async def _get_context():
        return await orchestrator.get_context(query, resolved)

    try:
        packet = _run_async(_get_context())
        typer.echo(format_context_packet(packet, json_output))
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)


@app.command()
def mcp():
    """Start ArchAI in MCP server mode (stdio, for AI agents)."""
    from archai.mcp_server import mcp as mcp_app

    mcp_app.run(transport="stdio")


@app.command()
def init(
    project_dir: str = typer.Argument(".", help="Project directory to configure"),
    model: str = typer.Option(
        None, "--model", "-m", help="LLM model (e.g. gpt-4, claude-sonnet-4-20250514)"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Overwrite existing .opencode/mcp.json"
    ),
    no_uv: bool = typer.Option(
        False, "--no-uv", help="Use 'archai mcp' directly instead of 'uv run archai mcp'"
    ),
):
    """Initialize archai in a project for OpenCode MCP integration.

    Creates .opencode.json with the MCP server configuration so OpenCode
    can discover and call archai's architecture tools in this project.
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

    if config_file.exists() and not force:
        typer.echo(
            typer.style(
                "⚠ .opencode.json already has mcpServers configured. Use --force to overwrite.",
                fg="yellow",
            )
        )
        raise typer.Exit(code=0)

    mcp_config = {
        "type": "stdio",
        "command": "archai" if no_uv else "uv",
        "args": ["mcp"] if no_uv else ["run", "archai", "mcp"],
        "env": [],
    }
    existing.setdefault("mcpServers", {})["archai"] = mcp_config

    config_file.write_text(json.dumps(existing, indent=2) + "\n")

    typer.echo(typer.style("✓ Configured archai MCP server in .opencode.json", fg="green"))

    if model:
        typer.echo(
            typer.style(
                f"ℹ Add ARCHAI_LLM_MODEL={model} to your .env file",
                fg="blue",
            )
        )

    typer.echo("")
    typer.echo("Next steps:")
    typer.echo("  1. Set your LLM provider environment variables in .env")
    typer.echo("  2. Open this directory in OpenCode")


if __name__ == "__main__":
    app()
