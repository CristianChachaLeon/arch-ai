"""Clustering Heuristics - Detect logical subsystems based on graph structure.

This module implements three clustering signals:
1. Directory proximity - files in same directory
2. Shared imports - files importing same modules
3. Call density - files that call each other
"""

import networkx as nx
from networkx.algorithms.community import greedy_modularity_communities
from typing import Dict, List

from archai.bootstrap.graph_builder import FileGraph


def cluster_files(graph: FileGraph) -> Dict[str, List[str]]:
    """
    Cluster files into logical subsystems based on graph structure.

    Uses three heuristics:
    - Directory proximity: files in same directory cluster together
    - Shared imports: files importing same modules cluster together
    - Call density: files with bidirectional calls cluster together

    Args:
        graph: A FileGraph containing the file relationships

    Returns:
        Dict mapping cluster names to lists of file paths
    """
    if graph.graph.number_of_nodes() == 0:
        return {}

    nodes = list(graph.graph.nodes())

    clusters: Dict[str, List[str]] = {}
    node_to_cluster: Dict[str, str] = {}

    node_dirs = {node: _get_directory(node) for node in nodes}

    shared_imports = _compute_shared_imports(graph, nodes)

    bidirectional = _get_bidirectional_edges(graph)

    temp_graph = nx.Graph()

    for node in nodes:
        temp_graph.add_node(node)

    for i, node_a in enumerate(nodes):
        for node_b in nodes[i + 1 :]:
            weight = _compute_edge_weight(node_a, node_b, node_dirs, shared_imports, bidirectional)
            if weight > 0:
                temp_graph.add_edge(node_a, node_b, weight=weight)

    for component in greedy_modularity_communities(temp_graph, weight="weight"):
        cluster_id = f"cluster_{len(clusters) + 1}"
        cluster_files = sorted(list(component))
        clusters[cluster_id] = cluster_files

        for node in component:
            node_to_cluster[node] = cluster_id

    return clusters


def _get_directory(path: str) -> str:
    """Get directory portion of a file path."""
    parts = path.replace("\\", "/").split("/")
    if len(parts) > 1:
        return "/".join(parts[:-1])
    return ""


def _compute_shared_imports(graph: FileGraph, nodes: List[str]) -> Dict[str, set]:
    """Compute set of imports for each node."""
    imports = {}
    for node in nodes:
        file_node = graph.get_node(node)
        if file_node:
            imports[node] = set(file_node.imports)
        else:
            imports[node] = set()
    return imports


def _get_bidirectional_edges(graph: FileGraph) -> set:
    """Get set of node pairs with bidirectional edges."""
    bidirectional = set()
    for edge in graph.graph.edges():
        a, b = edge
        if graph.graph.has_edge(b, a):
            pair = tuple(sorted([a, b]))
            bidirectional.add(pair)
    return bidirectional


def _compute_edge_weight(
    node_a: str,
    node_b: str,
    node_dirs: Dict[str, str],
    shared_imports: Dict[str, set],
    bidirectional: set,
) -> int:
    """Compute weight of edge between two nodes based on signals."""
    weight = 0

    if node_dirs[node_a] == node_dirs[node_b] and node_dirs[node_a] != "":
        weight += 3

    imports_a = shared_imports.get(node_a, set())
    imports_b = shared_imports.get(node_b, set())
    shared = imports_a & imports_b
    if shared:
        weight += 2 * len(shared)

    pair = tuple(sorted([node_a, node_b]))
    if pair in bidirectional:
        weight += 4
    elif node_a in imports_b or node_b in imports_a:
        weight += 1

    return weight
