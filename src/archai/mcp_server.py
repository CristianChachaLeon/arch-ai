"""ArchAI MCP Server - Architecture-aware tools for AI agents.

Runs as a stdio subprocess. Agent reads JSON from stdin, writes to stdout.

Usage:
    archai-mcp-server
    # or
    python -m archai.mcp_server
"""

from __future__ import annotations

import json
import os

from mcp.server.fastmcp import FastMCP

from archai.config import validate_repo_path
from archai.models import ChangeItem
from archai.inference.llm import LiteLLMProvider
from archai.middleware import ArchaiMiddleware
from archai.orchestrator import ArchaiOrchestrator

# --- Singletons (mirrors http/main.py) ---
LLM_MODEL = os.environ.get("ARCHAI_LLM_MODEL")
LLM_API_BASE = os.environ.get("ARCHAI_LLM_API_BASE")
LLM_API_KEY = os.environ.get("ARCHAI_LLM_API_KEY")
llm_provider = (
    LiteLLMProvider(model=LLM_MODEL, api_base=LLM_API_BASE, api_key=LLM_API_KEY)
    if LLM_MODEL
    else None
)
middleware = ArchaiMiddleware(llm_provider=llm_provider)
orchestrator = ArchaiOrchestrator(middleware)

mcp = FastMCP("archai")


@mcp.tool()
async def get_architecture_context(query: str, repo_path: str) -> str:
    """Get architecture-aware context for a query.

    Returns focus subsystem, constraints, relevant files, and reasoning.
    Use this before writing code to understand the target subsystem.
    """
    try:
        resolved = validate_repo_path(repo_path)
        packet = await orchestrator.get_context(query, resolved)
        return json.dumps(packet.model_dump(), indent=2)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


@mcp.tool()
async def validate_code_change(repo_path: str, changes: list[dict]) -> str:
    """Validate proposed code changes against architectural constraints.

    Call this automatically before applying changes to detect violations.
    Each change dict must have keys: file_path, patch. Optional: change_type.
    """
    try:
        resolved = validate_repo_path(repo_path)
        items = [ChangeItem(**c) for c in changes]
        result = await orchestrator.validate_changes(resolved, items)
        return json.dumps(result.model_dump(), indent=2)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


@mcp.tool()
async def get_blast_radius(repo_path: str, file_path: str, depth: int = 2) -> str:
    """Analyze the impact of changing a file.

    Returns direct/transitive dependents and affected subsystems.
    Call this automatically before applying changes.
    """
    try:
        resolved = validate_repo_path(repo_path)
        result = await orchestrator.get_blast_radius(resolved, file_path, depth)
        return json.dumps(result.model_dump(), indent=2)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


if __name__ == "__main__":
    mcp.run(transport="stdio")
