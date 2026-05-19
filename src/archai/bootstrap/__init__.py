"""ArchAI Bootstrap Module - File discovery and bootstrap utilities.

Pipeline:
    1. file_discovery - find all .py files
    2. ast_parser - parse files and extract metadata
    3. dependency_resolver - resolve imports to filenames
    4. graph_builder - build NetworkX graph
"""

from archai.bootstrap.file_discovery import discover_python_files
from archai.bootstrap.ast_parser import parse_python_file, get_imports, get_functions, get_classes
from archai.bootstrap.dependency_resolver import resolve_imports, FileNode
from archai.bootstrap.graph_builder import build_graph, FileGraph
from archai.bootstrap.cache import (
    compute_repo_hash,
    save_cache,
    load_cache,
    cache_exists,
    invalidate_cache,
    get_cache_path,
)

__all__ = [
    # Discovery
    "discover_python_files",
    # Parsing
    "parse_python_file",
    "get_imports",
    "get_functions",
    "get_classes",
    # Resolution
    "resolve_imports",
    # Graph
    "build_graph",
    "FileNode",
    "FileGraph",
    # Cache
    "compute_repo_hash",
    "save_cache",
    "load_cache",
    "cache_exists",
    "invalidate_cache",
    "get_cache_path",
]
