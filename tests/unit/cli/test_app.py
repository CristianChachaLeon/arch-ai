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

    def test_check_no_cycles(self, tmp_path):
        from unittest.mock import AsyncMock, patch

        from archai.bootstrap.graph_builder import FileNode, build_graph
        from archai.middleware.pipeline import PipelineResult

        project = tmp_path / "myproject"
        project.mkdir()
        (project / "Makefile").touch()

        file_nodes = [
            FileNode(path="src/main.py", imports=["src/utils.py"]),
            FileNode(path="src/utils.py", imports=[]),
        ]
        graph = build_graph(file_nodes)
        result = PipelineResult(
            repo_path=str(project),
            graph=graph,
            clusters={},
            file_count=2,
            edge_count=1,
            cluster_count=0,
        )

        with patch("archai.middleware.pipeline.ArchaiMiddleware") as MockMiddleware:
            instance = MockMiddleware.return_value
            instance.process = AsyncMock(return_value=result)
            result_invoke = runner.invoke(app, ["check", str(project)])
            assert result_invoke.exit_code == 0
            assert "No issues found" in result_invoke.output

    def test_check_with_cycles(self, tmp_path):
        from unittest.mock import AsyncMock, patch

        from archai.bootstrap.graph_builder import FileNode, build_graph
        from archai.middleware.pipeline import PipelineResult

        project = tmp_path / "myproject"
        project.mkdir()
        (project / "Makefile").touch()

        file_nodes = [
            FileNode(path="a.py", imports=["b.py"]),
            FileNode(path="b.py", imports=["a.py"]),
        ]
        graph = build_graph(file_nodes)
        result = PipelineResult(
            repo_path=str(project),
            graph=graph,
            clusters={},
            file_count=2,
            edge_count=2,
            cluster_count=0,
        )

        with patch("archai.middleware.pipeline.ArchaiMiddleware") as MockMiddleware:
            instance = MockMiddleware.return_value
            instance.process = AsyncMock(return_value=result)
            result_invoke = runner.invoke(app, ["check", str(project)])
            assert result_invoke.exit_code == 0
            assert "circular_dependency" in result_invoke.output
            assert "HIGH" in result_invoke.output

    def test_check_json_output(self, tmp_path):
        import json as stdjson
        from unittest.mock import AsyncMock, patch

        from archai.bootstrap.graph_builder import FileNode, build_graph
        from archai.middleware.pipeline import PipelineResult

        project = tmp_path / "myproject"
        project.mkdir()
        (project / "Makefile").touch()

        file_nodes = [
            FileNode(path="a.py", imports=["b.py"]),
            FileNode(path="b.py", imports=["a.py"]),
        ]
        graph = build_graph(file_nodes)
        result = PipelineResult(
            repo_path=str(project),
            graph=graph,
            clusters={},
            file_count=2,
            edge_count=2,
            cluster_count=0,
        )

        with patch("archai.middleware.pipeline.ArchaiMiddleware") as MockMiddleware:
            instance = MockMiddleware.return_value
            instance.process = AsyncMock(return_value=result)
            result_invoke = runner.invoke(app, ["check", str(project), "--json"])
            assert result_invoke.exit_code == 0
            parsed = stdjson.loads(result_invoke.output)
            assert parsed["total_issues"] == 1
            assert parsed["issues"][0]["type"] == "circular_dependency"


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

    def test_ci_healthy(self, tmp_path):
        from unittest.mock import AsyncMock, patch

        from archai.bootstrap.graph_builder import FileNode, build_graph
        from archai.middleware.pipeline import PipelineResult

        project = tmp_path / "myproject"
        project.mkdir()
        (project / "Makefile").touch()

        file_nodes = [
            FileNode(path="src/main.py", imports=["src/utils.py"]),
            FileNode(path="src/utils.py", imports=[]),
        ]
        graph = build_graph(file_nodes)
        result = PipelineResult(
            repo_path=str(project),
            graph=graph,
            clusters={},
            file_count=2,
            edge_count=1,
            cluster_count=0,
        )

        with patch("archai.middleware.pipeline.ArchaiMiddleware") as MockMiddleware:
            instance = MockMiddleware.return_value
            instance.process = AsyncMock(return_value=result)
            result_invoke = runner.invoke(app, ["ci", str(project)])
            assert result_invoke.exit_code == 0
            assert '"healthy": true' in result_invoke.output

    def test_ci_with_issues(self, tmp_path):
        from unittest.mock import AsyncMock, patch

        from archai.bootstrap.graph_builder import FileNode, build_graph
        from archai.middleware.pipeline import PipelineResult

        project = tmp_path / "myproject"
        project.mkdir()
        (project / "Makefile").touch()

        file_nodes = [
            FileNode(path="a.py", imports=["b.py"]),
            FileNode(path="b.py", imports=["a.py"]),
        ]
        graph = build_graph(file_nodes)
        result = PipelineResult(
            repo_path=str(project),
            graph=graph,
            clusters={},
            file_count=2,
            edge_count=2,
            cluster_count=0,
        )

        with patch("archai.middleware.pipeline.ArchaiMiddleware") as MockMiddleware:
            instance = MockMiddleware.return_value
            instance.process = AsyncMock(return_value=result)
            result_invoke = runner.invoke(app, ["ci", str(project)])
            assert result_invoke.exit_code == 1
            assert '"healthy": false' in result_invoke.output
            assert '"total_issues": 1' in result_invoke.output


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

    def test_blast_output(self, tmp_path):
        from unittest.mock import AsyncMock, patch

        from archai.models import BlastRadiusResponse

        project = tmp_path / "myproject"
        project.mkdir()
        (project / "Makefile").touch()

        mock_result = BlastRadiusResponse(
            focus_file="src/main.py",
            direct_dependents=["src/dep1.py", "src/dep2.py"],
            transitive_dependents=["src/trans1.py"],
            subsystems_affected={"Core": 2, "UI": 1},
        )

        with (
            patch("archai.middleware.pipeline.ArchaiMiddleware") as MockMiddleware,
            patch("archai.orchestrator.ArchaiOrchestrator") as MockOrch,
        ):
            instance = MockMiddleware.return_value
            instance.process = AsyncMock()
            mock_instance = MockOrch.return_value
            mock_instance.get_blast_radius = AsyncMock(return_value=mock_result)

            result_invoke = runner.invoke(app, ["blast", "src/main.py", str(project)])
            assert result_invoke.exit_code == 0
            assert "src/main.py" in result_invoke.output
            assert "src/dep1.py" in result_invoke.output
            assert "src/trans1.py" in result_invoke.output
            assert "Core" in result_invoke.output

    def test_blast_json_output(self, tmp_path):
        import json as stdjson
        from unittest.mock import AsyncMock, patch

        from archai.models import BlastRadiusResponse

        project = tmp_path / "myproject"
        project.mkdir()
        (project / "Makefile").touch()

        mock_result = BlastRadiusResponse(
            focus_file="src/main.py",
            direct_dependents=["src/dep1.py"],
            transitive_dependents=[],
        )

        with (
            patch("archai.middleware.pipeline.ArchaiMiddleware") as MockMiddleware,
            patch("archai.orchestrator.ArchaiOrchestrator") as MockOrch,
        ):
            instance = MockMiddleware.return_value
            instance.process = AsyncMock()
            mock_instance = MockOrch.return_value
            mock_instance.get_blast_radius = AsyncMock(return_value=mock_result)

            result_invoke = runner.invoke(app, ["blast", "src/main.py", str(project), "--json"])
            assert result_invoke.exit_code == 0
            parsed = stdjson.loads(result_invoke.output)
            assert parsed["focus_file"] == "src/main.py"
            assert len(parsed["direct_dependents"]) == 1

    def test_blast_with_function(self, tmp_path):
        from unittest.mock import AsyncMock, patch

        from archai.models import BlastRadiusResponse

        project = tmp_path / "myproject"
        project.mkdir()
        (project / "Makefile").touch()

        mock_result = BlastRadiusResponse(
            focus_file="src/main.py",
            direct_dependents=[],
            transitive_dependents=[],
            function_name="run",
            function_dependents=["src/caller.py"],
            function_dependencies=["src/helper.py"],
        )

        with (
            patch("archai.middleware.pipeline.ArchaiMiddleware") as MockMiddleware,
            patch("archai.orchestrator.ArchaiOrchestrator") as MockOrch,
        ):
            instance = MockMiddleware.return_value
            instance.process = AsyncMock()
            mock_instance = MockOrch.return_value
            mock_instance.get_blast_radius = AsyncMock(return_value=mock_result)

            result_invoke = runner.invoke(
                app, ["blast", "src/main.py", str(project), "--function", "run"]
            )
            assert result_invoke.exit_code == 0
            assert "Function:" in result_invoke.output
            assert "run" in result_invoke.output
            assert "src/caller.py" in result_invoke.output
            assert "src/helper.py" in result_invoke.output


class TestValidateCommand:
    """Tests for the ``validate`` command."""

    def test_validate_help(self):
        result = runner.invoke(app, ["validate", "--help"])
        assert result.exit_code == 0
        plain = _ANSI_RE.sub("", result.output)
        assert "Show structural context" in plain
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

    def test_validate_empty_patch(self, tmp_path):
        project = tmp_path / "myproject"
        project.mkdir()
        (project / "Makefile").touch()
        patch_file = tmp_path / "empty.patch"
        patch_file.write_text("")
        result_invoke = runner.invoke(app, ["validate", str(patch_file), str(project)])
        assert result_invoke.exit_code == 0
        assert "No changes detected" in result_invoke.output

    def test_validate_pretty_output(self, tmp_path):
        from unittest.mock import AsyncMock, patch

        from archai.bootstrap.graph_builder import FileNode, build_graph
        from archai.middleware.pipeline import PipelineResult

        project = tmp_path / "myproject"
        project.mkdir()
        (project / "Makefile").touch()
        patch_file = tmp_path / "changes.patch"
        patch_file.write_text("--- a/src/main.py\n+++ b/src/main.py\n@@ -1 +1 @@\n-old\n+new\n")

        file_nodes = [
            FileNode(path="src/main.py", imports=["src/utils.py"]),
            FileNode(path="src/utils.py", imports=[]),
        ]
        graph = build_graph(file_nodes)
        pipeline_result = PipelineResult(
            repo_path=str(project),
            graph=graph,
            clusters={"core": ["src/main.py"], "lib": ["src/utils.py"]},
            file_count=2,
            edge_count=1,
            cluster_count=2,
        )

        with (
            patch("archai.middleware.pipeline.ArchaiMiddleware") as MockMiddleware,
            patch("archai.orchestrator.ArchaiOrchestrator") as MockOrch,
        ):
            instance = MockMiddleware.return_value
            instance.process = AsyncMock()
            mock_instance = MockOrch.return_value
            mock_instance._get_pipeline_result = AsyncMock(return_value=pipeline_result)

            result_invoke = runner.invoke(app, ["validate", str(patch_file), str(project)])
            assert result_invoke.exit_code == 0
            assert "src/main.py" in result_invoke.output
            assert "core" in result_invoke.output
            assert "Cluster" in result_invoke.output
            assert "lib" in result_invoke.output

    def test_validate_with_new_imports(self, tmp_path):
        from unittest.mock import AsyncMock, patch

        from archai.bootstrap.graph_builder import FileNode, build_graph
        from archai.middleware.pipeline import PipelineResult

        project = tmp_path / "myproject"
        project.mkdir()
        (project / "Makefile").touch()
        patch_file = tmp_path / "changes.patch"
        patch_file.write_text(
            "--- a/src/main.py\n+++ b/src/main.py\n@@ -1 +1,3 @@\n old\n+from os import path\n+import json\n"
        )

        file_nodes = [FileNode(path="src/main.py", imports=[])]
        graph = build_graph(file_nodes)
        pipeline_result = PipelineResult(
            repo_path=str(project),
            graph=graph,
            clusters={"core": ["src/main.py"]},
            file_count=1,
            edge_count=0,
            cluster_count=1,
        )

        with (
            patch("archai.middleware.pipeline.ArchaiMiddleware") as MockMiddleware,
            patch("archai.orchestrator.ArchaiOrchestrator") as MockOrch,
        ):
            instance = MockMiddleware.return_value
            instance.process = AsyncMock()
            mock_instance = MockOrch.return_value
            mock_instance._get_pipeline_result = AsyncMock(return_value=pipeline_result)

            result_invoke = runner.invoke(app, ["validate", str(patch_file), str(project)])
            assert result_invoke.exit_code == 0
            assert "os.py" in result_invoke.output
            assert "json.py" in result_invoke.output
            assert "New imports" in result_invoke.output

    def test_validate_json_output(self, tmp_path):
        import json as stdjson
        from unittest.mock import AsyncMock, patch

        from archai.bootstrap.graph_builder import FileNode, build_graph
        from archai.middleware.pipeline import PipelineResult

        project = tmp_path / "myproject"
        project.mkdir()
        (project / "Makefile").touch()
        patch_file = tmp_path / "changes.patch"
        patch_file.write_text("--- a/src/main.py\n+++ b/src/main.py\n@@ -1 +1 @@\n-old\n+new\n")

        file_nodes = [FileNode(path="src/main.py", imports=[])]
        graph = build_graph(file_nodes)
        pipeline_result = PipelineResult(
            repo_path=str(project),
            graph=graph,
            clusters={"core": ["src/main.py"]},
            file_count=1,
            edge_count=0,
            cluster_count=1,
        )

        with (
            patch("archai.middleware.pipeline.ArchaiMiddleware") as MockMiddleware,
            patch("archai.orchestrator.ArchaiOrchestrator") as MockOrch,
        ):
            instance = MockMiddleware.return_value
            instance.process = AsyncMock()
            mock_instance = MockOrch.return_value
            mock_instance._get_pipeline_result = AsyncMock(return_value=pipeline_result)

            result_invoke = runner.invoke(
                app, ["validate", str(patch_file), str(project), "--json"]
            )
            assert result_invoke.exit_code == 0
            parsed = stdjson.loads(result_invoke.output)
            assert parsed["file_path"] == "src/main.py"
            assert parsed["file_cluster"] == "core"
            assert "cluster_files" in parsed


class TestFileCommand:
    """Tests for the ``file`` command."""

    def test_file_help(self):
        result = runner.invoke(app, ["file", "--help"])
        assert result.exit_code == 0
        plain = _ANSI_RE.sub("", result.output)
        assert "Get detailed analysis" in plain
        assert "FILE_PATH" in plain
        assert "--json" in plain

    def test_file_nonexistent_dir(self, tmp_path):
        result = runner.invoke(app, ["file", "x.py", str(tmp_path / "nonexistent")])
        assert result.exit_code == 1
        assert "Error" in result.output

    def test_file_pretty_output(self, tmp_path):
        from unittest.mock import AsyncMock, patch

        from archai.models import FileDetailResponse, FunctionDetail

        project = tmp_path / "myproject"
        project.mkdir()
        (project / "Makefile").touch()

        mock_result = FileDetailResponse(
            file_path="src/main.py",
            cluster="Core",
            functions=[
                FunctionDetail(
                    name="run", line=10, calls_internal=["init"], calls_external=["printf"]
                ),
                FunctionDetail(name="init", line=5),
            ],
            classes=["App"],
            imports=["src/utils.py"],
            external_import_count=2,
            dependents=["src/dep1.py"],
            dependencies=["src/utils.py"],
            external_dependency_count=3,
        )

        with (
            patch("archai.middleware.pipeline.ArchaiMiddleware") as MockMiddleware,
            patch("archai.orchestrator.ArchaiOrchestrator") as MockOrch,
        ):
            instance = MockMiddleware.return_value
            instance.process = AsyncMock()
            mock_instance = MockOrch.return_value
            mock_instance.get_file_detail = AsyncMock(return_value=mock_result)

            result_invoke = runner.invoke(app, ["file", "src/main.py", str(project)])
            assert result_invoke.exit_code == 0
            assert "src/main.py" in result_invoke.output
            assert "Core" in result_invoke.output
            assert "run" in result_invoke.output
            assert "App" in result_invoke.output
            assert "src/utils.py" in result_invoke.output
            assert "src/dep1.py" in result_invoke.output
            assert "external" in result_invoke.output

    def test_file_json_output(self, tmp_path):
        import json as stdjson
        from unittest.mock import AsyncMock, patch

        from archai.models import FileDetailResponse, FunctionDetail

        project = tmp_path / "myproject"
        project.mkdir()
        (project / "Makefile").touch()

        mock_result = FileDetailResponse(
            file_path="src/main.py",
            cluster="Core",
            functions=[FunctionDetail(name="run", line=10)],
            classes=[],
        )

        with (
            patch("archai.middleware.pipeline.ArchaiMiddleware") as MockMiddleware,
            patch("archai.orchestrator.ArchaiOrchestrator") as MockOrch,
        ):
            instance = MockMiddleware.return_value
            instance.process = AsyncMock()
            mock_instance = MockOrch.return_value
            mock_instance.get_file_detail = AsyncMock(return_value=mock_result)

            result_invoke = runner.invoke(app, ["file", "src/main.py", str(project), "--json"])
            assert result_invoke.exit_code == 0
            parsed = stdjson.loads(result_invoke.output)
            assert parsed["file_path"] == "src/main.py"
            assert parsed["cluster"] == "Core"
            assert len(parsed["functions"]) == 1
            assert parsed["functions"][0]["name"] == "run"


class TestStateCommandErrors:
    """Tests for state command error handling paths."""

    def test_state_process_error(self, tmp_path):
        from unittest.mock import AsyncMock, patch

        project = tmp_path / "myproject"
        project.mkdir()
        (project / "Makefile").touch()

        with patch("archai.middleware.pipeline.ArchaiMiddleware") as MockMiddleware:
            instance = MockMiddleware.return_value
            instance.process = AsyncMock(side_effect=Exception("analysis failed"))
            result_invoke = runner.invoke(app, ["state", str(project)])
            assert result_invoke.exit_code == 1
            assert "Error analyzing shared state" in result_invoke.output

    def test_state_json_error(self, tmp_path):
        from unittest.mock import AsyncMock, patch

        project = tmp_path / "myproject"
        project.mkdir()
        (project / "Makefile").touch()

        with patch("archai.middleware.pipeline.ArchaiMiddleware") as MockMiddleware:
            instance = MockMiddleware.return_value
            instance.process = AsyncMock(side_effect=Exception("analysis failed"))
            result_invoke = runner.invoke(app, ["state", str(project), "--json"])
            assert result_invoke.exit_code == 1
            assert "analysis failed" in result_invoke.output


class TestTraceCommandErrors:
    """Tests for trace command error handling paths."""

    def test_trace_process_error(self, tmp_path):
        from unittest.mock import AsyncMock, patch

        project = tmp_path / "myproject"
        project.mkdir()
        (project / "Makefile").touch()

        with (
            patch("archai.middleware.pipeline.ArchaiMiddleware") as MockMiddleware,
            patch("archai.orchestrator.ArchaiOrchestrator") as MockOrch,
        ):
            instance = MockMiddleware.return_value
            instance.process = AsyncMock()
            mock_instance = MockOrch.return_value
            mock_instance.trace_feature_flow = AsyncMock(
                side_effect=ValueError("function not found")
            )

            result_invoke = runner.invoke(app, ["trace", "unknown", str(project)])
            assert result_invoke.exit_code == 1
            assert "function not found" in result_invoke.output

    def test_trace_json_error(self, tmp_path):
        from unittest.mock import AsyncMock, patch

        project = tmp_path / "myproject"
        project.mkdir()
        (project / "Makefile").touch()

        with (
            patch("archai.middleware.pipeline.ArchaiMiddleware") as MockMiddleware,
            patch("archai.orchestrator.ArchaiOrchestrator") as MockOrch,
        ):
            instance = MockMiddleware.return_value
            instance.process = AsyncMock()
            mock_instance = MockOrch.return_value
            mock_instance.trace_feature_flow = AsyncMock(side_effect=ValueError("not found"))

            result_invoke = runner.invoke(app, ["trace", "unknown", str(project), "--json"])
            assert result_invoke.exit_code == 1
            assert "not found" in result_invoke.output


class TestValidateCommandErrors:
    """Tests for validate command error handling paths."""

    def test_validate_process_error(self, tmp_path):
        from unittest.mock import AsyncMock, patch

        project = tmp_path / "myproject"
        project.mkdir()
        (project / "Makefile").touch()
        patch_file = tmp_path / "changes.patch"
        patch_file.write_text("--- a/src/main.py\n+++ b/src/main.py\n@@ -1 +1 @@\n-old\n+new\n")

        with (
            patch("archai.middleware.pipeline.ArchaiMiddleware") as MockMiddleware,
            patch("archai.orchestrator.ArchaiOrchestrator") as MockOrch,
        ):
            instance = MockMiddleware.return_value
            instance.process = AsyncMock()
            mock_instance = MockOrch.return_value
            mock_instance._get_pipeline_result = AsyncMock(
                side_effect=RuntimeError("pipeline error")
            )

            result_invoke = runner.invoke(app, ["validate", str(patch_file), str(project)])
            assert result_invoke.exit_code == 1
            assert "pipeline error" in result_invoke.output

    def test_validate_process_error_json(self, tmp_path):
        from unittest.mock import AsyncMock, patch

        project = tmp_path / "myproject"
        project.mkdir()
        (project / "Makefile").touch()
        patch_file = tmp_path / "changes.patch"
        patch_file.write_text("--- a/src/main.py\n+++ b/src/main.py\n@@ -1 +1 @@\n-old\n+new\n")

        with (
            patch("archai.middleware.pipeline.ArchaiMiddleware") as MockMiddleware,
            patch("archai.orchestrator.ArchaiOrchestrator") as MockOrch,
        ):
            instance = MockMiddleware.return_value
            instance.process = AsyncMock()
            mock_instance = MockOrch.return_value
            mock_instance._get_pipeline_result = AsyncMock(
                side_effect=RuntimeError("pipeline error")
            )

            result_invoke = runner.invoke(
                app, ["validate", str(patch_file), str(project), "--json"]
            )
            assert result_invoke.exit_code == 1
            assert "pipeline error" in result_invoke.output
