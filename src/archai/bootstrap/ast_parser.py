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


import builtins

BUILTINS: frozenset[str] = frozenset(dir(builtins))


def _is_name_eq_main(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and isinstance(node.test.left, ast.Name)
        and node.test.left.id == "__name__"
        and len(node.test.ops) == 1
        and isinstance(node.test.ops[0], ast.Eq)
        and len(node.test.comparators) == 1
        and isinstance(node.test.comparators[0], ast.Constant)
        and node.test.comparators[0].value == "__main__"
    )


def _infer_type(node: ast.AST) -> str:
    if isinstance(node, ast.Constant):
        if node.value is None:
            return "NoneType"
        if isinstance(node.value, bool):
            return "bool"
        if isinstance(node.value, str):
            return "str"
        if isinstance(node.value, int):
            return "int"
        if isinstance(node.value, float):
            return "float"
    elif isinstance(node, ast.List):
        return "list"
    elif isinstance(node, ast.Set):
        return "set"
    elif isinstance(node, ast.Dict):
        return "dict"
    elif isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name):
            return node.func.id
        return "Unknown"
    return "Unknown"


def _collect_global_assignments(stmt: ast.AST, results: list[dict]) -> None:
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom)):
        return

    if isinstance(stmt, ast.If) and _is_name_eq_main(stmt):
        return

    if isinstance(stmt, ast.Assign):
        for target in stmt.targets:
            if isinstance(target, ast.Name):
                results.append({
                    "name": target.id,
                    "type": _infer_type(stmt.value),
                    "line": stmt.lineno,
                })
    elif isinstance(stmt, ast.AnnAssign):
        if isinstance(stmt.target, ast.Name):
            inferred: str = "Unknown"
            if stmt.value:
                inferred = _infer_type(stmt.value)
            elif isinstance(stmt.annotation, ast.Name):
                inferred = stmt.annotation.id
            results.append({
                "name": stmt.target.id,
                "type": inferred,
                "line": stmt.lineno,
            })
    elif isinstance(stmt, ast.AugAssign):
        if isinstance(stmt.target, ast.Name):
            results.append({
                "name": stmt.target.id,
                "type": _infer_type(stmt.value),
                "line": stmt.lineno,
            })
    else:
        for child in ast.iter_child_nodes(stmt):
            _collect_global_assignments(child, results)


def get_global_vars(tree: ast.AST) -> list[dict]:
    results: list[dict] = []
    for stmt in ast.iter_child_nodes(tree):
        _collect_global_assignments(stmt, results)
    return results


def _get_func_local_names(func_node: ast.FunctionDef) -> set[str]:
    local_names: set[str] = set()

    for arg in func_node.args.args:
        local_names.add(arg.arg)
    for arg in func_node.args.posonlyargs:
        local_names.add(arg.arg)
    for arg in func_node.args.kwonlyargs:
        local_names.add(arg.arg)
    if func_node.args.vararg:
        local_names.add(func_node.args.vararg.arg)
    if func_node.args.kwarg:
        local_names.add(func_node.args.kwarg.arg)

    global_names: set[str] = set()

    def _collect_globals(node: ast.AST) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return
        if isinstance(node, ast.Global):
            global_names.update(node.names)
        for child in ast.iter_child_nodes(node):
            _collect_globals(child)

    def _walk(node: ast.AST) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            if node.id not in global_names:
                local_names.add(node.id)
        for child in ast.iter_child_nodes(node):
            _walk(child)

    for child in ast.iter_child_nodes(func_node):
        _collect_globals(child)
    for child in ast.iter_child_nodes(func_node):
        _walk(child)
    return local_names


def _walk_body(node: ast.AST):
    stack: list[ast.AST] = [node]
    while stack:
        current = stack.pop()
        for child in ast.iter_child_nodes(current):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            yield child
            stack.append(child)


def get_var_access(tree: ast.AST) -> dict[str, dict]:
    var_access: dict[str, dict] = {}

    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        fn_name = node.name
        local_names = _get_func_local_names(node)

        reads: list[dict] = []
        writes: list[dict] = []
        seen_reads: set[str] = set()
        seen_writes: set[str] = set()

        for child in _walk_body(node):
            if isinstance(child, ast.AugAssign) and isinstance(child.target, ast.Name):
                name = child.target.id
                if name in local_names or name in BUILTINS:
                    continue
                if name not in seen_writes:
                    writes.append({"name": name, "line": child.lineno})
                    seen_writes.add(name)
                if name not in seen_reads:
                    reads.append({"name": name, "line": child.lineno})
                    seen_reads.add(name)
                continue

            if not isinstance(child, ast.Name):
                continue

            name = child.id
            if name in local_names or name in BUILTINS:
                continue

            if isinstance(child.ctx, ast.Store):
                if name not in seen_writes:
                    writes.append({"name": name, "line": child.lineno})
                    seen_writes.add(name)
            elif isinstance(child.ctx, ast.Load):
                if name not in seen_reads:
                    reads.append({"name": name, "line": child.lineno})
                    seen_reads.add(name)

        if reads or writes:
            var_access[fn_name] = {"writes": writes, "reads": reads}

    return var_access
