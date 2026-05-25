"""ArchaiOrchestrator - Tests for the full pipeline orchestrator."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from archai.http.models import ContextPacket, FileMetadata, SubsystemConstraints
from archai.middleware.pipeline import PipelineResult


@pytest.fixture
def base_clusters():
    return {
        "api": ["src/api/routes.py", "src/api/http_handlers.py"],
        "core": ["src/core/engine.py", "src/core/models.py", "tests/core/test_engine.py"],
        "tests": [
            "tests/api/test_routes.py",
            "tests/api/test_http_handlers.py",
            "tests/api/test_integration.py",
        ],
    }


@pytest.fixture
def mock_middleware(base_clusters):
    m = AsyncMock()
    result = PipelineResult(
        repo_path="/fake/repo",
        graph=AsyncMock(),
        clusters=base_clusters,
        file_count=8,
        edge_count=3,
        cluster_count=3,
        labeled_clusters=None,
    )
    m.process.return_value = result
    return m


@pytest.fixture
def cluster_aware_clusters():
    return {
        "cluster_1": [
            "src/api/routes.py",
            "src/api/http_handlers.py",
            "src/common/engine.py",
        ],
        "cluster_2": ["src/core/engine.py"],
        "cluster_0": [
            "tests/api/test_routes.py",  # source → cluster_1
            "tests/api/test_http_handlers.py",  # source → cluster_1
            "tests/common/test_engine.py",  # source → cluster_1
            "tests/core/test_engine.py",  # source → cluster_2
            "tests/api/test_integration.py",  # source → no cluster
        ],
    }


@pytest.fixture
def cluster_aware_middleware(cluster_aware_clusters):
    m = AsyncMock()
    result = PipelineResult(
        repo_path="/fake/repo",
        graph=AsyncMock(),
        clusters=cluster_aware_clusters,
        file_count=9,
        edge_count=3,
        cluster_count=3,
        labeled_clusters=None,
    )
    m.process.return_value = result
    return m


class TestArchaiOrchestrator:
    """Test suite for ArchaiOrchestrator."""

    async def test_get_context_returns_context_packet(self, mock_middleware):
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        orch = ArchaiOrchestrator(mock_middleware)
        packet = await orch.get_context("http", "/fake/repo")

        assert isinstance(packet, ContextPacket)

    async def test_get_context_resolves_focus(self, mock_middleware):
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        orch = ArchaiOrchestrator(mock_middleware)
        packet = await orch.get_context("http handler", "/fake/repo")

        assert packet.focus == "api"

    async def test_get_context_includes_subgraph(self, mock_middleware):
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        orch = ArchaiOrchestrator(mock_middleware)
        packet = await orch.get_context("http", "/fake/repo")

        assert "src/api/routes.py" in packet.subgraph
        assert "src/api/http_handlers.py" in packet.subgraph
        assert "src/core/engine.py" not in packet.subgraph

    async def test_get_context_focus_is_semantic_label(self, base_clusters):
        """Focus should be the semantic label from LabeledCluster.name, not the raw cluster ID."""
        from archai.orchestrator.orchestrator import ArchaiOrchestrator
        from archai.inference.labeler import LabeledCluster

        labeled = [
            LabeledCluster(
                cluster_id="api",
                files=["src/api/routes.py", "src/api/http_handlers.py"],
                name="API Layer",
                description="HTTP API endpoints and routing",
                reasoning="Contains HTTP handlers and route definitions",
            ),
            LabeledCluster(
                cluster_id="core",
                files=["src/core/engine.py", "src/core/models.py"],
                name="Core Engine",
                description="Core business logic and data models",
                reasoning="Contains engine and model definitions",
            ),
        ]
        m = AsyncMock()
        result = PipelineResult(
            repo_path="/fake/repo",
            graph=AsyncMock(),
            clusters=base_clusters,
            file_count=8,
            edge_count=3,
            cluster_count=3,
            labeled_clusters=labeled,
        )
        m.process.return_value = result

        orch = ArchaiOrchestrator(m)
        packet = await orch.get_context("data models", "/fake/repo")

        assert packet.focus == "Core Engine"
        assert packet.focus != "core"

    async def test_get_context_with_labeled_clusters(self, base_clusters):
        from archai.orchestrator.orchestrator import ArchaiOrchestrator
        from archai.inference.labeler import LabeledCluster

        labeled = [
            LabeledCluster(
                cluster_id="api",
                files=["src/api/routes.py", "src/api/http_handlers.py"],
                name="API Layer",
                description="HTTP API endpoints and routing",
                reasoning="Contains HTTP handlers and route definitions",
            ),
            LabeledCluster(
                cluster_id="core",
                files=["src/core/engine.py", "src/core/models.py"],
                name="Core Engine",
                description="Core business logic and data models",
                reasoning="Contains engine and model definitions",
            ),
        ]
        m = AsyncMock()
        result = PipelineResult(
            repo_path="/fake/repo",
            graph=AsyncMock(),
            clusters=base_clusters,
            file_count=8,
            edge_count=3,
            cluster_count=3,
            labeled_clusters=labeled,
        )
        m.process.return_value = result

        orch = ArchaiOrchestrator(m)
        packet = await orch.get_context("data models", "/fake/repo")

        assert packet.focus == "Core Engine"
        assert isinstance(packet.focus_reasoning, str) and len(packet.focus_reasoning) > 0

    async def test_get_context_without_labeled_clusters(self, mock_middleware):
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        orch = ArchaiOrchestrator(mock_middleware)
        packet = await orch.get_context("http", "/fake/repo")

        assert isinstance(packet, ContextPacket)
        assert packet.focus == "api"

    async def test_get_context_unknown_focus(self, mock_middleware):
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        orch = ArchaiOrchestrator(mock_middleware)
        packet = await orch.get_context("zzzznonexistent", "/fake/repo")

        assert packet.focus == "unknown"
        assert packet.subgraph == []

    async def test_get_context_packet_fields(self, mock_middleware):
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        orch = ArchaiOrchestrator(mock_middleware)
        packet = await orch.get_context("http", "/fake/repo")

        assert isinstance(packet.focus, str)
        assert isinstance(packet.focus_reasoning, str)
        assert isinstance(packet.constraints, SubsystemConstraints)
        assert isinstance(packet.subgraph, list)
        assert isinstance(packet.relevant_files, list)
        assert isinstance(packet.metadata, dict)

        assert packet.metadata.get("source") == "orchestrator"
        assert packet.metadata.get("cluster_count") == 3

        if packet.relevant_files:
            rf = packet.relevant_files[0]
            assert isinstance(rf, FileMetadata)
            assert isinstance(rf.path, str)
            assert isinstance(rf.reason, str)
            assert isinstance(rf.importance, float)

    async def test_context_includes_related_test_files(self, mock_middleware):
        """Test files related to focus should appear in relevant_files."""
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        orch = ArchaiOrchestrator(mock_middleware)
        packet = await orch.get_context("http handler", "/fake/repo")

        test_file_paths = [rf.path for rf in packet.relevant_files]
        assert "tests/api/test_routes.py" in test_file_paths
        assert "tests/api/test_http_handlers.py" in test_file_paths

    async def test_subgraph_includes_test_files(self, mock_middleware):
        """Test files should also appear in subgraph."""
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        orch = ArchaiOrchestrator(mock_middleware)
        packet = await orch.get_context("http handler", "/fake/repo")

        assert "tests/api/test_routes.py" in packet.subgraph

    async def test_unrelated_test_files_excluded(self, mock_middleware):
        """Test files from other subsystems should not appear."""
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        orch = ArchaiOrchestrator(mock_middleware)
        packet = await orch.get_context("http handler", "/fake/repo")

        test_file_paths = [rf.path for rf in packet.relevant_files]
        assert "tests/core/test_engine.py" not in test_file_paths

    def test_find_related_test_files_cluster_aware(self, cluster_aware_clusters):
        """Only test files whose source cluster matches the focus cluster should be included."""
        from archai.orchestrator.orchestrator import _find_related_test_files

        focus_files = cluster_aware_clusters["cluster_1"]
        result = _find_related_test_files(focus_files, cluster_aware_clusters)

        assert "tests/api/test_routes.py" in result
        assert "tests/api/test_http_handlers.py" in result
        assert "tests/common/test_engine.py" in result
        assert "tests/core/test_engine.py" not in result
        assert "tests/api/test_integration.py" not in result

    async def test_cluster_aware_filters_via_orchestrator(self, cluster_aware_middleware):
        """Orchestrator should only include tests whose source cluster matches focus."""
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        orch = ArchaiOrchestrator(cluster_aware_middleware)
        packet = await orch.get_context("routes", "/fake/repo")

        test_file_paths = [rf.path for rf in packet.relevant_files]
        assert "tests/api/test_routes.py" in test_file_paths
        assert "tests/api/test_http_handlers.py" in test_file_paths
        assert "tests/common/test_engine.py" in test_file_paths
        assert "tests/core/test_engine.py" not in test_file_paths
        assert "tests/api/test_integration.py" not in test_file_paths

    async def test_test_files_excluded_when_source_has_no_cluster(self, mock_middleware):
        """Test files whose source file isn't in any cluster should be excluded."""
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        orch = ArchaiOrchestrator(mock_middleware)
        packet = await orch.get_context("http handler", "/fake/repo")

        test_file_paths = [rf.path for rf in packet.relevant_files]
        # tests/api/test_integration.py maps to src/api/integration.py which
        # doesn't exist in any cluster → excluded by cluster-aware refinement
        assert "tests/api/test_integration.py" not in test_file_paths

    async def test_unknown_focus_has_no_test_files(self, mock_middleware):
        """Unknown focus should have empty subgraph and no test files."""
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        orch = ArchaiOrchestrator(mock_middleware)
        packet = await orch.get_context("nonexistent", "/fake/repo")

        assert packet.focus == "unknown"
        assert packet.subgraph == []

    async def test_concurrent_requests_dedup_process_call(self, mock_middleware):
        """Concurrent requests for same repo should call middleware.process() only once."""
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        orch = ArchaiOrchestrator(mock_middleware)

        repo_path = "/fake/repo"
        results = await asyncio.gather(
            orch.get_context("http", repo_path),
            orch.get_context("auth", repo_path),
        )

        assert len(results) == 2
        assert isinstance(results[0], ContextPacket)
        assert isinstance(results[1], ContextPacket)

        mock_middleware.process.assert_awaited_once()

    async def test_constraints_populated_from_labeled_clusters(self, base_clusters):
        """Constraints should be populated from the LabeledCluster matching focus."""
        from archai.orchestrator.orchestrator import ArchaiOrchestrator
        from archai.inference.labeler import LabeledCluster

        labeled = [
            LabeledCluster(
                cluster_id="api",
                files=["src/api/routes.py"],
                name="API Layer",
                description="HTTP API endpoints",
                reasoning="Contains HTTP handlers",
                async_only=True,
                forbidden_dependencies=["src/legacy/"],
            ),
            LabeledCluster(
                cluster_id="core",
                files=["src/core/engine.py"],
                name="Core Engine",
                description="Core business logic",
                reasoning="Contains engine",
                no_blocking_io=True,
                allowed_dependencies=["src/common/"],
            ),
        ]
        m = AsyncMock()
        result = PipelineResult(
            repo_path="/fake/repo",
            graph=AsyncMock(),
            clusters=base_clusters,
            file_count=4,
            edge_count=3,
            cluster_count=2,
            labeled_clusters=labeled,
        )
        m.process.return_value = result

        orch = ArchaiOrchestrator(m)
        packet = await orch.get_context("http", "/fake/repo")

        # Focus matched "api" cluster → should use api LabeledCluster constraints
        assert packet.constraints.async_only is True
        assert packet.constraints.forbidden_dependencies == ["src/legacy/"]
        # These should remain default since api LabeledCluster didn't set them
        assert packet.constraints.no_blocking_io is False
        assert packet.constraints.allowed_dependencies == []

    async def test_constraints_empty_without_labeled_clusters(self, mock_middleware):
        """Without labeled clusters, constraints should be empty defaults."""
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        orch = ArchaiOrchestrator(mock_middleware)
        packet = await orch.get_context("http", "/fake/repo")

        assert packet.constraints.async_only is False
        assert packet.constraints.no_blocking_io is False
        assert packet.constraints.forbidden_dependencies == []
        assert packet.constraints.allowed_dependencies == []

    async def test_constraints_default_for_unknown_focus(self, mock_middleware):
        """Unknown focus should still return valid (empty) constraints."""
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        orch = ArchaiOrchestrator(mock_middleware)
        packet = await orch.get_context("zzzznonexistent", "/fake/repo")

        assert isinstance(packet.constraints, SubsystemConstraints)
        assert packet.constraints.async_only is False

    async def test_force_bypasses_cache_and_updates_it(self, mock_middleware):
        """force=True should bypass cache, process again, and persist result."""
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        orch = ArchaiOrchestrator(mock_middleware)

        # First call populates cache
        await orch.get_context("http", "/fake/repo")
        assert mock_middleware.process.await_count == 1

        # Second call without force uses cache
        await orch.get_context("auth", "/fake/repo")
        assert mock_middleware.process.await_count == 1  # Cache hit

        # Third call with force bypasses cache and updates it
        await orch.get_context("db", "/fake/repo", force=True)
        assert mock_middleware.process.await_count == 2  # Fresh process

        # Fourth call without force uses updated cache
        await orch.get_context("cache", "/fake/repo")
        assert mock_middleware.process.await_count == 2  # Cache hit again
