"""AST Parsing - Test suite using PythonLangHandler protocol"""

import pytest
from pathlib import Path

from archai.bootstrap.python_handler import PythonLangHandler
from archai.bootstrap.language import ParsedFile


class TestAstParser:
    """Test suite for PythonLangHandler.parse()"""

    @staticmethod
    def create_python_file(tmp_path: Path, filename: str, content: str) -> Path:
        file_path = tmp_path / filename
        file_path.write_text(content)
        return file_path

    def test_parse_python_file_returns_ast(self, tmp_path: Path):
        file_content = "def hello(): pass\n"
        file_path = self.create_python_file(tmp_path, "simple.py", file_content)

        result = PythonLangHandler().parse(file_path)

        assert isinstance(result, ParsedFile)
        assert isinstance(result.path, str)
        assert result.language == "python"
        assert isinstance(result.imports, list)
        assert isinstance(result.functions, list)
        assert isinstance(result.classes, list)

    def test_parse_python_file_extracts_functions(self, tmp_path: Path):
        file_content = """
def hello():
    pass

def world():
    return 42

async def async_fetch():
    pass

async def async_process(data):
    return data
"""
        file_path = self.create_python_file(tmp_path, "functions.py", file_content)

        result = PythonLangHandler().parse(file_path)

        assert "hello" in result.functions
        assert "world" in result.functions
        assert "async_fetch" in result.functions
        assert "async_process" in result.functions

    def test_parse_python_file_extracts_classes(self, tmp_path: Path):
        file_content = """
class User:
    pass

class Admin(User):
    pass
"""
        file_path = self.create_python_file(tmp_path, "classes.py", file_content)

        result = PythonLangHandler().parse(file_path)

        assert "User" in result.classes
        assert "Admin" in result.classes

    def test_parse_python_file_extracts_imports(self, tmp_path: Path):
        file_content = """
import os
import sys
from pathlib import Path
from typing import List, Dict
"""
        file_path = self.create_python_file(tmp_path, "imports.py", file_content)

        result = PythonLangHandler().parse(file_path)

        assert "os" in result.imports
        assert "sys" in result.imports
        assert "pathlib.Path" in result.imports
        assert "typing.List" in result.imports
        assert "typing.Dict" in result.imports

    def test_parse_python_file_extracts_relative_imports(self, tmp_path: Path):
        file_content = """
from . import x
from .foo import bar
from .. import y
from ..sibling import func
from ...pkg import z
"""
        file_path = self.create_python_file(tmp_path, "relative_imports.py", file_content)

        result = PythonLangHandler().parse(file_path)

        assert ".x" in result.imports
        assert ".foo.bar" in result.imports
        assert "..y" in result.imports
        assert "..sibling.func" in result.imports
        assert "...pkg.z" in result.imports

    def test_parse_python_file_with_syntax_error(self, tmp_path: Path):
        file_content = "def broken(::):\n"
        file_path = self.create_python_file(tmp_path, "syntax_error.py", file_content)

        with pytest.raises(SyntaxError):
            PythonLangHandler().parse(file_path)

    def test_parse_empty_python_file(self, tmp_path: Path):
        file_content = ""
        file_path = self.create_python_file(tmp_path, "empty.py", file_content)

        result = PythonLangHandler().parse(file_path)

        assert isinstance(result, ParsedFile)
        assert result.functions == []
        assert result.classes == []
        assert result.imports == []

    def test_parse_file_with_comments_only(self, tmp_path: Path):
        file_content = "# This is a comment\n# Another comment\n"
        file_path = self.create_python_file(tmp_path, "comments.py", file_content)

        result = PythonLangHandler().parse(file_path)

        assert isinstance(result, ParsedFile)
        assert result.functions == []
        assert result.classes == []
        assert result.imports == []


class TestPythonLangHandlerIsProjectRoot:
    """Tests for PythonLangHandler.is_project_root()."""

    @staticmethod
    def test_is_project_root_with_pyproject_toml(tmp_path: Path):
        (tmp_path / "pyproject.toml").touch()
        assert PythonLangHandler().is_project_root(tmp_path) is True

    @staticmethod
    def test_is_project_root_with_setup_py(tmp_path: Path):
        (tmp_path / "setup.py").touch()
        assert PythonLangHandler().is_project_root(tmp_path) is True

    @staticmethod
    def test_is_project_root_with_setup_cfg(tmp_path: Path):
        (tmp_path / "setup.cfg").touch()
        assert PythonLangHandler().is_project_root(tmp_path) is True

    @staticmethod
    def test_is_project_root_empty(tmp_path: Path):
        assert PythonLangHandler().is_project_root(tmp_path) is False


class TestGetGlobalVars:
    """Tests for get_global_vars()"""

    def test_simple_assignment(self):
        import ast
        from archai.bootstrap.ast_parser import get_global_vars

        tree = ast.parse("DEBUG = True\nNAME = 'arch-ai'\nCOUNT = 42\nRATIO = 3.14\nITEMS = []\nDATA = None\n")
        result = get_global_vars(tree)

        names = {v["name"] for v in result}
        assert "DEBUG" in names
        assert "NAME" in names
        assert "COUNT" in names
        assert "RATIO" in names
        assert "ITEMS" in names
        assert "DATA" in names

        types = {v["name"]: v["type"] for v in result}
        assert types["DEBUG"] == "bool"
        assert types["NAME"] == "str"
        assert types["COUNT"] == "int"
        assert types["RATIO"] == "float"
        assert types["ITEMS"] == "list"
        assert types["DATA"] == "NoneType"

    def test_augmented_assignment(self):
        import ast
        from archai.bootstrap.ast_parser import get_global_vars

        tree = ast.parse("counter = 0\ncounter += 1\n")
        result = get_global_vars(tree)
        names = {v["name"] for v in result}
        assert "counter" in names
        assert len(result) == 2

    def test_annotated_assignment(self):
        import ast
        from archai.bootstrap.ast_parser import get_global_vars

        tree = ast.parse("x: int = 10\nname: str\nflag: bool = False\n")
        result = get_global_vars(tree)
        names = {v["name"] for v in result}
        assert "x" in names
        assert "name" in names
        assert "flag" in names
        assert len(result) == 3

    def test_multiple_targets(self):
        import ast
        from archai.bootstrap.ast_parser import get_global_vars

        tree = ast.parse("A = B = 0\n")
        result = get_global_vars(tree)
        names = [v["name"] for v in result]
        assert names == ["A", "B"]

    def test_skips_imports_and_defs(self):
        import ast
        from archai.bootstrap.ast_parser import get_global_vars

        tree = ast.parse("import os\nfrom sys import path\n\ndef func(): pass\n\nclass Klass: pass\n\nCONFIG = {}\n")
        result = get_global_vars(tree)
        names = {v["name"] for v in result}
        assert "CONFIG" in names
        assert "os" not in names
        assert "func" not in names
        assert "Klass" not in names

    def test_skips_if_name_eq_main(self):
        import ast
        from archai.bootstrap.ast_parser import get_global_vars

        tree = ast.parse(
            "CONFIG = {}\n"
            'if __name__ == "__main__":\n'
            "    VERBOSE = True\n"
        )
        result = get_global_vars(tree)
        names = {v["name"] for v in result}
        assert "CONFIG" in names
        assert "VERBOSE" not in names

    def test_skips_attribute_and_subscript_assignments(self):
        import ast
        from archai.bootstrap.ast_parser import get_global_vars

        tree = ast.parse(
            "obj.attr = 1\n"
            "items[0] = 2\n"
            "GLOBAL = 3\n"
        )
        result = get_global_vars(tree)
        names = {v["name"] for v in result}
        assert "GLOBAL" in names
        assert len(result) == 1

    def test_call_type_inference(self):
        import ast
        from archai.bootstrap.ast_parser import get_global_vars

        tree = ast.parse(
            "result = compute()\n"
            "data = get_data()\n"
        )
        result = get_global_vars(tree)
        types = {v["name"]: v["type"] for v in result}
        assert types["result"] == "compute"
        assert types["data"] == "get_data"

    def test_no_global_vars(self):
        import ast
        from archai.bootstrap.ast_parser import get_global_vars

        tree = ast.parse("def func(): pass\n")
        assert get_global_vars(tree) == []


class TestGetVarAccess:
    """Tests for get_var_access()"""

    def test_function_reads_global(self):
        import ast
        from archai.bootstrap.ast_parser import get_var_access

        tree = ast.parse(
            "DEBUG = True\n"
            "\n"
            "def log():\n"
            "    if DEBUG:\n"
            "        print('debug')\n"
        )
        result = get_var_access(tree)
        assert "log" in result
        assert len(result["log"]["reads"]) == 1
        assert result["log"]["reads"][0]["name"] == "DEBUG"
        assert result["log"]["writes"] == []

    def test_function_writes_global(self):
        import ast
        from archai.bootstrap.ast_parser import get_var_access

        tree = ast.parse(
            "counter = 0\n"
            "\n"
            "def increment():\n"
            "    global counter\n"
            "    counter = counter + 1\n"
        )
        result = get_var_access(tree)
        assert "increment" in result
        assert result["increment"]["writes"][0]["name"] == "counter"

    def test_function_writes_global_with_global_keyword(self):
        import ast
        from archai.bootstrap.ast_parser import get_var_access

        tree = ast.parse(
            "count = 0\n"
            "\n"
            "def update():\n"
            "    global count\n"
            "    count = get_count()\n"
        )
        result = get_var_access(tree)
        assert "update" in result
        write_names = {w["name"] for w in result["update"]["writes"]}
        assert "count" in write_names

    def test_ignores_local_vars_and_params(self):
        import ast
        from archai.bootstrap.ast_parser import get_var_access

        tree = ast.parse(
            "def process(data):\n"
            "    result = data + 1\n"
            "    return result\n"
        )
        result = get_var_access(tree)
        assert "process" not in result or (
            result["process"]["reads"] == [] and result["process"]["writes"] == []
        )

    def test_augmented_assignment(self):
        import ast
        from archai.bootstrap.ast_parser import get_var_access

        tree = ast.parse(
            "total = 0\n"
            "\n"
            "def add():\n"
            "    global total\n"
            "    total += 1\n"
        )
        result = get_var_access(tree)
        assert "add" in result
        assert any(w["name"] == "total" for w in result["add"]["writes"])
        assert any(r["name"] == "total" for r in result["add"]["reads"])

    def test_multiple_functions(self):
        import ast
        from archai.bootstrap.ast_parser import get_var_access

        tree = ast.parse(
            "DEBUG = True\n"
            "counter = 0\n"
            "\n"
            "def log():\n"
            "    if DEBUG:\n"
            "        print('x')\n"
            "\n"
            "def inc():\n"
            "    global counter\n"
            "    counter += 1\n"
        )
        result = get_var_access(tree)
        assert "log" in result
        assert "inc" in result
        assert result["log"]["reads"][0]["name"] == "DEBUG"
        assert result["inc"]["writes"][0]["name"] == "counter"


class TestParsePopulatesStateFields:
    """Tests that PythonLangHandler.parse() populates global_vars and var_access"""

    def test_parse_global_vars_populated(self, tmp_path):
        file_content = "DEBUG = True\nTIMEOUT = 30\n"
        file_path = tmp_path / "settings.py"
        file_path.write_text(file_content)

        result = PythonLangHandler().parse(file_path)

        assert len(result.global_vars) == 2
        names = {v["name"] for v in result.global_vars}
        assert "DEBUG" in names
        assert "TIMEOUT" in names

    def test_parse_var_access_populated(self, tmp_path):
        file_content = (
            "DEBUG = True\n"
            "\n"
            "def run():\n"
            "    if DEBUG:\n"
            "        print('running')\n"
        )
        file_path = tmp_path / "runner.py"
        file_path.write_text(file_content)

        result = PythonLangHandler().parse(file_path)

        assert "run" in result.var_access
        assert len(result.var_access["run"]["reads"]) == 1
        assert result.var_access["run"]["reads"][0]["name"] == "DEBUG"

    def test_parse_populated_defaults_for_clean_file(self, tmp_path):
        file_content = "def foo(): pass\n"
        file_path = tmp_path / "clean.py"
        file_path.write_text(file_content)

        result = PythonLangHandler().parse(file_path)

        assert result.global_vars == []
        assert result.var_access == {}
