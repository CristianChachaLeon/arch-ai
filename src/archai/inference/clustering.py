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

# Similarity weights - higher = more likely to be in same cluster
DIRECTORY_MATCH_WEIGHT = 3
SHARED_IMPORT_WEIGHT = 2
BIDIRECTIONAL_CALL_WEIGHT = 4
UNIDIRECTIONAL_CALL_WEIGHT = 1


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

    # Step 1: Build a graph where edges represent file similarity
    similarity_graph = _build_similarity_graph(graph)

    # Step 2: Find communities (clusters) using modularity optimization
    return _detect_communities(similarity_graph)


def _build_similarity_graph(graph: FileGraph) -> nx.Graph:
    """Build weighted graph where edge weight = file similarity."""
    nodes = list(graph.graph.nodes())

    # Pre-compute features for all nodes
    node_dirs = {node: _extract_directory(node) for node in nodes}
    shared_imports = _compute_shared_imports(graph, nodes)
    bidirectional_calls = _find_bidirectional_calls(graph)
    unidirectional_calls = _find_unidirectional_calls(graph)

    # Build weighted graph
    similarity_graph = nx.Graph()
    similarity_graph.add_nodes_from(nodes)

    for i, node_a in enumerate(nodes):
        for node_b in nodes[i + 1 :]:
            similarity = _calculate_similarity(
                node_a, node_b, node_dirs, shared_imports, bidirectional_calls, unidirectional_calls
            )
            if similarity > 0:
                similarity_graph.add_edge(node_a, node_b, weight=similarity)

    return similarity_graph


def _detect_communities(graph: nx.Graph) -> Dict[str, List[str]]:
    """Find communities using modularity optimization."""
    clusters: Dict[str, List[str]] = {}

    for component in greedy_modularity_communities(graph, weight="weight"):
        cluster_id = f"cluster_{len(clusters) + 1}"
        clusters[cluster_id] = sorted(list(component))

    return clusters


def _extract_directory(path: str) -> str:
    """Extract directory portion from a file path."""
    parts = path.replace("\\", "/").split("/")
    return "/".join(parts[:-1]) if len(parts) > 1 else ""


def _compute_shared_imports(graph: FileGraph, nodes: List[str]) -> Dict[str, set]:
    """Build a mapping of node -> set of imported modules."""
    return {
        node: set(graph.get_node(node).imports) if graph.get_node(node) else set() for node in nodes
    }


def _find_bidirectional_calls(graph: FileGraph) -> set:
    """Find all pairs of files that call each other (bidirectional)."""
    bidirectional = set()
    for edge in graph.graph.edges():
        source, target = edge
        if graph.graph.has_edge(target, source):
            pair = tuple(sorted([source, target]))
            bidirectional.add(pair)
    return bidirectional


def _find_unidirectional_calls(graph: FileGraph) -> set:
    """Find directed file dependency pairs (edges from graph)."""
    return set(graph.graph.edges())


def _calculate_similarity(
    node_a: str,
    node_b: str,
    node_dirs: Dict[str, str],
    shared_imports: Dict[str, set],
    bidirectional_calls: set,
    unidirectional_calls: set,
) -> int:
    """Calculate similarity score between two files (higher = more similar)."""
    similarity = 0

    # Signal 1: Same directory
    if node_dirs[node_a] == node_dirs[node_b] and node_dirs[node_a]:
        similarity += DIRECTORY_MATCH_WEIGHT

    # Signal 2: Shared imports
    imports_a = shared_imports.get(node_a, set())
    imports_b = shared_imports.get(node_b, set())
    common_imports = imports_a & imports_b
    if common_imports:
        similarity += SHARED_IMPORT_WEIGHT * len(common_imports)

    # Signal 3: Call relationships (using graph edges, not raw imports)
    pair = tuple(sorted([node_a, node_b]))
    if pair in bidirectional_calls:
        similarity += BIDIRECTIONAL_CALL_WEIGHT
    elif (node_a, node_b) in unidirectional_calls or (node_b, node_a) in unidirectional_calls:
        similarity += UNIDIRECTIONAL_CALL_WEIGHT

    return similarity
