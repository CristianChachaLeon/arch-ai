"""Function Graph - Tests for FunctionNode, FunctionGraph, and build_function_graph."""

from archai.bootstrap.graph_builder import (
    FunctionNode,
    FunctionGraph,
    FileNode,
    build_function_graph,
    function_dependents,
    function_dependencies,
)
from archai.bootstrap.language import FunctionInfo


class TestFunctionNode:
    """Tests for the FunctionNode dataclass."""

    def test_function_node_creation(self):
        node = FunctionNode(
            name="my_func",
            file_path="src/main.c",
            calls_internal=["helper"],
            calls_external=["printf"],
        )
        assert node.name == "my_func"
        assert node.file_path == "src/main.c"
        assert node.calls_internal == ["helper"]
        assert node.calls_external == ["printf"]


class TestFunctionGraph:
    """Tests for the FunctionGraph wrapper class."""

    def test_function_graph_add_node(self):
        fg = FunctionGraph()
        node = FunctionNode(name="f1", file_path="a.c", calls_internal=[], calls_external=[])
        fg.add_node("a.c::f1", node)
        assert fg.node_count == 1
        assert fg.get_node("a.c::f1") is node

    def test_function_graph_add_edge(self):
        fg = FunctionGraph()
        n1 = FunctionNode(name="f1", file_path="a.c", calls_internal=["f2"], calls_external=[])
        n2 = FunctionNode(name="f2", file_path="a.c", calls_internal=[], calls_external=[])
        fg.add_node("a.c::f1", n1)
        fg.add_node("a.c::f2", n2)
        fg.graph.add_edge("a.c::f1", "a.c::f2")
        assert fg.edge_count == 1
        assert fg.graph.has_edge("a.c::f1", "a.c::f2")


class TestBuildFunctionGraph:
    """Tests for build_function_graph."""

    @staticmethod
    def _make_funcs(count: int, **overrides: dict) -> list[FunctionInfo]:
        """Helper to create a list of FunctionInfo objects for testing."""
        funcs = []
        for i in range(count):
            kwargs = {"name": f"f{i}", "line": i + 1}
            for val in overrides.values():
                if isinstance(val, dict) and i in val:
                    kwargs.update(val[i])
            funcs.append(FunctionInfo(**kwargs))
        return funcs

    def test_build_function_graph_empty(self):
        """Empty list of FileNodes should return an empty FunctionGraph."""
        result = build_function_graph([])
        assert result.node_count == 0
        assert result.edge_count == 0

    def test_build_function_graph_below_threshold(self):
        """FileNode with 5 functions_detail → empty graph (threshold is 20)."""
        funcs = self._make_funcs(5)
        file_node = FileNode(path="small.c", functions_detail=funcs)
        result = build_function_graph([file_node])
        assert result.node_count == 0

    def test_build_function_graph_above_threshold(self):
        """FileNode with 25 functions_detail → graph with 25 nodes."""
        funcs = self._make_funcs(25)
        file_node = FileNode(path="big.c", functions_detail=funcs)
        result = build_function_graph([file_node])
        assert result.node_count == 25

    def test_build_function_graph_internal_edges(self):
        """Functions that call each other internally → edges exist."""
        funcs = self._make_funcs(25, overrides={0: {"calls_internal": ["f1"]}})
        file_node = FileNode(path="edges.c", functions_detail=funcs)
        result = build_function_graph([file_node])
        assert result.node_count == 25
        assert result.graph.has_edge("edges.c::f0", "edges.c::f1")

    def test_build_function_graph_cross_file_edges(self):
        """Two FileNodes with cross-file calls → edges between them."""
        funcs_a = self._make_funcs(25, overrides={0: {"calls_external": ["callee_in_b"]}})
        file_a = FileNode(path="a.c", functions_detail=funcs_a)

        funcs_b = [FunctionInfo(name=f"f{i}", line=i + 1) for i in range(25)]
        funcs_b[0] = FunctionInfo(name="callee_in_b", line=1)
        file_b = FileNode(path="b.c", functions_detail=funcs_b)

        result = build_function_graph([file_a, file_b])
        assert result.node_count == 50
        assert result.graph.has_edge("a.c::f0", "b.c::callee_in_b")

    def test_function_dependents(self):
        """function_dependents should return correct predecessors."""
        funcs = self._make_funcs(25, overrides={0: {"calls_internal": ["f1"]}})
        file_node = FileNode(path="test.c", functions_detail=funcs)
        result = build_function_graph([file_node])
        deps = function_dependents(result, "test.c", "f1")
        assert "test.c::f0" in deps

    def test_function_dependencies(self):
        """function_dependencies should return correct successors."""
        funcs = self._make_funcs(25, overrides={0: {"calls_internal": ["f1"]}})
        file_node = FileNode(path="test.c", functions_detail=funcs)
        result = build_function_graph([file_node])
        deps = function_dependencies(result, "test.c", "f0")
        assert "test.c::f1" in deps

    def test_function_dependents_empty_for_leaf(self):
        """Leaf function with no callers should return empty dependents."""
        funcs = self._make_funcs(25, overrides={0: {"calls_internal": ["f1"]}})
        file_node = FileNode(path="test.c", functions_detail=funcs)
        result = build_function_graph([file_node])
        deps = function_dependents(result, "test.c", "f0")
        assert deps == []

    def test_function_dependencies_empty_for_root(self):
        """Root function with no calls should return empty dependencies."""
        funcs = self._make_funcs(25)
        file_node = FileNode(path="test.c", functions_detail=funcs)
        result = build_function_graph([file_node])
        deps = function_dependencies(result, "test.c", "f0")
        assert deps == []
