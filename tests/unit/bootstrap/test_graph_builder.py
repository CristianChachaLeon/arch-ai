"""Graph Builder - Tests for NetworkX graph construction.

SRP: graph_builder only builds the graph.
Parsing is done by ast_parser module separately.
"""

import networkx as nx

from archai.bootstrap.graph_builder import build_graph, FileNode, FileGraph


class TestGraphBuilder:
    """Test suite for graph_builder module - ONLY graph construction."""

    def test_build_graph_creates_nodes(self):
        """Should create a node for each FileNode provided."""
        # Arrange
        file_nodes = [
            FileNode(path="main.py", imports=[]),
            FileNode(path="utils.py", imports=[]),
        ]

        # Act
        graph = build_graph(file_nodes)

        # Assert
        assert graph.graph.number_of_nodes() == 2
        assert "main.py" in graph.graph.nodes()
        assert "utils.py" in graph.graph.nodes()

    def test_build_graph_creates_edges_from_imports(self):
        """Should create edges based on import relationships."""
        # Arrange
        file_nodes = [
            FileNode(path="main.py", imports=["utils.py"]),
            FileNode(path="utils.py", imports=[]),
        ]

        # Act
        graph = build_graph(file_nodes)

        # Assert
        assert ("main.py", "utils.py") in graph.graph.edges()

    def test_build_graph_handles_no_imports(self):
        """Should handle nodes with no imports."""
        # Arrange
        file_nodes = [
            FileNode(path="standalone.py", imports=[]),
        ]

        # Act
        graph = build_graph(file_nodes)

        # Assert
        assert graph.graph.number_of_nodes() == 1
        assert graph.graph.number_of_edges() == 0

    def test_build_graph_returns_networkx_graph(self):
        """Should return a FileGraph with nx.DiGraph."""
        # Arrange
        file_nodes = [
            FileNode(path="app.py", imports=[]),
        ]

        # Act
        result = build_graph(file_nodes)

        # Assert
        assert isinstance(result, FileGraph)
        assert isinstance(result.graph, nx.DiGraph)

    def test_build_graph_stores_file_metadata(self):
        """Should store file metadata in nodes."""
        # Arrange
        file_nodes = [
            FileNode(
                path="user.py",
                imports=["os"],
                functions=["authenticate"],
                classes=["User"],
            ),
        ]

        # Act
        graph = build_graph(file_nodes)

        # Assert
        node = graph.get_node("user.py")
        assert node is not None
        assert "User" in node.classes
        assert "authenticate" in node.functions
        assert "os" in node.imports

    def test_build_graph_handles_relative_imports(self):
        """Should handle relative imports (from . import x)."""
        # Arrange
        file_nodes = [
            FileNode(path="main.py", imports=["utils.py"]),
            FileNode(path="utils.py", imports=[]),
        ]

        # Act
        graph = build_graph(file_nodes)

        # Assert
        assert graph.graph.number_of_nodes() == 2
        assert ("main.py", "utils.py") in graph.graph.edges()

    def test_build_graph_empty_list(self):
        """Should handle empty list of nodes without errors."""
        # Act
        graph = build_graph([])

        # Assert
        assert graph.graph.number_of_nodes() == 0
        assert graph.graph.number_of_edges() == 0

    def test_build_graph_skips_nonexistent_targets(self):
        """Should skip edges when target file doesn't exist in the graph."""
        # Arrange
        file_nodes = [
            FileNode(path="main.py", imports=["nonexistent.py"]),
        ]

        # Act
        graph = build_graph(file_nodes)

        # Assert
        assert graph.graph.number_of_nodes() == 1
        assert graph.graph.number_of_edges() == 0

    def test_build_graph_handles_cycle_dependency(self):
        """Should handle circular dependencies gracefully."""
        # Arrange
        file_nodes = [
            FileNode(path="a.py", imports=["b.py"]),
            FileNode(path="b.py", imports=["a.py"]),
        ]

        # Act
        graph = build_graph(file_nodes)

        # Assert
        assert graph.graph.number_of_nodes() == 2
        assert graph.graph.number_of_edges() == 2
        assert ("a.py", "b.py") in graph.graph.edges()
        assert ("b.py", "a.py") in graph.graph.edges()

    def test_build_graph_deduplicates_edges(self):
        """Should not create duplicate edges for multiple imports to same target."""
        # Arrange
        file_nodes = [
            FileNode(path="main.py", imports=["utils.py", "utils.py"]),
            FileNode(path="utils.py", imports=[]),
        ]

        # Act
        graph = build_graph(file_nodes)

        # Assert
        assert graph.graph.number_of_edges() == 1

    def test_build_graph_handles_self_import(self):
        """Should not create self-loop edge."""
        # Arrange
        file_nodes = [
            FileNode(path="main.py", imports=["main.py"]),
        ]

        # Act
        graph = build_graph(file_nodes)

        # Assert
        assert graph.graph.number_of_edges() == 0
        assert ("main.py", "main.py") not in graph.graph.edges()


class TestFileNode:
    """Tests for FileNode data class."""

    def test_filename_returns_basename(self):
        """Should return just the filename from a path with directories."""
        # Arrange
        node = FileNode(path="src/main.py", imports=[])

        # Act
        result = node.filename

        # Assert
        assert result == "main.py"

    def test_filename_with_init_py(self):
        """Should return __init__.py for package init files."""
        # Arrange
        node = FileNode(path="src/pkg/__init__.py", imports=[])

        # Act
        result = node.filename

        # Assert
        assert result == "__init__.py"

    def test_filename_top_level(self):
        """Should return the filename for a top-level file."""
        # Arrange
        node = FileNode(path="utils.py", imports=[])

        # Act
        result = node.filename

        # Assert
        assert result == "utils.py"


class TestFileGraph:
    """Tests for FileGraph wrapper class."""

    def test_init_with_existing_graph(self):
        """Should wrap an existing nx.DiGraph when passed."""
        # Arrange
        existing = nx.DiGraph()
        existing.add_edge("a", "b")

        # Act
        file_graph = FileGraph(graph=existing)

        # Assert
        assert file_graph.graph.number_of_nodes() == 2
        assert file_graph.graph.number_of_edges() == 1
        assert ("a", "b") in file_graph.graph.edges()

    def test_detect_cycles_returns_empty_on_networkx_error(self, monkeypatch):
        """Should return empty list when nx.simple_cycles raises NetworkXError."""
        # Arrange
        file_graph = FileGraph()
        file_graph.graph.add_edge("a", "b")
        monkeypatch.setattr(
            "networkx.simple_cycles",
            lambda _: (_ for _ in ()).throw(nx.NetworkXError("boom")),
        )

        # Act
        cycles = file_graph.detect_cycles()

        # Assert
        assert cycles == []


class TestCollapseCycles:
    """Tests for collapse_cycles edge redirection logic."""

    def test_collapse_cycles_preserves_outside_to_cycle_edge(self):
        """Should redirect edges from outside nodes to cyclic_module."""
        # Arrange
        file_graph = FileGraph()
        file_graph.add_node(FileNode(path="a.py", imports=["b.py"]))
        file_graph.add_node(FileNode(path="b.py", imports=["a.py"]))
        file_graph.add_node(FileNode(path="c.py", imports=["a.py"]))
        file_graph.graph.add_edge("a.py", "b.py")
        file_graph.graph.add_edge("b.py", "a.py")
        file_graph.graph.add_edge("c.py", "a.py")

        # Act
        collapsed = file_graph.collapse_cycles()

        # Assert
        assert collapsed.graph.has_edge("c.py", "cyclic_module")
        assert "cyclic_module" in collapsed.graph.nodes()
        assert "a.py" not in collapsed.graph.nodes()
        assert "b.py" not in collapsed.graph.nodes()

    def test_collapse_cycles_preserves_cycle_to_outside_edge(self):
        """Should redirect edges from cycle nodes to outside target."""
        # Arrange
        file_graph = FileGraph()
        file_graph.add_node(FileNode(path="a.py", imports=["b.py"]))
        file_graph.add_node(FileNode(path="b.py", imports=["a.py"]))
        file_graph.add_node(FileNode(path="c.py", imports=[]))
        file_graph.graph.add_edge("a.py", "b.py")
        file_graph.graph.add_edge("b.py", "a.py")
        file_graph.graph.add_edge("a.py", "c.py")

        # Act
        collapsed = file_graph.collapse_cycles()

        # Assert
        assert collapsed.graph.has_edge("cyclic_module", "c.py")
        assert "a.py" not in collapsed.graph.nodes()
        assert "b.py" not in collapsed.graph.nodes()

    def test_collapse_cycles_preserves_non_cyclic_edge(self):
        """Should preserve edges between nodes outside any cycle as-is."""
        # Arrange
        file_graph = FileGraph()
        file_graph.add_node(FileNode(path="a.py", imports=["b.py"]))
        file_graph.add_node(FileNode(path="b.py", imports=["a.py"]))
        file_graph.add_node(FileNode(path="d.py", imports=["e.py"]))
        file_graph.add_node(FileNode(path="e.py", imports=[]))
        file_graph.graph.add_edge("a.py", "b.py")
        file_graph.graph.add_edge("b.py", "a.py")
        file_graph.graph.add_edge("d.py", "e.py")

        # Act
        collapsed = file_graph.collapse_cycles()

        # Assert
        assert collapsed.graph.has_edge("d.py", "e.py")
        assert collapsed.graph.number_of_edges() == 1  # d->e only, no cross-cycle edges
