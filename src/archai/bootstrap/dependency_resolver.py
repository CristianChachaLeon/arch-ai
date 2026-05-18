"""Dependency Resolver - Resolve raw imports to relative file paths.

This module handles resolving import statements to actual file paths
relative to the repository root.

SRP: Only resolves imports - does not build the graph.
"""

from archai.bootstrap.graph_builder import FileNode
from typing import List, Dict
from pathlib import Path


# Common Python stdlib modules to exclude from resolution
STDLIB_MODULES = {
    # Built-in modules
    "os",
    "sys",
    "re",
    "json",
    "logging",
    "datetime",
    "time",
    "collections",
    "itertools",
    "functools",
    "operator",
    " pathlib",
    "typing",
    "copy",
    "io",
    "tempfile",
    "shutil",
    "glob",
    "fnmatch",
    "argparse",
    "threading",
    "multiprocessing",
    "subprocess",
    "socket",
    "ssl",
    "http",
    "urllib",
    "email",
    "html",
    "xml",
    "sqlite3",
    "dbm",
    "pickle",
    "marshal",
    "struct",
    "codecs",
    "unicodedata",
    "string",
    "textwrap",
    "random",
    "math",
    "statistics",
    "decimal",
    "fractions",
    "numbers",
    "cmath",
    "array",
    "bisect",
    "graphlib",
    "heapq",
    "queue",
    "weakref",
    "types",
    "inspect",
    "traceback",
    "gc",
    "ast",
    "dis",
    "inspect",
    "platform",
    "errno",
    "ctypes",
    "mmap",
    "signal",
    "posixpath",
    "ntpath",
    "posix",
    "pwd",
    "grp",
    "resource",
    "locale",
    "gettext",
    "optparse",
    "getopt",
    " warnings",
    "contextlib",
    "abc",
    "atexit",
    "trace",
    "code",
    "codeop",
    "contextvars",
    "dataclasses",
    "typing",
    "collections.abc",
    "typing_extensions",
    # Common third-party that might conflict
    "pip",
    "setuptools",
    "wheel",
    "pytest",
    "unittest",
}


def _is_stdlib_module(module_name: str) -> bool:
    """Check if a module name is a stdlib or common external module."""
    # Check first part of the import
    first_part = module_name.split(".")[0].split(",")[0].strip()
    return first_part in STDLIB_MODULES


def _resolve_single_import(import_name: str, files_by_stem: Dict[str, str]) -> str:
    """Resolve a single import name to a relative path.

    Args:
        import_name: The import string (e.g., "utils.helpers", "os")
        files_by_stem: Dict mapping file stem (without extension) -> relative path

    Returns:
        The resolved relative path or empty string if not found.
    """
    # Skip stdlib modules
    if _is_stdlib_module(import_name):
        return ""

    # Handle relative imports (starts with .)
    if import_name.startswith("."):
        module = import_name.lstrip(".")
        if module:
            parts = module.split(".")
            # Try most specific first
            for i in range(len(parts), 0, -1):
                stem = parts[i - 1]
                if stem in files_by_stem:
                    return files_by_stem[stem]
            # Fallback to first part
            stem = parts[0]
            if stem in files_by_stem:
                return files_by_stem[stem]
            return f"{stem}/__init__.py"
        # Relative import without module = __init__.py
        return "__init__.py"

    # Handle absolute imports like "utils.helpers", "os", "dataclasses.dataclass"
    parts = import_name.split(".")

    # Strategy: Try to find by stem matching
    # e.g., "archai.bootstrap.graph_builder" -> try "graph_builder"
    for stem in reversed(parts):
        if stem in files_by_stem:
            return files_by_stem[stem]

    # Fallback: first part
    stem = parts[0]
    if stem in files_by_stem:
        return files_by_stem[stem]

    return ""


def resolve_imports(file_nodes: List[FileNode]) -> List[FileNode]:
    """
    Resolve raw imports to relative paths based on available files.

    This function takes FileNodes with raw imports (e.g., "utils.helpers",
    "models.user.User") and resolves them to relative paths (e.g.,
    "utils/helpers.py", "models/user.py") based on the files that exist
    in the repository.

    Only imports that match files in the repository are included.
    Stdlib and third-party imports are filtered out.

    Args:
        file_nodes: List of FileNode objects with raw imports.
                    Each node should have 'path' as relative path from repo root.

    Returns:
        List of FileNode objects with imports resolved to relative paths.

    Example:
        Input:  FileNode(path="src/main.py", imports=["utils.helpers", "os", "requests"])
        Output: FileNode(path="src/main.py", imports=["utils/helpers.py"])
        # "os" and "requests" are stdlib/external, filtered out
    """
    # Build lookup by stem (filename without extension)
    # e.g., "helpers" -> "utils/helpers.py"
    files_by_stem: Dict[str, str] = {}
    for node in file_nodes:
        stem = Path(node.path).stem
        # If stem already exists, prefer shorter path (root-level files)
        if stem not in files_by_stem or len(node.path.split("/")) < len(
            files_by_stem[stem].split("/")
        ):
            files_by_stem[stem] = node.path

    # Resolve imports for each node
    resolved_nodes = []

    for node in file_nodes:
        resolved_imports = []

        for imp in node.imports:
            resolved = _resolve_single_import(imp, files_by_stem)
            # Only include if the resolved path exists in our repo
            if resolved and resolved in {n.path for n in file_nodes}:
                resolved_imports.append(resolved)

        # Create new node with resolved imports (only local ones)
        resolved_node = FileNode(
            path=node.path,
            imports=resolved_imports,
            functions=node.functions,
            classes=node.classes,
        )
        resolved_nodes.append(resolved_node)

    return resolved_nodes
