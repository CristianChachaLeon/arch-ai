"""Clustering Heuristics - Detect logical subsystems based on graph structure.

This module implements three clustering signals:
1. Directory proximity - files in same directory
2. Shared imports - files importing same modules
3. Call density - files that call each other
"""

import re

import networkx as nx
from networkx.algorithms.community import greedy_modularity_communities
from typing import Dict, List

from archai.bootstrap.graph_builder import FileGraph, FunctionGraph

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


# Intra-file function clustering constants
# Note: SAME_FILE is NOT a weight — being in the same file is the grouping criterion,
# not a similarity signal. Differentiation comes from call relationships and naming.
FUNCTION_BIDIRECTIONAL_CALL_WEIGHT = 10
FUNCTION_UNIDIRECTIONAL_CALL_WEIGHT = 5
FUNCTION_SHARED_CALLED_WEIGHT = 2
FUNCTION_PREFIX_MATCH_WEIGHT = 8


def cluster_functions(fg: FunctionGraph) -> dict[str, list[str]]:
    """Cluster functions within their parent files.

    For each file in the function graph, builds a similarity graph
    of its functions and detects communities using modularity optimization.

    Args:
        fg: A FunctionGraph containing function-level call relationships.

    Returns:
        Dict mapping file paths to dicts of {module_name: [function_names]}.
    """
    # Group function nodes by file
    file_groups: dict[str, list[str]] = {}
    for key in fg.graph.nodes():
        file_path = key.split("::")[0]
        if file_path not in file_groups:
            file_groups[file_path] = []
        file_groups[file_path].append(key)

    result: dict[str, dict[str, list[str]]] = {}

    for file_path, func_keys in file_groups.items():
        if len(func_keys) < 2:
            result[file_path] = {"module_1": [k.split("::")[1] for k in func_keys]}
            continue

        sim_graph = nx.Graph()
        sim_graph.add_nodes_from(func_keys)

        for i, a in enumerate(func_keys):
            for b in func_keys[i + 1 :]:
                similarity = _calc_function_similarity(fg, a, b)
                if similarity > 0:
                    sim_graph.add_edge(a, b, weight=similarity)

        clusters: dict[str, list[str]] = {}
        for component in greedy_modularity_communities(sim_graph, weight="weight"):
            cluster_id = f"module_{len(clusters) + 1}"
            clusters[cluster_id] = sorted(component)

        named = _auto_name_clusters(clusters)
        result[file_path] = {
            name: [k.split("::")[1] for k in funcs] for name, funcs in named.items()
        }

    return result


def _calc_function_similarity(fg: FunctionGraph, key_a: str, key_b: str) -> int:
    """Calculate similarity between two functions."""
    similarity = 0
    node_a = fg.get_node(key_a)
    node_b = fg.get_node(key_b)

    if node_a is None or node_b is None:
        return 0

    # Signal 1: Same naming prefix (e.g., "print*", "sel*", "du_*")
    name_a = node_a.name
    name_b = node_b.name
    prefix_a = re.match(r"^([A-Za-z_][a-z0-9_]*)", name_a)
    prefix_b = re.match(r"^([A-Za-z_][a-z0-9_]*)", name_b)
    if prefix_a and prefix_b and prefix_a.group(1) == prefix_b.group(1):
        similarity += FUNCTION_PREFIX_MATCH_WEIGHT

    if fg.graph.has_edge(key_a, key_b) and fg.graph.has_edge(key_b, key_a):
        similarity += FUNCTION_BIDIRECTIONAL_CALL_WEIGHT
    elif fg.graph.has_edge(key_a, key_b) or fg.graph.has_edge(key_b, key_a):
        similarity += FUNCTION_UNIDIRECTIONAL_CALL_WEIGHT

    calls_a = set()
    if node_a.calls_internal:
        calls_a.update(node_a.calls_internal)
    if node_a.calls_external:
        calls_a.update(node_a.calls_external)
    calls_b = set()
    if node_b.calls_internal:
        calls_b.update(node_b.calls_internal)
    if node_b.calls_external:
        calls_b.update(node_b.calls_external)
    shared = calls_a & calls_b
    if shared:
        similarity += FUNCTION_SHARED_CALLED_WEIGHT * len(shared)

    return similarity


def _auto_name_clusters(clusters: dict[str, list[str]]) -> dict[str, list[str]]:
    """Name clusters by the most common function prefix.

    Extracts the leading lowercase word prefix from each function name
    and uses the most common prefix as the cluster name.

    Args:
        clusters: Dict of {cluster_id: [function_keys]}.

    Returns:
        Dict of {name: [function_keys]} where names are auto-generated.
    """
    named: dict[str, list[str]] = {}
    for cluster_id, func_keys in clusters.items():
        names = [k.split("::")[-1] for k in func_keys]
        prefix_counts: dict[str, int] = {}
        for name in names:
            m = re.match(r"^([a-z_][a-z0-9_]*)", name)
            if m:
                prefix = m.group(1)
                prefix_counts[prefix] = prefix_counts.get(prefix, 0) + 1

        if prefix_counts:
            best_prefix = max(prefix_counts, key=prefix_counts.get)
            named[best_prefix] = func_keys
        else:
            named[cluster_id] = func_keys

    return named
