"""ArchAI MCP Server - Architecture-aware tools for AI agents.

Runs as a stdio subprocess. Agent reads JSON from stdin, writes to stdout.

Usage:
    archai-mcp-server
    # or
    python -m archai.mcp_server
"""

from __future__ import annotations

import json
import logging

from mcp.server.fastmcp import FastMCP

from archai.config import validate_repo_path
from archai.models import ChangeItem, StructuralChangeValidation
from archai.middleware import ArchaiMiddleware
from archai.orchestrator import ArchaiOrchestrator
from archai.orchestrator.orchestrator import get_cluster_edges

logger = logging.getLogger("archai.mcp")

# No LLM provider needed — archai is a pure structural analysis engine.
# The MCP server returns raw structural data (clusters, edges, dependencies).
# OpenCode's agent uses its own LLM to interpret the data and infer constraints.
middleware = ArchaiMiddleware(llm_provider=None)
orchestrator = ArchaiOrchestrator(middleware)

mcp = FastMCP("archai")


@mcp.tool()
async def get_architecture_context(query: str, repo_path: str) -> str:
    """Analyze a repository's architecture for a given query.

    Returns cluster structure and file dependencies so YOUR LLM can:
    - Name each cluster based on its files (e.g. "API Layer", "Database")
    - Infer architecture constraints (async-only, forbidden dependencies)
    - Understand how the focus subsystem relates to others

    STRATEGY FOR YOUR LLM:
    - Clusters that depend on many others → likely API/entry points → async
    - Clusters with no dependents → leaf modules → few restrictions
    - Leaf clusters should NOT import from API clusters (circular risk)
    - Use cluster_edges to understand the layering of the architecture

    Example inference:
    - Cluster with [routes.py, middleware.py, handlers.py] → "API Layer"
    - Cluster with [models.py, repository.py] → "Database Layer"
    - If "API" depends on "Database" but NOT vice versa → clean layering

    Args:
        query: Question about the codebase (e.g. "how does auth work")
        repo_path: Absolute path to the repository root
    """
    try:
        resolved = validate_repo_path(repo_path)
        context = await orchestrator.get_structural_context(query, resolved)
        return json.dumps(context.model_dump(), indent=2)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


@mcp.tool()
async def validate_code_change(repo_path: str, changes: list[dict]) -> str:
    """Analyze proposed code changes and provide structural context for validation.

    Returns which cluster the changed files belong to, their dependencies,
    and what new imports the patch introduces. YOUR LLM should use this
    structural data to determine if the change violates architecture rules.

    STRATEGY FOR YOUR LLM:
    - Check if new imports cross into forbidden clusters
    - Check if the file belongs to an async-only cluster and the patch
      introduces blocking I/O (time.sleep, requests.get, etc.)
    - Check if a leaf module is importing from an API layer
    - Consider the blast radius before approving the change

    Each change dict must have keys: file_path, patch. Optional: change_type.

    Args:
        repo_path: Absolute path to the repository root
        changes: List of change dicts with file_path and patch
    """
    try:
        resolved = validate_repo_path(repo_path)
        items = [ChangeItem(**c) for c in changes]

        # Get pipeline data for structural context
        pipeline_result = await orchestrator._get_pipeline_result(resolved)
        graph = pipeline_result.graph.graph

        results = []
        for change in items:
            file_cluster = pipeline_result.get_cluster_for_file(change.file_path)
            cluster_files = (
                list(pipeline_result.clusters.get(file_cluster, [])) if file_cluster else []
            )

            # Compute cross-cluster dependencies
            cluster_deps = {"imports_from_cluster": [], "imported_by_clusters": []}
            if file_cluster:
                edges = [
                    e
                    for e in get_cluster_edges(graph, pipeline_result.clusters)
                    if e.from_cluster == file_cluster or e.to_cluster == file_cluster
                ]
                for e in edges:
                    if (
                        e.from_cluster == file_cluster
                        and e.to_cluster not in cluster_deps["imports_from_cluster"]
                    ):
                        cluster_deps["imports_from_cluster"].append(e.to_cluster)
                    if (
                        e.to_cluster == file_cluster
                        and e.from_cluster not in cluster_deps["imported_by_clusters"]
                    ):
                        cluster_deps["imported_by_clusters"].append(e.from_cluster)

            # Detect new imports in the patch (added lines only)
            import re

            added_lines = [
                line[1:]
                for line in change.patch.splitlines()
                if line.startswith("+") and not line.startswith("+++")
            ]
            added_text = "\n".join(added_lines)

            new_imports = re.findall(
                r"^(?:from\s+(\S+)\s+)?import\s+(\S+)", added_text, re.MULTILINE
            )
            new_import_paths = []
            for from_match, import_match in new_imports:
                if from_match:
                    new_import_paths.append(from_match.replace(".", "/") + ".py")
                else:
                    new_import_paths.append(import_match.replace(".", "/") + ".py")

            # Build file dependencies for the changed file
            file_deps = {}
            if change.file_path in graph:
                file_deps[change.file_path] = sorted(graph.successors(change.file_path))

            validation = StructuralChangeValidation(
                file_cluster=file_cluster or "unknown",
                cluster_files=cluster_files,
                cluster_dependencies=cluster_deps,
                file_dependencies=file_deps,
                new_imports_in_patch=new_import_paths,
                patch_summary={
                    "files_changed": [change.file_path],
                    "new_imports": new_import_paths,
                },
            )
            results.append(validation.model_dump())

        if not results:
            return json.dumps({"changes": [], "note": "No changes to validate"}, indent=2)
        return json.dumps(results if len(results) > 1 else results[0], indent=2)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


@mcp.tool()
async def get_blast_radius(repo_path: str, file_path: str, depth: int = 2) -> str:
    """Analyze the impact of changing a file in the dependency graph.

    Returns direct/transitive dependents and affected subsystems.
    YOUR LLM should assess whether the impact is acceptable:
    - >5 direct dependents → high risk, warn the user
    - Affects core/infra cluster → needs careful review
    - Only affects tests → low risk

    Args:
        repo_path: Absolute path to the repository root
        file_path: The file being changed (relative to repo root)
        depth: How deep to traverse for transitive dependents (1-5, default 2)
    """
    try:
        resolved = validate_repo_path(repo_path)
        result = await orchestrator.get_blast_radius(resolved, file_path, depth)
        return json.dumps(result.model_dump(), indent=2)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


if __name__ == "__main__":
    mcp.run(transport="stdio")
