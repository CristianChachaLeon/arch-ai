"""Tests for the ArchAI Middleware Pipeline."""

from unittest.mock import AsyncMock

import pytest

from archai.inference.labeler import LabeledCluster
from archai.middleware.pipeline import ArchaiMiddleware, PipelineResult


class TestArchaiMiddleware:
    """Test suite for ArchaiMiddleware."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create a temporary repository with Python files."""
        # Create some Python files with imports
        (tmp_path / "main.py").write_text(
            """
import utils
from models import User

def run():
    pass
"""
        )

        (tmp_path / "utils.py").write_text(
            """
def helper():
    pass
"""
        )

        (tmp_path / "models").mkdir()
        (tmp_path / "models" / "__init__.py").write_text("")
        (tmp_path / "models" / "user.py").write_text(
            """
class User:
    pass
"""
        )

        (tmp_path / "services").mkdir()
        (tmp_path / "services" / "__init__.py").write_text("")
        (tmp_path / "services" / "auth.py").write_text(
            """
from models import User

def authenticate():
    pass
"""
        )

        return tmp_path

    async def test_middleware_processes_repository(self, temp_repo):
        """Middleware should process repository through full pipeline."""
        middleware = ArchaiMiddleware()
        result = await middleware.process(temp_repo)

        assert isinstance(result, PipelineResult)
        assert result.file_count > 0
        assert result.graph is not None

    async def test_pipeline_creates_clusters(self, temp_repo):
        """Pipeline should create clusters from the graph."""
        middleware = ArchaiMiddleware()
        result = await middleware.process(temp_repo)

        assert isinstance(result.clusters, dict)
        assert result.cluster_count > 0
        # At least some files should be clustered
        total_files_in_clusters = sum(len(files) for files in result.clusters.values())
        assert total_files_in_clusters > 0

    async def test_pipeline_result_to_dict(self, temp_repo):
        """PipelineResult should serialize to dict."""
        middleware = ArchaiMiddleware()
        result = await middleware.process(temp_repo)

        data = result.to_dict()

        assert "repo_path" in data
        assert "file_count" in data
        assert "edge_count" in data
        assert "cluster_count" in data
        assert "clusters" in data

    async def test_get_cluster_for_file(self, temp_repo):
        """Should find which cluster a file belongs to."""
        middleware = ArchaiMiddleware()
        result = await middleware.process(temp_repo)

        # Find a file that's in a cluster
        found_any = False
        for cluster_name, files in result.clusters.items():
            if files:
                # Test with the first file in the cluster
                found = result.get_cluster_for_file(files[0])
                assert found == cluster_name
                found_any = True
                break

        assert found_any, "Expected at least one clustered file for lookup assertion"

    async def test_middleware_handles_empty_directory(self, tmp_path):
        """Middleware should handle empty directory gracefully."""
        middleware = ArchaiMiddleware()
        result = await middleware.process(tmp_path)

        assert result.file_count == 0
        assert result.edge_count == 0
        assert result.cluster_count == 0
        assert result.clusters == {}

    async def test_middleware_handles_nonexistent_path(self, tmp_path):
        """Middleware should raise error for nonexistent path."""
        middleware = ArchaiMiddleware()

        missing_path = tmp_path / "definitely_missing_dir"
        # discover_python_files raises ValueError for invalid paths
        with pytest.raises(ValueError, match="Path is not a directory"):
            await middleware.process(missing_path)

    async def test_label_clusters_called_when_provider_given(self, temp_repo):
        """When an LLM provider is passed, label_clusters should be called."""
        mock_provider = AsyncMock(spec=["generate_structured"])
        mock_provider.generate_structured = AsyncMock(
            return_value=LabeledCluster(
                cluster_id="test_cluster",
                files=["main.py"],
                name="Test Module",
                description="A test module",
            )
        )

        middleware = ArchaiMiddleware(llm_provider=mock_provider)
        result = await middleware.process(temp_repo)

        assert mock_provider.generate_structured.called
        assert result.labeled_clusters is not None

    async def test_labeled_clusters_in_pipeline_result(self, temp_repo):
        """PipelineResult should contain labeled clusters when provider is given."""
        mock_provider = AsyncMock(spec=["generate_structured"])
        mock_provider.generate_structured = AsyncMock(
            return_value=LabeledCluster(
                cluster_id="test_cluster",
                files=["main.py"],
                name="Test Module",
                description="A test module",
            )
        )

        middleware = ArchaiMiddleware(llm_provider=mock_provider)
        result = await middleware.process(temp_repo)

        assert result.labeled_clusters is not None
        for lc in result.labeled_clusters:
            assert isinstance(lc, LabeledCluster)
            assert lc.name
            assert lc.description

    async def test_labeled_clusters_in_to_dict(self, temp_repo):
        """to_dict should include cluster_names when labeled clusters exist."""
        mock_provider = AsyncMock(spec=["generate_structured"])
        mock_provider.generate_structured = AsyncMock(
            return_value=LabeledCluster(
                cluster_id="test_cluster",
                files=["main.py"],
                name="Test Module",
                description="A test module",
            )
        )

        middleware = ArchaiMiddleware(llm_provider=mock_provider)
        result = await middleware.process(temp_repo)
        data = result.to_dict()

        assert "cluster_names" in data
        assert isinstance(data["cluster_names"], dict)
