"""Tests for the ArchAI CLI Typer app."""

import json
import re
from unittest import mock

from typer.testing import CliRunner

from archai.cli.app import app

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
runner = CliRunner()


class TestVersion:
    """Tests for the ``--version`` flag."""

    def test_version_output_format(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert re.match(r"archai-mcp v\d+\.\d+\.\d+", result.output.strip())


class TestCliHelp:
    """Tests for CLI help output."""

    def test_help_shows_commands(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "serve" in result.output
        assert "init" in result.output
        # start and ask were removed — archai is MCP-only
        assert "start" not in result.output
        assert "ask" not in result.output

    def test_serve_help(self):
        result = runner.invoke(app, ["serve", "--help"])
        assert result.exit_code == 0

    def test_mcp_help(self):
        result = runner.invoke(app, ["mcp", "--help"])
        assert result.exit_code == 0

    def test_init_help(self):
        result = runner.invoke(app, ["init", "--help"])
        assert result.exit_code == 0
        assert "PROJECT_DIR" in result.output


class TestServeCommand:
    """Tests for the ``serve`` command."""

    def test_serve_invokes_run(self):
        with mock.patch("archai.mcp_server.mcp") as mock_mcp:
            result = runner.invoke(app, ["serve"])
            assert result.exit_code == 0
            mock_mcp.run.assert_called_once_with(transport="stdio")

    def test_mcp_alias_invokes_serve(self):
        with mock.patch("archai.mcp_server.mcp") as mock_mcp:
            result = runner.invoke(app, ["mcp"])
            assert result.exit_code == 0
            mock_mcp.run.assert_called_once_with(transport="stdio")


class TestStateCommand:
    """Tests for the ``state`` command."""

    def test_state_help(self):
        result = runner.invoke(app, ["state", "--help"])
        assert result.exit_code == 0
        plain = _ANSI_RE.sub("", result.output)
        assert "Analyze shared global state" in plain
        assert "--var" in plain
        assert "--json" in plain

    def test_state_nonexistent_dir(self, tmp_path):
        result = runner.invoke(app, ["state", str(tmp_path / "nonexistent")])
        assert result.exit_code == 1
        assert "Error" in result.output

    def test_state_json_output(self, tmp_path):
        """Test state command with --json flag using a valid dir."""
        import json as stdjson
        from unittest.mock import AsyncMock, patch

        from archai.bootstrap.graph_builder import FileNode, build_graph
        from archai.middleware.pipeline import PipelineResult

        project = tmp_path / "myproject"
        project.mkdir()
        (project / "Makefile").touch()

        file_nodes = [
            FileNode(
                path="main.c",
                imports=[],
                functions=[],
                classes=[],
                global_vars=[
                    {"name": "debug_mode", "line": 1, "is_static": False},
                    {"name": "counter", "line": 2, "is_static": True},
                ],
            ),
        ]
        graph = build_graph(file_nodes)
        result = PipelineResult(
            repo_path=str(project),
            graph=graph,
            clusters={},
            file_count=1,
            edge_count=0,
            cluster_count=0,
        )

        with patch("archai.middleware.pipeline.ArchaiMiddleware") as MockMiddleware:
            instance = MockMiddleware.return_value
            instance.process = AsyncMock(return_value=result)
            result_invoke = runner.invoke(app, ["state", str(project), "--json"])
            assert result_invoke.exit_code == 0
            parsed = stdjson.loads(result_invoke.output)
            assert parsed["total_count"] == 2
            assert parsed["variables"][0]["name"] == "counter"
            assert parsed["variables"][1]["name"] == "debug_mode"

    def test_state_pretty_output(self, tmp_path):
        """Test state command pretty-print with --var filter."""
        from unittest.mock import AsyncMock, patch

        from archai.bootstrap.graph_builder import FileNode, build_graph
        from archai.middleware.pipeline import PipelineResult

        project = tmp_path / "myproject"
        project.mkdir()
        (project / "Makefile").touch()

        file_nodes = [
            FileNode(
                path="main.c",
                imports=[],
                functions=[],
                classes=[],
                global_vars=[
                    {"name": "debug_mode", "line": 1, "is_static": False},
                    {"name": "counter", "line": 2, "is_static": True},
                ],
            ),
        ]
        graph = build_graph(file_nodes)
        result = PipelineResult(
            repo_path=str(project),
            graph=graph,
            clusters={},
            file_count=1,
            edge_count=0,
            cluster_count=0,
        )

        with patch("archai.middleware.pipeline.ArchaiMiddleware") as MockMiddleware:
            instance = MockMiddleware.return_value
            instance.process = AsyncMock(return_value=result)
            result_invoke = runner.invoke(app, ["state", str(project), "--var", "debug"])
            assert result_invoke.exit_code == 0
            assert "debug_mode" in result_invoke.output
            assert "counter" not in result_invoke.output


class TestInit:
    """Tests for the ``init`` command."""

    def test_creates_opencode_json(self, tmp_path):
        result = runner.invoke(app, ["init", str(tmp_path)])
        assert result.exit_code == 0
        config_file = tmp_path / ".opencode.json"
        assert config_file.exists()
        config = json.loads(config_file.read_text())
        archai_cfg = config["mcp"]["archai"]
        assert archai_cfg["type"] == "local"
        assert archai_cfg["command"] == ["archai", "serve"]
        assert archai_cfg["enabled"] is True
        # No environment block — archai needs no LLM config
        assert "environment" not in archai_cfg

    def test_no_environment_passthrough(self, tmp_path):
        """Verify init does NOT add LLM environment passthrough."""
        result = runner.invoke(app, ["init", str(tmp_path)])
        assert result.exit_code == 0
        config = json.loads((tmp_path / ".opencode.json").read_text())
        archai_cfg = config["mcp"]["archai"]
        assert "environment" not in archai_cfg
        # Just the three required fields
        assert set(archai_cfg.keys()) == {"type", "command", "enabled"}

    def test_preserves_existing_config_when_archai_not_configured(self, tmp_path):
        """If .opencode.json exists but archai is not configured, add it."""
        config_file = tmp_path / ".opencode.json"
        config_file.write_text(json.dumps({"data": {"directory": ".opencode"}}))
        result = runner.invoke(app, ["init", str(tmp_path)])
        assert result.exit_code == 0
        config = json.loads(config_file.read_text())
        assert config["data"]["directory"] == ".opencode"
        archai_cfg = config["mcp"]["archai"]
        assert archai_cfg["type"] == "local"
        assert archai_cfg["command"] == ["archai", "serve"]
        assert archai_cfg["enabled"] is True

    def test_skips_if_already_configured(self, tmp_path):
        """If archai already configured, do nothing."""
        config_file = tmp_path / ".opencode.json"
        existing_config = {
            "mcp": {
                "archai": {
                    "type": "local",
                    "command": ["archai", "mcp"],
                    "enabled": True,
                }
            }
        }
        config_file.write_text(json.dumps(existing_config))
        result = runner.invoke(app, ["init", str(tmp_path)])
        assert result.exit_code == 0
        # Config should not change
        config = json.loads(config_file.read_text())
        assert config == existing_config

    def test_adds_to_existing_mcp_config(self, tmp_path):
        """If other MCP servers exist, keep them."""
        config_file = tmp_path / ".opencode.json"
        existing_config = {
            "mcp": {
                "other-server": {
                    "type": "local",
                    "command": ["other", "command"],
                }
            }
        }
        config_file.write_text(json.dumps(existing_config))
        result = runner.invoke(app, ["init", str(tmp_path)])
        assert result.exit_code == 0
        config = json.loads(config_file.read_text())
        assert "other-server" in config["mcp"]
        assert "archai" in config["mcp"]
