"""Dependency Resolver - Tests for PythonLangHandler.resolve_import()."""

from pathlib import Path

from archai.bootstrap.python_handler import PythonLangHandler


def _handler():
    return PythonLangHandler()


class TestStdlibFiltering:
    """Tests that stdlib modules return None from resolve_import()."""

    @staticmethod
    def test_resolve_stdlib_os():
        assert _handler().resolve_import("os", "main.py", set(), Path("/root")) is None

    @staticmethod
    def test_resolve_stdlib_dotted_path():
        assert _handler().resolve_import("os.path", "main.py", set(), Path("/root")) is None

    @staticmethod
    def test_resolve_non_stdlib_with_no_match():
        assert _handler().resolve_import("myapp", "main.py", {"main.py"}, Path("/root")) is None

    @staticmethod
    def test_resolve_non_stdlib_dotted_with_no_match():
        assert (
            _handler().resolve_import("myapp.models.user", "main.py", {"main.py"}, Path("/root"))
            is None
        )

    @staticmethod
    def test_resolve_empty_string():
        assert _handler().resolve_import("", "main.py", set(), Path("/root")) is None


class TestResolveAbsoluteImport:
    """Tests for resolve_import() — absolute import resolution."""

    @staticmethod
    def test_resolve_exact_module_match():
        handler = _handler()
        all_files = {"utils/helpers.py", "main.py"}
        result = handler.resolve_import("utils.helpers", "main.py", all_files, Path("/root"))
        assert result == "utils/helpers.py"

    @staticmethod
    def test_resolve_partial_module_prefix():
        handler = _handler()
        all_files = {"src/pkg_a/__init__.py", "main.py"}
        result = handler.resolve_import("pkg_a.utils", "main.py", all_files, Path("/root"))
        assert result == "src/pkg_a/__init__.py"

    @staticmethod
    def test_resolve_module_most_specific_first():
        handler = _handler()
        all_files = {"shallow/helpers.py", "deep/pkg_a/helpers.py", "main.py"}
        result = handler.resolve_import("pkg_a.helpers", "main.py", all_files, Path("/root"))
        assert result == "deep/pkg_a/helpers.py"

    @staticmethod
    def test_resolve_stem_fallback():
        handler = _handler()
        all_files = {"utils/helper.py", "main.py"}
        result = handler.resolve_import("models.helper", "main.py", all_files, Path("/root"))
        assert result == "utils/helper.py"

    @staticmethod
    def test_resolve_stem_fallback_reversed_order():
        handler = _handler()
        all_files = {"other/models.py", "utils/helper.py", "main.py"}
        result = handler.resolve_import("models.helper", "main.py", all_files, Path("/root"))
        assert result == "other/models.py"

    @staticmethod
    def test_resolve_no_match_returns_none():
        handler = _handler()
        all_files = {"path.py", "main.py"}
        result = handler.resolve_import("nonexistent.module", "main.py", all_files, Path("/root"))
        assert result is None


class TestResolveRelativeImport:
    """Tests for resolve_import() — relative import resolution."""

    @staticmethod
    def test_resolve_relative_with_importer_path():
        handler = _handler()
        all_files = {"src/module.py", "src/main.py"}
        result = handler.resolve_import(".module", "src/main.py", all_files, Path("/root"))
        assert result == "src/module.py"

    @staticmethod
    def test_resolve_relative_without_matching_target():
        handler = _handler()
        all_files = {"src/main.py"}
        result = handler.resolve_import(".module", "src/main.py", all_files, Path("/root"))
        assert result is None

    @staticmethod
    def test_resolve_multi_level_relative():
        handler = _handler()
        all_files = {"target.py", "a/b/c/main.py"}
        result = handler.resolve_import("...target", "a/b/c/main.py", all_files, Path("/root"))
        assert result == "target.py"

    @staticmethod
    def test_resolve_relative_strategy1_exact_path():
        handler = _handler()
        all_files = {"src/models/user.py", "src/main.py"}
        result = handler.resolve_import(".models.user", "src/main.py", all_files, Path("/root"))
        assert result == "src/models/user.py"

    @staticmethod
    def test_resolve_relative_strategy2_init_file():
        handler = _handler()
        all_files = {"src/services/__init__.py", "src/main.py"}
        result = handler.resolve_import(".services", "src/main.py", all_files, Path("/root"))
        assert result == "src/services/__init__.py"

    @staticmethod
    def test_resolve_relative_strategy3_stem():
        handler = _handler()
        all_files = {"other_pkg/user.py", "src/main.py"}
        result = handler.resolve_import(".models.user", "src/main.py", all_files, Path("/root"))
        assert result == "other_pkg/user.py"

    @staticmethod
    def test_resolve_relative_all_strategies_fail():
        handler = _handler()
        all_files = {"src/main.py"}
        result = handler.resolve_import(".nonexistent", "src/main.py", all_files, Path("/root"))
        assert result is None

    @staticmethod
    def test_resolve_relative_just_double_dots():
        handler = _handler()
        all_files = {"src/__init__.py", "src/services/main.py"}
        result = handler.resolve_import("..", "src/services/main.py", all_files, Path("/root"))
        assert result == "src/__init__.py"

    @staticmethod
    def test_resolve_relative_single_dot():
        handler = _handler()
        all_files = {"src/services/__init__.py", "src/services/main.py"}
        result = handler.resolve_import(".", "src/services/main.py", all_files, Path("/root"))
        assert result == "src/services/__init__.py"

    @staticmethod
    def test_resolve_relative_just_dots_no_init_in_files():
        handler = _handler()
        all_files = {"src/services/main.py"}
        result = handler.resolve_import("..", "src/services/main.py", all_files, Path("/root"))
        assert result is None


class TestResolveSingleImport:
    """Tests covering the full resolution behavior via resolve_import()."""

    @staticmethod
    def test_stem_prefers_shorter_path():
        handler = _handler()
        all_files = {"deep/path/helper.py", "helper.py", "src/main.py"}
        result = handler.resolve_import("other_pkg.helper", "src/main.py", all_files, Path("/root"))
        assert result == "helper.py"

    @staticmethod
    def test_module_from_regular_file():
        handler = _handler()
        all_files = {"src/pkg_a/utils/helper.py", "src/main.py"}
        result = handler.resolve_import(
            "pkg_a.utils.helper", "src/main.py", all_files, Path("/root")
        )
        assert result == "src/pkg_a/utils/helper.py"

    @staticmethod
    def test_module_from_init_file():
        handler = _handler()
        all_files = {"src/pkg_a/__init__.py", "src/main.py"}
        result = handler.resolve_import("pkg_a", "src/main.py", all_files, Path("/root"))
        assert result == "src/pkg_a/__init__.py"

    @staticmethod
    def test_module_suffixes_for_regular_file():
        handler = _handler()
        all_files = {"src/pkg_a/utils/helper.py", "src/other.py"}
        result = handler.resolve_import("utils.helper", "src/other.py", all_files, Path("/root"))
        assert result == "src/pkg_a/utils/helper.py"

    @staticmethod
    def test_keeps_path_in_resolved():
        handler = _handler()
        all_files = {"utils/helpers.py", "src/main.py"}
        result = handler.resolve_import("utils.helpers", "src/main.py", all_files, Path("/root"))
        assert result == "utils/helpers.py"

    @staticmethod
    def test_filters_when_path_not_in_all_files():
        handler = _handler()
        all_files = {"src/main.py"}
        result = handler.resolve_import("utils.helpers", "src/main.py", all_files, Path("/root"))
        assert result is None

    @staticmethod
    def test_filters_stdlib():
        handler = _handler()
        all_files = {"src/main.py"}
        result = handler.resolve_import("os", "src/main.py", all_files, Path("/root"))
        assert result is None

    @staticmethod
    def test_filters_mixed():
        handler = _handler()
        all_files = {"utils/helpers.py", "src/main.py"}
        r1 = handler.resolve_import("os", "src/main.py", all_files, Path("/root"))
        r2 = handler.resolve_import("utils.helpers", "src/main.py", all_files, Path("/root"))
        assert r1 is None
        assert r2 == "utils/helpers.py"

    @staticmethod
    def test_end_to_end():
        handler = _handler()
        all_files = {"pkg_b/helper.py", "pkg_a/main.py"}
        r1 = handler.resolve_import("pkg_b.helper", "pkg_a/main.py", all_files, Path("/root"))
        r2 = handler.resolve_import("os", "pkg_a/main.py", all_files, Path("/root"))
        assert r1 == "pkg_b/helper.py"
        assert r2 is None

    @staticmethod
    def test_self_referencing_resolved():
        handler = _handler()
        all_files = {"src/main.py"}
        result = handler.resolve_import("src.main", "src/main.py", all_files, Path("/root"))
        assert result == "src/main.py"

    @staticmethod
    def test_relative_from_init_importer():
        handler = _handler()
        all_files = {"src/services/__init__.py", "src/services/sub/service.py"}
        result = handler.resolve_import(
            ".sub.service", "src/services/__init__.py", all_files, Path("/root")
        )
        assert result == "src/services/sub/service.py"


class TestResolveSingleImportDirect:
    """Direct _resolve_single_import tests for edge cases (empty importer_path)."""

    @staticmethod
    def test_relative_without_importer_path():
        from archai.bootstrap.dependency_resolver import _resolve_single_import

        result = _resolve_single_import(".module", {}, {}, "")
        assert result == ""

    @staticmethod
    def test_relative_multi_level_without_importer_path():
        from archai.bootstrap.dependency_resolver import _resolve_single_import

        result = _resolve_single_import("..module", {}, {}, "")
        assert result == ""

    @staticmethod
    def test_relative_just_dots_without_importer_path():
        from archai.bootstrap.dependency_resolver import _resolve_single_import

        result = _resolve_single_import("..", {}, {}, "")
        assert result == "__init__.py"

    @staticmethod
    def test_relative_single_dot_without_importer_path():
        from archai.bootstrap.dependency_resolver import _resolve_single_import

        result = _resolve_single_import(".", {}, {}, "")
        assert result == "__init__.py"

    @staticmethod
    def test_relative_without_importer_stem_match():
        from archai.bootstrap.dependency_resolver import _resolve_single_import

        result = _resolve_single_import(".helper", {"helper": "utils/helper.py"}, {}, "")
        assert result == "utils/helper.py"


class TestResolveImportsFunction:
    """Tests for resolve_imports() function — covers lines 233-281."""

    @staticmethod
    def test_basic_resolution():
        from archai.bootstrap.dependency_resolver import resolve_imports, FileNode

        nodes = [
            FileNode(path="src/main.py", imports=["utils.helpers", "os"]),
            FileNode(path="src/utils/helpers.py", imports=[]),
        ]
        resolved = resolve_imports(nodes)
        assert len(resolved) == 2
        assert resolved[0].imports == ["src/utils/helpers.py"]

    @staticmethod
    def test_filters_non_existent():
        from archai.bootstrap.dependency_resolver import resolve_imports, FileNode

        nodes = [
            FileNode(path="src/main.py", imports=["nonexistent.nope"]),
            FileNode(path="src/utils.py", imports=[]),
        ]
        resolved = resolve_imports(nodes)
        assert resolved[0].imports == []

    @staticmethod
    def test_filters_stdlib():
        from archai.bootstrap.dependency_resolver import resolve_imports, FileNode

        nodes = [
            FileNode(path="src/main.py", imports=["os", "logging"]),
            FileNode(path="src/utils.py", imports=[]),
        ]
        resolved = resolve_imports(nodes)
        assert resolved[0].imports == []

    @staticmethod
    def test_stem_fallback_when_module_lookup_misses():
        from archai.bootstrap.dependency_resolver import resolve_imports, FileNode

        nodes = [
            FileNode(path="src/main.py", imports=["other_pkg.helper"]),
            FileNode(path="deep/path/helper.py", imports=[]),
            FileNode(path="helper.py", imports=[]),
        ]
        resolved = resolve_imports(nodes)
        assert resolved[0].imports == ["helper.py"]

    @staticmethod
    def test_stem_skips_longer_path_when_shorter_registered_first():
        from archai.bootstrap.dependency_resolver import resolve_imports, FileNode

        nodes = [
            FileNode(path="helper.py", imports=[]),
            FileNode(path="deep/path/helper.py", imports=[]),
            FileNode(path="src/main.py", imports=["other_pkg.helper"]),
        ]
        resolved = resolve_imports(nodes)
        assert resolved[2].imports == ["helper.py"]

    @staticmethod
    def test_init_file_resolution():
        from archai.bootstrap.dependency_resolver import resolve_imports, FileNode

        nodes = [
            FileNode(path="src/main.py", imports=["pkg_a"]),
            FileNode(path="src/pkg_a/__init__.py", imports=[]),
        ]
        resolved = resolve_imports(nodes)
        assert resolved[0].imports == ["src/pkg_a/__init__.py"]

    @staticmethod
    def test_module_suffix_resolution():
        from archai.bootstrap.dependency_resolver import resolve_imports, FileNode

        nodes = [
            FileNode(path="src/main.py", imports=["pkg_a.utils.helper"]),
            FileNode(path="src/pkg_a/utils/helper.py", imports=[]),
        ]
        resolved = resolve_imports(nodes)
        assert resolved[0].imports == ["src/pkg_a/utils/helper.py"]

    @staticmethod
    def test_preserves_functions_and_classes():
        from archai.bootstrap.dependency_resolver import resolve_imports, FileNode

        nodes = [
            FileNode(
                path="src/main.py",
                imports=["utils.helpers"],
                functions=["main"],
                classes=["App"],
            ),
            FileNode(path="src/utils/helpers.py", imports=[]),
        ]
        resolved = resolve_imports(nodes)
        assert resolved[0].functions == ["main"]
        assert resolved[0].classes == ["App"]

    @staticmethod
    def test_relative_import_resolution():
        from archai.bootstrap.dependency_resolver import resolve_imports, FileNode

        nodes = [
            FileNode(path="src/services/main.py", imports=[".module"]),
            FileNode(path="src/services/module.py", imports=[]),
        ]
        resolved = resolve_imports(nodes)
        assert resolved[0].imports == ["src/services/module.py"]

    @staticmethod
    def test_empty_imports_stays_empty():
        from archai.bootstrap.dependency_resolver import resolve_imports, FileNode

        nodes = [
            FileNode(path="src/main.py", imports=[]),
            FileNode(path="src/utils.py", imports=[]),
        ]
        resolved = resolve_imports(nodes)
        assert resolved[0].imports == []
