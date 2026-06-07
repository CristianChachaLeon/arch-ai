"""Call Extraction - Tests for extracting function calls from C files."""

import pytest


class TestCallQueryConstant:
    """Tests for the _CALL_QUERY constant."""

    def test_call_query_constant(self):
        from archai.bootstrap.c_handler import _CALL_QUERY

        assert isinstance(_CALL_QUERY, str)
        assert len(_CALL_QUERY) > 0


class TestExtractFunctionCalls:
    """Integration tests for call extraction — requires tree-sitter-c."""

    def setup_method(self):
        pytest.importorskip("tree_sitter_c")
        from archai.bootstrap.c_handler import CLangHandler

        self.handler = CLangHandler()

    def test_extract_function_calls_basic(self, tmp_path):
        """Functions that call other functions defined in the same file
        should appear in calls_internal."""
        c_file = tmp_path / "test.c"
        c_file.write_text(
            "#include <stdio.h>\n"
            "\n"
            "void helper() {}\n"
            "\n"
            "void caller() {\n"
            "    helper();\n"
            "}\n"
        )
        parsed = self.handler.parse(c_file)
        caller_detail = next(fd for fd in parsed.functions_detail if fd.name == "caller")
        assert "helper" in caller_detail.calls_internal

    def test_extract_function_calls_no_calls(self, tmp_path):
        """Function with no calls should have empty calls_internal and calls_external."""
        c_file = tmp_path / "test.c"
        c_file.write_text("void standalone() {\n" "    int x = 42;\n" "}\n")
        parsed = self.handler.parse(c_file)
        assert len(parsed.functions_detail) == 1
        fd = parsed.functions_detail[0]
        assert fd.calls_internal == []
        assert fd.calls_external == []

    def test_extract_function_calls_external(self, tmp_path):
        """Functions calling something NOT defined in the file go to calls_external."""
        c_file = tmp_path / "test.c"
        c_file.write_text(
            "#include <stdio.h>\n"
            "\n"
            "void caller() {\n"
            "    external_func();\n"
            '    printf("hello");\n'
            "}\n"
        )
        parsed = self.handler.parse(c_file)
        caller_detail = next(fd for fd in parsed.functions_detail if fd.name == "caller")
        assert "external_func" in caller_detail.calls_external
        assert "printf" in caller_detail.calls_external
        assert caller_detail.calls_internal == []

    def test_extract_function_calls_empty_file(self, tmp_path):
        """Empty .c file should produce empty functions_detail."""
        c_file = tmp_path / "empty.c"
        c_file.write_text("// just a comment\n")
        parsed = self.handler.parse(c_file)
        assert parsed.functions_detail == []

    def test_struct_extraction_for_c(self, tmp_path):
        """Parse a .c file with struct definitions and verify structs appear in classes."""
        c_file = tmp_path / "structs.c"
        c_file.write_text(
            "struct Point {\n"
            "    int x;\n"
            "    int y;\n"
            "};\n"
            "\n"
            "struct Line {\n"
            "    struct Point start;\n"
            "    struct Point end;\n"
            "};\n"
            "\n"
            "int main() { return 0; }\n"
        )
        parsed = self.handler.parse(c_file)
        assert "Point" in parsed.classes
        assert "Line" in parsed.classes
