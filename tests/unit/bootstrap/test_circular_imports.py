"""Circular Imports - Tests for cycle detection and collapse.

T-014: Handle circular imports (collapse cycles) — Colapsar ciclos en
nodos virtuales (e.g., "cyclic module")
"""

from archai.bootstrap.graph_builder import build_graph, FileNode


class TestCircularImportHandler:
    """Test suite for circular import detection and collapsing."""

    def test_detect_simple_cycle_a_b_a(self):
        """Should detect a simple A -> B -> A cycle."""
        file_nodes = [
            FileNode(path="a.py", imports=["b.py"]),
            FileNode(path="b.py", imports=["a.py"]),
        ]
        graph = build_graph(file_nodes)

        cycles = list(graph.detect_cycles())
        assert len(cycles) == 1

    def test_detect_cycle_with_three_nodes(self):
        """Should detect a three-node cycle: A -> B -> C -> A."""
        file_nodes = [
            FileNode(path="a.py", imports=["b.py"]),
            FileNode(path="b.py", imports=["c.py"]),
            FileNode(path="c.py", imports=["a.py"]),
        ]
        graph = build_graph(file_nodes)

        cycles = list(graph.detect_cycles())
        assert len(cycles) == 1

    def test_detect_multiple_cycles(self):
        """Should detect multiple independent cycles."""
        file_nodes = [
            FileNode(path="a.py", imports=["b.py"]),
            FileNode(path="b.py", imports=["a.py"]),
            FileNode(path="x.py", imports=["y.py"]),
            FileNode(path="y.py", imports=["x.py"]),
        ]
        graph = build_graph(file_nodes)

        cycles = list(graph.detect_cycles())
        assert len(cycles) == 2

    def test_no_cycles_returns_empty(self):
        """Should return empty list when no cycles exist."""
        file_nodes = [
            FileNode(path="a.py", imports=["b.py"]),
            FileNode(path="b.py", imports=["c.py"]),
            FileNode(path="c.py", imports=[]),
        ]
        graph = build_graph(file_nodes)

        cycles = list(graph.detect_cycles())
        assert len(cycles) == 0

    def test_collapse_cycle_creates_virtual_node(self):
        """Should create a virtual 'cyclic module' node when collapsing."""
        file_nodes = [
            FileNode(path="a.py", imports=["b.py"]),
            FileNode(path="b.py", imports=["a.py"]),
        ]
        graph = build_graph(file_nodes)

        collapsed = graph.collapse_cycles()

        assert collapsed.graph.number_of_nodes() == 1
        assert collapsed.get_node("cyclic_module") is not None

    def test_collapse_preserves_non_cyclic_relationships(self):
        """Should preserve edges to/from nodes outside cycles."""
        file_nodes = [
            FileNode(path="main.py", imports=["a.py"]),
            FileNode(path="a.py", imports=["b.py"]),
            FileNode(path="b.py", imports=["a.py"]),
        ]
        graph = build_graph(file_nodes)

        collapsed = graph.collapse_cycles()

        assert ("main.py", "cyclic_module") in collapsed.graph.edges()

    def test_collapse_without_cycles_preserves_structure(self):
        """Should preserve node/edge structure and metadata when no cycles exist."""
        file_nodes = [
            FileNode(path="main.py", imports=["a.py"]),
            FileNode(path="a.py", imports=["b.py"]),
            FileNode(path="b.py", imports=["c.py"]),
            FileNode(path="c.py", imports=[]),
        ]
        graph = build_graph(file_nodes)

        collapsed = graph.collapse_cycles()

        assert collapsed.graph.number_of_nodes() == 4
        assert collapsed.graph.number_of_edges() == 3
        assert ("main.py", "a.py") in collapsed.graph.edges()
        assert ("a.py", "b.py") in collapsed.graph.edges()
        assert ("b.py", "c.py") in collapsed.graph.edges()
        assert collapsed.get_node("main.py") is not None
        assert collapsed.get_node("a.py") is not None
        assert collapsed.get_node("b.py") is not None
        assert collapsed.get_node("c.py") is not None
        assert collapsed.get_node("cyclic_module") is None
