"""File discovery - Find all Python files in a directory"""

from pathlib import Path


# Directories to exclude from discovery
EXCLUDED_DIRS = {
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
    ".egg-info",
    "dist",
    "build",
}


def discover_python_files(repo_path: Path) -> list[Path]:
    """
    Discover all Python files in a directory recursively.

    Args:
        repo_path: Root directory to search

    Returns:
        List of Path objects for .py files, sorted alphabetically
    """
    if not repo_path.is_dir():
        raise ValueError(f"Path is not a directory: {repo_path}")

    python_files = []

    for path in repo_path.rglob("*.py"):
        # Skip excluded directories
        if any(excluded in path.parts for excluded in EXCLUDED_DIRS):
            continue

        # Skip files starting with underscore (except __init__.py)
        if path.name.startswith("_") and path.name != "__init__.py":
            continue

        python_files.append(path)

    return sorted(python_files)
