"""Disk Cache - Cache FileGraph with hash-based invalidation.

SRP: This module handles only caching logic, not graph construction.
Invalidation is based on SHA256 hash of Python file contents.
"""

import hashlib
import pickle
from pathlib import Path
from typing import Optional

from archai.bootstrap.graph_builder import FileGraph


CACHE_DIR = Path.home() / ".archai" / "cache"


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
            content = py_file.read_bytes()
            hash_obj.update(content)
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
        "graph": graph,
    }

    with open(cache_file, "wb") as f:
        pickle.dump(cache_data, f)


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
        with open(cache_file, "rb") as f:
            cache_data = pickle.load(f)
    except (pickle.UnpicklingError, OSError):
        return None

    stored_hash = cache_data.get("repo_hash")
    current_hash = compute_repo_hash(repo_path)

    if stored_hash != current_hash:
        return None

    return cache_data.get("graph")


def invalidate_cache(repo_path: str) -> None:
    """Remove cache file for the repository.

    Args:
        repo_path: Absolute path to the repository root.
    """
    cache_file = get_cache_path(repo_path)
    if cache_file.exists():
        cache_file.unlink()
