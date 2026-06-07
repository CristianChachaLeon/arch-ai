"""Tests for the ArchAI CLI Typer app."""

import json
import re
from unittest import mock

from typer.testing import CliRunner

from archai.cli.app import app

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _make_mock_trace_result(**overrides):
    from unittest.mock import MagicMock

    mock = MagicMock()
    mock.entry_point = "main"
    mock.entry_file = "src/main.c"
    mock.functions_traced = 3
    mock.call_chain = []
    mock.shared_state = ["cfg", "buffer"]
    mock.side_effects = []
    mock.risks = []

    for k, v in overrides.items():
        setattr(mock, k, v)
    return mock


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


class TestTraceCommand:
    """Tests for the ``trace`` command."""

    def test_trace_help(self):
        result = runner.invoke(app, ["trace", "--help"])
        assert result.exit_code == 0
        plain = _ANSI_RE.sub("", result.output)
        assert "Trace a feature" in plain
        assert "ENTRY_POINT" in plain
        assert "--json" in plain

    def test_trace_nonexistent_dir(self, tmp_path):
        result = runner.invoke(app, ["trace", "main", str(tmp_path / "nonexistent")])
        assert result.exit_code == 1
        assert "Error" in result.output

    def test_trace_pretty_output(self, tmp_path):
        """Test trace command with pretty-print output."""
        from unittest.mock import AsyncMock, patch

        from archai.models import CallNode, Risk, SideEffect

        project = tmp_path / "myproject"
        project.mkdir()
        (project / "Makefile").touch()

        mock_result = _make_mock_trace_result(
            call_chain=[
                CallNode(
                    function="main",
                    file_path="src/main.c",
                    line=5,
                    calls=[
                        CallNode(function="fork", file_path="src/main.c", line=42),
                    ],
                )
            ],
            side_effects=[SideEffect(type="fork", description="Process creation via fork")],
            risks=[Risk(severity="high", description="Fork risk")],
        )

        with (
            patch("archai.middleware.pipeline.ArchaiMiddleware") as MockMiddleware,
            patch("archai.orchestrator.ArchaiOrchestrator") as MockOrch,
        ):
            instance = MockMiddleware.return_value
            instance.process = AsyncMock()
            mock_instance = MockOrch.return_value
            mock_instance.trace_feature_flow = AsyncMock(return_value=mock_result)

            result_invoke = runner.invoke(app, ["trace", "main", str(project)])
            assert result_invoke.exit_code == 0
            assert "cfg" in result_invoke.output
            assert "buffer" in result_invoke.output
            assert "fork" in result_invoke.output
            assert "HIGH" in result_invoke.output

    def test_trace_json_output(self, tmp_path):
        """Test trace command with --json flag using a valid dir."""
        import json as stdjson
        from unittest.mock import AsyncMock, MagicMock, patch

        project = tmp_path / "myproject"
        project.mkdir()
        (project / "Makefile").touch()

        mock_result = MagicMock()
        mock_result.model_dump = MagicMock(
            return_value={
                "entry_point": "run",
                "entry_file": "src/main.c",
                "functions_traced": 2,
                "call_chain": [],
                "shared_state": ["cfg"],
                "side_effects": [],
                "risks": [],
            }
        )

        with (
            patch("archai.middleware.pipeline.ArchaiMiddleware") as MockMiddleware,
            patch("archai.orchestrator.ArchaiOrchestrator") as MockOrch,
        ):
            instance = MockMiddleware.return_value
            instance.process = AsyncMock()
            mock_instance = MockOrch.return_value
            mock_instance.trace_feature_flow = AsyncMock(return_value=mock_result)

            result_invoke = runner.invoke(app, ["trace", "run", str(project), "--json"])
            assert result_invoke.exit_code == 0
            parsed = stdjson.loads(result_invoke.output)
            assert parsed["entry_point"] == "run"
            assert parsed["functions_traced"] == 2
            assert "cfg" in parsed["shared_state"]


class TestCheckCommand:
    """Tests for the ``check`` command."""

    def test_check_help(self):
        result = runner.invoke(app, ["check", "--help"])
        assert result.exit_code == 0
        plain = _ANSI_RE.sub("", result.output)
        assert "Check architecture" in plain
        assert "--json" in plain

    def test_check_nonexistent_dir(self, tmp_path):
        result = runner.invoke(app, ["check", str(tmp_path / "nonexistent")])
        assert result.exit_code == 1
        assert "Error" in result.output


class TestPlanCommand:
    """Tests for the ``plan`` command."""

    def test_plan_help(self):
        result = runner.invoke(app, ["plan", "--help"])
        assert result.exit_code == 0
        plain = _ANSI_RE.sub("", result.output)
        assert "Suggest files" in plain
        assert "DESCRIPTION" in plain
        assert "--json" in plain

    def test_plan_nonexistent_dir(self, tmp_path):
        result = runner.invoke(app, ["plan", "add feature", str(tmp_path / "nonexistent")])
        assert result.exit_code == 1
        assert "Error" in result.output


class TestCiCommand:
    """Tests for the ``ci`` command."""

    def test_ci_help(self):
        result = runner.invoke(app, ["ci", "--help"])
        assert result.exit_code == 0
        plain = _ANSI_RE.sub("", result.output)
        assert "Run archai checks" in plain
        assert "REPO_PATH" in plain

    def test_ci_nonexistent_dir(self, tmp_path):
        result = runner.invoke(app, ["ci", str(tmp_path / "nonexistent")])
        assert result.exit_code == 1


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


class TestBlastCommand:
    """Tests for the ``blast`` command."""

    def test_blast_help(self):
        result = runner.invoke(app, ["blast", "--help"])
        assert result.exit_code == 0
        plain = _ANSI_RE.sub("", result.output)
        assert "Analyze the impact" in plain
        assert "FILE_PATH" in plain
        assert "--depth" in plain
        assert "--json" in plain

    def test_blast_nonexistent_dir(self, tmp_path):
        result = runner.invoke(app, ["blast", "x.py", str(tmp_path / "nonexistent")])
        assert result.exit_code == 1
        assert "Error" in result.output


class TestValidateCommand:
    """Tests for the ``validate`` command."""

    def test_validate_help(self):
        result = runner.invoke(app, ["validate", "--help"])
        assert result.exit_code == 0
        plain = _ANSI_RE.sub("", result.output)
        assert "Validate proposed code changes" in plain
        assert "PATCH_FILE" in plain
        assert "--json" in plain

    def test_validate_nonexistent_dir(self, tmp_path):
        result = runner.invoke(app, ["validate", "x.patch", str(tmp_path / "nonexistent")])
        assert result.exit_code == 1
        assert "Error" in result.output

    def test_validate_nonexistent_patch(self, tmp_path):
        project = tmp_path / "myproject"
        project.mkdir()
        (project / "Makefile").touch()
        result = runner.invoke(app, ["validate", str(tmp_path / "nope.patch"), str(project)])
        assert result.exit_code == 1
        assert "not found" in result.output
