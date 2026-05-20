"""Dependency Resolver - Tests for resolving raw imports to relative file paths."""

from archai.bootstrap.dependency_resolver import (
    _is_stdlib_module,
    _resolve_single_import,
    resolve_imports,
)
from archai.bootstrap.graph_builder import FileNode


class TestIsStdlibModule:
    """Tests for _is_stdlib_module() — identifies stdlib modules."""

    @staticmethod
    def test_is_stdlib_module_recognizes_os():
        assert _is_stdlib_module("os") is True

    @staticmethod
    def test_is_stdlib_module_recognizes_dotted_stdlib():
        assert _is_stdlib_module("os.path") is True

    @staticmethod
    def test_is_stdlib_module_rejects_non_stdlib():
        assert _is_stdlib_module("myapp") is False

    @staticmethod
    def test_is_stdlib_module_rejects_dotted_non_stdlib():
        assert _is_stdlib_module("myapp.models.user") is False

    @staticmethod
    def test_is_stdlib_module_with_empty_string():
        assert _is_stdlib_module("") is False


class TestResolveSingleImportStdlibAbsolute:
    """Tests for _resolve_single_import() — stdlib filtering + absolute imports."""

    @staticmethod
    def test_resolve_single_stdlib_returns_empty():
        assert _resolve_single_import("os", {}, {}) == ""

    @staticmethod
    def test_resolve_single_stdlib_dotted_returns_empty():
        assert _resolve_single_import("os.path", {}, {}) == ""

    @staticmethod
    def test_resolve_single_exact_module_match():
        files_by_module = {"utils.helpers": "utils/helpers.py"}
        result = _resolve_single_import("utils.helpers", {}, files_by_module)
        assert result == "utils/helpers.py"

    @staticmethod
    def test_resolve_single_partial_module_prefix():
        files_by_module = {"pkg_a": "src/pkg_a/__init__.py"}
        result = _resolve_single_import("pkg_a.utils", {}, files_by_module)
        assert result == "src/pkg_a/__init__.py"

    @staticmethod
    def test_resolve_single_module_most_specific_first():
        files_by_module = {
            "helpers": "shallow/helpers.py",
            "pkg_a.helpers": "deep/pkg_a/helpers.py",
        }
        result = _resolve_single_import("pkg_a.helpers", {}, files_by_module)
        assert result == "deep/pkg_a/helpers.py"

    @staticmethod
    def test_resolve_single_stem_fallback():
        files_by_stem = {"helper": "utils/helper.py"}
        files_by_module = {}
        result = _resolve_single_import("models.helper", files_by_stem, files_by_module)
        assert result == "utils/helper.py"

    @staticmethod
    def test_resolve_single_stem_fallback_reversed_order():
        files_by_stem = {"models": "other/models.py", "helper": "utils/helper.py"}
        files_by_module = {}
        result = _resolve_single_import("models.helper", files_by_stem, files_by_module)
        assert result == "utils/helper.py"

    @staticmethod
    def test_resolve_single_no_match_returns_empty():
        files_by_stem = {"existing": "path.py"}
        files_by_module = {"foo": "bar.py"}
        result = _resolve_single_import("nonexistent.module", files_by_stem, files_by_module)
        assert result == ""


class TestResolveSingleImportRelative:
    """Tests for _resolve_single_import() — relative import resolution."""

    @staticmethod
    def test_resolve_single_relative_with_importer_path():
        files_by_stem = {"module": "src/module.py"}
        result = _resolve_single_import(".module", files_by_stem, {}, "src/main.py")
        assert result == "src/module.py"

    @staticmethod
    def test_resolve_single_relative_without_importer_path():
        files_by_stem = {"other": "src/module.py"}
        result = _resolve_single_import(".module", files_by_stem, {})
        assert result == ""

    @staticmethod
    def test_resolve_single_multi_level_relative():
        files_by_stem = {"target": "target.py"}
        result = _resolve_single_import("...target", files_by_stem, {}, "a/b/c/main.py")
        assert result == "target.py"

    @staticmethod
    def test_resolve_single_relative_strategy1_exact_path():
        files_by_stem = {"user": "src/models/user.py"}
        result = _resolve_single_import(".models.user", files_by_stem, {}, "src/main.py")
        assert result == "src/models/user.py"

    @staticmethod
    def test_resolve_single_relative_strategy2_init_file():
        files_by_stem = {"dummy": "src/services/__init__.py"}
        result = _resolve_single_import(".services", files_by_stem, {}, "src/main.py")
        assert result == "src/services/__init__.py"

    @staticmethod
    def test_resolve_single_relative_strategy3_stem():
        files_by_stem = {"user": "other_pkg/user.py"}
        result = _resolve_single_import(".models.user", files_by_stem, {}, "src/main.py")
        assert result == "other_pkg/user.py"

    @staticmethod
    def test_resolve_single_relative_all_strategies_fail():
        result = _resolve_single_import(".nonexistent", {}, {}, "src/main.py")
        assert result == ""

    @staticmethod
    def test_resolve_single_relative_just_dots():
        result = _resolve_single_import("..", {}, {}, "src/services/main.py")
        assert result == "src/__init__.py"

    @staticmethod
    def test_resolve_single_relative_single_dot():
        result = _resolve_single_import(".", {}, {}, "src/services/main.py")
        assert result == "src/services/__init__.py"

    @staticmethod
    def test_resolve_single_relative_just_dots_no_importer():
        result = _resolve_single_import("..", {}, {})
        assert result == "__init__.py"


class TestResolveImports:
    """Tests for resolve_imports() — full resolution pipeline."""

    @staticmethod
    def test_resolve_imports_stem_prefers_shorter_path():
        nodes = [
            FileNode("deep/path/helper.py"),
            FileNode("helper.py"),
            FileNode("src/main.py", imports=["other_pkg.helper"]),
        ]
        resolved = resolve_imports(nodes)
        assert "helper.py" in resolved[2].imports

    @staticmethod
    def test_resolve_imports_module_from_regular_file():
        nodes = [
            FileNode("src/pkg_a/utils/helper.py"),
            FileNode("src/main.py", imports=["pkg_a.utils.helper"]),
        ]
        resolved = resolve_imports(nodes)
        assert "src/pkg_a/utils/helper.py" in resolved[1].imports

    @staticmethod
    def test_resolve_imports_module_from_init_file():
        nodes = [
            FileNode("src/pkg_a/__init__.py"),
            FileNode("src/main.py", imports=["pkg_a"]),
        ]
        resolved = resolve_imports(nodes)
        assert "src/pkg_a/__init__.py" in resolved[1].imports

    @staticmethod
    def test_resolve_imports_module_suffixes_for_regular_file():
        nodes = [
            FileNode("src/pkg_a/utils/helper.py"),
            FileNode("src/other.py", imports=["utils.helper"]),
        ]
        resolved = resolve_imports(nodes)
        assert "src/pkg_a/utils/helper.py" in resolved[1].imports

    @staticmethod
    def test_resolve_imports_keeps_path_in_nodes():
        nodes = [
            FileNode("src/main.py", imports=["utils.helpers"]),
            FileNode("utils/helpers.py"),
        ]
        resolved = resolve_imports(nodes)
        assert "utils/helpers.py" in resolved[0].imports

    @staticmethod
    def test_resolve_imports_filters_when_path_not_in_nodes():
        nodes = [
            FileNode("src/main.py", imports=["utils.helpers"]),
        ]
        resolved = resolve_imports(nodes)
        assert resolved[0].imports == []

    @staticmethod
    def test_resolve_imports_filters_stdlib():
        nodes = [
            FileNode("src/main.py", imports=["os", "sys", "json"]),
        ]
        resolved = resolve_imports(nodes)
        assert resolved[0].imports == []

    @staticmethod
    def test_resolve_imports_filters_mixed():
        nodes = [
            FileNode("src/main.py", imports=["os", "utils.helpers"]),
            FileNode("utils/helpers.py"),
        ]
        resolved = resolve_imports(nodes)
        assert resolved[0].imports == ["utils/helpers.py"]

    @staticmethod
    def test_resolve_imports_preserves_metadata():
        nodes = [
            FileNode(
                path="src/main.py",
                imports=["utils.helper"],
                functions=["run", "setup"],
                classes=["App"],
            ),
            FileNode("utils/helper.py"),
        ]
        resolved = resolve_imports(nodes)
        assert resolved[0].path == "src/main.py"
        assert resolved[0].functions == ["run", "setup"]
        assert resolved[0].classes == ["App"]

    @staticmethod
    def test_resolve_imports_end_to_end():
        nodes = [
            FileNode("pkg_a/main.py", imports=["pkg_b.helper", "os"]),
            FileNode("pkg_b/helper.py"),
        ]
        resolved = resolve_imports(nodes)
        assert resolved[0].imports == ["pkg_b/helper.py"]

    @staticmethod
    def test_resolve_imports_empty_list():
        assert resolve_imports([]) == []

    @staticmethod
    def test_resolve_imports_self_referencing_not_included():
        nodes = [
            FileNode("src/main.py", imports=["src.main"]),
        ]
        resolved = resolve_imports(nodes)
        assert resolved[0].imports == ["src/main.py"]

    @staticmethod
    def test_resolve_imports_with_init_importer():
        nodes = [
            FileNode("src/services/__init__.py", imports=[".sub.service"]),
            FileNode("src/services/sub/service.py"),
        ]
        resolved = resolve_imports(nodes)
        assert "src/services/sub/service.py" in resolved[0].imports
