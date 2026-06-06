"""Tests for the ArchAI MCP server (archai.mcp_server)."""

import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mcp_env():
    """Return a fresh mcp_server module with all deps mocked.

    Patches are applied BEFORE module-level singletons are created so
    ``orchestrator`` and ``middleware`` are mock instances.
    Access the tool functions and mock orchestrator via the returned dict.
    """
    sys.modules.pop("archai.mcp_server", None)

    with (
        patch("archai.middleware.ArchaiMiddleware"),
        patch("archai.orchestrator.ArchaiOrchestrator") as mock_orch_cls,
        patch("archai.config.validate_repo_path") as mock_validate,
    ):
        mock_orch_instance = mock_orch_cls.return_value
        mock_validate.side_effect = lambda p: p

        import archai.mcp_server as m

        ctx = {
            "module": m,
            "mock_validate": mock_validate,
            "mock_orch_instance": mock_orch_instance,
        }
        yield ctx


def _make_structural_context(**overrides):
    packet = MagicMock()
    packet.model_dump = MagicMock(
        return_value={
            "focus_cluster": "cluster_api",
            "focus_files": ["src/api/routes.py", "src/api/handlers.py"],
            "focus_reasoning": "Query about HTTP handlers",
            "all_clusters": {
                "cluster_api": ["src/api/routes.py", "src/api/handlers.py"],
                "cluster_db": ["src/db/models.py"],
            },
            "cluster_edges": [
                {
                    "from_cluster": "cluster_api",
                    "to_cluster": "cluster_db",
                    "files": ["src/api/routes.py"],
                }
            ],
            "file_dependencies": {"src/api/routes.py": ["src/db/models.py"]},
            "test_files": ["tests/api/test_routes.py"],
            "metadata": {"source": "orchestrator", "cluster_count": 2},
            **overrides,
        }
    )
    return packet


def _make_pipeline_result(**overrides):
    """Build a mock PipelineResult for validate_code_change."""
    graph = MagicMock()
    graph.successors.return_value = []
    graph.__contains__.return_value = True

    pr = MagicMock()
    pr.graph.graph = graph
    pr.get_cluster_for_file.return_value = "cluster_api"
    pr.clusters = {
        "cluster_api": ["src/api/routes.py", "src/api/handlers.py"],
        "cluster_db": ["src/db/models.py"],
    }

    defaults = {
        "graph": pr.graph,
        "get_cluster_for_file": pr.get_cluster_for_file,
        "clusters": pr.clusters,
    }
    for k, v in defaults.items():
        if k not in overrides:
            setattr(pr, k, v)
    for k, v in overrides.items():
        setattr(pr, k, v)
    return pr


def _make_cluster_edge(from_c, to_c, files):
    e = MagicMock()
    e.from_cluster = from_c
    e.to_cluster = to_c
    e.files = files
    return e


class TestGetArchitectureContext:
    """Tests for the ``get_architecture_context`` MCP tool."""

    async def test_returns_structural_context_as_json(self, mcp_env):
        m = mcp_env["module"]
        orch = mcp_env["mock_orch_instance"]
        orch.get_structural_context = AsyncMock(return_value=_make_structural_context())

        result = await m.get_architecture_context("How does auth work?", "/fake/repo")
        parsed = json.loads(result)
        assert parsed["focus_cluster"] == "cluster_api"
        assert len(parsed["cluster_edges"]) == 1
        assert len(parsed["all_clusters"]) == 2

    async def test_calls_orchestrator_with_query_and_resolved_path(self, mcp_env):
        m = mcp_env["module"]
        orch = mcp_env["mock_orch_instance"]
        orch.get_structural_context = AsyncMock(return_value=_make_structural_context())

        await m.get_architecture_context("query", "/fake/repo")
        orch.get_structural_context.assert_awaited_once_with("query", "/fake/repo")

    async def test_validates_repo_path(self, mcp_env):
        m = mcp_env["module"]
        validate = mcp_env["mock_validate"]
        orch = mcp_env["mock_orch_instance"]
        orch.get_structural_context = AsyncMock(return_value=_make_structural_context())

        await m.get_architecture_context("q", "../outside")
        validate.assert_called_once_with("../outside")

    async def test_error_returns_json_error(self, mcp_env):
        m = mcp_env["module"]
        orch = mcp_env["mock_orch_instance"]
        orch.get_structural_context = AsyncMock(side_effect=ValueError("Something went wrong"))

        result = await m.get_architecture_context("query", "/fake/repo")
        parsed = json.loads(result)
        assert "error" in parsed
        assert "Something went wrong" in parsed["error"]


class TestValidateCodeChange:
    """Tests for the ``validate_code_change`` MCP tool."""

    async def test_returns_structural_validation(self, mcp_env):
        m = mcp_env["module"]
        orch = mcp_env["mock_orch_instance"]
        pr = _make_pipeline_result()
        orch._get_pipeline_result = AsyncMock(return_value=pr)

        changes = [{"file_path": "src/api/routes.py", "patch": "from db.models import User"}]
        result = await m.validate_code_change("/fake/repo", changes)
        parsed = json.loads(result)
        assert parsed["file_cluster"] == "cluster_api"
        assert "cluster_files" in parsed
        assert "file_dependencies" in parsed
        assert "new_imports_in_patch" in parsed
        assert "patch_summary" in parsed

    async def test_multiple_changes_returns_list(self, mcp_env):
        m = mcp_env["module"]
        orch = mcp_env["mock_orch_instance"]
        pr = _make_pipeline_result()
        orch._get_pipeline_result = AsyncMock(return_value=pr)

        changes = [
            {"file_path": "src/api/routes.py", "patch": "import os"},
            {"file_path": "src/db/models.py", "patch": "import sys"},
        ]
        result = await m.validate_code_change("/fake/repo", changes)
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) == 2
        assert parsed[0]["file_cluster"] == "cluster_api"
        assert parsed[1]["file_cluster"] == "cluster_api"

    async def test_unknown_file_cluster(self, mcp_env):
        m = mcp_env["module"]
        orch = mcp_env["mock_orch_instance"]
        pr = _make_pipeline_result()
        pr.get_cluster_for_file.return_value = None
        orch._get_pipeline_result = AsyncMock(return_value=pr)

        changes = [{"file_path": "unknown.py", "patch": ""}]
        result = await m.validate_code_change("/fake/repo", changes)
        parsed = json.loads(result)
        assert parsed["file_cluster"] == "unknown"

    async def test_error_returns_json_error(self, mcp_env):
        m = mcp_env["module"]
        orch = mcp_env["mock_orch_instance"]
        orch._get_pipeline_result = AsyncMock(side_effect=RuntimeError("pipeline failed"))

        result = await m.validate_code_change("/fake/repo", [])
        parsed = json.loads(result)
        assert "error" in parsed


class TestGetBlastRadius:
    """Tests for the ``get_blast_radius`` MCP tool."""

    async def test_returns_blast_radius(self, mcp_env):
        m = mcp_env["module"]
        orch = mcp_env["mock_orch_instance"]
        mock_resp = MagicMock()
        mock_resp.model_dump = MagicMock(
            return_value={
                "focus_file": "src/core/engine.py",
                "direct_dependents": ["src/api/routes.py"],
                "direct_dependencies": [],
                "transitive_dependents": [],
                "subsystems_affected": {"api": 1},
            }
        )
        orch.get_blast_radius = AsyncMock(return_value=mock_resp)

        result = await m.get_blast_radius("/fake/repo", "src/core/engine.py", depth=2)
        parsed = json.loads(result)
        assert parsed["focus_file"] == "src/core/engine.py"

    async def test_default_depth(self, mcp_env):
        m = mcp_env["module"]
        orch = mcp_env["mock_orch_instance"]
        mock_resp = MagicMock()
        mock_resp.model_dump = MagicMock(return_value={})
        orch.get_blast_radius = AsyncMock(return_value=mock_resp)

        await m.get_blast_radius("/fake/repo", "x.py")
        orch.get_blast_radius.assert_awaited_once_with("/fake/repo", "x.py", 2)

    async def test_custom_depth(self, mcp_env):
        m = mcp_env["module"]
        orch = mcp_env["mock_orch_instance"]
        mock_resp = MagicMock()
        mock_resp.model_dump = MagicMock(return_value={})
        orch.get_blast_radius = AsyncMock(return_value=mock_resp)

        await m.get_blast_radius("/fake/repo", "x.py", depth=3)
        orch.get_blast_radius.assert_awaited_once_with("/fake/repo", "x.py", 3)

    async def test_validates_repo_path(self, mcp_env):
        m = mcp_env["module"]
        validate = mcp_env["mock_validate"]
        orch = mcp_env["mock_orch_instance"]
        mock_resp = MagicMock()
        mock_resp.model_dump = MagicMock(return_value={})
        orch.get_blast_radius = AsyncMock(return_value=mock_resp)

        await m.get_blast_radius("/some/repo", "x.py")
        validate.assert_called_once_with("/some/repo")

    async def test_error_returns_json_error(self, mcp_env):
        m = mcp_env["module"]
        orch = mcp_env["mock_orch_instance"]
        orch.get_blast_radius = AsyncMock(side_effect=ValueError("file not found"))

        result = await m.get_blast_radius("/fake/repo", "nonexistent.py")
        parsed = json.loads(result)
        assert "error" in parsed
        assert "file not found" in parsed["error"]


class TestValidateRepoPathGuard:
    """Tests for the ``validate_repo_path`` guard in MCP tools."""

    async def test_get_context_rejects_outside_path(self, mcp_env):
        m = mcp_env["module"]
        validate = mcp_env["mock_validate"]
        validate.side_effect = ValueError("repo_path must be within the repo root")

        result = await m.get_architecture_context("query", "/etc/passwd")
        parsed = json.loads(result)
        assert "error" in parsed
        assert "repo_path must be within" in parsed["error"]

    async def test_validate_changes_rejects_outside_path(self, mcp_env):
        m = mcp_env["module"]
        validate = mcp_env["mock_validate"]
        validate.side_effect = ValueError("repo_path must be within the repo root")

        result = await m.validate_code_change("/etc/passwd", [])
        parsed = json.loads(result)
        assert "error" in parsed

    async def test_blast_radius_rejects_outside_path(self, mcp_env):
        m = mcp_env["module"]
        validate = mcp_env["mock_validate"]
        validate.side_effect = ValueError("repo_path must be within the repo root")

        result = await m.get_blast_radius("/etc/passwd", "file.py")
        parsed = json.loads(result)
        assert "error" in parsed
