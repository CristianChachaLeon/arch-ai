"""Tests for the ArchAI CLI Typer app."""

import json
import os
import re
from unittest import mock

import pytest
from typer.testing import CliRunner

from archai.cli.app import app

runner = CliRunner()


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


class TestCliHelp:
    """Tests for CLI help output."""

    def test_help_shows_commands(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "start" in result.output
        assert "ask" in result.output
        assert "mcp" in result.output
        assert "init" in result.output

    def test_start_help(self):
        result = runner.invoke(app, ["start", "--help"])
        assert result.exit_code == 0
        assert "--json" in _strip_ansi(result.output)

    def test_ask_help(self):
        result = runner.invoke(app, ["ask", "--help"])
        assert result.exit_code == 0
        assert "QUERY" in result.output
        assert "--json" in _strip_ansi(result.output)

    def test_mcp_help(self):
        result = runner.invoke(app, ["mcp", "--help"])
        assert result.exit_code == 0


class TestStartCommand:
    """Tests for the ``start`` command."""

    @pytest.fixture
    def mock_pipeline(self):
        """Mock the full pipeline so no real async work runs."""
        fake_dict = {
            "repo_path": "/fake/repo",
            "file_count": 5,
            "edge_count": 3,
            "cluster_count": 2,
            "clusters": {"c1": ["a.py", "b.py"]},
        }
        with (
            mock.patch("archai.middleware.pipeline.ArchaiMiddleware") as mw_cls,
            mock.patch("archai.cli.output.format_process_result") as fmt,
        ):
            mw_instance = mw_cls.return_value
            pipeline_result = mock.MagicMock()
            pipeline_result.to_dict.return_value = fake_dict
            mw_instance.process = mock.AsyncMock(return_value=pipeline_result)
            fmt.return_value = "Formatted output"
            yield fmt, mw_cls

    def test_start_with_repo_path(self, mock_pipeline):
        result = runner.invoke(app, ["start", "/fake/repo"])
        assert result.exit_code == 0
        assert "Formatted output" in result.output

    def test_start_json_output(self, mock_pipeline):
        fmt, _ = mock_pipeline
        fmt.return_value = json.dumps({"file_count": 5})
        result = runner.invoke(app, ["start", "/fake/repo", "--json"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["file_count"] == 5

    def test_start_error_handling(self, mock_pipeline):
        _, mw_cls = mock_pipeline
        mw_instance = mw_cls.return_value
        mw_instance.process = mock.AsyncMock(side_effect=ValueError("boom"))
        result = runner.invoke(app, ["start", "/fake/repo"])
        assert result.exit_code == 1
        assert "Error: boom" in result.output

    @mock.patch.dict(os.environ, {"ARCHAI_LLM_MODEL": "gpt-4"}, clear=True)
    def test_start_with_llm_model_env(self):
        fake_dict = {
            "repo_path": "/fake/repo",
            "file_count": 3,
            "edge_count": 1,
            "cluster_count": 1,
            "clusters": {},
        }
        with (
            mock.patch("archai.middleware.pipeline.ArchaiMiddleware") as mw_cls,
            mock.patch("archai.cli.output.format_process_result") as fmt,
            mock.patch("archai.inference.llm.litellm_provider.LiteLLMProvider") as llm_cls,
        ):
            mw_instance = mw_cls.return_value
            pipeline_result = mock.MagicMock()
            pipeline_result.to_dict.return_value = fake_dict
            mw_instance.process = mock.AsyncMock(return_value=pipeline_result)
            fmt.return_value = "done"
            result = runner.invoke(app, ["start", "/fake/repo"])
            assert result.exit_code == 0
            llm_cls.assert_called_once_with(model="gpt-4", api_base=None, api_key=None)

    def test_start_without_llm_model(self):
        fake_dict = {
            "repo_path": "/fake/repo",
            "file_count": 3,
            "edge_count": 1,
            "cluster_count": 1,
            "clusters": {},
        }
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch("archai.middleware.pipeline.ArchaiMiddleware") as mw_cls,
            mock.patch("archai.cli.output.format_process_result") as fmt,
            mock.patch("archai.inference.llm.litellm_provider.LiteLLMProvider") as llm_cls,
        ):
            mw_instance = mw_cls.return_value
            pipeline_result = mock.MagicMock()
            pipeline_result.to_dict.return_value = fake_dict
            mw_instance.process = mock.AsyncMock(return_value=pipeline_result)
            fmt.return_value = "done"
            result = runner.invoke(app, ["start", "/fake/repo"])
            assert result.exit_code == 0
            llm_cls.assert_not_called()

    def test_start_empty_output_does_not_print(self, mock_pipeline):
        fmt, _ = mock_pipeline
        fmt.return_value = ""
        result = runner.invoke(app, ["start", "/fake/repo"])
        assert result.exit_code == 0
        assert result.output.strip() == ""

    def test_start_uses_detect_repo_root_when_no_path(self):
        with (
            mock.patch("archai.config.detect_repo_root", return_value="/detected/repo"),
            mock.patch("archai.middleware.pipeline.ArchaiMiddleware") as mw_cls,
            mock.patch("archai.cli.output.format_process_result") as fmt,
        ):
            mw_instance = mw_cls.return_value
            pipeline_result = mock.MagicMock()
            pipeline_result.to_dict.return_value = {
                "repo_path": "/detected/repo",
                "file_count": 0,
                "edge_count": 0,
                "cluster_count": 0,
                "clusters": {},
            }
            mw_instance.process = mock.AsyncMock(return_value=pipeline_result)
            fmt.return_value = "detected"
            result = runner.invoke(app, ["start"])
            assert result.exit_code == 0
            assert "detected" in result.output


class TestAskCommand:
    """Tests for the ``ask`` command."""

    @pytest.fixture
    def mock_orchestrator(self):
        fake_packet = {
            "focus": "API Layer",
            "focus_reasoning": "Query about HTTP handlers",
            "constraints": {},
            "relevant_files": [],
        }
        with (
            mock.patch("archai.middleware.pipeline.ArchaiMiddleware") as mw_cls,
            mock.patch("archai.orchestrator.orchestrator.ArchaiOrchestrator") as orch_cls,
            mock.patch("archai.cli.output.format_context_packet") as fmt,
        ):
            mw_instance = mw_cls.return_value
            mw_instance.process = mock.AsyncMock(return_value=mock.MagicMock())

            orch_instance = orch_cls.return_value
            context_packet = mock.MagicMock()
            context_packet.model_dump.return_value = fake_packet
            orch_instance.get_context = mock.AsyncMock(return_value=context_packet)

            fmt.return_value = "Context output"
            yield fmt, orch_cls

    def test_ask_with_query(self, mock_orchestrator):
        result = runner.invoke(app, ["ask", "How does auth work?", "/fake/repo"])
        assert result.exit_code == 0
        assert "Context output" in result.output

    def test_ask_json_output(self, mock_orchestrator):
        fmt, _ = mock_orchestrator
        fmt.return_value = json.dumps({"focus": "API Layer"})
        result = runner.invoke(app, ["ask", "How does auth work?", "/fake/repo", "--json"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["focus"] == "API Layer"

    def test_ask_error_handling(self, mock_orchestrator):
        _, orch_cls = mock_orchestrator
        orch_instance = orch_cls.return_value
        orch_instance.get_context = mock.AsyncMock(side_effect=RuntimeError("fail"))
        result = runner.invoke(app, ["ask", "query", "/fake/repo"])
        assert result.exit_code == 1
        assert "Error: fail" in result.output

    def test_ask_uses_detect_repo_root_when_no_path(self):
        with (
            mock.patch("archai.config.detect_repo_root", return_value="/detected/repo"),
            mock.patch("archai.middleware.pipeline.ArchaiMiddleware") as mw_cls,
            mock.patch("archai.orchestrator.orchestrator.ArchaiOrchestrator") as orch_cls,
            mock.patch("archai.cli.output.format_context_packet") as fmt,
        ):
            mw_instance = mw_cls.return_value
            mw_instance.process = mock.AsyncMock(return_value=mock.MagicMock())

            orch_instance = orch_cls.return_value
            context_packet = mock.MagicMock()
            context_packet.model_dump.return_value = {
                "focus": "detected",
                "focus_reasoning": "",
                "constraints": {},
                "relevant_files": [],
            }
            orch_instance.get_context = mock.AsyncMock(return_value=context_packet)
            fmt.return_value = "detected"

            result = runner.invoke(app, ["ask", "query"])
            assert result.exit_code == 0

    @mock.patch.dict(
        os.environ,
        {"ARCHAI_LLM_MODEL": "gpt-4", "ARCHAI_LLM_API_BASE": "https://custom"},
        clear=True,
    )
    def test_ask_env_var_propagation(self):
        fake_packet = {
            "focus": "Core",
            "focus_reasoning": "Test",
            "constraints": {},
            "relevant_files": [],
        }
        with (
            mock.patch("archai.inference.llm.litellm_provider.LiteLLMProvider") as llm_cls,
            mock.patch("archai.middleware.pipeline.ArchaiMiddleware") as mw_cls,
            mock.patch("archai.orchestrator.orchestrator.ArchaiOrchestrator") as orch_cls,
            mock.patch("archai.cli.output.format_context_packet") as fmt,
        ):
            mw_instance = mw_cls.return_value
            mw_instance.process = mock.AsyncMock(return_value=mock.MagicMock())

            orch_instance = orch_cls.return_value
            context_packet = mock.MagicMock()
            context_packet.model_dump.return_value = fake_packet
            orch_instance.get_context = mock.AsyncMock(return_value=context_packet)
            fmt.return_value = "done"
            result = runner.invoke(app, ["ask", "query", "/fake/repo"])
            assert result.exit_code == 0
            llm_cls.assert_called_once_with(model="gpt-4", api_base="https://custom", api_key=None)


class TestMcpCommand:
    """Tests for the ``mcp`` command."""

    def test_mcp_invokes_run(self):
        with mock.patch("archai.mcp_server.mcp") as mock_mcp:
            result = runner.invoke(app, ["mcp"])
            assert result.exit_code == 0
            mock_mcp.run.assert_called_once_with(transport="stdio")


class TestInit:
    """Tests for the ``init`` command."""

    MCP_SERVER_UV = {
        "type": "local",
        "command": ["uv", "run", "archai", "mcp"],
        "enabled": True,
    }
    MCP_SERVER_DIRECT = {
        "type": "local",
        "command": ["archai", "mcp"],
        "enabled": True,
    }

    def test_creates_opencode_json(self, tmp_path):
        result = runner.invoke(app, ["init", str(tmp_path)])
        assert result.exit_code == 0
        config_file = tmp_path / ".opencode.json"
        assert config_file.exists()
        config = json.loads(config_file.read_text())
        assert config == {"mcp": {"archai": self.MCP_SERVER_DIRECT}}

    def test_uses_direct_by_default(self, tmp_path):
        result = runner.invoke(app, ["init", str(tmp_path)])
        assert result.exit_code == 0
        config = json.loads((tmp_path / ".opencode.json").read_text())
        assert config["mcp"]["archai"] == self.MCP_SERVER_DIRECT

    def test_uv_flag_uses_uv_run(self, tmp_path):
        result = runner.invoke(app, ["init", str(tmp_path), "--uv"])
        assert result.exit_code == 0
        config = json.loads((tmp_path / ".opencode.json").read_text())
        assert config["mcp"]["archai"] == self.MCP_SERVER_UV

    def test_respects_force_flag(self, tmp_path):
        config_file = tmp_path / ".opencode.json"
        config_file.write_text('{"existing": true}')
        result = runner.invoke(app, ["init", str(tmp_path)])
        assert result.exit_code == 0
        assert json.loads(config_file.read_text()) == {"existing": True}

        result = runner.invoke(app, ["init", str(tmp_path), "--force"])
        assert result.exit_code == 0
        config = json.loads(config_file.read_text())
        assert config["mcp"]["archai"] == self.MCP_SERVER_DIRECT

    def test_preserves_existing_config(self, tmp_path):
        config_file = tmp_path / ".opencode.json"
        config_file.write_text(json.dumps({"data": {"directory": ".opencode"}}))
        result = runner.invoke(app, ["init", str(tmp_path), "--force"])
        assert result.exit_code == 0
        config = json.loads(config_file.read_text())
        assert config["data"]["directory"] == ".opencode"
        assert config["mcp"]["archai"] == self.MCP_SERVER_DIRECT
