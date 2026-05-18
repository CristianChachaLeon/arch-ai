"""Disk Cache - Cache FileGraph with hash-based invalidation.

SRP: This module handles only caching logic, not graph construction.
Invalidation is based on SHA256 hash of Python file contents.
"""

import hashlib
import json
from pathlib import Path
from typing import Any, Optional

from archai.bootstrap.graph_builder import FileGraph


CACHE_DIR = Path.home() / ".archai" / "cache"


def _serialize_graph(graph: FileGraph) -> dict[str, Any]:
    """Serialize FileGraph to JSON-serializable dict."""
    return {
        "graph": {
            "nodes": [
                {
                    "path": node.path,
                    "imports": node.imports,
                    "functions": node.functions,
                    "classes": node.classes,
                }
                for node in graph._nodes.values()
            ],
            "edges": list(graph.graph.edges),
        },
        "metadata": {
            "node_count": graph.graph.number_of_nodes(),
            "edge_count": len(graph.graph.edges),
        },
    }


def _deserialize_graph(data: dict[str, Any]) -> FileGraph:
    """Deserialize JSON dict to FileGraph with schema validation."""
    if not isinstance(data, dict):
        raise ValueError("Invalid cache data: not a dict")

    if "graph" not in data or "metadata" not in data:
        raise ValueError("Invalid cache data: missing required keys")

    from archai.bootstrap.graph_builder import FileNode, build_graph

    nodes_data = data["graph"].get("nodes", [])
    if not isinstance(nodes_data, list):
        raise ValueError("Invalid cache data: nodes must be a list")

    file_nodes = []
    for node_data in nodes_data:
        if not isinstance(node_data, dict):
            raise ValueError("Invalid cache data: node must be a dict")
        if "path" not in node_data:
            raise ValueError("Invalid cache data: node missing path")

        file_nodes.append(
            FileNode(
                path=node_data["path"],
                imports=node_data.get("imports", []),
                functions=node_data.get("functions", []),
                classes=node_data.get("classes", []),
            )
        )

    return build_graph(file_nodes)


def get_cache_path(repo_path: str) -> Path:
    """Get the cache file path for a repository.

    Args:
        repo_path: Absolute path to the repository root.

    Returns:
        Path to the cache file in ~/.archai/cache/.
    """
    path_hash = hashlib.sha256(repo_path.encode()).hexdigest()
    return CACHE_DIR / f"{path_hash}.pkl"


def compute_repo_hash(repo_path: str) -> str:
    """Compute SHA256 hash of all .py files in the repository.

    Args:
        repo_path: Absolute path to the repository root.

    Returns:
        SHA256 hex digest representing the state of Python files.
    """
    hash_obj = hashlib.sha256()

    repo = Path(repo_path)
    if not repo.exists():
        return hash_obj.hexdigest()

    py_files = sorted(repo.rglob("*.py"))

    for py_file in py_files:
        try:
            rel_path = py_file.relative_to(repo).as_posix()
            content = py_file.read_bytes()
            hash_obj.update(rel_path.encode("utf-8"))
            hash_obj.update(b"\0")
            hash_obj.update(content)
            hash_obj.update(b"\0")
        except (OSError, PermissionError):
            continue

    return hash_obj.hexdigest()


def cache_exists(repo_path: str) -> bool:
    """Check if a cache file exists for the repository.

    Args:
        repo_path: Absolute path to the repository root.

    Returns:
        True if cache file exists, False otherwise.
    """
    cache_file = get_cache_path(repo_path)
    return cache_file.exists()


def save_cache(repo_path: str, graph: FileGraph) -> None:
    """Save FileGraph to disk cache with current repo hash.

    Args:
        repo_path: Absolute path to the repository root.
        graph: FileGraph to cache.
    """
    cache_file = get_cache_path(repo_path)
    cache_file.parent.mkdir(parents=True, exist_ok=True)

    repo_hash = compute_repo_hash(repo_path)

    cache_data = {
        "repo_hash": repo_hash,
        "graph": _serialize_graph(graph),
    }

    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(cache_data, f)


def load_cache(repo_path: str) -> Optional[FileGraph]:
    """Load FileGraph from disk cache if valid.

    Args:
        repo_path: Absolute path to the repository root.

    Returns:
        FileGraph if cache exists and is valid, None otherwise.
    """
    cache_file = get_cache_path(repo_path)

    if not cache_file.exists():
        return None

    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            cache_data = json.load(f)
    except (json.JSONDecodeError, OSError, EOFError):
        return None

    stored_hash = cache_data.get("repo_hash")
    current_hash = compute_repo_hash(repo_path)

    if stored_hash != current_hash:
        return None

    try:
        return _deserialize_graph(cache_data.get("graph", {}))
    except (ValueError, KeyError, TypeError, AttributeError):
        return None


def invalidate_cache(repo_path: str) -> None:
    """Remove cache file for the repository.

    Args:
        repo_path: Absolute path to the repository root.
    """
    cache_file = get_cache_path(repo_path)
    if cache_file.exists():
        cache_file.unlink()
