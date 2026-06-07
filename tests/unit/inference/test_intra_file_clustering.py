"""Intra-File Clustering - Tests for cluster_functions and helpers."""

from archai.bootstrap.graph_builder import FunctionNode, FunctionGraph
from archai.inference.clustering import (
    cluster_functions,
    _calc_function_similarity,
    _auto_name_clusters,
)


class TestClusterFunctions:
    """Tests for cluster_functions."""

    def test_cluster_functions_empty_graph(self):
        """Empty FunctionGraph → empty dict."""
        result = cluster_functions(FunctionGraph())
        assert result == {}

    def test_cluster_functions_single_function(self):
        """Graph with 1 function → single module."""
        fg = FunctionGraph()
        node = FunctionNode(name="foo", file_path="a.c", calls_internal=[], calls_external=[])
        fg.add_node("a.c::foo", node)
        result = cluster_functions(fg)
        assert result == {"a.c": {"module_1": ["foo"]}}

    def test_cluster_functions_by_prefix(self):
        """Functions with same prefix should cluster together."""
        fg = FunctionGraph()
        for name in ["printA", "printB", "printC"]:
            node = FunctionNode(name=name, file_path="a.c", calls_internal=[], calls_external=[])
            fg.add_node(f"a.c::{name}", node)

        # Fully connect the graph so community detection puts them together
        names = ["printA", "printB", "printC"]
        for i in range(len(names)):
            for j in range(len(names)):
                if i != j:
                    fg.graph.add_edge(f"a.c::{names[i]}", f"a.c::{names[j]}")

        result = cluster_functions(fg)
        assert "a.c" in result
        assert "print" in result["a.c"]
        assert sorted(result["a.c"]["print"]) == sorted(names)


class TestAutoNameClusters:
    """Tests for _auto_name_clusters."""

    def test_auto_name_clusters_prefix(self):
        """Cluster with functions 'printA', 'printB', 'printC' → named 'print'."""
        clusters = {
            "module_1": [
                "a.c::printA",
                "a.c::printB",
                "a.c::printC",
            ],
        }
        named = _auto_name_clusters(clusters)
        assert "print" in named
        assert len(named["print"]) == 3

    def test_auto_name_clusters_no_prefix(self):
        """Functions 'Abc', 'Xyz' (uppercase) → no prefix match → fallback to module_N."""
        clusters = {
            "module_1": ["a.c::Abc", "a.c::Xyz"],
        }
        named = _auto_name_clusters(clusters)
        assert "module_1" in named
        assert len(named["module_1"]) == 2


class TestCalcFunctionSimilarity:
    """Tests for _calc_function_similarity."""

    def test_calc_function_similarity_bidirectional(self):
        """Functions that call each other → high similarity."""
        fg = FunctionGraph()
        n1 = FunctionNode(name="foo", file_path="a.c", calls_internal=["bar"], calls_external=[])
        n2 = FunctionNode(name="bar", file_path="a.c", calls_internal=["foo"], calls_external=[])
        fg.add_node("a.c::foo", n1)
        fg.add_node("a.c::bar", n2)
        fg.graph.add_edge("a.c::foo", "a.c::bar")
        fg.graph.add_edge("a.c::bar", "a.c::foo")
        sim = _calc_function_similarity(fg, "a.c::foo", "a.c::bar")
        assert sim == 10

    def test_calc_function_similarity_prefix(self):
        """Functions with same prefix → medium similarity."""
        fg = FunctionGraph()
        n1 = FunctionNode(name="printHello", file_path="a.c", calls_internal=[], calls_external=[])
        n2 = FunctionNode(name="printWorld", file_path="a.c", calls_internal=[], calls_external=[])
        fg.add_node("a.c::printHello", n1)
        fg.add_node("a.c::printWorld", n2)
        sim = _calc_function_similarity(fg, "a.c::printHello", "a.c::printWorld")
        assert sim == 8

    def test_calc_function_similarity_no_relation(self):
        """Functions with no calls, no shared prefix → 0 similarity."""
        fg = FunctionGraph()
        n1 = FunctionNode(name="abc", file_path="a.c", calls_internal=[], calls_external=[])
        n2 = FunctionNode(name="xyz", file_path="a.c", calls_internal=[], calls_external=[])
        fg.add_node("a.c::abc", n1)
        fg.add_node("a.c::xyz", n2)
        sim = _calc_function_similarity(fg, "a.c::abc", "a.c::xyz")
        assert sim == 0

    def test_calc_function_similarity_missing_node(self):
        """If either node is missing from the graph → 0."""
        fg = FunctionGraph()
        node = FunctionNode(name="foo", file_path="a.c", calls_internal=[], calls_external=[])
        fg.add_node("a.c::foo", node)
        sim = _calc_function_similarity(fg, "a.c::foo", "a.c::nonexistent")
        assert sim == 0

    def test_calc_function_similarity_shared_calls(self):
        """Functions that call the same functions get shared-called weight."""
        fg = FunctionGraph()
        n1 = FunctionNode(name="a1", file_path="a.c", calls_internal=["util"], calls_external=[])
        n2 = FunctionNode(name="a2", file_path="a.c", calls_internal=["util"], calls_external=[])
        fg.add_node("a.c::a1", n1)
        fg.add_node("a.c::a2", n2)
        sim = _calc_function_similarity(fg, "a.c::a1", "a.c::a2")
        assert sim == 2  # FUNCTION_SHARED_CALLED_WEIGHT (2) * 1 shared call
