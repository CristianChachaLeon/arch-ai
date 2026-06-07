"""C/C++ Handler - Tests for parsing C and C++ files."""

import pytest


class TestCLangHandler:
    """Tests for CLangHandler."""

    def setup_method(self):
        from archai.bootstrap.c_handler import CLangHandler

        self.handler = CLangHandler()

    def test_language(self):
        assert self.handler.language == "c"

    def test_extensions(self):
        assert self.handler.extensions == frozenset({".c"})

    def test_project_files(self):
        assert "Makefile" in self.handler.project_files
        assert "CMakeLists.txt" in self.handler.project_files

    def test_is_project_root_with_makefile(self, tmp_path):
        project = tmp_path / "myproject"
        project.mkdir()
        (project / "Makefile").touch()
        assert self.handler.is_project_root(project) is True

    def test_is_project_root_with_cmakelists(self, tmp_path):
        project = tmp_path / "myproject"
        project.mkdir()
        (project / "CMakeLists.txt").touch()
        assert self.handler.is_project_root(project) is True

    def test_is_project_root_empty(self, tmp_path):
        project = tmp_path / "empty"
        project.mkdir()
        assert self.handler.is_project_root(project) is False

    def test_resolve_local_include(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.c").touch()
        (tmp_path / "src" / "utils").mkdir()
        (tmp_path / "src" / "utils" / "helper.h").touch()

        all_files = {"src/main.c", "src/utils/helper.h"}
        result = self.handler.resolve_import(
            '"utils/helper.h"',
            "src/main.c",
            all_files,
            tmp_path,
        )
        assert result == "src/utils/helper.h"

    def test_resolve_system_include(self, tmp_path):
        all_files: set[str] = set()
        result = self.handler.resolve_import(
            "<stdio.h>",
            "src/main.c",
            all_files,
            tmp_path,
        )
        assert result == "external"

    def test_resolve_file_relative_include(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.c").touch()
        (tmp_path / "src" / "helper.h").touch()

        all_files = {"src/main.c", "src/helper.h"}
        result = self.handler.resolve_import(
            '"helper.h"',
            "src/main.c",
            all_files,
            tmp_path,
        )
        assert result == "src/helper.h"

    def test_resolve_project_wide_include(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "include").mkdir()
        (tmp_path / "src" / "main.c").touch()
        (tmp_path / "include" / "helper.h").touch()

        all_files = {"src/main.c", "include/helper.h"}
        result = self.handler.resolve_import(
            '"helper.h"',
            "src/main.c",
            all_files,
            tmp_path,
        )
        assert result == "include/helper.h"

    def test_resolve_unresolvable_include(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.c").touch()

        all_files = {"src/main.c"}
        result = self.handler.resolve_import(
            '"nonexistent.h"',
            "src/main.c",
            all_files,
            tmp_path,
        )
        assert result is None

    def test_parse_raises_without_tree_sitter_c(self, tmp_path):
        try:
            import tree_sitter_c  # noqa: F401

            has_grammar = True
        except ImportError:
            has_grammar = False

        c_file = tmp_path / "test.c"
        c_file.write_text("int main() { return 0; }")

        if has_grammar:
            parsed = self.handler.parse(c_file)
            assert parsed.language == "c"
        else:
            with pytest.raises(ImportError, match="tree-sitter-c"):
                self.handler.parse(c_file)


class TestCppLangHandler:
    """Tests for CppLangHandler."""

    def setup_method(self):
        from archai.bootstrap.c_handler import CppLangHandler

        self.handler = CppLangHandler()

    def test_language(self):
        assert self.handler.language == "cpp"

    def test_extensions(self):
        assert self.handler.extensions == frozenset(
            {
                ".cpp",
                ".hpp",
                ".cc",
                ".cxx",
                ".hh",
                ".h",
            }
        )

    def test_project_files(self):
        assert "Makefile" in self.handler.project_files
        assert "CMakeLists.txt" in self.handler.project_files

    def test_is_project_root_with_makefile(self, tmp_path):
        project = tmp_path / "myproject"
        project.mkdir()
        (project / "Makefile").touch()
        assert self.handler.is_project_root(project) is True

    def test_is_project_root_with_cmakelists(self, tmp_path):
        project = tmp_path / "myproject"
        project.mkdir()
        (project / "CMakeLists.txt").touch()
        assert self.handler.is_project_root(project) is True

    def test_is_project_root_empty(self, tmp_path):
        project = tmp_path / "empty"
        project.mkdir()
        assert self.handler.is_project_root(project) is False

    def test_resolve_local_include(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.cpp").touch()
        (tmp_path / "src" / "utils").mkdir()
        (tmp_path / "src" / "utils" / "helper.hpp").touch()

        all_files = {"src/main.cpp", "src/utils/helper.hpp"}
        result = self.handler.resolve_import(
            '"utils/helper.hpp"',
            "src/main.cpp",
            all_files,
            tmp_path,
        )
        assert result == "src/utils/helper.hpp"

    def test_resolve_system_include(self, tmp_path):
        all_files: set[str] = set()
        result = self.handler.resolve_import(
            "<iostream>",
            "src/main.cpp",
            all_files,
            tmp_path,
        )
        assert result == "external"

    def test_parse_raises_without_tree_sitter_cpp(self, tmp_path):
        try:
            import tree_sitter_cpp  # noqa: F401

            has_grammar = True
        except ImportError:
            has_grammar = False

        cpp_file = tmp_path / "test.cpp"
        cpp_file.write_text("int main() { return 0; }")

        if has_grammar:
            parsed = self.handler.parse(cpp_file)
            assert parsed.language == "cpp"
        else:
            with pytest.raises(ImportError, match="tree-sitter-cpp"):
                self.handler.parse(cpp_file)


class TestCLangHandlerParse:
    """Integration tests for CLangHandler.parse() — requires tree-sitter-c."""

    def setup_method(self):
        pytest.importorskip("tree_sitter_c")
        from archai.bootstrap.c_handler import CLangHandler

        self.handler = CLangHandler()

    def test_parse_c_file(self, tmp_path):
        c_file = tmp_path / "test.c"
        c_file.write_text(
            "#include <stdio.h>\n"
            '#include "utils/helper.h"\n'
            "\n"
            "int main() {\n"
            "    return 0;\n"
            "}\n"
            "\n"
            "void helper_function() {\n"
            "}\n"
        )

        parsed = self.handler.parse(c_file)

        assert parsed.language == "c"
        assert "<stdio.h>" in parsed.imports
        assert '"utils/helper.h"' in parsed.imports
        assert "main" in parsed.functions
        assert "helper_function" in parsed.functions

    def test_parse_h_file(self, tmp_path):
        h_file = tmp_path / "test.h"
        h_file.write_text(
            "#ifndef MY_HEADER_H\n"
            "#define MY_HEADER_H\n"
            "\n"
            "void declared_func();\n"
            "\n"
            "#endif\n"
        )

        parsed = self.handler.parse(h_file)

        assert parsed.language == "c"
        assert parsed.imports == []


class TestCppLangHandlerParse:
    """Integration tests for CppLangHandler.parse() — requires tree-sitter-cpp."""

    def setup_method(self):
        pytest.importorskip("tree_sitter_cpp")
        from archai.bootstrap.c_handler import CppLangHandler

        self.handler = CppLangHandler()

    def test_parse_cpp_file(self, tmp_path):
        cpp_file = tmp_path / "test.cpp"
        cpp_file.write_text(
            "#include <iostream>\n"
            '#include "myclass.hpp"\n'
            "\n"
            "class MyClass {\n"
            "public:\n"
            "    MyClass() {}\n"
            "    void doSomething() {}\n"
            "};\n"
            "\n"
            "int main() {\n"
            "    MyClass obj;\n"
            "    obj.doSomething();\n"
            "    return 0;\n"
            "}\n"
        )

        parsed = self.handler.parse(cpp_file)

        assert parsed.language == "cpp"
        assert "<iostream>" in parsed.imports
        assert '"myclass.hpp"' in parsed.imports
        assert "main" in parsed.functions
        assert "MyClass" in parsed.classes

    def test_parse_cpp_header(self, tmp_path):
        hpp_file = tmp_path / "test.hpp"
        hpp_file.write_text(
            "#ifndef MY_CLASS_HPP\n"
            "#define MY_CLASS_HPP\n"
            "\n"
            "class MyOtherClass {\n"
            "    int value;\n"
            "public:\n"
            "    MyOtherClass(int v) : value(v) {}\n"
            "    int getValue() const { return value; }\n"
            "};\n"
            "\n"
            "#endif\n"
        )

        parsed = self.handler.parse(hpp_file)

        assert parsed.language == "cpp"
        assert "MyOtherClass" in parsed.classes

    def test_parse_cpp_with_namespace_function(self, tmp_path):
        """Test parsing C++ with namespaced functions — covers qualified_identifier."""
        cpp_file = tmp_path / "ns.cpp"
        cpp_file.write_text(
            "namespace ns {\n"
            "    void func() {}\n"
            "}\n"
            "\n"
            "void ns::MyClass::method() {}\n"
            "\n"
            "int main() { return 0; }\n"
        )
        parsed = self.handler.parse(cpp_file)
        assert parsed.language == "cpp"
        assert "func" in parsed.functions
        assert "main" in parsed.functions
        assert "MyClass::method" in parsed.functions

    def test_parse_cpp_with_struct(self, tmp_path):
        """Test parsing C++ with struct — covers struct_specifier branch."""
        cpp_file = tmp_path / "struct.cpp"
        cpp_file.write_text(
            "struct Point {\n" "    int x;\n" "};\n" "\n" "int main() { return 0; }\n"
        )
        parsed = self.handler.parse(cpp_file)
        assert parsed.language == "cpp"
        assert "Point" in parsed.classes


class TestGetCParserImportError:
    """Tests for _get_c_parser() ImportError branch."""

    @staticmethod
    def test_get_c_parser_raises_without_tree_sitter_c():
        import builtins
        import sys
        from unittest.mock import patch
        from archai.bootstrap.c_handler import _get_c_parser

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "tree_sitter_c":
                raise ImportError("No module named tree_sitter_c")
            return original_import(name, *args, **kwargs)

        with patch.dict(sys.modules):
            sys.modules.pop("tree_sitter_c", None)
            with patch("builtins.__import__", side_effect=mock_import):
                with pytest.raises(ImportError, match="tree-sitter-c"):
                    _get_c_parser()


class TestGetCppParserImportError:
    """Tests for _get_cpp_parser() ImportError branch."""

    @staticmethod
    def test_get_cpp_parser_raises_without_tree_sitter_cpp():
        import builtins
        import sys
        from unittest.mock import patch
        from archai.bootstrap.c_handler import _get_cpp_parser

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "tree_sitter_cpp":
                raise ImportError("No module named tree_sitter_cpp")
            return original_import(name, *args, **kwargs)

        with patch.dict(sys.modules):
            sys.modules.pop("tree_sitter_cpp", None)
            with patch("builtins.__import__", side_effect=mock_import):
                with pytest.raises(ImportError, match="tree-sitter-cpp"):
                    _get_cpp_parser()
