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


# --- LLM auto-detection ---
# Priority: --model flag > ARCHAI_LLM_MODEL env > OpenCode config > API key env vars > default

_OPENCODE_CONFIG_PATHS = (
    Path.home() / ".config" / "opencode" / "opencode.json",
    Path.home() / ".opencode" / "opencode.json",
)

_OPENCODE_PROPRIETARY_PREFIXES = ("opencode/",)

_API_KEY_ENV_VARS = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY")

_API_KEY_TO_DEFAULT_MODEL = {
    "ANTHROPIC_API_KEY": "claude-sonnet-4-20250514",
    "OPENAI_API_KEY": "gpt-4o",
    "GEMINI_API_KEY": "gemini-2.0-flash",
    "GROQ_API_KEY": "llama-3.3-70b-versatile",
}

_OPENCODE_PROVIDER_TO_API_BASE = {
    "ollama": {"ollama": True},  # litellm handles ollama natively
}


def _read_opencode_config() -> dict | None:
    """Read OpenCode's config file from standard paths."""
    for path in _OPENCODE_CONFIG_PATHS:
        if path.exists():
            try:
                return json.loads(path.read_text())
            except (json.JSONDecodeError, OSError):
                continue
    return None


def _extract_opencode_llm(opencode_config: dict) -> tuple[str | None, str | None, str | None]:
    """Extract (model, api_base, api_key_source) from OpenCode config.

    Looks at agent model references and provider configs to find
    the first non-proprietary model usable by litellm.
    """
    providers = opencode_config.get("provider", {})
    agents = opencode_config.get("agent", {})

    # Collect all unique models from agents (skip empty and proprietary)
    agent_models: set[str] = set()
    for agent_cfg in agents.values():
        m = agent_cfg.get("model", "")
        if not m or any(m.startswith(p) for p in _OPENCODE_PROPRIETARY_PREFIXES):
            continue
        agent_models.add(m)

    if not agent_models:
        return None, None, None

    # Pick the first usable model
    model = next(iter(agent_models))

    # Extract provider prefix (e.g. "ollama" from "ollama/qwen2.5-coder:7b")
    provider_name = model.split("/")[0] if "/" in model else ""
    if provider_name and provider_name in providers:
        provider_cfg = providers[provider_name]
        options = provider_cfg.get("options", {})
        api_base = options.get("baseURL")
        return model, api_base, f"OpenCode ({provider_name})"

    return model, None, f"OpenCode (provider: {provider_name})" if provider_name else None


def _detect_llm_config(override_model: str | None) -> tuple[list[str], str, str | None]:
    """Detect LLM configuration from all available sources.

    Returns (detected_keys, resolved_model, source_info).
    Source info is a human-readable string like "OpenCode (ollama)".
    """
    detected = [k for k in _API_KEY_ENV_VARS if os.environ.get(k)]

    # Priority 1: explicit --model flag
    if override_model:
        return detected, override_model, "--model flag"

    # Priority 2: ARCHAI_LLM_MODEL env var
    env_model = os.environ.get("ARCHAI_LLM_MODEL")
    if env_model:
        return detected, env_model, "ARCHAI_LLM_MODEL env"

    # Priority 3: OpenCode config
    opencode_config = _read_opencode_config()
    if opencode_config:
        oc_model, oc_api_base, oc_source = _extract_opencode_llm(opencode_config)
        if oc_model:
            if oc_api_base:
                os.environ["ARCHAI_LLM_API_BASE"] = oc_api_base
            return detected, oc_model, oc_source or "OpenCode"

    # Priority 4: API key auto-detect
    if detected:
        return detected, _API_KEY_TO_DEFAULT_MODEL[detected[0]], "auto-detect (env)"

    # Priority 5: built-in default
    return detected, "claude-sonnet-4-20250514", "built-in default"


@app.command()
def init(
    project_dir: str = typer.Argument(".", help="Project directory to configure"),
    model: str = typer.Option(
        None, "--model", "-m", help="LLM model (e.g. gpt-4, claude-sonnet-4-20250514)"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Overwrite existing .opencode/mcp.json"
    ),
    uv: bool = typer.Option(
        False, "--uv", help="Use 'uv run archai mcp' instead of 'archai mcp' directly"
    ),
):
    """Initialize archai in a project for OpenCode MCP integration.

    Creates .opencode.json with the MCP server configuration so OpenCode
    can discover and call archai's architecture tools in this project.

    The configuration includes environment passthrough — OpenCode will
    forward your LLM API keys and model setting to archai automatically.
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
                "⚠ .opencode.json already exists. Use --force to overwrite.",
                fg="yellow",
            )
        )
        raise typer.Exit(code=0)

    # Detect LLM and build environment passthrough
    detected_keys, resolved_model, source = _detect_llm_config(model)
    env_passthrough: dict[str, str] = {}
    for key in _API_KEY_ENV_VARS:
        env_passthrough[key] = "{env:" + key + "}"
    env_passthrough["ARCHAI_LLM_MODEL"] = "{env:ARCHAI_LLM_MODEL}"
    # If we detected an API base from OpenCode, pass it through too
    api_base = os.environ.get("ARCHAI_LLM_API_BASE")
    if api_base:
        env_passthrough["ARCHAI_LLM_API_BASE"] = api_base

    command = ["uv", "run", "archai", "mcp"] if uv else ["archai", "mcp"]
    existing.setdefault("mcp", {})["archai"] = {
        "type": "local",
        "command": command,
        "enabled": True,
        "environment": env_passthrough,
    }

    config_file.write_text(json.dumps(existing, indent=2) + "\n")

    typer.echo(typer.style("✓ Configured archai MCP server in .opencode.json", fg="green"))
    typer.echo("")

    if source and "OpenCode" in source:
        typer.echo(typer.style(f"🔑 Using LLM from {source}", fg="cyan"))
        typer.echo(typer.style("   Model:", fg="cyan") + f" {resolved_model}")
        if api_base:
            typer.echo(typer.style("   API Base:", fg="cyan") + f" {api_base}")
    elif detected_keys:
        typer.echo(typer.style("🔑 LLM detected:", fg="cyan") + f" {', '.join(detected_keys)}")
        typer.echo(typer.style("   Model:", fg="cyan") + f" {resolved_model}")
    else:
        typer.echo(
            typer.style(
                "⚠ No LLM configuration found.\n"
                "  archai will use its default model, but for best results\n"
                "  configure your LLM in OpenCode first, then run archai init again.",
                fg="yellow",
            )
        )
        typer.echo(typer.style("   Model:", fg="cyan") + f" {resolved_model}")

    typer.echo("")
    typer.echo(typer.style("✓ archai is ready! Open this directory in OpenCode.", fg="green"))


if __name__ == "__main__":
    app()
