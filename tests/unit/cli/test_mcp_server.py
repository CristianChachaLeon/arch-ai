"""Tests for the ArchAI MCP server (archai.mcp_server)."""

import json
import os
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
        patch("archai.middleware.ArchaiMiddleware") as mock_mw_cls,
        patch("archai.orchestrator.ArchaiOrchestrator") as mock_orch_cls,
        patch("archai.config.validate_repo_path") as mock_validate,
    ):
        mock_mw_instance = mock_mw_cls.return_value
        mock_mw_instance.process = AsyncMock()

        mock_orch_instance = mock_orch_cls.return_value
        mock_orch_instance.get_context = AsyncMock()
        mock_orch_instance.validate_changes = AsyncMock()
        mock_orch_instance.get_blast_radius = AsyncMock()

        mock_validate.side_effect = lambda p: p

        import archai.mcp_server as m

        ctx = {
            "module": m,
            "mock_validate": mock_validate,
            "mock_orch_instance": mock_orch_instance,
        }
        yield ctx


def _make_context_packet(**overrides):
    """Build a return-value chain for async mock calls.

    AsyncMock auto-creates child mocks as AsyncMock too, so we must
    explicitly set ``return_value`` to a plain MagicMock and set
    ``model_dump`` to a MagicMock that returns the desired dict.
    """
    packet = MagicMock()
    packet.model_dump = MagicMock(
        return_value={
            "focus": "API Layer",
            "focus_reasoning": "Query about HTTP handlers",
            "constraints": {
                "async_only": True,
                "no_blocking_io": False,
                "forbidden_dependencies": [],
                "allowed_dependencies": [],
            },
            "relevant_files": [],
            **overrides,
        }
    )
    return packet


def _make_validation_response(**overrides):
    resp = MagicMock()
    resp.model_dump = MagicMock(
        return_value={
            "valid": True,
            "violations": [],
            **overrides,
        }
    )
    return resp


def _make_blast_response(**overrides):
    resp = MagicMock()
    resp.model_dump = MagicMock(
        return_value={
            "focus_file": "src/core/engine.py",
            "direct_dependents": ["src/api/routes.py"],
            "direct_dependencies": [],
            "transitive_dependents": [],
            "subsystems_affected": {"api": 1},
            **overrides,
        }
    )
    return resp


class TestGetArchitectureContext:
    """Tests for the ``get_architecture_context`` MCP tool."""

    async def test_returns_focus_as_json(self, mcp_env):
        m = mcp_env["module"]
        orch = mcp_env["mock_orch_instance"]
        orch.get_context = AsyncMock(return_value=_make_context_packet())

        result = await m.get_architecture_context("How does auth work?", "/fake/repo")
        parsed = json.loads(result)
        assert parsed["focus"] == "API Layer"
        assert parsed["constraints"]["async_only"] is True

    async def test_calls_orchestrator_with_query_and_resolved_path(self, mcp_env):
        m = mcp_env["module"]
        orch = mcp_env["mock_orch_instance"]
        orch.get_context = AsyncMock(return_value=_make_context_packet())

        await m.get_architecture_context("query", "/fake/repo")
        orch.get_context.assert_awaited_once_with("query", "/fake/repo")

    async def test_validates_repo_path(self, mcp_env):
        m = mcp_env["module"]
        validate = mcp_env["mock_validate"]
        orch = mcp_env["mock_orch_instance"]
        orch.get_context = AsyncMock(return_value=_make_context_packet())

        await m.get_architecture_context("q", "../outside")
        validate.assert_called_once_with("../outside")

    async def test_error_returns_json_error(self, mcp_env):
        m = mcp_env["module"]
        orch = mcp_env["mock_orch_instance"]
        orch.get_context = AsyncMock(side_effect=ValueError("Something went wrong"))

        result = await m.get_architecture_context("query", "/fake/repo")
        parsed = json.loads(result)
        assert "error" in parsed
        assert "Something went wrong" in parsed["error"]


class TestValidateCodeChange:
    """Tests for the ``validate_code_change`` MCP tool."""

    async def test_returns_validation_result(self, mcp_env):
        m = mcp_env["module"]
        orch = mcp_env["mock_orch_instance"]
        orch.validate_changes = AsyncMock(return_value=_make_validation_response())

        changes = [{"file_path": "src/main.py", "patch": "def foo(): pass"}]
        result = await m.validate_code_change("/fake/repo", changes)
        parsed = json.loads(result)
        assert parsed["valid"] is True
        assert parsed["violations"] == []

    async def test_invalid_changes(self, mcp_env):
        m = mcp_env["module"]
        orch = mcp_env["mock_orch_instance"]
        orch.validate_changes = AsyncMock(
            return_value=_make_validation_response(
                valid=False,
                violations=[{"file": "src/main.py", "rule": "no_blocking_io", "message": "nope"}],
            )
        )

        changes = [{"file_path": "src/main.py", "patch": "time.sleep(1)"}]
        result = await m.validate_code_change("/fake/repo", changes)
        parsed = json.loads(result)
        assert parsed["valid"] is False
        assert len(parsed["violations"]) == 1

    async def test_validates_repo_path(self, mcp_env):
        m = mcp_env["module"]
        validate = mcp_env["mock_validate"]
        orch = mcp_env["mock_orch_instance"]
        orch.validate_changes = AsyncMock(return_value=_make_validation_response())

        await m.validate_code_change("/some/path", [])
        validate.assert_called_once_with("/some/path")

    async def test_error_returns_json_error(self, mcp_env):
        m = mcp_env["module"]
        orch = mcp_env["mock_orch_instance"]
        orch.validate_changes = AsyncMock(side_effect=RuntimeError("validation failure"))

        result = await m.validate_code_change("/fake/repo", [])
        parsed = json.loads(result)
        assert "error" in parsed


class TestGetBlastRadius:
    """Tests for the ``get_blast_radius`` MCP tool."""

    async def test_returns_blast_radius(self, mcp_env):
        m = mcp_env["module"]
        orch = mcp_env["mock_orch_instance"]
        orch.get_blast_radius = AsyncMock(return_value=_make_blast_response())

        result = await m.get_blast_radius("/fake/repo", "src/core/engine.py", depth=2)
        parsed = json.loads(result)
        assert parsed["focus_file"] == "src/core/engine.py"

    async def test_default_depth(self, mcp_env):
        m = mcp_env["module"]
        orch = mcp_env["mock_orch_instance"]
        orch.get_blast_radius = AsyncMock(return_value=_make_blast_response())

        await m.get_blast_radius("/fake/repo", "x.py")
        orch.get_blast_radius.assert_awaited_once_with("/fake/repo", "x.py", 2)

    async def test_custom_depth(self, mcp_env):
        m = mcp_env["module"]
        orch = mcp_env["mock_orch_instance"]
        orch.get_blast_radius = AsyncMock(return_value=_make_blast_response())

        await m.get_blast_radius("/fake/repo", "x.py", depth=3)
        orch.get_blast_radius.assert_awaited_once_with("/fake/repo", "x.py", 3)

    async def test_validates_repo_path(self, mcp_env):
        m = mcp_env["module"]
        validate = mcp_env["mock_validate"]
        orch = mcp_env["mock_orch_instance"]
        orch.get_blast_radius = AsyncMock(return_value=_make_blast_response())

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


class TestMcpServerEnvVars:
    """Tests for env var propagation in MCP server singletons."""

    async def test_env_vars_reach_llm_provider(self):
        """When ARCHAI_LLM_MODEL is set, LiteLLMProvider should be constructed."""
        sys.modules.pop("archai.mcp_server", None)
        env = {
            "ARCHAI_LLM_MODEL": "gpt-4",
            "ARCHAI_LLM_API_BASE": "https://custom",
            "ARCHAI_LLM_API_KEY": "sk-test",
        }
        with (
            patch.dict(os.environ, env, clear=True),
            patch("archai.middleware.ArchaiMiddleware") as mock_mw_cls,
            patch("archai.orchestrator.ArchaiOrchestrator") as mock_orch_cls,
            patch("archai.config.validate_repo_path", lambda p: p),
            patch("archai.inference.llm.LiteLLMProvider") as llm_cls,
        ):
            mock_mw_cls.return_value.process = AsyncMock()

            mock_orch = mock_orch_cls.return_value
            mock_orch.get_context = AsyncMock(return_value=_make_context_packet())

            import archai.mcp_server as m

            await m.get_architecture_context("query", "/fake/path")
            llm_cls.assert_called_once_with(
                model="gpt-4", api_base="https://custom", api_key="sk-test"
            )

    async def test_no_env_no_llm_provider(self):
        """When ARCHAI_LLM_MODEL is not set, no LLM provider is created."""
        sys.modules.pop("archai.mcp_server", None)
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("archai.middleware.ArchaiMiddleware") as mock_mw_cls,
            patch("archai.orchestrator.ArchaiOrchestrator") as mock_orch_cls,
            patch("archai.config.validate_repo_path", lambda p: p),
            patch("archai.inference.llm.LiteLLMProvider") as llm_cls,
        ):
            mock_mw_cls.return_value.process = AsyncMock()

            mock_orch = mock_orch_cls.return_value
            mock_orch.get_context = AsyncMock(return_value=_make_context_packet())

            import archai.mcp_server as m

            await m.get_architecture_context("query", "/fake/path")
            assert mock_mw_cls.call_count == 1
            mw_call_kwargs = mock_mw_cls.call_args[1]
            assert mw_call_kwargs.get("llm_provider") is None
            llm_cls.assert_not_called()


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
