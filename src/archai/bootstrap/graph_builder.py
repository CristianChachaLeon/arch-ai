"""Graph Builder - Build NetworkX graph from parsed file metadata.

This module only constructs the graph. Parsing is done by ast_parser.
"""

from dataclasses import dataclass

import networkx as nx
from typing import List, Dict


class FileNode:
    """Represents a file node in the graph with its metadata.

    Attributes:
        path: Relative path from repo root (e.g., "src/archai/bootstrap/__init__.py")
        imports: List of resolved import paths relative to repo root
        functions: List of function names defined in this file
        classes: List of class names defined in this file
    """

    def __init__(
        self,
        path: str,
        imports: List[str] = None,
        functions: List[str] = None,
        classes: List[str] = None,
        functions_detail: list | None = None,
        global_vars: list | None = None,
        var_access: dict | None = None,
    ):
        # Normalize path to use forward slashes
        self.path = path.replace("\\", "/")
        self.imports = imports or []
        self.functions = functions or []
        self.classes = classes or []
        self.functions_detail = functions_detail or []
        self.global_vars = global_vars or []
        self.var_access = var_access or {}

    @property
    def filename(self) -> str:
        """Return just the filename (e.g., '__init__.py')"""
        return self.path.split("/")[-1]


@dataclass
class FunctionNode:
    """Represents a function node in the function-level dependency graph.

    Attributes:
        name: Function name.
        file_path: Path of the file containing this function.
        calls_internal: Functions called within the same file.
        calls_external: Functions called in other project files.
        is_static: Whether the function is file-scoped (e.g., C `static`).
    """

    name: str
    file_path: str
    calls_internal: list[str]
    calls_external: list[str]
    is_static: bool = False


class FunctionGraph:
    """Wrapper for a NetworkX directed graph with function metadata.

    Nodes are keyed as '{file_path}::{function_name}'.
    Edges represent 'caller -> callee' relationships.
    """

    def __init__(self, graph: nx.DiGraph | None = None):
        if graph is None:
            self.graph = nx.DiGraph()
        else:
            self.graph = graph
        self._nodes: dict[str, FunctionNode] = {}

    def get_node(self, key: str) -> FunctionNode | None:
        return self._nodes.get(key)

    def add_node(self, key: str, node: FunctionNode):
        self._nodes[key] = node
        self.graph.add_node(key)

    @property
    def node_count(self) -> int:
        return self.graph.number_of_nodes()

    @property
    def edge_count(self) -> int:
        return self.graph.number_of_edges()


# Minimum number of functions in a file to trigger intra-file analysis
INTRA_FILE_THRESHOLD = 20


def _build_key(file_path: str, function_name: str) -> str:
    """Build a unique key for a function node."""
    return f"{file_path}::{function_name}"


def build_function_graph(file_nodes: list[FileNode]) -> FunctionGraph:
    """Build a function-level dependency graph from file nodes.

    Only includes files with more than INTRA_FILE_THRESHOLD functions.
    Creates nodes for each function and edges for call relationships.

    Args:
        file_nodes: List of FileNode objects with functions_detail.

    Returns:
        FunctionGraph with function-level nodes and call edges.
    """
    fg = FunctionGraph()
    all_funcs: dict[str, FunctionNode] = {}

    for fn in file_nodes:
        if not hasattr(fn, "functions_detail") or not fn.functions_detail:
            continue
        if len(fn.functions_detail) <= INTRA_FILE_THRESHOLD:
            continue

        for func in fn.functions_detail:
            key = _build_key(fn.path, func.name)
            node = FunctionNode(
                name=func.name,
                file_path=fn.path,
                calls_internal=list(func.calls_internal),
                calls_external=list(func.calls_external),
            )
            all_funcs[key] = node
            fg.add_node(key, node)

    name_to_keys: dict[str, list[str]] = {}
    for k, n in all_funcs.items():
        name_to_keys.setdefault(n.name, []).append(k)

    for key, node in all_funcs.items():
        for callee in node.calls_internal:
            callee_key = _build_key(node.file_path, callee)
            if callee_key in all_funcs:
                fg.graph.add_edge(key, callee_key)

        for callee in node.calls_external:
            for other_key in name_to_keys.get(callee, []):
                other_node = all_funcs[other_key]
                if other_node.file_path != node.file_path and not other_node.is_static:
                    fg.graph.add_edge(key, other_key)

    return fg


def function_dependents(fg: FunctionGraph, file_path: str, function_name: str) -> list[str]:
    """Get functions that depend on (call) a given function."""
    key = _build_key(file_path, function_name)
    if key not in fg.graph:
        return []
    return sorted(fg.graph.predecessors(key))


def function_dependencies(fg: FunctionGraph, file_path: str, function_name: str) -> list[str]:
    """Get functions that a given function depends on (calls)."""
    key = _build_key(file_path, function_name)
    if key not in fg.graph:
        return []
    return sorted(fg.graph.successors(key))


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

    def detect_cycles(self):
        """
        Detect cycles in the graph using NetworkX's simple_cycles.

        Yields:
            List of cycles, where each cycle is a list of node names.
            Example: [['a.py', 'b.py', 'a.py']]
        """
        # Use simple_cycles which finds elementary cycles
        try:
            cycles = list(nx.simple_cycles(self.graph))
            return cycles
        except (nx.NetworkXError, nx.NetworkXException):
            return []

    def collapse_cycles(self) -> "FileGraph":
        """
        Collapse all detected cycles into a single virtual 'cyclic_module' node.

        All files that are part of any cycle are replaced with one virtual node
        called 'cyclic_module'. Edges to/from nodes outside the cycles are
        preserved and reconnected to the virtual node.

        Returns:
            A new FileGraph with cycles collapsed.
        """
        cycles = self.detect_cycles()
        if not cycles:
            new_graph = FileGraph(self.graph.copy())
            new_graph._nodes = self._nodes.copy()
            return new_graph

        # Find all nodes that are part of any cycle
        cyclic_nodes: set = set()
        for cycle in cycles:
            for node in cycle:
                cyclic_nodes.add(node)

        # Create new graph
        new_graph = nx.DiGraph()
        new_file_graph = FileGraph(new_graph)

        # Add all non-cyclic nodes to new graph
        for node_name, node_obj in self._nodes.items():
            if node_name not in cyclic_nodes:
                new_file_graph.add_node(node_obj)

        # Add virtual cyclic module node
        cyclic_node = FileNode(path="cyclic_module", imports=[], functions=[], classes=[])
        new_file_graph.add_node(cyclic_node)

        # Reconstruct edges, redirecting from/to cyclic nodes to virtual node
        for u, v in self.graph.edges():
            if u in cyclic_nodes and v in cyclic_nodes:
                # Both in cycle: edge internal to cyclic module, skip
                continue
            elif u in cyclic_nodes and v not in cyclic_nodes:
                # From cycle to outside: connect virtual -> outside
                new_graph.add_edge("cyclic_module", v)
            elif u not in cyclic_nodes and v in cyclic_nodes:
                # From outside to cycle: connect outside -> virtual
                new_graph.add_edge(u, "cyclic_module")
            else:
                # Neither in cycle: keep as is
                new_graph.add_edge(u, v)

        return new_file_graph


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

    # Create edges based on resolved import relationships
    # NOTE: imports should already be resolved to relative file paths
    # by dependency_resolver before calling build_graph
    for node in file_nodes:
        for imp in node.imports:
            if imp == "external":
                if "external" not in files_by_name:
                    ext_node = FileNode(path="external", imports=[], functions=[], classes=[])
                    file_graph.add_node(ext_node)
                    files_by_name["external"] = ext_node
                graph.add_edge(node.path, "external")
            elif imp != node.path and imp in files_by_name:
                graph.add_edge(node.path, imp)

    return file_graph
