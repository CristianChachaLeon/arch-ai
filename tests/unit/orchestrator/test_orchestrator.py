# -*- coding: utf-8 -*-
"""ArchaiOrchestrator - Tests for the full pipeline orchestrator."""

import asyncio
from unittest.mock import AsyncMock

import networkx as nx
import pytest

from archai.models import (
    BlastRadiusResponse,
    ChangeItem,
    ContextPacket,
    FileMetadata,
    SubsystemConstraints,
    ValidateChangeResponse,
)
from archai.models import LabeledCluster
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
            # NEW: inline test cases
            "src/api/tests/test_routes.py",  # /tests/ strip → src/api/routes.py → cluster_1 ✅
            "src/api/test_routes.py",  # inline → src/api/routes.py → cluster_1 ✅
            "src/core/tests/test_engine.py",  # /tests/ strip → src/core/engine.py → cluster_2 ✅
            "src/core/test_engine.py",  # inline → src/core/engine.py → cluster_2 ✅
            "src/other/test_unrelated.py",  # inline → src/other/unrelated.py → no cluster ❌
        ],
    }


@pytest.fixture
def blast_graph():
    """Build a directed graph with known edges for blast radius testing.

    Edge semantics: A → B means "A imports B"

    Graph structure:
        src/app/main.py → src/api/routes.py
        tests/api/test_routes.py → src/api/routes.py
        src/api/routes.py → src/core/engine.py
        src/api/routes.py → src/api/middleware.py
        src/api/http_handlers.py → src/core/engine.py
        src/api/http_handlers.py → src/api/middleware.py
        src/core/engine.py → src/core/models.py
        src/core/engine.py → src/core/utils.py
        src/core/utils.py → src/core/models.py
        src/core/models.py → src/core/base.py

        Isolated file (no edges): src/standalone/config.py
    """
    from archai.bootstrap.graph_builder import FileGraph, FileNode

    graph = nx.DiGraph()
    edges = [
        ("src/app/main.py", "src/api/routes.py"),
        ("tests/api/test_routes.py", "src/api/routes.py"),
        ("src/api/routes.py", "src/core/engine.py"),
        ("src/api/routes.py", "src/api/middleware.py"),
        ("src/api/http_handlers.py", "src/core/engine.py"),
        ("src/api/http_handlers.py", "src/api/middleware.py"),
        ("src/core/engine.py", "src/core/models.py"),
        ("src/core/engine.py", "src/core/utils.py"),
        ("src/core/utils.py", "src/core/models.py"),
        ("src/core/models.py", "src/core/base.py"),
    ]
    for u, v in edges:
        graph.add_edge(u, v)

    # Add all node files that appear only as successors
    all_nodes = set()
    for u, v in edges:
        all_nodes.add(u)
        all_nodes.add(v)
    # Add an isolated file with no edges
    all_nodes.add("src/standalone/config.py")
    for node in all_nodes:
        if node not in graph:
            graph.add_node(node)

    fg = FileGraph(graph)
    for node in all_nodes:
        fg._nodes[node] = FileNode(path=node)
    return fg


@pytest.fixture
def blast_clusters():
    return {
        "api": ["src/api/routes.py", "src/api/http_handlers.py", "src/api/middleware.py"],
        "core": [
            "src/core/engine.py",
            "src/core/models.py",
            "src/core/utils.py",
            "src/core/base.py",
        ],
        "app": ["src/app/main.py"],
        "tests": ["tests/api/test_routes.py"],
        "standalone": ["src/standalone/config.py"],
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


@pytest.fixture
def blast_middleware(blast_graph, blast_clusters):
    m = AsyncMock()
    result = PipelineResult(
        repo_path="/fake/repo",
        graph=blast_graph,
        clusters=blast_clusters,
        file_count=10,
        edge_count=10,
        cluster_count=5,
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
        """Test files related to focus should appear in relevant_files, without duplication."""
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        orch = ArchaiOrchestrator(mock_middleware)
        packet = await orch.get_context("http handler", "/fake/repo")

        test_file_paths = [rf.path for rf in packet.relevant_files]
        assert "tests/api/test_routes.py" in test_file_paths
        assert "tests/api/test_http_handlers.py" in test_file_paths

        # Verify no duplicate paths in relevant_files
        assert len(test_file_paths) == len(set(test_file_paths))

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

    def test_inline_tests_in_src_mapped_correctly(self, cluster_aware_clusters):
        """Inline tests inside src/ should be correctly mapped to their source clusters."""
        from archai.orchestrator.orchestrator import _find_related_test_files

        # Focus on cluster_1 → should include src/api/tests/test_routes.py and src/api/test_routes.py
        focus_1 = cluster_aware_clusters["cluster_1"]
        result_1 = _find_related_test_files(focus_1, cluster_aware_clusters)
        assert "src/api/tests/test_routes.py" in result_1
        assert "src/api/test_routes.py" in result_1

        # Focus on cluster_2 → should include src/core/test_engine.py
        focus_2 = cluster_aware_clusters["cluster_2"]
        result_2 = _find_related_test_files(focus_2, cluster_aware_clusters)
        assert "src/core/test_engine.py" in result_2
        assert "src/core/tests/test_engine.py" in result_2

    async def test_cluster_aware_filters_via_orchestrator(self, cluster_aware_middleware):
        """Orchestrator should only include tests whose source cluster matches focus."""
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        orch = ArchaiOrchestrator(cluster_aware_middleware)
        packet = await orch.get_context("http_handlers", "/fake/repo")

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

    async def test_no_duplicate_test_files_in_relevant_files(self, mock_middleware):
        """Test files already in the focus subgraph should not be duplicated in relevant_files."""
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        orch = ArchaiOrchestrator(mock_middleware)
        packet = await orch.get_context("engine", "/fake/repo")

        relevant_paths = [rf.path for rf in packet.relevant_files]
        assert len(relevant_paths) == len(
            set(relevant_paths)
        ), "No duplicate paths in relevant_files"

        # tests/core/test_engine.py is in the core subgraph → appears in
        # relevant_files ONCE (as focus file), not twice (not duplicated
        # as "related test file")
        assert "tests/core/test_engine.py" in packet.subgraph
        assert relevant_paths.count("tests/core/test_engine.py") == 1

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

    # --- validate_changes tests ---

    async def test_validate_changes_valid_when_no_violations(self, mock_middleware):
        """Validation returns valid=True when no constraints are violated."""
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        orch = ArchaiOrchestrator(mock_middleware)
        changes = [
            ChangeItem(
                file_path="src/api/routes.py",
                patch="def get_user(): pass",
            ),
        ]
        response = await orch.validate_changes("/fake/repo", changes)

        assert isinstance(response, ValidateChangeResponse)
        assert response.valid is True
        assert response.violations == []

    async def test_validate_changes_catches_async_violation(self, base_clusters):
        """Validation catches async violations when patch contains blocking I/O."""
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        labeled = [
            LabeledCluster(
                cluster_id="api",
                files=["src/api/routes.py", "src/api/http_handlers.py"],
                name="API Layer",
                description="HTTP API endpoints",
                reasoning="Contains HTTP handlers",
                async_only=True,
            ),
        ]
        m = AsyncMock()
        result = PipelineResult(
            repo_path="/fake/repo",
            graph=AsyncMock(),
            clusters=base_clusters,
            file_count=5,
            edge_count=2,
            cluster_count=2,
            labeled_clusters=labeled,
        )
        m.process.return_value = result

        orch = ArchaiOrchestrator(m)
        changes = [
            ChangeItem(
                file_path="src/api/routes.py",
                patch="def handle(): time.sleep(1)",
            ),
        ]
        response = await orch.validate_changes("/fake/repo", changes)

        assert response.valid is False
        assert len(response.violations) == 1
        v = response.violations[0]
        assert v.file == "src/api/routes.py"
        assert v.rule == "no_blocking_io"
        assert "time.sleep" in v.message

    async def test_validate_changes_catches_forbidden_dependency(self, base_clusters):
        """Validation catches forbidden dependency violations."""
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        labeled = [
            LabeledCluster(
                cluster_id="core",
                files=["src/core/engine.py", "src/core/models.py"],
                name="Core Engine",
                description="Core business logic",
                reasoning="Contains engine",
                forbidden_dependencies=["os", "subprocess"],
            ),
        ]
        m = AsyncMock()
        result = PipelineResult(
            repo_path="/fake/repo",
            graph=AsyncMock(),
            clusters=base_clusters,
            file_count=5,
            edge_count=2,
            cluster_count=2,
            labeled_clusters=labeled,
        )
        m.process.return_value = result

        orch = ArchaiOrchestrator(m)
        changes = [
            ChangeItem(
                file_path="src/core/engine.py",
                patch="import os\n\ndef run():\n    pass",
            ),
        ]
        response = await orch.validate_changes("/fake/repo", changes)

        assert response.valid is False
        assert len(response.violations) == 1
        v = response.violations[0]
        assert v.file == "src/core/engine.py"
        assert v.rule == "forbidden_dependency"
        assert "os" in v.message

    async def test_validate_changes_labeled_clusters_none(self, mock_middleware):
        """Validation returns valid=True when labeled_clusters is None."""
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        orch = ArchaiOrchestrator(mock_middleware)
        changes = [
            ChangeItem(
                file_path="src/api/routes.py",
                patch="def get_user(): pass",
            ),
        ]
        response = await orch.validate_changes("/fake/repo", changes)

        assert response.valid is True
        assert response.violations == []

    async def test_validate_changes_unknown_file(self, mock_middleware):
        """Validation flags unknown files not in any cluster."""
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        orch = ArchaiOrchestrator(mock_middleware)
        changes = [
            ChangeItem(
                file_path="src/unknown/module.py",
                patch="x = 1",
            ),
        ]
        response = await orch.validate_changes("/fake/repo", changes)

        assert response.valid is False
        assert len(response.violations) == 1
        v = response.violations[0]
        assert v.file == "src/unknown/module.py"
        assert v.rule == "unknown_file"


class TestGetSharedState:
    """Test suite for ArchaiOrchestrator.get_shared_state."""

    def _make_middleware(self, file_nodes):
        """Create a mock middleware that returns a PipelineResult with given file_nodes."""
        from unittest.mock import AsyncMock
        from archai.bootstrap.graph_builder import build_graph

        m = AsyncMock()
        graph = build_graph(file_nodes)
        result = PipelineResult(
            repo_path="/fake/repo",
            graph=graph,
            clusters={},
            file_count=len(file_nodes),
            edge_count=0,
            cluster_count=0,
        )
        m.process.return_value = result
        return m

    async def test_get_shared_state_returns_response(self):
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        middleware = self._make_middleware([])
        orch = ArchaiOrchestrator(middleware)
        result = await orch.get_shared_state("/fake/repo")

        assert result.total_count == 0
        assert result.variables == []

    async def test_get_shared_state_with_global_vars(self):
        from archai.orchestrator.orchestrator import ArchaiOrchestrator
        from archai.bootstrap.graph_builder import FileNode

        file_nodes = [
            FileNode(
                path="src/main.c",
                imports=[],
                functions=[],
                classes=[],
                global_vars=[
                    {"name": "cfg", "line": 10, "is_static": False},
                    {"name": "buffer", "line": 15, "is_static": True},
                ],
            ),
        ]
        middleware = self._make_middleware(file_nodes)
        orch = ArchaiOrchestrator(middleware)
        response = await orch.get_shared_state("/fake/repo")

        assert response.total_count == 2
        names = {v.name for v in response.variables}
        assert names == {"cfg", "buffer"}

    async def test_get_shared_state_filter(self):
        from archai.orchestrator.orchestrator import ArchaiOrchestrator
        from archai.bootstrap.graph_builder import FileNode

        file_nodes = [
            FileNode(
                path="src/main.c",
                imports=[],
                functions=[],
                classes=[],
                global_vars=[
                    {"name": "debug_mode", "line": 5, "is_static": False},
                    {"name": "max_connections", "line": 10, "is_static": False},
                ],
            ),
        ]
        middleware = self._make_middleware(file_nodes)
        orch = ArchaiOrchestrator(middleware)
        response = await orch.get_shared_state("/fake/repo", variable_filter="debug")

        assert response.total_count == 1
        assert response.variables[0].name == "debug_mode"

    async def test_get_shared_state_empty_repo(self):
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        middleware = self._make_middleware([])
        orch = ArchaiOrchestrator(middleware)
        response = await orch.get_shared_state("/fake/repo")

        assert response.total_count == 0
        assert response.variables == []

    async def test_get_shared_state_multiple_files(self):
        from archai.orchestrator.orchestrator import ArchaiOrchestrator
        from archai.bootstrap.graph_builder import FileNode

        file_nodes = [
            FileNode(
                path="src/main.c",
                imports=[],
                functions=[],
                classes=[],
                global_vars=[
                    {"name": "cfg", "line": 10, "is_static": False},
                ],
            ),
            FileNode(
                path="src/utils.c",
                imports=[],
                functions=[],
                classes=[],
                global_vars=[
                    {"name": "debug_flag", "line": 5, "is_static": True},
                ],
            ),
        ]
        middleware = self._make_middleware(file_nodes)
        orch = ArchaiOrchestrator(middleware)
        response = await orch.get_shared_state("/fake/repo")

        assert response.total_count == 2
        names = {v.name for v in response.variables}
        assert names == {"cfg", "debug_flag"}

    async def test_get_shared_state_most_written(self):
        """Test that var_access data flows into SharedVariable writers/readers."""
        from archai.orchestrator.orchestrator import ArchaiOrchestrator
        from archai.bootstrap.graph_builder import FileNode

        file_nodes = [
            FileNode(
                path="src/main.c",
                imports=[],
                functions=[],
                classes=[],
                global_vars=[{"name": "verbose", "line": 1, "is_static": False}],
                var_access={
                    "main": {
                        "writes": [{"name": "verbose", "line": 5}],
                        "reads": [],
                    },
                    "log": {
                        "writes": [{"name": "verbose", "line": 10}],
                        "reads": [{"name": "verbose", "line": 12}],
                    },
                },
            ),
        ]
        middleware = self._make_middleware(file_nodes)
        orch = ArchaiOrchestrator(middleware)
        response = await orch.get_shared_state("/fake/repo")

        assert response.total_count == 1
        verbose = response.variables[0]
        assert verbose.name == "verbose"
        assert len(verbose.writers) == 2
        assert len(verbose.readers) == 1
        assert verbose.writers[0].function == "main"
        assert verbose.writers[0].access_type == "write"
        assert verbose.writers[1].function == "log"
        assert verbose.writers[1].access_type == "write"
        assert verbose.readers[0].function == "log"
        assert verbose.readers[0].access_type == "read"
        assert "verbose" in response.most_written
        assert "verbose" in response.most_read

    async def test_get_shared_state_filter_by_substring(self):
        """Test case-insensitive substring filtering."""
        from archai.orchestrator.orchestrator import ArchaiOrchestrator
        from archai.bootstrap.graph_builder import FileNode

        file_nodes = [
            FileNode(
                path="src/main.c",
                imports=[],
                functions=[],
                classes=[],
                global_vars=[
                    {"name": "DEBUG_MODE", "line": 1, "is_static": False},
                    {"name": "max_connections", "line": 5, "is_static": False},
                ],
            ),
        ]
        middleware = self._make_middleware(file_nodes)
        orch = ArchaiOrchestrator(middleware)
        response = await orch.get_shared_state("/fake/repo", variable_filter="debug")

        assert response.total_count == 1
        assert response.variables[0].name == "DEBUG_MODE"

    async def test_get_shared_state_no_global_vars_in_node(self):
        """FileNode with no global_vars should not cause issues."""
        from archai.orchestrator.orchestrator import ArchaiOrchestrator
        from archai.bootstrap.graph_builder import FileNode

        file_nodes = [
            FileNode(
                path="src/main.py",
            ),
        ]
        middleware = self._make_middleware(file_nodes)
        orch = ArchaiOrchestrator(middleware)
        response = await orch.get_shared_state("/fake/repo")

        assert response.total_count == 0
        assert response.variables == []

    async def test_get_shared_state_no_global_vars_pretty_print(self, tmp_path):
        """Test orchestrator with no global vars and verify filtering."""
        from archai.orchestrator.orchestrator import ArchaiOrchestrator
        from archai.bootstrap.graph_builder import FileNode

        file_nodes = [
            FileNode(path="src/main.py"),
        ]
        middleware = self._make_middleware(file_nodes)
        orch = ArchaiOrchestrator(middleware)
        response = await orch.get_shared_state("/fake/repo", variable_filter="nonexistent")

        assert response.total_count == 0
        assert response.variables == []
        assert response.most_written == []
        assert response.most_read == []

    async def test_get_shared_state_uses_cache(self):
        """Verify the cache path in _get_pipeline_result is tested."""
        from archai.orchestrator.orchestrator import ArchaiOrchestrator
        from archai.bootstrap.graph_builder import FileNode

        file_nodes = [
            FileNode(
                path="src/main.c",
                imports=[],
                functions=[],
                classes=[],
                global_vars=[{"name": "cfg", "line": 10, "is_static": False}],
            ),
        ]
        middleware = self._make_middleware(file_nodes)
        orch = ArchaiOrchestrator(middleware)

        # First call populates cache
        await orch.get_shared_state("/fake/repo")
        assert middleware.process.await_count == 1

        # Second call uses cache
        await orch.get_shared_state("/fake/repo")
        assert middleware.process.await_count == 1  # Still 1

        # Third call with different filter still uses cache (same pipeline result)
        await orch.get_shared_state("/fake/repo", variable_filter="cfg")
        assert middleware.process.await_count == 1  # Still 1


class TestTraceFeatureFlow:
    """Test suite for ArchaiOrchestrator.trace_feature_flow."""

    @pytest.fixture
    def trace_middleware(self):
        from unittest.mock import AsyncMock, MagicMock
        from archai.bootstrap.graph_builder import FileGraph, FunctionGraph, FileNode, FunctionNode
        import networkx as nx

        # Build a simple function graph
        fg = FunctionGraph()
        fg.add_node(
            "src/main.c::main",
            FunctionNode(
                name="main",
                file_path="src/main.c",
                calls_internal=["run_plugin"],
                calls_external=["printf"],
            ),
        )
        fg.add_node(
            "src/main.c::run_plugin",
            FunctionNode(
                name="run_plugin",
                file_path="src/main.c",
                calls_internal=["fork"],
                calls_external=["execvp"],
            ),
        )
        fg.add_node(
            "src/main.c::fork",
            FunctionNode(name="fork", file_path="src/main.c", calls_internal=[], calls_external=[]),
        )

        # Add edges
        fg.graph.add_edge("src/main.c::main", "src/main.c::run_plugin")
        fg.graph.add_edge("src/main.c::run_plugin", "src/main.c::fork")

        # Build a file graph with global vars
        file_graph = nx.DiGraph()
        file_graph.add_node("src/main.c")
        fg_file = FileGraph(file_graph)
        fn = FileNode(
            path="src/main.c",
            functions=["main", "run_plugin", "fork"],
            global_vars=[{"name": "cfg", "line": 1}, {"name": "pselbuf", "line": 2}],
        )
        fg_file._nodes["src/main.c"] = fn

        m = AsyncMock()
        result = MagicMock()
        result.function_graph = fg
        result.graph = fg_file
        result.repo_path = "/fake/repo"
        m.process.return_value = result

        # Need _get_pipeline_result to use this result
        return m

    async def test_trace_returns_call_chain(self, trace_middleware):
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        orch = ArchaiOrchestrator(trace_middleware)

        result = await orch.trace_feature_flow("/fake/repo", "main")

        assert result.entry_point == "main"
        assert result.functions_traced >= 1
        assert len(result.call_chain) == 1

    async def test_trace_entry_not_found(self, trace_middleware):
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        orch = ArchaiOrchestrator(trace_middleware)

        result = await orch.trace_feature_flow("/fake/repo", "nonexistent")

        assert result.functions_traced == 0

    async def test_trace_no_function_graph(self):
        from unittest.mock import AsyncMock, MagicMock
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        m = AsyncMock()
        result = MagicMock()
        result.function_graph = None
        m.process.return_value = result

        orch = ArchaiOrchestrator(m)
        result = await orch.trace_feature_flow("/fake/repo", "main")

        assert result.functions_traced == 0

    async def test_trace_detects_side_effects_and_risks(self, trace_middleware):
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        orch = ArchaiOrchestrator(trace_middleware)

        result = await orch.trace_feature_flow("/fake/repo", "fork")

        # fork name triggers side effect + risk
        se_types = [se.type for se in result.side_effects]
        assert "fork" in se_types
        risk_severities = [r.severity for r in result.risks]
        assert "high" in risk_severities

        assert result.functions_traced == 1

    async def test_trace_collects_shared_state(self, trace_middleware):
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        orch = ArchaiOrchestrator(trace_middleware)

        result = await orch.trace_feature_flow("/fake/repo", "main")

        # Per-function shared state tracking is not yet implemented,
        # so this remains empty until AST-level variable access is tracked.
        assert result.shared_state == []


class TestDetectSideEffects:
    """Tests for _detect_side_effects helper."""

    def _make_node(self, name="fn"):
        from archai.bootstrap.graph_builder import FunctionNode

        return FunctionNode(name=name, file_path="x.c", calls_internal=[], calls_external=[])

    def test_fork_side_effect(self):
        from archai.orchestrator.orchestrator import _detect_side_effects

        effects = _detect_side_effects("fork_process", self._make_node())
        assert len(effects) == 1
        assert effects[0].type == "fork"

    def test_clone_side_effect(self):
        from archai.orchestrator.orchestrator import _detect_side_effects

        effects = _detect_side_effects("clone_task", self._make_node())
        assert len(effects) == 1
        assert effects[0].type == "fork"

    def test_exec_side_effect(self):
        from archai.orchestrator.orchestrator import _detect_side_effects

        self._make_node()
        effects = _detect_side_effects("exec_cmd", self._make_node())
        assert len(effects) == 1
        assert effects[0].type == "exec"

    def test_spawn_side_effect(self):
        from archai.orchestrator.orchestrator import _detect_side_effects

        effects = _detect_side_effects("spawn_worker", self._make_node())
        assert len(effects) == 1
        assert effects[0].type == "exec"

    def test_file_io_side_effect(self):
        from archai.orchestrator.orchestrator import _detect_side_effects

        effects = _detect_side_effects("open_file", self._make_node())
        assert len(effects) == 1
        assert effects[0].type == "file_io"

    def test_fread_side_effect(self):
        from archai.orchestrator.orchestrator import _detect_side_effects

        effects = _detect_side_effects("fread_data", self._make_node())
        assert len(effects) == 1
        assert effects[0].type == "file_io"

    def test_network_side_effect(self):
        from archai.orchestrator.orchestrator import _detect_side_effects

        effects = _detect_side_effects("connect_server", self._make_node())
        assert len(effects) == 1
        assert effects[0].type == "network"

    def test_socket_side_effect(self):
        from archai.orchestrator.orchestrator import _detect_side_effects

        effects = _detect_side_effects("socket_bind", self._make_node())
        assert len(effects) == 1
        assert effects[0].type == "network"

    def test_signal_side_effect(self):
        from archai.orchestrator.orchestrator import _detect_side_effects

        effects = _detect_side_effects("signal_handler", self._make_node())
        assert len(effects) == 1
        assert effects[0].type == "signal"

    def test_kill_side_effect(self):
        from archai.orchestrator.orchestrator import _detect_side_effects

        effects = _detect_side_effects("kill_process", self._make_node())
        assert len(effects) == 1
        assert effects[0].type == "signal"

    def test_multiple_side_effects(self):
        from archai.orchestrator.orchestrator import _detect_side_effects

        effects = _detect_side_effects("fork_exec_read", self._make_node())
        types = {e.type for e in effects}
        assert "fork" in types
        assert "exec" in types
        assert "file_io" in types

    def test_no_side_effects(self):
        from archai.orchestrator.orchestrator import _detect_side_effects

        effects = _detect_side_effects("normal_function", self._make_node())
        assert effects == []


class TestDetectRisks:
    """Tests for _detect_risks helper."""

    def _make_node(self, name="fn"):
        from archai.bootstrap.graph_builder import FunctionNode

        return FunctionNode(name=name, file_path="x.c", calls_internal=[], calls_external=[])

    def test_fork_risk(self):
        from archai.orchestrator.orchestrator import _detect_risks

        risks = _detect_risks("fork", self._make_node(), 0)
        assert len(risks) == 1
        assert risks[0].severity == "high"

    def test_clone_risk(self):
        from archai.orchestrator.orchestrator import _detect_risks

        risks = _detect_risks("clone", self._make_node(), 0)
        assert len(risks) == 1
        assert risks[0].severity == "high"

    def test_deep_chain_risk(self):
        from archai.orchestrator.orchestrator import _detect_risks

        risks = _detect_risks("helper", self._make_node(), 8)
        assert len(risks) == 1
        assert risks[0].severity == "medium"

    def test_signal_risk(self):
        from archai.orchestrator.orchestrator import _detect_risks

        risks = _detect_risks("sigaction", self._make_node(), 0)
        assert len(risks) == 1
        assert risks[0].severity == "high"

    def test_no_risks(self):
        from archai.orchestrator.orchestrator import _detect_risks

        risks = _detect_risks("normal_func", self._make_node(), 1)
        assert risks == []


class TestGetFileDependencies:
    """Tests for get_file_dependencies helper."""

    def test_get_file_dependencies_all_nodes(self):
        from archai.orchestrator.orchestrator import get_file_dependencies
        import networkx as nx

        g = nx.DiGraph()
        g.add_edge("a.py", "b.py")
        g.add_edge("a.py", "c.py")
        g.add_node("d.py")  # No imports

        result = get_file_dependencies(g)
        assert "a.py" in result
        assert result["a.py"] == ["b.py", "c.py"]
        assert "d.py" not in result  # No deps → omitted


class TestBlastRadius:
    """Test suite for ArchaiOrchestrator.get_blast_radius."""

    async def test_get_blast_radius_returns_expected_structure(self, blast_middleware):
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        orch = ArchaiOrchestrator(blast_middleware)
        result = await orch.get_blast_radius("/fake/repo", "src/core/engine.py")

        assert isinstance(result, BlastRadiusResponse)
        assert result.focus_file == "src/core/engine.py"
        assert isinstance(result.direct_dependents, list)
        assert isinstance(result.direct_dependencies, list)
        assert isinstance(result.transitive_dependents, list)
        assert isinstance(result.subsystems_affected, dict)

    async def test_get_blast_radius_direct_dependents(self, blast_middleware):
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        orch = ArchaiOrchestrator(blast_middleware)
        result = await orch.get_blast_radius("/fake/repo", "src/core/engine.py")

        # Files that directly import engine.py
        assert set(result.direct_dependents) == {
            "src/api/routes.py",
            "src/api/http_handlers.py",
        }

    async def test_get_blast_radius_direct_dependencies(self, blast_middleware):
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        orch = ArchaiOrchestrator(blast_middleware)
        result = await orch.get_blast_radius("/fake/repo", "src/core/engine.py")

        # Files that engine.py directly imports
        assert set(result.direct_dependencies) == {
            "src/core/models.py",
            "src/core/utils.py",
        }

    async def test_get_blast_radius_file_not_in_graph(self, blast_middleware):
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        orch = ArchaiOrchestrator(blast_middleware)

        with pytest.raises(ValueError, match="not found in dependency graph"):
            await orch.get_blast_radius("/fake/repo", "src/nonexistent.py")

    async def test_get_blast_radius_transitive_depth(self, blast_middleware):
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        orch = ArchaiOrchestrator(blast_middleware)

        # engine.py at depth=1: only direct dependents, no transitive
        result_d1 = await orch.get_blast_radius("/fake/repo", "src/core/engine.py", depth=1)
        assert result_d1.transitive_dependents == []

        # engine.py at depth=2: files that import engine.py's importers
        result_d2 = await orch.get_blast_radius("/fake/repo", "src/core/engine.py", depth=2)
        assert set(result_d2.transitive_dependents) == {
            "src/app/main.py",
            "tests/api/test_routes.py",
        }

        # models.py at depth=2
        result_m2 = await orch.get_blast_radius("/fake/repo", "src/core/models.py", depth=2)
        # Files that import models.py: engine.py, utils.py  (direct)
        # Files that import engine.py/utils.py's importers: routes.py, http_handlers.py  (transitive)
        assert "src/core/engine.py" in result_m2.direct_dependents
        assert "src/core/utils.py" in result_m2.direct_dependents
        assert "src/api/routes.py" in result_m2.transitive_dependents
        assert "src/api/http_handlers.py" in result_m2.transitive_dependents

    async def test_get_blast_radius_subsystems_affected(self, blast_middleware):
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        orch = ArchaiOrchestrator(blast_middleware)
        result = await orch.get_blast_radius("/fake/repo", "src/core/engine.py", depth=2)

        # Affected: routes.py (api), http_handlers.py (api), main.py (app), test_routes.py (tests)
        assert result.subsystems_affected.get("api") == 2
        assert result.subsystems_affected.get("app") == 1
        assert result.subsystems_affected.get("tests") == 1

    async def test_get_blast_radius_no_dependents(self, blast_middleware):
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        orch = ArchaiOrchestrator(blast_middleware)
        result = await orch.get_blast_radius("/fake/repo", "src/standalone/config.py")

        assert result.direct_dependents == []
        assert result.direct_dependencies == []
        assert result.transitive_dependents == []
        assert result.subsystems_affected == {}


class TestStripTestPrefix:
    """Tests for _strip_test_prefix helper."""

    def test_removes_test_prefix(self):
        from archai.orchestrator.orchestrator import _strip_test_prefix

        assert _strip_test_prefix("test_routes.py") == "routes.py"

    def test_removes_test_suffix(self):
        from archai.orchestrator.orchestrator import _strip_test_prefix

        assert _strip_test_prefix("routes_test.py") == "routes.py"

    def test_no_prefix_or_suffix(self):
        from archai.orchestrator.orchestrator import _strip_test_prefix

        assert _strip_test_prefix("routes.py") == "routes.py"


class TestGetClusterEdges:
    """Tests for get_cluster_edges helper."""

    def test_basic_cluster_edges(self):
        from archai.orchestrator.orchestrator import get_cluster_edges
        import networkx as nx

        g = nx.DiGraph()
        g.add_edge("src/a.py", "src/b.py")
        g.add_edge("src/a.py", "src/c.py")
        clusters = {"cluster_a": ["src/a.py"], "cluster_b": ["src/b.py"], "cluster_c": ["src/c.py"]}

        edges = get_cluster_edges(g, clusters)
        assert len(edges) == 2
        edge_pairs = {(e.from_cluster, e.to_cluster) for e in edges}
        assert ("cluster_a", "cluster_b") in edge_pairs
        assert ("cluster_a", "cluster_c") in edge_pairs

    def test_file_not_in_graph_skipped(self):
        from archai.orchestrator.orchestrator import get_cluster_edges
        import networkx as nx

        g = nx.DiGraph()
        g.add_node("src/a.py")
        clusters = {"cluster_a": ["src/a.py", "src/missing.py"]}

        edges = get_cluster_edges(g, clusters)
        # No error — missing file is simply skipped
        assert edges == []

    def test_multiple_files_same_edge(self):
        """Multiple files from same cluster importing same target cluster should generate one edge."""
        from archai.orchestrator.orchestrator import get_cluster_edges
        import networkx as nx

        g = nx.DiGraph()
        g.add_edge("src/a1.py", "src/b.py")
        g.add_edge("src/a2.py", "src/b.py")
        clusters = {"cluster_a": ["src/a1.py", "src/a2.py"], "cluster_b": ["src/b.py"]}

        edges = get_cluster_edges(g, clusters)
        assert len(edges) == 1
        assert edges[0].from_cluster == "cluster_a"
        assert edges[0].to_cluster == "cluster_b"
        assert len(edges[0].files) == 2


class TestGetFileDependenciesExtended:
    """Extended tests for get_file_dependencies helper."""

    def test_get_file_dependencies_specific_files(self):
        from archai.orchestrator.orchestrator import get_file_dependencies
        import networkx as nx

        g = nx.DiGraph()
        g.add_edge("a.py", "b.py")
        g.add_edge("a.py", "c.py")
        g.add_edge("d.py", "e.py")

        result = get_file_dependencies(g, files=["a.py"])
        assert "a.py" in result
        assert "d.py" not in result

    def test_get_file_dependencies_node_not_in_graph(self):
        """File not in graph should be simply skipped."""
        from archai.orchestrator.orchestrator import get_file_dependencies
        import networkx as nx

        g = nx.DiGraph()
        g.add_edge("a.py", "b.py")

        result = get_file_dependencies(g, files=["nonexistent.py"])
        assert result == {}


class TestBlastRadiusExtended:
    """Tests for function-level blast radius analysis."""

    async def _make_function_blast_middleware(self):
        from unittest.mock import AsyncMock
        from archai.bootstrap.graph_builder import FileGraph, FunctionGraph, FunctionNode
        import networkx as nx

        fg = FunctionGraph()
        fg.add_node(
            "src/main.py::run",
            FunctionNode(name="run", file_path="src/main.py", calls_internal=[], calls_external=[]),
        )
        fg.add_node(
            "src/main.py::helper",
            FunctionNode(
                name="helper", file_path="src/main.py", calls_internal=[], calls_external=[]
            ),
        )
        fg.graph.add_edge("src/main.py::run", "src/main.py::helper")

        file_graph = nx.DiGraph()
        file_graph.add_node("src/main.py")
        fg_file = FileGraph(file_graph)

        m = AsyncMock()
        result = AsyncMock()
        result.graph = fg_file
        result.function_graph = fg
        result.repo_path = "/fake/repo"
        m.process.return_value = result
        return m

    async def test_blast_radius_with_function_name(self):
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        middleware = await self._make_function_blast_middleware()
        orch = ArchaiOrchestrator(middleware)
        result = await orch.get_blast_radius("/fake/repo", "src/main.py", function_name="run")

        assert result.function_name == "run"
        assert "src/main.py::helper" in result.function_dependencies

    async def test_blast_radius_function_not_found(self):
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        middleware = await self._make_function_blast_middleware()
        orch = ArchaiOrchestrator(middleware)

        with pytest.raises(ValueError, match="missing key"):
            await orch.get_blast_radius("/fake/repo", "src/main.py", function_name="nonexistent")


class TestGetFileDetail:
    """Tests for ArchaiOrchestrator.get_file_detail."""

    @pytest.fixture
    def detail_middleware(self):
        from unittest.mock import AsyncMock
        from archai.bootstrap.graph_builder import FileNode, build_graph

        file_nodes = [
            FileNode(
                path="src/main.py",
                imports=["src/utils.py"],
                functions=["run", "process"],
                classes=["App"],
            ),
            FileNode(path="src/utils.py", imports=[]),
        ]
        fg = build_graph(file_nodes)
        fg.graph.add_edge("src/main.py", "src/utils.py")

        m = AsyncMock()
        result = AsyncMock()
        result.graph = fg
        result.repo_path = "/fake/repo"
        m.process.return_value = result
        return m

    async def test_get_file_detail_with_functions_and_classes(self, detail_middleware):
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        def mock_get_cluster_for_file(file_path):
            return "core" if file_path == "src/main.py" else None

        detail_middleware.process.return_value.get_cluster_for_file = mock_get_cluster_for_file

        orch = ArchaiOrchestrator(detail_middleware)
        result = await orch.get_file_detail("/fake/repo", "src/main.py")

        assert result.file_path == "src/main.py"
        assert result.cluster == "core"
        assert len(result.functions) == 2
        assert len(result.classes) == 1
        assert result.imports == ["src/utils.py"]
        assert result.dependents == []

    async def test_get_file_detail_not_in_graph(self, detail_middleware):
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        orch = ArchaiOrchestrator(detail_middleware)

        with pytest.raises(ValueError, match="not found in dependency graph"):
            await orch.get_file_detail("/fake/repo", "src/nonexistent.py")


class TestGetStructuralContext:
    """Tests for ArchaiOrchestrator.get_structural_context."""

    async def test_get_structural_context_returns_packet(self, mock_middleware):
        from archai.orchestrator.orchestrator import ArchaiOrchestrator
        from archai.models import StructuralContext

        orch = ArchaiOrchestrator(mock_middleware)
        result = await orch.get_structural_context("http", "/fake/repo")

        assert isinstance(result, StructuralContext)
        assert result.focus_cluster == "api"
        assert "src/api/routes.py" in result.focus_files
        assert isinstance(result.cluster_edges, list)
        assert isinstance(result.file_dependencies, dict)
        assert isinstance(result.test_files, list)

    async def test_get_structural_context_with_force(self, mock_middleware):
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        orch = ArchaiOrchestrator(mock_middleware)
        result = await orch.get_structural_context("http", "/fake/repo", force=True)

        assert result.focus_cluster == "api"


class TestProposeChange:
    """Tests for ArchaiOrchestrator.propose_change."""

    async def test_propose_change_returns_suggestions(self):
        from unittest.mock import AsyncMock
        from archai.orchestrator.orchestrator import ArchaiOrchestrator
        import networkx as nx

        g = nx.DiGraph()
        g.add_node("src/api/routes.py")
        g.add_node("src/core/engine.py")
        g.add_node("external")

        m = AsyncMock()
        result = AsyncMock()
        result.graph.graph = g
        result.repo_path = "/fake/repo"
        result.clusters = {}
        m.process.return_value = result

        orch = ArchaiOrchestrator(m)
        response = await orch.propose_change("/fake/repo", "add api route")

        assert "description" in response
        assert "suggested_files" in response
        assert "src/api/routes.py" in response["suggested_files"]

    async def test_propose_change_no_keyword_matches(self):
        from unittest.mock import AsyncMock
        from archai.orchestrator.orchestrator import ArchaiOrchestrator
        import networkx as nx

        g = nx.DiGraph()
        g.add_node("src/core/engine.py")

        m = AsyncMock()
        result = AsyncMock()
        result.graph.graph = g
        result.repo_path = "/fake/repo"
        m.process.return_value = result

        orch = ArchaiOrchestrator(m)
        response = await orch.propose_change("/fake/repo", "zzzznonexistent")

        assert response["total_matches"] == 0
        assert response["suggested_files"] == []


class TestBuildFileToSubsystem:
    """Tests for _build_file_to_subsystem helper."""

    def test_with_labeled_clusters(self):
        from archai.orchestrator.orchestrator import _build_file_to_subsystem
        from unittest.mock import MagicMock
        from archai.models import LabeledCluster

        result = MagicMock()
        result.labeled_clusters = [
            LabeledCluster(
                cluster_id="api",
                files=["src/api/routes.py"],
                name="API Layer",
                description="",
                reasoning="",
            ),
        ]
        result.clusters = {"api": ["src/api/routes.py"]}

        mapping = _build_file_to_subsystem(result)
        assert mapping["src/api/routes.py"] == "API Layer"

    def test_without_labeled_clusters(self):
        from archai.orchestrator.orchestrator import _build_file_to_subsystem
        from unittest.mock import MagicMock

        result = MagicMock()
        result.labeled_clusters = None
        result.clusters = {"api": ["src/api/routes.py"], "core": ["src/core/engine.py"]}

        mapping = _build_file_to_subsystem(result)
        assert mapping["src/api/routes.py"] == "api"
        assert mapping["src/core/engine.py"] == "core"


class TestValidateChangesExtended:
    """Extended tests for validate_changes edge cases."""

    async def test_validate_changes_cluster_without_label(self, base_clusters):
        """File in a known cluster but no labeled_clusters should pass."""
        from archai.orchestrator.orchestrator import ArchaiOrchestrator
        from archai.middleware.pipeline import PipelineResult
        from unittest.mock import AsyncMock

        labeled = [
            LabeledCluster(
                cluster_id="api",
                files=["src/api/routes.py"],
                name="API Layer",
                description="",
                reasoning="",
                async_only=True,
            ),
        ]
        m = AsyncMock()
        result = PipelineResult(
            repo_path="/fake/repo",
            graph=AsyncMock(),
            clusters=base_clusters,
            file_count=5,
            edge_count=2,
            cluster_count=2,
            labeled_clusters=labeled,
        )
        m.process.return_value = result

        orch = ArchaiOrchestrator(m)
        changes = [
            ChangeItem(file_path="src/core/engine.py", patch="x = 1"),
        ]
        response = await orch.validate_changes("/fake/repo", changes)

        # engine.py is in "core" cluster, but no LabeledCluster for "core"
        # → cluster is not in label_lookup → continue (no violation)
        assert response.valid is True

    async def test_validate_changes_no_blocking_io_match(self, base_clusters):
        """Blocking I/O pattern check when async_only but patch is clean."""
        from archai.orchestrator.orchestrator import ArchaiOrchestrator
        from archai.middleware.pipeline import PipelineResult
        from unittest.mock import AsyncMock

        labeled = [
            LabeledCluster(
                cluster_id="api",
                files=["src/api/routes.py"],
                name="API Layer",
                description="",
                reasoning="",
                async_only=True,
            ),
        ]
        m = AsyncMock()
        result = PipelineResult(
            repo_path="/fake/repo",
            graph=AsyncMock(),
            clusters=base_clusters,
            file_count=5,
            edge_count=2,
            cluster_count=2,
            labeled_clusters=labeled,
        )
        m.process.return_value = result

        orch = ArchaiOrchestrator(m)
        changes = [
            ChangeItem(file_path="src/api/routes.py", patch="async def get():\n    pass"),
        ]
        response = await orch.validate_changes("/fake/repo", changes)

        assert response.valid is True

    async def test_validate_changes_forbidden_dependency_match(self, base_clusters):
        """Forbidden dependency regex should match import statements."""
        from archai.orchestrator.orchestrator import ArchaiOrchestrator
        from archai.middleware.pipeline import PipelineResult
        from unittest.mock import AsyncMock

        labeled = [
            LabeledCluster(
                cluster_id="api",
                files=["src/api/routes.py"],
                name="API Layer",
                description="",
                reasoning="",
                forbidden_dependencies=["os"],
            ),
        ]
        m = AsyncMock()
        result = PipelineResult(
            repo_path="/fake/repo",
            graph=AsyncMock(),
            clusters=base_clusters,
            file_count=5,
            edge_count=2,
            cluster_count=2,
            labeled_clusters=labeled,
        )
        m.process.return_value = result

        orch = ArchaiOrchestrator(m)
        changes = [
            ChangeItem(file_path="src/api/routes.py", patch="import os\n\ndef run():\n    pass"),
        ]
        response = await orch.validate_changes("/fake/repo", changes)

        assert response.valid is False
        assert response.violations[0].rule == "forbidden_dependency"


class TestGetPipelineResultExtended:
    """Extended tests for _get_pipeline_result edge cases."""

    async def test_force_calls_process_again(self, mock_middleware):
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        orch = ArchaiOrchestrator(mock_middleware)

        # First call populates cache
        await orch.get_context("http", "/fake/repo")
        assert mock_middleware.process.await_count == 1

        # Force should bypass cache and process again
        await orch.get_context("db", "/fake/repo", force=True)
        assert mock_middleware.process.await_count == 2


class TestGetContextExtended:
    """Extended tests for get_context edge cases."""

    async def test_unknown_focus_no_labeled_clusters(self, cluster_aware_middleware):
        """Focus 'unknown' should produce empty subgraph with labeled clusters available."""
        from archai.orchestrator.orchestrator import ArchaiOrchestrator

        orch = ArchaiOrchestrator(cluster_aware_middleware)
        packet = await orch.get_context("nonexistent", "/fake/repo")

        assert packet.focus == "unknown"
        assert packet.subgraph == []
