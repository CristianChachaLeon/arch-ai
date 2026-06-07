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
