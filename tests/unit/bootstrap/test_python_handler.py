"""PythonLangHandler - Tests for state analysis fields (global_vars, var_access)."""

from pathlib import Path

from archai.bootstrap.language import ParsedFile
from archai.bootstrap.python_handler import PythonLangHandler


class TestPythonHandlerStateFields:
    """Verifies PythonLangHandler.parse() populates global_vars and var_access."""

    def test_global_vars_and_var_access_populated(self, tmp_path: Path):
        file_content = (
            "DEBUG = True\n"
            "TIMEOUT = 30\n"
            "\n"
            "def run():\n"
            "    global DEBUG\n"
            "    if DEBUG:\n"
            "        print('running')\n"
            "\n"
            "def reset():\n"
            "    global TIMEOUT\n"
            "    TIMEOUT = 60\n"
        )
        file_path = tmp_path / "settings.py"
        file_path.write_text(file_content)

        result = PythonLangHandler().parse(file_path)

        assert isinstance(result, ParsedFile)
        assert len(result.global_vars) == 2
        gv_names = {g["name"] for g in result.global_vars}
        gv_types = {g["name"]: g["type"] for g in result.global_vars}
        assert "DEBUG" in gv_names
        assert "TIMEOUT" in gv_names
        assert gv_types["DEBUG"] == "bool"
        assert gv_types["TIMEOUT"] == "int"

        assert "run" in result.var_access
        assert "reset" in result.var_access
        assert any(
            r["name"] == "DEBUG" for r in result.var_access["run"]["reads"]
        )
        assert any(
            w["name"] == "TIMEOUT" for w in result.var_access["reset"]["writes"]
        )

    def test_no_globals_in_clean_file(self, tmp_path: Path):
        file_content = (
            "import os\n"
            "from sys import path\n"
            "\n"
            "def util():\n"
            "    x = 1\n"
            "    return x\n"
        )
        file_path = tmp_path / "clean.py"
        file_path.write_text(file_content)

        result = PythonLangHandler().parse(file_path)

        assert result.global_vars == []
        assert result.var_access == {}
