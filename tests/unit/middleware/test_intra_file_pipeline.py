"""Intra-File Pipeline - Tests for pipeline with intra-file clustering."""

from archai.bootstrap.graph_builder import FileGraph, FileNode, FunctionGraph
from archai.middleware.pipeline import PipelineResult, ArchaiMiddleware


class TestPipelineResultSubClusters:
    """Tests for PipelineResult with intra-file clustering data."""

    def test_pipeline_result_sub_clusters(self):
        """PipelineResult should store and retrieve sub_clusters."""
        sub_clusters = {
            "src/main.c": {
                "helper": ["helper_a", "helper_b"],
                "main": ["main"],
            }
        }
        result = PipelineResult(
            repo_path="/test",
            graph=FileGraph(),
            clusters={},
            file_count=1,
            edge_count=0,
            cluster_count=0,
            sub_clusters=sub_clusters,
        )
        assert result.sub_clusters == sub_clusters
        assert "src/main.c" in result.sub_clusters
        assert "helper" in result.sub_clusters["src/main.c"]

    def test_pipeline_result_function_graph(self):
        """PipelineResult should store function_graph."""
        fg = FunctionGraph()
        result = PipelineResult(
            repo_path="/test",
            graph=FileGraph(),
            clusters={},
            file_count=0,
            edge_count=0,
            cluster_count=0,
            function_graph=fg,
        )
        assert result.function_graph is fg

    def test_pipeline_result_sub_clusters_default_empty(self):
        """sub_clusters should default to empty dict."""
        result = PipelineResult(
            repo_path="/test",
            graph=FileGraph(),
            clusters={},
            file_count=0,
            edge_count=0,
            cluster_count=0,
        )
        assert result.sub_clusters == {}

    def test_pipeline_result_function_graph_default_none(self):
        """function_graph should default to None."""
        result = PipelineResult(
            repo_path="/test",
            graph=FileGraph(),
            clusters={},
            file_count=0,
            edge_count=0,
            cluster_count=0,
        )
        assert result.function_graph is None


class TestBootstrapReturnsFileNodes:
    """Tests for _run_bootstrap return type."""

    def test_bootstrap_returns_file_nodes(self, tmp_path):
        """_run_bootstrap should return tuple of (list[FileNode], FileGraph)."""
        (tmp_path / "setup.py").write_text("from setuptools import setup\nsetup()\n")
        (tmp_path / "main.py").write_text("def main(): pass\n")

        middleware = ArchaiMiddleware()
        file_nodes, graph = middleware._run_bootstrap(tmp_path)

        assert isinstance(file_nodes, list)
        assert len(file_nodes) > 0
        assert all(isinstance(fn, FileNode) for fn in file_nodes)
        assert isinstance(graph, FileGraph)
