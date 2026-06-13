"""Tests for C/C++ .c ↔ .h mapping."""

from archai.bootstrap.c_mapping import build_c_h_mapping


def test_empty_file_nodes():
    assert build_c_h_mapping([], "/fake/repo") == {}


def test_no_h_files():
    nodes = [
        _make_node("src/main.c"),
        _make_node("src/utils.c"),
    ]
    assert build_c_h_mapping(nodes, "/fake/repo") == {}


def test_no_c_files():
    nodes = [
        _make_node("include/main.h"),
        _make_node("include/utils.h"),
    ]
    assert build_c_h_mapping(nodes, "/fake/repo") == {}


def test_basic_c_h_mapping():
    nodes = [
        _make_node("src/Demangle.c"),
        _make_node("src/Demangle.h"),
    ]
    result = build_c_h_mapping(nodes, "/fake/repo")
    assert result["src/Demangle.c"] == "src/Demangle.h"
    assert result["src/Demangle.h"] == "src/Demangle.c"


def test_same_directory_mapping():
    nodes = [
        _make_node("src/core/Demangle.c"),
        _make_node("src/core/Demangle.h"),
    ]
    result = build_c_h_mapping(nodes, "/fake/repo")
    assert result["src/core/Demangle.c"] == "src/core/Demangle.h"
    assert result["src/core/Demangle.h"] == "src/core/Demangle.c"


def test_different_directory_no_mapping():
    """Same basename but different directories should NOT map."""
    nodes = [
        _make_node("src/core/Demangle.c"),
        _make_node("include/Demangle.h"),
    ]
    result = build_c_h_mapping(nodes, "/fake/repo")
    assert result == {}


def test_multiple_mappings():
    nodes = [
        _make_node("src/core/engine.c"),
        _make_node("src/core/engine.h"),
        _make_node("src/core/utils.c"),
        _make_node("src/core/utils.h"),
        _make_node("src/main.c"),
    ]
    result = build_c_h_mapping(nodes, "/fake/repo")
    assert result["src/core/engine.c"] == "src/core/engine.h"
    assert result["src/core/engine.h"] == "src/core/engine.c"
    assert result["src/core/utils.c"] == "src/core/utils.h"
    assert result["src/core/utils.h"] == "src/core/utils.c"
    # main.c has no .h → no mapping
    assert "src/main.c" not in result


def test_cpp_extensions():
    nodes = [
        _make_node("src/core/engine.cpp"),
        _make_node("src/core/engine.hpp"),
        _make_node("src/core/utils.cc"),
        _make_node("src/core/utils.hh"),
        _make_node("src/core/module.cxx"),
        _make_node("src/core/module.h"),
    ]
    result = build_c_h_mapping(nodes, "/fake/repo")
    assert result["src/core/engine.cpp"] == "src/core/engine.hpp"
    assert result["src/core/engine.hpp"] == "src/core/engine.cpp"
    assert result["src/core/utils.cc"] == "src/core/utils.hh"
    assert result["src/core/utils.hh"] == "src/core/utils.cc"
    assert result["src/core/module.cxx"] == "src/core/module.h"
    assert result["src/core/module.h"] == "src/core/module.cxx"


def test_standalone_h_no_c():
    """A .h without a corresponding .c should not appear in mapping."""
    nodes = [
        _make_node("include/api.h"),
        _make_node("include/config.h"),
        _make_node("src/main.c"),
    ]
    result = build_c_h_mapping(nodes, "/fake/repo")
    assert "src/main.c" not in result  # main.c has no .h
    assert "include/api.h" not in result
    assert "include/config.h" not in result


def test_case_sensitivity():
    """Mapping should be case-sensitive by default."""
    nodes = [
        _make_node("src/Demangle.c"),
        _make_node("src/demangle.h"),
    ]
    result = build_c_h_mapping(nodes, "/fake/repo")
    assert result == {}


def _make_node(path: str):
    from archai.bootstrap.graph_builder import FileNode
    return FileNode(path=path)
