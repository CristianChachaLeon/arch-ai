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


def _extract_file_scope_vars(root_node: Node, lang: Any) -> list[dict]:
    """Extract file-scope (global) variable declarations from C/C++ files.

    Walks direct children of translation_unit to find declarations
    at file scope (not inside functions or blocks).

    Returns:
        list of dicts with keys: name, line, is_static
    """
    vars_found: list[dict] = []

    def is_function_decl(node: Node) -> bool:
        """Check if a declaration node is actually a function declaration."""
        for child in node.children:
            if child.type == "function_declarator":
                return True
            # Recurse into nested declarators (pointer, etc.)
            if is_function_decl(child):
                return True
        return False

    for child in root_node.children:
        if child.type != "declaration":
            continue

        if is_function_decl(child):
            continue

        # Check for 'static' storage class
        is_static = False
        for c in child.children:
            if c.type == "storage_class_specifier":
                text = c.text
                if text is not None and text.decode("utf-8") == "static":
                    is_static = True
                    break

        # Find variable names in this declaration
        # Handles: "int cfg;", "int cfg = 0;", "char buf[256];", "int *ptr;"
        def find_var_names(node: Node) -> list[tuple[Node, str]]:
            """Find (line_node, name) pairs from a declaration node."""
            result: list[tuple[Node, str]] = []
            for c in node.children:
                if c.type == "init_declarator":
                    decl_name = c.child_by_field_name("declarator")
                    if decl_name is not None:
                        name = _find_first_name_node(decl_name)
                        if name:
                            result.append((c, name))
                elif c.type in ("identifier",):
                    text = c.text
                    if text is not None:
                        name = text.decode("utf-8")
                        _SKIP_TYPES = frozenset(
                            {
                                "int",
                                "char",
                                "void",
                                "float",
                                "double",
                                "long",
                                "short",
                                "unsigned",
                                "signed",
                                "const",
                                "static",
                                "extern",
                                "volatile",
                                "auto",
                                "register",
                            }
                        )
                        if name and name not in _SKIP_TYPES:
                            result.append((c, name))
                elif c.type in ("array_declarator", "pointer_declarator"):
                    name = _find_first_name_node(c)
                    if name:
                        result.append((c, name))
            return result

        for line_node, name in find_var_names(child):
            if name not in [v["name"] for v in vars_found]:
                line = line_node.start_point[0] + 1 if hasattr(line_node, "start_point") else 0
                vars_found.append(
                    {
                        "name": name,
                        "line": line,
                        "is_static": is_static,
                    }
                )

    return vars_found


def _extract_var_access(
    func_node: Node,
    lang: Any,
    global_names: set[str],
) -> tuple[list[dict], list[dict]]:
    """Extract which global variables a function reads and writes.

    Args:
        func_node: Function definition AST node
        lang: tree-sitter Language object
        global_names: Set of known global variable names

    Returns:
        Tuple of (writes, reads) where each is a list of
        dicts with keys: name, line
    """
    writes: list[dict] = []
    reads: list[dict] = []

    # Find assignment targets via tree-sitter query
    assign_query = """
    (assignment_expression
      left: (identifier) @target
    )
    """
    try:
        query = tree_sitter.Query(lang, assign_query)
        cursor = tree_sitter.QueryCursor(query)
        assigns = cursor.captures(func_node)
    except Exception:
        assigns = {}

    written_vars: set[str] = set()
    for node in assigns.get("target", []):
        text = node.text
        if text is None:
            continue
        name = text.decode("utf-8")
        if name in global_names and name not in written_vars:
            written_vars.add(name)
            line = node.start_point[0] + 1 if hasattr(node, "start_point") else 0
            writes.append({"name": name, "line": line})

    # Walk the function body for identifier references
    seen: set[str] = set()

    def walk_identifiers(node: Node, depth: int = 0) -> None:
        if depth > 30:
            return
        if node.type == "identifier":
            text = node.text
            if text is not None:
                name = text.decode("utf-8")
                if name in global_names and name not in seen:
                    seen.add(name)
                    if name in written_vars:
                        # Already counted as a write, but also track as read
                        # if there's a non-assignment reference
                        pass
                    else:
                        line = node.start_point[0] + 1 if hasattr(node, "start_point") else 0
                        reads.append({"name": name, "line": line})
        for child in node.children:
            walk_identifiers(child, depth + 1)

    walk_identifiers(func_node)

    return writes, reads


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

    # Extract struct/class for both C and C++ (struct_specifier works for C too)
    classes = _extract_classes_from_tree(root_node)

    # Extract global variable declarations (file-scope)
    global_vars: list[dict] = []
    if language_name in ("c", "cpp"):
        global_vars = _extract_file_scope_vars(root_node, lang)

    global_names = {g["name"] for g in global_vars}
    var_access: dict[str, dict] = {}

    # Second pass: extract calls AND variable access per function
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

        if global_names:
            writes, reads = _extract_var_access(node, lang, global_names)
            if writes or reads:
                var_access[name] = {"writes": writes, "reads": reads}

    return ParsedFile(
        path=str(file),
        imports=imports,
        functions=functions,
        functions_detail=functions_detail,
        classes=classes,
        language="",
        global_vars=global_vars,
        var_access=var_access,
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
