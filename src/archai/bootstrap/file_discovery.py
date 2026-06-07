"""File discovery - Find files in a directory by extension"""

from pathlib import Path


# Directories to exclude from Python discovery (backward compat)
PYTHON_EXCLUDED_DIRS = frozenset(
    {
        "venv",
        ".venv",
        "env",
        ".env",
        "ENV",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "node_modules",
        ".git",
        ".tox",
        "dist",
        "build",
    }
)

# Backward-compatible alias
EXCLUDED_DIRS = PYTHON_EXCLUDED_DIRS


def discover_files(
    repo_path: Path,
    extensions: frozenset[str],
    excluded_dirs: frozenset[str] | None = None,
) -> list[Path]:
    """Discover all files matching the given extensions, excluding specified dirs.

    Args:
        repo_path: Root directory to search
        extensions: Set of file extensions to find (e.g., {'.py', '.pyx'})
        excluded_dirs: Set of directory names to exclude (default: empty)

    Returns:
        Sorted list of Path objects matching the extensions.
    """
    if not repo_path.is_dir():
        raise ValueError(f"Path is not a directory: {repo_path}")

    excludes = excluded_dirs if excluded_dirs is not None else frozenset()
    files: list[Path] = []

    for ext in extensions:
        for path in repo_path.rglob(f"*{ext}"):
            # Skip symlinks to avoid circular references
            if path.is_symlink() or any(
                parent.is_symlink() for parent in path.parents if parent != repo_path
            ):
                continue

            # Skip excluded directories (exact match or .egg-info/.dist-info suffixes)
            parts = path.parts
            if any(ex in parts for ex in excludes):
                continue
            if any(part.endswith((".egg-info", ".dist-info")) for part in parts):
                continue

            # Skip files starting with underscore (except __init__.py) — Python convention
            if ext == ".py" and path.name.startswith("_") and path.name != "__init__.py":
                continue

            files.append(path)

    return sorted(files)


def discover_python_files(repo_path: Path) -> list[Path]:
    """Discover all Python files in a directory recursively.

    Backward-compatible wrapper around discover_files.

    Args:
        repo_path: Root directory to search

    Returns:
        List of Path objects for .py files, sorted alphabetically
    """
    return discover_files(repo_path, frozenset({".py"}), PYTHON_EXCLUDED_DIRS)
