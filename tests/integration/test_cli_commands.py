"""Integration tests for ALL archai CLI commands against real fixture repos.

Tests run ACTUAL archai commands (not mocked) via CliRunner against
minimal Python and C/C++ fixture repositories.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from archai.cli.app import app

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

runner = CliRunner()

FIXTURES_DIR = Path(__file__).parent / "fixtures"

FIXTURE_NAMES = [
    "py-simple",
    "py-modules",
    "py-cli",
    "py-with-deps",
    "py-empty",
    "c-simple",
    "c-multi",
    "cpp-simple",
    "cpp-multi",
    "c-empty",
]

# Fixtures that contain actual source code (not empty)
NON_EMPTY = {n for n in FIXTURE_NAMES if "empty" not in n}

# Fixtures that have a `main.py` file
HAS_MAIN_PY = {"py-simple", "py-modules", "py-cli", "py-with-deps"}

# Fixtures that have a `greet` function defined
HAS_GREET = {"py-simple", "py-cli", "c-simple", "cpp-simple"}

# Fixtures that have a `main` function defined
HAS_MAIN_FN = {
    "py-simple", "py-cli",
    "c-simple", "c-multi",
    "cpp-simple", "cpp-multi",
}

# Fixtures that have global variables
HAS_GLOBALS = {"py-simple", "py-modules", "c-simple", "cpp-simple"}

# Fixtures with C source files
HAS_C_FILE = {"c-simple", "c-multi"}

# Fixtures with C++ source files
HAS_CPP_FILE = {"cpp-simple", "cpp-multi"}

# Various source files per fixture
FILES = {
    "py-simple": "main.py",
    "py-modules": "main.py",
    "py-cli": "cli.py",
    "py-with-deps": "a.py",
    "c-simple": "main.c",
    "c-multi": "main.c",
    "cpp-simple": "main.cpp",
    "cpp-multi": "main.cpp",
}

# Functions to trace per fixture (keyed by fixture name)
TRACE_FUNCS = {
    "py-simple": "greet",
    "py-modules": "process_user",
    "py-cli": "greet",
    "py-with-deps": "foo",
    "c-simple": "main",
    "c-multi": "main",
    "cpp-simple": "main",
    "cpp-multi": "main",
}

# Variable names for --var filter
VAR_NAMES = {
    "py-simple": "counter",
    "py-modules": "EMAIL_RE",
    "c-simple": "counter",
    "cpp-simple": "counter",
}


def fixture_path(name: str) -> Path:
    return FIXTURES_DIR / name


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


# ─── No-repo commands: --help, --version ───────────────────────────


class TestMeta:
    """Tests that don't need a repo path."""

    def test_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        plain = strip_ansi(result.output)
        assert "Usage" in plain
        assert "analyze" in plain
        assert "context" in plain

    def test_version(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert re.match(r"archai-mcp v\d+\.\d+\.\d+", result.output.strip())


# ─── init command (uses tmp_path, avoids fixture pollution) ────────


class TestInit:
    def test_init_creates_config(self, tmp_path):
        result = runner.invoke(app, ["init", str(tmp_path)])
        assert result.exit_code == 0
        config_file = tmp_path / ".opencode" / "opencode.json"
        assert config_file.exists()
        config = json.loads(config_file.read_text())
        assert config["mcp"]["archai"]["type"] == "local"
        assert config["mcp"]["archai"]["command"] == ["archai", "serve"]
        assert config["mcp"]["archai"]["enabled"] is True

    def test_init_on_nonempty_dir(self, tmp_path):
        (tmp_path / "main.py").write_text("x = 1")
        result = runner.invoke(app, ["init", str(tmp_path)])
        assert result.exit_code == 0
        config_file = tmp_path / ".opencode" / "opencode.json"
        assert config_file.exists()


# ─── parametrized commands ─────────────────────────────────────────


class TestAnalyze:
    @pytest.mark.parametrize("fixture_name", NON_EMPTY)
    def test_analyze_pretty(self, fixture_name: str):
        path = fixture_path(fixture_name)
        result = runner.invoke(app, ["analyze", str(path)])
        plain = strip_ansi(result.output)
        assert result.exit_code == 0, f"Failed on {fixture_name}: {plain[:500]}"
        assert "Architecture Overview" in plain

    @pytest.mark.parametrize("fixture_name", NON_EMPTY)
    def test_analyze_json(self, fixture_name: str):
        path = fixture_path(fixture_name)
        result = runner.invoke(app, ["analyze", str(path), "--json"])
        assert result.exit_code == 0, f"Failed on {fixture_name}"
        parsed = json.loads(result.output)
        assert "file_count" in parsed
        assert parsed["file_count"] > 0

    @pytest.mark.parametrize("fixture_name", NON_EMPTY)
    def test_analyze_force(self, fixture_name: str):
        path = fixture_path(fixture_name)
        result = runner.invoke(app, ["analyze", str(path), "--force"])
        assert result.exit_code == 0, f"Failed on {fixture_name}"
        plain = strip_ansi(result.output)
        assert "Architecture Overview" in plain

    @pytest.mark.parametrize("fixture_name", FIXTURE_NAMES)
    def test_analyze_empty(self, fixture_name: str):
        """Empty fixtures should still exit 0 but show 0 files."""
        if "empty" not in fixture_name:
            pytest.skip("Only for empty fixtures")
        path = fixture_path(fixture_name)
        result = runner.invoke(app, ["analyze", str(path)])
        assert result.exit_code == 0, f"Failed on {fixture_name}"
        plain = strip_ansi(result.output)
        assert "Architecture Overview" in plain

    @pytest.mark.parametrize("fixture_name", FIXTURE_NAMES)
    def test_analyze_json_empty(self, fixture_name: str):
        if "empty" in fixture_name:
            path = fixture_path(fixture_name)
            result = runner.invoke(app, ["analyze", str(path), "--json"])
            assert result.exit_code == 0
            parsed = json.loads(result.output)
            assert parsed["file_count"] == 0
        else:
            pytest.skip("Not an empty fixture")


class TestContext:
    @pytest.mark.parametrize("fixture_name", NON_EMPTY)
    def test_context_pretty(self, fixture_name: str):
        path = fixture_path(fixture_name)
        result = runner.invoke(app, ["context", "main", str(path)])
        plain = strip_ansi(result.output)
        assert result.exit_code == 0, f"Failed on {fixture_name}: {plain[:500]}"
        assert "Architecture Context" in plain

    @pytest.mark.parametrize("fixture_name", NON_EMPTY)
    def test_context_json(self, fixture_name: str):
        path = fixture_path(fixture_name)
        result = runner.invoke(app, ["context", "main", str(path), "--json"])
        assert result.exit_code == 0, f"Failed on {fixture_name}"
        parsed = json.loads(result.output)
        assert "focus_cluster" in parsed

    @pytest.mark.parametrize("fixture_name", {"py-empty", "c-empty"})
    def test_context_empty(self, fixture_name: str):
        path = fixture_path(fixture_name)
        result = runner.invoke(app, ["context", "main", str(path)])
        assert result.exit_code == 0, f"Failed on {fixture_name}"

    def test_context_nonexistent_dir(self):
        result = runner.invoke(app, ["context", "auth", "/nonexistent/path"])
        assert result.exit_code == 1
        assert "Error" in result.output


class TestFile:
    @pytest.mark.parametrize(
        ("fixture_name", "file_arg"),
        [
            pytest.param("py-simple", "main.py", id="py-simple"),
            pytest.param("py-modules", "main.py", id="py-modules"),
            pytest.param("py-cli", "cli.py", id="py-cli"),
            pytest.param("py-with-deps", "a.py", id="py-with-deps"),
            pytest.param("c-simple", "main.c", id="c-simple"),
            pytest.param("c-multi", "main.c", id="c-multi"),
            pytest.param("cpp-simple", "main.cpp", id="cpp-simple"),
            pytest.param("cpp-multi", "main.cpp", id="cpp-multi"),
            pytest.param("py-empty", "nope.py", marks=pytest.mark.xfail, id="py-empty"),
            pytest.param("c-empty", "nope.c", marks=pytest.mark.xfail, id="c-empty"),
        ],
    )
    def test_file_pretty(self, fixture_name: str, file_arg: str):
        path = fixture_path(fixture_name)
        result = runner.invoke(app, ["file", file_arg, str(path)])
        plain = strip_ansi(result.output)
        assert result.exit_code == 0, f"Failed on {fixture_name}: {plain[:500]}"
        assert file_arg in plain
        assert "Functions" in plain

    @pytest.mark.parametrize(
        ("fixture_name", "file_arg"),
        [
            pytest.param("py-simple", "main.py", id="py-simple"),
            pytest.param("py-modules", "main.py", id="py-modules"),
            pytest.param("py-cli", "cli.py", id="py-cli"),
            pytest.param("py-with-deps", "a.py", id="py-with-deps"),
            pytest.param("c-simple", "main.c", id="c-simple"),
            pytest.param("c-multi", "main.c", id="c-multi"),
            pytest.param("cpp-simple", "main.cpp", id="cpp-simple"),
            pytest.param("cpp-multi", "main.cpp", id="cpp-multi"),
        ],
    )
    def test_file_json(self, fixture_name: str, file_arg: str):
        path = fixture_path(fixture_name)
        result = runner.invoke(app, ["file", file_arg, str(path), "--json"])
        assert result.exit_code == 0, f"Failed on {fixture_name}: {result.output[:300]}"
        parsed = json.loads(result.output)
        assert parsed["file_path"] == file_arg

    def test_file_nonexistent_fixture(self):
        result = runner.invoke(app, ["file", "main.py", "/nonexistent"])
        assert result.exit_code == 1
        assert "Error" in result.output


class TestState:
    @pytest.mark.parametrize("fixture_name", HAS_GLOBALS)
    def test_state_pretty(self, fixture_name: str):
        path = fixture_path(fixture_name)
        result = runner.invoke(app, ["state", str(path)])
        plain = strip_ansi(result.output)
        assert result.exit_code == 0, f"Failed on {fixture_name}: {plain[:500]}"
        assert "Shared State" in plain

    @pytest.mark.parametrize("fixture_name", HAS_GLOBALS)
    def test_state_json(self, fixture_name: str):
        path = fixture_path(fixture_name)
        result = runner.invoke(app, ["state", str(path), "--json"])
        assert result.exit_code == 0, f"Failed on {fixture_name}"
        parsed = json.loads(result.output)
        assert "total_count" in parsed
        assert parsed["total_count"] > 0

    @pytest.mark.parametrize("fixture_name", HAS_GLOBALS)
    def test_state_var_filter(self, fixture_name: str):
        var_name = VAR_NAMES[fixture_name]
        path = fixture_path(fixture_name)
        result = runner.invoke(app, ["state", str(path), "--var", var_name])
        plain = strip_ansi(result.output)
        assert result.exit_code == 0, f"Failed on {fixture_name}: {plain[:500]}"
        assert var_name in plain

    @pytest.mark.parametrize("fixture_name", NON_EMPTY - HAS_GLOBALS)
    def test_state_no_globals(self, fixture_name: str):
        """Fixtures without module-level globals should report 0."""
        path = fixture_path(fixture_name)
        result = runner.invoke(app, ["state", str(path)])
        plain = strip_ansi(result.output)
        assert result.exit_code == 0, f"Failed on {fixture_name}: {plain[:500]}"
        assert "No global variables found" in plain

    @pytest.mark.parametrize("fixture_name", FIXTURE_NAMES)
    def test_state_empty(self, fixture_name: str):
        if "empty" not in fixture_name:
            pytest.skip("Only for empty fixtures")
        path = fixture_path(fixture_name)
        result = runner.invoke(app, ["state", str(path)])
        assert result.exit_code == 0, f"Failed on {fixture_name}"

    def test_state_nonexistent_dir(self):
        result = runner.invoke(app, ["state", "/nonexistent"])
        assert result.exit_code == 1
        assert "Error" in result.output


class TestTrace:
    @pytest.mark.parametrize(
        ("fixture_name", "func_name"),
        [
            pytest.param("py-simple", "greet", id="py-simple"),
            pytest.param("py-modules", "process_user", id="py-modules"),
            pytest.param("py-cli", "greet", id="py-cli"),
            pytest.param("py-with-deps", "foo", id="py-with-deps"),
            pytest.param("c-simple", "main", id="c-simple"),
            pytest.param("c-multi", "main", id="c-multi"),
            pytest.param("cpp-simple", "main", id="cpp-simple"),
            pytest.param("cpp-multi", "main", id="cpp-multi"),
            pytest.param("py-empty", "main", id="py-empty"),
            pytest.param("c-empty", "main", id="c-empty"),
        ],
    )
    def test_trace_pretty(self, fixture_name: str, func_name: str):
        path = fixture_path(fixture_name)
        result = runner.invoke(app, ["trace", func_name, str(path)])
        plain = strip_ansi(result.output)
        assert result.exit_code == 0, f"Failed on {fixture_name}: {plain[:500]}"
        assert "Trace Analysis" in plain
        if "empty" not in fixture_name:
            assert func_name in plain, f"Function {func_name} not found in output"

    @pytest.mark.parametrize(
        ("fixture_name", "func_name"),
        [
            pytest.param("py-simple", "greet", id="py-simple"),
            pytest.param("py-modules", "process_user", id="py-modules"),
            pytest.param("py-cli", "greet", id="py-cli"),
            pytest.param("py-with-deps", "foo", id="py-with-deps"),
            pytest.param("c-simple", "main", id="c-simple"),
            pytest.param("c-multi", "main", id="c-multi"),
            pytest.param("cpp-simple", "main", id="cpp-simple"),
            pytest.param("cpp-multi", "main", id="cpp-multi"),
        ],
    )
    def test_trace_json(self, fixture_name: str, func_name: str):
        path = fixture_path(fixture_name)
        result = runner.invoke(app, ["trace", func_name, str(path), "--json"])
        assert result.exit_code == 0, f"Failed on {fixture_name}: {result.output[:300]}"
        parsed = json.loads(result.output)
        assert parsed["entry_point"] == func_name

    def test_trace_nonexistent_dir(self):
        result = runner.invoke(app, ["trace", "main", "/nonexistent"])
        assert result.exit_code == 1
        assert "Error" in result.output


class TestBlast:
    @pytest.mark.parametrize(
        ("fixture_name", "file_arg"),
        [
            pytest.param("py-simple", "main.py", id="py-simple"),
            pytest.param("py-modules", "main.py", id="py-modules"),
            pytest.param("py-cli", "cli.py", id="py-cli"),
            pytest.param("py-with-deps", "a.py", id="py-with-deps"),
            pytest.param("c-simple", "main.c", id="c-simple"),
            pytest.param("c-multi", "main.c", id="c-multi"),
            pytest.param("cpp-simple", "main.cpp", id="cpp-simple"),
            pytest.param("cpp-multi", "main.cpp", id="cpp-multi"),
            pytest.param("py-empty", "nope.py", marks=pytest.mark.xfail, id="py-empty"),
            pytest.param("c-empty", "nope.c", marks=pytest.mark.xfail, id="c-empty"),
        ],
    )
    def test_blast_pretty(self, fixture_name: str, file_arg: str):
        path = fixture_path(fixture_name)
        result = runner.invoke(app, ["blast", file_arg, str(path)])
        plain = strip_ansi(result.output)
        assert result.exit_code == 0, f"Failed on {fixture_name}: {plain[:500]}"
        assert "Blast Radius" in plain

    @pytest.mark.parametrize(
        ("fixture_name", "file_arg"),
        [
            pytest.param("py-simple", "main.py", id="py-simple"),
            pytest.param("py-modules", "main.py", id="py-modules"),
            pytest.param("py-cli", "cli.py", id="py-cli"),
            pytest.param("py-with-deps", "a.py", id="py-with-deps"),
            pytest.param("c-simple", "main.c", id="c-simple"),
            pytest.param("c-multi", "main.c", id="c-multi"),
            pytest.param("cpp-simple", "main.cpp", id="cpp-simple"),
            pytest.param("cpp-multi", "main.cpp", id="cpp-multi"),
        ],
    )
    def test_blast_json(self, fixture_name: str, file_arg: str):
        path = fixture_path(fixture_name)
        result = runner.invoke(app, ["blast", file_arg, str(path), "--json"])
        assert result.exit_code == 0, f"Failed on {fixture_name}: {result.output[:300]}"
        parsed = json.loads(result.output)
        assert parsed["focus_file"] == file_arg

    def test_blast_nonexistent_dir(self):
        result = runner.invoke(app, ["blast", "x.py", "/nonexistent"])
        assert result.exit_code == 1
        assert "Error" in result.output


class TestValidate:
    """Validate command requires a patch file — tests with temp patches."""

    def test_validate_no_changes(self, tmp_path):
        (tmp_path / "main.py").write_text("x = 1")
        patch_file = tmp_path / "empty.patch"
        patch_file.write_text("")
        result = runner.invoke(app, ["validate", str(patch_file), str(tmp_path)])
        assert result.exit_code == 0
        assert "No changes detected" in strip_ansi(result.output)

    def test_validate_with_patch(self, tmp_path):
        (tmp_path / "main.py").write_text("x = 1")
        patch_file = tmp_path / "change.patch"
        patch_file.write_text(
            "--- a/main.py\n+++ b/main.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n"
        )
        result = runner.invoke(app, ["validate", str(patch_file), str(tmp_path)])
        plain = strip_ansi(result.output)
        assert result.exit_code == 0, f"Failed: {plain[:500]}"
        assert "Structural Analysis" in plain

    def test_validate_json(self, tmp_path):
        (tmp_path / "main.py").write_text("x = 1")
        patch_file = tmp_path / "change.patch"
        patch_file.write_text(
            "--- a/main.py\n+++ b/main.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n"
        )
        result = runner.invoke(app, ["validate", str(patch_file), str(tmp_path), "--json"])
        assert result.exit_code == 0, f"Failed: {result.output[:300]}"
        parsed = json.loads(result.output)
        assert "file_path" in parsed
        assert parsed["file_path"] == "main.py"
