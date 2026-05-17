"""AST Parser - Parse Python files using standard library ast module.

Note: This implementation uses Python's built-in ast module for reliability.
Future versions can integrate tree-sitter for faster parsing and multi-language support.
"""

import ast
import tokenize
from pathlib import Path


def parse_python_file(file_path: Path) -> ast.AST:
    """
    Parses a Python file and returns its AST using the standard library.

    Args:
        file_path: Path to the Python file.

    Returns:
        An ast.AST object representing the parsed file.

    Raises:
        SyntaxError: If the file contains invalid Python syntax.
        FileNotFoundError: If the file does not exist.
    """
    with tokenize.open(file_path) as f:
        code = f.read()
    if not code.strip():
        # Return an empty Module for empty files
        return ast.Module(body=[], type_ignores=[])

    return ast.parse(code, filename=str(file_path))


def get_imports(tree: ast.AST) -> list[str]:
    """
    Extracts all import statements from an AST.

    Args:
        tree: The parsed AST tree.

    Returns:
        List of imported module/component names.
    """
    imports = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            rel_prefix = "." * node.level
            for alias in node.names:
                if node.module:
                    imports.append(f"{rel_prefix}{node.module}.{alias.name}")
                else:
                    imports.append(f"{rel_prefix}{alias.name}")

    return imports


def get_functions(tree: ast.AST) -> list[str]:
    """
    Extracts all function definitions from an AST.

    Args:
        tree: The parsed AST tree.

    Returns:
        List of function names.
    """
    functions = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(node.name)

    return functions


def get_classes(tree: ast.AST) -> list[str]:
    """
    Extracts all class definitions from an AST.

    Args:
        tree: The parsed AST tree.

    Returns:
        List of class names.
    """
    classes = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            classes.append(node.name)

    return classes
