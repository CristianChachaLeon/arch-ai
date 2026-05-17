"""Graph Builder - Tests for NetworkX graph construction.

SRP: graph_builder only builds the graph.
Parsing is done by ast_parser module separately.
"""

from pathlib import Path
import networkx as nx

from archai.bootstrap.ast_parser import parse_python_file, get_imports, get_functions, get_classes
from archai.bootstrap.graph_builder import build_graph, FileNode, FileGraph


class TestGraphBuilder:
    """Test suite for graph_builder module - ONLY graph construction."""

    @staticmethod
    def create_file_nodes(tmp_path: Path, files: dict[str, str]) -> list[FileNode]:
        """Parse files and create FileNodes - parsing happens in ast_parser, not here."""
        file_nodes = []

        for filename, content in files.items():
            file_path = tmp_path / filename
            file_path.write_text(content)

            # Parse is done by ast_parser (separate responsibility)
            tree = parse_python_file(file_path)
            imports = get_imports(tree)
            functions = get_functions(tree)
            classes = get_classes(tree)

            file_nodes.append(
                FileNode(
                    path=filename,
                    imports=imports,
                    functions=functions,
                    classes=classes,
                )
            )

        return file_nodes

    def test_build_graph_creates_nodes(self, tmp_path: Path):
        """Should create a node for each FileNode provided."""
        # Arrange
        files = {
            "main.py": "def main(): pass",
            "utils.py": "def helper(): pass",
        }
        file_nodes = self.create_file_nodes(tmp_path, files)

        # Act
        graph = build_graph(file_nodes)

        # Assert
        assert graph.graph.number_of_nodes() == 2
        assert "main.py" in graph.graph.nodes()
        assert "utils.py" in graph.graph.nodes()

    def test_build_graph_creates_edges_from_imports(self, tmp_path: Path):
        """Should create edges based on import relationships."""
        # Arrange
        files = {
            "main.py": "import utils",
            "utils.py": "def helper(): pass",
        }
        file_nodes = self.create_file_nodes(tmp_path, files)

        # Act
        graph = build_graph(file_nodes)

        # Assert
        edges = list(graph.graph.edges())
        assert ("main.py", "utils.py") in edges

    def test_build_graph_handles_no_imports(self, tmp_path: Path):
        """Should handle nodes with no imports."""
        # Arrange
        files = {
            "standalone.py": "def foo(): pass",
        }
        file_nodes = self.create_file_nodes(tmp_path, files)

        # Act
        graph = build_graph(file_nodes)

        # Assert
        assert graph.graph.number_of_nodes() == 1
        assert graph.graph.number_of_edges() == 0

    def test_build_graph_returns_networkx_graph(self, tmp_path: Path):
        """Should return a FileGraph with nx.DiGraph."""
        # Arrange
        files = {"app.py": "import os"}
        file_nodes = self.create_file_nodes(tmp_path, files)

        # Act
        result = build_graph(file_nodes)

        # Assert
        assert isinstance(result, FileGraph)
        assert isinstance(result.graph, nx.DiGraph)

    def test_build_graph_stores_file_metadata(self, tmp_path: Path):
        """Should store file metadata in nodes."""
        # Arrange
        files = {
            "user.py": """
import os

class User:
    def authenticate(self):
        pass
"""
        }
        file_nodes = self.create_file_nodes(tmp_path, files)

        # Act
        graph = build_graph(file_nodes)

        # Assert
        node = graph.get_node("user.py")
        assert node is not None
        assert "User" in node.classes
        assert "authenticate" in node.functions
        assert "os" in node.imports

    def test_build_graph_handles_relative_imports(self, tmp_path: Path):
        """Should handle relative imports (from . import x)."""
        # Arrange
        files = {
            "main.py": "from . import utils",
            "utils.py": "def helper(): pass",
        }
        file_nodes = self.create_file_nodes(tmp_path, files)

        # Act
        graph = build_graph(file_nodes)

        # Assert
        assert graph.graph.number_of_nodes() == 2

    def test_build_graph_empty_list(self, tmp_path: Path):
        """Should handle empty list of nodes without errors."""
        # Act
        graph = build_graph([])

        # Assert
        assert graph.graph.number_of_nodes() == 0
        assert graph.graph.number_of_edges() == 0
