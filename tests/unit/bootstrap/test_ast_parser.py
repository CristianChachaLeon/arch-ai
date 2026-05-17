"""AST Parsing - Test suite using Python's ast module"""

import pytest
from pathlib import Path
import ast as py_ast

from archai.bootstrap.ast_parser import parse_python_file, get_imports, get_functions, get_classes


class TestAstParser:
    """Test suite for ast_parser module"""

    @staticmethod
    def create_python_file(tmp_path: Path, filename: str, content: str) -> Path:
        """Helper to create a Python file in temp directory."""
        file_path = tmp_path / filename
        file_path.write_text(content)
        return file_path

    def test_parse_python_file_returns_ast(self, tmp_path: Path):
        """Should parse a valid Python file and return an AST object."""
        # Arrange
        file_content = "def hello(): pass\n"
        file_path = self.create_python_file(tmp_path, "simple.py", file_content)

        # Act
        tree = parse_python_file(file_path)

        # Assert
        assert isinstance(tree, py_ast.AST)
        assert isinstance(tree, py_ast.Module)

    def test_parse_python_file_extracts_functions(self, tmp_path: Path):
        """Should extract function definitions from the AST, including async functions."""
        # Arrange
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

        # Act
        tree = parse_python_file(file_path)
        functions = get_functions(tree)

        # Assert
        assert "hello" in functions
        assert "world" in functions
        assert "async_fetch" in functions
        assert "async_process" in functions

    def test_parse_python_file_extracts_classes(self, tmp_path: Path):
        """Should extract class definitions from the AST."""
        # Arrange
        file_content = """
class User:
    pass

class Admin(User):
    pass
"""
        file_path = self.create_python_file(tmp_path, "classes.py", file_content)

        # Act
        tree = parse_python_file(file_path)
        classes = get_classes(tree)

        # Assert
        assert "User" in classes
        assert "Admin" in classes

    def test_parse_python_file_extracts_imports(self, tmp_path: Path):
        """Should extract import statements from the AST."""
        # Arrange
        file_content = """
import os
import sys
from pathlib import Path
from typing import List, Dict
"""
        file_path = self.create_python_file(tmp_path, "imports.py", file_content)

        # Act
        tree = parse_python_file(file_path)
        imports = get_imports(tree)

        # Assert
        assert "os" in imports
        assert "sys" in imports
        assert "pathlib.Path" in imports
        assert "typing.List" in imports
        assert "typing.Dict" in imports

    def test_parse_python_file_extracts_relative_imports(self, tmp_path: Path):
        """Should extract relative import statements with correct prefix dots."""
        # Arrange
        file_content = """
from . import x
from .foo import bar
from .. import y
from ..sibling import func
from ...pkg import z
"""
        file_path = self.create_python_file(tmp_path, "relative_imports.py", file_content)

        # Act
        tree = parse_python_file(file_path)
        imports = get_imports(tree)

        # Assert - verify relative import depth is preserved
        assert ".x" in imports
        assert ".foo.bar" in imports
        assert "..y" in imports
        assert "..sibling.func" in imports
        assert "...pkg.z" in imports

    def test_parse_python_file_with_syntax_error(self, tmp_path: Path):
        """Should raise SyntaxError for invalid Python code."""
        # Arrange
        file_content = "def broken(::):\n"
        file_path = self.create_python_file(tmp_path, "syntax_error.py", file_content)

        # Act & Assert
        with pytest.raises(SyntaxError):
            parse_python_file(file_path)

    def test_parse_empty_python_file(self, tmp_path: Path):
        """Should parse an empty Python file without error."""
        # Arrange
        file_content = ""
        file_path = self.create_python_file(tmp_path, "empty.py", file_content)

        # Act
        tree = parse_python_file(file_path)

        # Assert
        assert isinstance(tree, py_ast.Module)
        assert tree.body == []

    def test_parse_file_with_comments_only(self, tmp_path: Path):
        """Should parse a Python file with only comments."""
        # Arrange
        file_content = "# This is a comment\n# Another comment\n"
        file_path = self.create_python_file(tmp_path, "comments.py", file_content)

        # Act
        tree = parse_python_file(file_path)

        # Assert
        assert isinstance(tree, py_ast.Module)
        # Comments are not part of the AST body
        assert tree.body == []
