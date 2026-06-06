"""Tests for the ArchAI CLI Typer app."""

import json
from unittest import mock

from typer.testing import CliRunner

from archai.cli.app import app

runner = CliRunner()


class TestCliHelp:
    """Tests for CLI help output."""

    def test_help_shows_commands(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "mcp" in result.output
        assert "init" in result.output
        # start and ask were removed — archai is MCP-only
        assert "start" not in result.output
        assert "ask" not in result.output

    def test_mcp_help(self):
        result = runner.invoke(app, ["mcp", "--help"])
        assert result.exit_code == 0

    def test_init_help(self):
        result = runner.invoke(app, ["init", "--help"])
        assert result.exit_code == 0
        assert "PROJECT_DIR" in result.output


class TestMcpCommand:
    """Tests for the ``mcp`` command."""

    def test_mcp_invokes_run(self):
        with mock.patch("archai.mcp_server.mcp") as mock_mcp:
            result = runner.invoke(app, ["mcp"])
            assert result.exit_code == 0
            mock_mcp.run.assert_called_once_with(transport="stdio")


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
        assert archai_cfg["command"] == ["archai", "mcp"]
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
        assert archai_cfg["command"] == ["archai", "mcp"]
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
