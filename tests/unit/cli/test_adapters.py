"""Tests for agent adapters (base + all implementations)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import tomllib

from archai.cli.adapters import AGENT_MAP, resolve_adapters
from archai.cli.adapters.base import BaseAgentAdapter
from archai.cli.adapters.claude import ClaudeCodeAdapter
from archai.cli.adapters.cursor import CursorAdapter
from archai.cli.adapters.gemini import GeminiCliAdapter
from archai.cli.adapters.opencode import OpenCodeAdapter


class TestAgentMap:
    """All agents are registered."""

    def test_all_agents_registered(self):
        assert set(AGENT_MAP) == {"opencode", "gemini", "claude", "cursor"}

    def test_each_is_adapter_subclass(self):
        for cls in AGENT_MAP.values():
            assert issubclass(cls, BaseAgentAdapter)


class TestResolveAdapters:
    """resolve_adapters utility."""

    def test_single_agent_returns_list_of_one(self, tmp_path):
        adapters = resolve_adapters("opencode", tmp_path)
        assert len(adapters) == 1
        assert isinstance(adapters[0], OpenCodeAdapter)

    def test_all_returns_all_four(self, tmp_path):
        adapters = resolve_adapters("all", tmp_path)
        assert len(adapters) == 4

    def test_all_returns_distinct_types(self, tmp_path):
        adapters = resolve_adapters("all", tmp_path)
        types = {type(a) for a in adapters}
        assert types == {OpenCodeAdapter, ClaudeCodeAdapter, CursorAdapter, GeminiCliAdapter}


class TestOpenCodeAdapter:
    """OpenCode adapter — TOML format."""

    def test_config_path(self, tmp_path):
        adapter = OpenCodeAdapter(tmp_path)
        assert adapter.config_path() == tmp_path / ".opencode" / "opencode.toml"

    def test_generate_config(self):
        adapter = OpenCodeAdapter(Path("/dummy"))
        config = adapter.generate_config(["archai", "serve"])
        assert config == {
            "mcp": {
                "archai": {
                    "type": "local",
                    "command": ["archai", "serve"],
                    "enabled": True,
                }
            }
        }

    def test_serialize(self):
        adapter = OpenCodeAdapter(Path("/dummy"))
        config = adapter.generate_config(["archai", "serve"])
        raw = adapter.serialize(config)
        parsed = tomllib.loads(raw)
        assert parsed["mcp"]["archai"]["type"] == "local"
        assert parsed["mcp"]["archai"]["command"] == ["archai", "serve"]
        assert parsed["mcp"]["archai"]["enabled"] is True

    def test_write_creates_file(self, tmp_path):
        adapter = OpenCodeAdapter(tmp_path)
        result = adapter.write()
        assert result == tmp_path / ".opencode" / "opencode.toml"
        assert result.exists()
        parsed = tomllib.loads(result.read_text())
        assert parsed["mcp"]["archai"]["command"] == ["archai", "serve"]

    def test_write_skips_if_already_configured(self, tmp_path):
        config_dir = tmp_path / ".opencode"
        config_dir.mkdir()
        config_file = config_dir / "opencode.toml"
        config_file.write_text('[mcp.archai]\ntype = "local"\ncommand = ["archai", "serve"]\nenabled = true\n')
        adapter = OpenCodeAdapter(tmp_path)
        result = adapter.write()
        assert result is None

    def test_write_merges_with_existing_mcp(self, tmp_path):
        config_dir = tmp_path / ".opencode"
        config_dir.mkdir()
        config_file = config_dir / "opencode.toml"
        config_file.write_text('[mcp.other]\ncommand = ["other"]\n')
        adapter = OpenCodeAdapter(tmp_path)
        result = adapter.write()
        assert result is not None
        parsed = tomllib.loads(result.read_text())
        assert "other" in parsed["mcp"]
        assert "archai" in parsed["mcp"]

    def test_write_custom_command(self, tmp_path):
        adapter = OpenCodeAdapter(tmp_path)
        result = adapter.write(mcp_command=["archai", "serve", "--port", "9999"])
        assert result.exists()
        parsed = tomllib.loads(result.read_text())
        assert parsed["mcp"]["archai"]["command"] == ["archai", "serve", "--port", "9999"]


class TestClaudeCodeAdapter:
    """Claude Code adapter — JSON format."""

    def test_config_path(self, tmp_path):
        adapter = ClaudeCodeAdapter(tmp_path)
        assert adapter.config_path() == tmp_path / ".claude" / "settings.json"

    def test_generate_config(self):
        adapter = ClaudeCodeAdapter(Path("/dummy"))
        config = adapter.generate_config(["archai", "serve"])
        assert config == {
            "mcpServers": {
                "archai": {
                    "command": "archai",
                    "args": ["serve"],
                }
            }
        }

    def test_serialize(self):
        adapter = ClaudeCodeAdapter(Path("/dummy"))
        config = adapter.generate_config(["archai", "serve"])
        raw = adapter.serialize(config)
        parsed = json.loads(raw)
        assert parsed["mcpServers"]["archai"]["command"] == "archai"
        assert parsed["mcpServers"]["archai"]["args"] == ["serve"]

    def test_write_creates_file(self, tmp_path):
        adapter = ClaudeCodeAdapter(tmp_path)
        result = adapter.write()
        assert result == tmp_path / ".claude" / "settings.json"
        assert result.exists()
        parsed = json.loads(result.read_text())
        assert parsed["mcpServers"]["archai"]["command"] == "archai"

    def test_write_merges_existing(self, tmp_path):
        config_dir = tmp_path / ".claude"
        config_dir.mkdir()
        config_file = config_dir / "settings.json"
        config_file.write_text(json.dumps({"mcpServers": {"other": {"command": "other"}}}))
        adapter = ClaudeCodeAdapter(tmp_path)
        result = adapter.write()
        parsed = json.loads(result.read_text())
        assert "other" in parsed["mcpServers"]
        assert "archai" in parsed["mcpServers"]


class TestCursorAdapter:
    """Cursor adapter — JSON format."""

    def test_config_path(self, tmp_path):
        adapter = CursorAdapter(tmp_path)
        assert adapter.config_path() == tmp_path / ".cursor" / "mcp.json"

    def test_generate_config(self):
        adapter = CursorAdapter(Path("/dummy"))
        config = adapter.generate_config(["archai", "serve"])
        assert config == {
            "mcpServers": {
                "archai": {
                    "command": "archai",
                    "args": ["serve"],
                }
            }
        }

    def test_write_creates_file(self, tmp_path):
        adapter = CursorAdapter(tmp_path)
        result = adapter.write()
        assert result == tmp_path / ".cursor" / "mcp.json"
        parsed = json.loads(result.read_text())
        assert parsed["mcpServers"]["archai"]["command"] == "archai"

    def test_write_merges_existing(self, tmp_path):
        config_dir = tmp_path / ".cursor"
        config_dir.mkdir()
        config_file = config_dir / "mcp.json"
        config_file.write_text(json.dumps({"mcpServers": {"other": {"command": "other"}}}))
        adapter = CursorAdapter(tmp_path)
        result = adapter.write()
        parsed = json.loads(result.read_text())
        assert "other" in parsed["mcpServers"]
        assert "archai" in parsed["mcpServers"]


class TestGeminiCliAdapter:
    """Gemini CLI adapter — JSON format."""

    def test_config_path(self, tmp_path):
        adapter = GeminiCliAdapter(tmp_path)
        assert adapter.config_path() == tmp_path / ".gemini" / "settings.json"

    def test_generate_config(self):
        adapter = GeminiCliAdapter(Path("/dummy"))
        config = adapter.generate_config(["archai", "serve"])
        assert config == {
            "mcpServers": {
                "archai": {
                    "command": "archai",
                    "args": ["serve"],
                }
            }
        }

    def test_write_creates_file(self, tmp_path):
        adapter = GeminiCliAdapter(tmp_path)
        result = adapter.write()
        assert result == tmp_path / ".gemini" / "settings.json"
        parsed = json.loads(result.read_text())
        assert parsed["mcpServers"]["archai"]["command"] == "archai"

    def test_write_merges_existing(self, tmp_path):
        config_dir = tmp_path / ".gemini"
        config_dir.mkdir()
        config_file = config_dir / "settings.json"
        config_file.write_text(json.dumps({"other_key": "value"}))
        adapter = GeminiCliAdapter(tmp_path)
        result = adapter.write()
        parsed = json.loads(result.read_text())
        assert parsed["other_key"] == "value"
        assert "archai" in parsed["mcpServers"]
