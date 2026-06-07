"""C/C++ Language Handler - Parses C and C++ files using tree-sitter.

Handles:
- C: .c, .h files
- C++: .cpp, .hpp, .cc, .cxx, .hh files
- Include resolution: local (#include "file.h") vs system (#include <file.h>)
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import tree_sitter

from archai.bootstrap.language import (
    FunctionInfo,
    ParsedFile,
    SHARED_EXCLUDED_DIRS,
    register_handler,
)

if TYPE_CHECKING:
    from tree_sitter import Node

_INCLUDE_QUERY = """
[
  (preproc_include (string_literal) @include)
  (preproc_include (system_lib_string) @include)
]
"""

_FUNCTION_QUERY = """
(function_definition) @function
"""

_CALL_QUERY = """
(call_expression function: (identifier) @call)
"""


def _get_c_parser() -> Any:
    try:
        from tree_sitter_c import language  # type: ignore[import-not-found]
    except ImportError:
        raise ImportError(
            "tree-sitter-c is not installed. Run: pip install archai-mcp[c]"
        ) from None

    # Must create Language AFTER C++ was created (see _get_cpp_parser)
    return tree_sitter.Parser(tree_sitter.Language(language()))


def _get_cpp_parser() -> Any:
    try:
        from tree_sitter_cpp import language  # type: ignore[import-not-found]
    except ImportError:
        raise ImportError(
            "tree-sitter-cpp is not installed. Run: pip install archai-mcp[cpp]"
        ) from None

    return tree_sitter.Parser(tree_sitter.Language(language()))


def _query_captures(root_node: Node, query_str: str, lang: Any) -> dict[str, list[Node]]:
    query = tree_sitter.Query(lang, query_str)
    cursor = tree_sitter.QueryCursor(query)
    return cursor.captures(root_node)


def _find_first_name_node(node: Node) -> str | None:
    """Walk the AST subtree to find the first function/method name.

    Handles regular identifiers (function names), field_identifiers (class methods),
    and qualified identifiers (namespaced functions).
    """
    if node.type in ("identifier", "field_identifier"):
        text = node.text
        if text is not None:
            return text.decode("utf-8")
    if node.type == "qualified_identifier":
        name_node = node.child_by_field_name("name")
        if name_node is not None:
            text = name_node.text
            if text is not None:
                return text.decode("utf-8")
    for child in node.children:
        result = _find_first_name_node(child)
        if result is not None:
            return result
    return None


# Cache the simple walk to avoid repeated traversal
_extract_function_name = _find_first_name_node


def _extract_classes_from_tree(root_node: Node) -> list[str]:
    """Extract class/struct names by walking the AST tree directly.

    Uses tree walking instead of tree-sitter queries to avoid cross-grammar
    compatibility issues when both C and C++ grammars are loaded in the same process.
    """
    classes: list[str] = []

    def walk(node: Node) -> None:
        if node.type in ("class_specifier", "struct_specifier"):
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                text = name_node.text
                if text is not None:
                    classes.append(text.decode("utf-8"))
        for child in node.children:
            walk(child)

    walk(root_node)
    return classes


def _extract_function_calls(function_node: Node, query_lang: Any) -> list[str]:
    """Extract function names called within a function definition.

    Uses tree-sitter query to find call_expression nodes and extracts
    the function name from each call.

    Args:
        function_node: The function_definition AST node.
        query_lang: The tree-sitter Language object for query creation.

    Returns:
        List of called function name strings.
    """
    query = tree_sitter.Query(query_lang, _CALL_QUERY)
    cursor = tree_sitter.QueryCursor(query)
    calls = cursor.captures(function_node)
    result: list[str] = []
    for node in calls.get("call", []):
        text = node.text
        if text is not None:
            name = text.decode("utf-8")
            if name and name not in result:
                result.append(name)
    return result


def _do_parse(file: Path, parser: Any, language_name: str = "") -> ParsedFile:
    source = file.read_text("utf-8")
    tree = parser.parse(bytes(source, "utf-8"))
    root_node = tree.root_node
    lang = parser.language

    includes = _query_captures(root_node, _INCLUDE_QUERY, lang)
    imports: list[str] = []
    for node in includes.get("include", []):
        text = node.text
        if text is not None:
            imports.append(text.decode("utf-8"))

    funcs = _query_captures(root_node, _FUNCTION_QUERY, lang)
    functions: list[str] = []
    functions_detail: list[FunctionInfo] = []
    # Build set of all function names in this file for categorizing calls
    all_func_names: set[str] = set()

    # First pass: extract all function names
    for node in funcs.get("function", []):
        name = _extract_function_name(node)
        if name:
            all_func_names.add(name)

    # Second pass: extract calls per function
    for node in funcs.get("function", []):
        name = _extract_function_name(node)
        if not name:
            continue
        functions.append(name)
        called = _extract_function_calls(node, lang)
        internal = [c for c in called if c in all_func_names]
        external = [c for c in called if c not in all_func_names]
        line = node.start_point[0] + 1 if hasattr(node, "start_point") else 0
        functions_detail.append(
            FunctionInfo(
                name=name,
                line=line,
                calls_internal=internal,
                calls_external=external,
            )
        )

    classes: list[str] = []
    # Extract struct/class for both C and C++ (struct_specifier works for C too)
    classes = _extract_classes_from_tree(root_node)

    return ParsedFile(
        path=str(file),
        imports=imports,
        functions=functions,
        functions_detail=functions_detail,
        classes=classes,
        language="",
    )


def _resolve_include(
    include_name: str,
    file_path: str,
    all_files: set[str],
    project_root: Path,
) -> str | None:
    if include_name.startswith("<"):
        return "external"

    path = include_name.strip("\"'")
    file_dir = Path(file_path).parent
    candidate = file_dir / path

    if str(candidate) in all_files:
        return str(candidate)

    for f in all_files:
        if f.endswith("/" + path) or f == path:
            return f

    return None


@register_handler  # type: ignore[arg-type]
class CLangHandler:
    language = "c"
    extensions = frozenset({".c"})
    project_files = (
        "Makefile",
        "CMakeLists.txt",
        ".clang-format",
        "compile_commands.json",
        "Kbuild",
    )
    excluded_dirs = SHARED_EXCLUDED_DIRS

    def is_project_root(self, path: Path) -> bool:
        return any((path / pf).exists() for pf in self.project_files)

    def parse(self, file: Path) -> ParsedFile:
        parser = _get_c_parser()
        result = _do_parse(file, parser, language_name=self.language)
        result.language = self.language
        return result

    def resolve_import(
        self,
        import_name: str,
        file_path: str,
        all_files: set[str],
        project_root: Path,
    ) -> str | None:
        return _resolve_include(import_name, file_path, all_files, project_root)


@register_handler  # type: ignore[arg-type]
class CppLangHandler:
    language = "cpp"
    extensions = frozenset({".cpp", ".hpp", ".cc", ".cxx", ".hh", ".h"})
    project_files = (
        "Makefile",
        "CMakeLists.txt",
        ".clang-format",
        "compile_commands.json",
    )
    excluded_dirs = SHARED_EXCLUDED_DIRS

    def is_project_root(self, path: Path) -> bool:
        return any((path / pf).exists() for pf in self.project_files)

    def parse(self, file: Path) -> ParsedFile:
        parser = _get_cpp_parser()
        result = _do_parse(file, parser, language_name=self.language)
        result.language = self.language
        return result

    def resolve_import(
        self,
        import_name: str,
        file_path: str,
        all_files: set[str],
        project_root: Path,
    ) -> str | None:
        return _resolve_include(import_name, file_path, all_files, project_root)
