"""Graph Builder - Build NetworkX graph from parsed file metadata.

This module only constructs the graph. Parsing is done by ast_parser.
SRP: This module has ONE responsibility - build the graph from FileNode data.
"""

import networkx as nx
from typing import List, Dict


class FileNode:
    """Represents a file node in the graph with its metadata."""

    def __init__(
        self,
        path: str,
        imports: List[str] = None,
        functions: List[str] = None,
        classes: List[str] = None,
    ):
        self.path = path
        self.imports = imports or []
        self.functions = functions or []
        self.classes = classes or []


class FileGraph:
    """Wrapper for a NetworkX directed graph with file metadata."""

    def __init__(self, graph: nx.DiGraph = None):
        if graph is None:
            self.graph = nx.DiGraph()
        else:
            self.graph = graph
        self._nodes: Dict[str, FileNode] = {}

    def get_node(self, name: str) -> FileNode:
        """Get the FileNode for a given file name."""
        return self._nodes.get(name)

    def add_node(self, node: FileNode):
        """Add a file node to the graph."""
        self._nodes[node.path] = node
        self.graph.add_node(node.path)


def _resolve_import_to_filename(import_name: str) -> str:
    """Resolve an import name to a filename."""
    # Handle relative imports (starts with .)
    if import_name.startswith("."):
        # Extract module name after dots
        module = import_name.lstrip(".")
        if module:
            return f"{module.split('.')[0]}.py"
        return "__init__.py"

    # Handle absolute imports - just use the module name as filename
    return f"{import_name.split('.')[0]}.py"


def build_graph(file_nodes: List[FileNode]) -> FileGraph:
    """
    Build a graph from a list of FileNodes.

    This function ONLY builds the graph - it does NOT parse files.
    Parsing should be done by ast_parser module before calling this.

    Args:
        file_nodes: List of FileNode objects with metadata (path, imports, etc.)

    Returns:
        A FileGraph containing the NetworkX graph with metadata.
    """
    graph = nx.DiGraph()
    file_graph = FileGraph(graph)

    # Create a lookup for quick access
    files_by_name: Dict[str, FileNode] = {node.path: node for node in file_nodes}

    # Add all nodes to the graph
    for node in file_nodes:
        file_graph.add_node(node)

    # Create edges based on import relationships
    for node in file_nodes:
        for imp in node.imports:
            target_filename = _resolve_import_to_filename(imp)

            # Check if target exists in our graph
            if target_filename in files_by_name:
                graph.add_edge(node.path, target_filename)

    return file_graph
