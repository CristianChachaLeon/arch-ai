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
    "pathlib",
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
    "warnings",
    "contextlib",
    "abc",
    "atexit",
    "trace",
    "code",
    "codeop",
    "contextvars",
    "dataclasses",
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


def _resolve_single_import(
    import_name: str,
    files_by_stem: Dict[str, str],
    files_by_module: Dict[str, str],
    importer_path: str = "",
) -> str:
    """Resolve a single import name to a relative path.

    Args:
        import_name: The import string (e.g., "utils.helpers", "os")
        files_by_stem: Dict mapping file stem (without extension) -> relative path
        files_by_module: Dict mapping dotted module path -> relative file path
        importer_path: The path of the file doing the import (for relative import resolution)

    Returns:
        The resolved relative path, "external" for stdlib modules,
        or empty string if not found.
    """
    # Skip stdlib modules
    if _is_stdlib_module(import_name):
        return "external"

    # Handle relative imports (starts with .)
    if import_name.startswith("."):
        level = len(import_name) - len(import_name.lstrip("."))
        module_part = import_name.lstrip(".")

        if importer_path:
            current_dir = str(Path(importer_path).parent)
        else:
            current_dir = ""

        for _ in range(level - 1):
            if current_dir:
                current_dir = str(Path(current_dir).parent)

        available_paths = set(files_by_stem.values())

        if module_part:
            parts = module_part.split(".")

            # Strategy 1: Try exact relative paths (most to least specific)
            # e.g., "models.user" from "src/services/" -> "src/models/user.py"
            for i in range(len(parts), 0, -1):
                rel = "/".join(parts[:i])
                candidate = f"{current_dir}/{rel}.py" if current_dir else f"{rel}.py"
                candidate = candidate.lstrip("/")
                if candidate in available_paths:
                    return candidate

            # Strategy 2: Try __init__.py
            for i in range(len(parts), 0, -1):
                rel = "/".join(parts[:i])
                candidate = (
                    f"{current_dir}/{rel}/__init__.py" if current_dir else f"{rel}/__init__.py"
                )
                candidate = candidate.lstrip("/")
                if candidate in available_paths:
                    return candidate

            # Strategy 3: Fallback to global stem lookup
            for i in range(len(parts), 0, -1):
                if parts[i - 1] in files_by_stem:
                    return files_by_stem[parts[i - 1]]

            return ""

        # Just dots (from ., from ..) = __init__.py in target directory
        init_candidate = f"{current_dir}/__init__.py" if current_dir else "__init__.py"
        return init_candidate

    # Handle absolute imports like "utils.helpers", "os", "dataclasses.dataclass"
    parts = import_name.split(".")

    # Strategy 1: Try exact dotted-module match (full path first, then shorter)
    # e.g., "pkg_a.utils.helper" -> try "pkg_a.utils.helper", then "pkg_a.utils", then "pkg_a"
    # This avoids stem collisions when different packages have same module names
    for i in range(len(parts), 0, -1):
        dotted = ".".join(parts[:i])
        if dotted in files_by_module:
            return files_by_module[dotted]

    # Strategy 2: Fallback to stem lookup (last resort)
    for stem in reversed(parts):
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
    Stdlib and third-party imports are marked as "external".

    Args:
        file_nodes: List of FileNode objects with raw imports.
                    Each node should have 'path' as relative path from repo root.

    Returns:
        List of FileNode objects with imports resolved to relative paths.

    Example:
        Input:  FileNode(path="src/main.py", imports=["utils.helpers", "os", "requests"])
        Output: FileNode(path="src/main.py", imports=["utils/helpers.py", "external"])
        # "os" and "requests" are stdlib/external, marked as "external"
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

    # Build lookup by full dotted module path (for exact prefix matching)
    # e.g., "src.pkg_a.utils.helper" -> "src/pkg_a/utils/helper.py"
    # and its suffixes like "pkg_a.utils.helper", "utils.helper"
    # This avoids stem collisions when different packages have same module names
    files_by_module: Dict[str, str] = {}
    for node in file_nodes:
        # Convert "src/pkg_a/utils/helper.py" -> parts ["src", "pkg_a", "utils", "helper"]
        module_parts = node.path.replace(".py", "").split("/")
        # Handle __init__.py: strip the "__init__" part
        if module_parts[-1] == "__init__":
            module_parts = module_parts[:-1]

        # Add all suffix variants (most specific first)
        for i in range(len(module_parts)):
            suffix = ".".join(module_parts[i:])
            if suffix not in files_by_module:  # First one wins (most specific path)
                files_by_module[suffix] = node.path

    # Resolve imports for each node
    resolved_nodes = []

    for node in file_nodes:
        resolved_imports = []

        for imp in node.imports:
            resolved = _resolve_single_import(imp, files_by_stem, files_by_module, node.path)
            # Include "external" marker for cross-language/system/stdlib imports
            if resolved == "external":
                resolved_imports.append("external")
            elif resolved and resolved in {n.path for n in file_nodes}:
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
