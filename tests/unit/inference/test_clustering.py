"""Clustering Heuristics - Tests for clustering files into logical subsystems.

This module tests the clustering heuristics that detect logical subsystems
based on graph structure (directory proximity, shared imports, call density).
"""

from archai.bootstrap.graph_builder import build_graph, FileNode
from archai.inference.clustering import cluster_files


class TestClustering:
    """Test suite for clustering heuristics."""

    def test_cluster_by_directory_proximity(self):
        """Files in same directory should be in same cluster."""
        file_nodes = [
            FileNode(path="src/models/user.py", imports=[]),
            FileNode(path="src/models/auth.py", imports=[]),
            FileNode(path="src/utils/helper.py", imports=[]),
        ]
        graph = build_graph(file_nodes)

        clusters = cluster_files(graph)

        user_cluster = None
        auth_cluster = None
        helper_cluster = None

        for cluster_name, files in clusters.items():
            if "src/models/user.py" in files:
                user_cluster = cluster_name
            if "src/models/auth.py" in files:
                auth_cluster = cluster_name
            if "src/utils/helper.py" in files:
                helper_cluster = cluster_name

        assert user_cluster is not None
        assert auth_cluster is not None
        assert helper_cluster is not None

        assert user_cluster == auth_cluster
        assert user_cluster != helper_cluster

    def test_cluster_by_shared_imports(self):
        """Files that import the same modules should be in same cluster."""
        file_nodes = [
            FileNode(path="app.py", imports=["utils.py"]),
            FileNode(path="service.py", imports=["utils.py"]),
            FileNode(path="other.py", imports=[]),
            FileNode(path="utils.py", imports=[]),
        ]
        graph = build_graph(file_nodes)

        clusters = cluster_files(graph)

        app_cluster = None
        service_cluster = None
        other_cluster = None

        for cluster_name, files in clusters.items():
            if "app.py" in files:
                app_cluster = cluster_name
            if "service.py" in files:
                service_cluster = cluster_name
            if "other.py" in files:
                other_cluster = cluster_name

        assert app_cluster is not None
        assert service_cluster is not None
        assert app_cluster == service_cluster
        assert other_cluster != app_cluster
        assert other_cluster != service_cluster

    def test_cluster_by_call_density(self):
        """Files that call each other should be in same cluster."""
        file_nodes = [
            FileNode(path="main.py", imports=["processor.py"]),
            FileNode(path="processor.py", imports=["main.py"]),
            FileNode(path="standalone.py", imports=[]),
        ]
        graph = build_graph(file_nodes)

        clusters = cluster_files(graph)

        main_cluster = None
        processor_cluster = None

        for cluster_name, files in clusters.items():
            if "main.py" in files:
                main_cluster = cluster_name
            if "processor.py" in files:
                processor_cluster = cluster_name

        assert main_cluster is not None
        assert processor_cluster is not None
        assert main_cluster == processor_cluster

    def test_cluster_returns_dict_with_list_values(self):
        """Should return a dict where each value is a list of file paths."""
        file_nodes = [
            FileNode(path="a.py", imports=[]),
        ]
        graph = build_graph(file_nodes)

        clusters = cluster_files(graph)

        assert isinstance(clusters, dict)
        assert len(clusters) > 0

        for cluster_name, files in clusters.items():
            assert isinstance(cluster_name, str)
            assert isinstance(files, list)
            assert all(isinstance(f, str) for f in files)

    def test_cluster_handles_empty_graph(self):
        """Should handle empty graph without errors."""
        graph = build_graph([])

        clusters = cluster_files(graph)

        assert isinstance(clusters, dict)
        assert len(clusters) == 0

    def test_cluster_single_file(self):
        """Should handle single file graph."""
        file_nodes = [
            FileNode(path="main.py", imports=[]),
        ]
        graph = build_graph(file_nodes)

        clusters = cluster_files(graph)

        assert len(clusters) >= 1
        assert "main.py" in sum(clusters.values(), [])

    def test_cluster_combined_signals(self):
        """Should combine directory, imports, and call density signals."""
        file_nodes = [
            FileNode(path="src/api/main.py", imports=["handlers.py"]),
            FileNode(path="src/api/handlers.py", imports=["services.py"]),
            FileNode(path="src/api/services.py", imports=["models.py"]),
            FileNode(path="src/models/user.py", imports=[]),
            FileNode(path="tests/test_user.py", imports=[]),
        ]
        graph = build_graph(file_nodes)

        clusters = cluster_files(graph)

        api_clusters = [
            files for files in clusters.values() if all(f.startswith("src/api/") for f in files)
        ]
        assert any(len(cluster) >= 3 for cluster in api_clusters)
