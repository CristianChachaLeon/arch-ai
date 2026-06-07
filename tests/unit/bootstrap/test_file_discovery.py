"""File Discovery - RED (test before implementation)"""

import os

import pytest


class TestFileDiscovery:
    """Test suite for file_discovery module"""

    def test_discover_python_files_finds_all_py_files(self, tmp_path):
        """Should discover all .py files in directory recursively"""
        # Arrange: create test files
        (tmp_path / "main.py").touch()
        (tmp_path / "utils.py").touch()
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "helper.py").touch()
        (tmp_path / "sub" / "deep").mkdir()
        (tmp_path / "sub" / "deep" / "nested.py").touch()

        from archai.bootstrap import file_discovery

        result = file_discovery.discover_python_files(tmp_path)

        # Assert: should find all 4 .py files
        assert len(result) == 4
        assert all(p.suffix == ".py" for p in result)

    def test_discover_python_files_excludes_non_python_files(self, tmp_path):
        """Should exclude non-.py files"""
        # Arrange
        (tmp_path / "main.py").touch()
        (tmp_path / "data.txt").touch()
        (tmp_path / "config.js").touch()
        (tmp_path / "readme.md").touch()

        # Act
        from archai.bootstrap import file_discovery

        result = file_discovery.discover_python_files(tmp_path)

        # Assert: only .py files
        assert len(result) == 1
        assert result[0].name == "main.py"

    def test_discover_python_files_handles_empty_directory(self, tmp_path):
        """Should return empty list when no .py files found"""
        # Arrange: empty directory
        (tmp_path / "readme.txt").touch()

        # Act
        from archai.bootstrap import file_discovery

        result = file_discovery.discover_python_files(tmp_path)

        # Assert
        assert result == []

    def test_discover_python_files_excludes_underscore_files(self, tmp_path):
        """Should exclude files starting with underscore (private)"""
        # Arrange
        (tmp_path / "main.py").touch()
        (tmp_path / "_private.py").touch()
        (tmp_path / "__init__.py").touch()

        # Act
        from archai.bootstrap import file_discovery

        result = file_discovery.discover_python_files(tmp_path)

        # Assert: __init__.py included, _private.py excluded
        assert len(result) == 2
        names = [p.name for p in result]
        assert "main.py" in names
        assert "__init__.py" in names
        assert "_private.py" not in names

    def test_discover_python_files_excludes_virtual_environments(self, tmp_path):
        """Should exclude venv, .venv, env directories"""
        # Arrange
        (tmp_path / "main.py").touch()
        (tmp_path / "venv").mkdir()
        (tmp_path / "venv" / "site.py").touch()
        (tmp_path / ".venv").mkdir()
        (tmp_path / ".venv" / "py.py").touch()

        # Act
        from archai.bootstrap import file_discovery

        result = file_discovery.discover_python_files(tmp_path)

        # Assert: only main.py
        assert len(result) == 1
        assert result[0].name == "main.py"

    def test_discover_python_files_returns_sorted_list(self, tmp_path):
        """Should return sorted list of files"""
        # Arrange
        (tmp_path / "z_file.py").touch()
        (tmp_path / "a_file.py").touch()
        (tmp_path / "m_file.py").touch()

        # Act
        from archai.bootstrap import file_discovery

        result = file_discovery.discover_python_files(tmp_path)

        # Assert: sorted alphabetically
        names = [p.name for p in result]
        assert names == ["a_file.py", "m_file.py", "z_file.py"]

    def test_discover_python_files_raises_on_file_path(self, tmp_path):
        """Should raise ValueError when path is a file, not a directory"""
        # Arrange
        file_path = tmp_path / "not_a_dir.py"
        file_path.touch()

        # Act / Assert
        from archai.bootstrap import file_discovery

        with pytest.raises(ValueError, match="Path is not a directory"):
            file_discovery.discover_python_files(file_path)

    def test_discover_python_files_skips_symlink(self, tmp_path):
        """Should skip symlinks but include the real file"""
        # Arrange
        real_file = tmp_path / "real.py"
        real_file.touch()

        link_path = tmp_path / "link.py"
        os.symlink(real_file, link_path)

        # Act
        from archai.bootstrap import file_discovery

        result = file_discovery.discover_python_files(tmp_path)

        # Assert: real file included, symlink excluded
        assert real_file in result
        assert link_path not in result


class TestDiscoverFiles:
    """Tests for the generic discover_files() function."""

    def test_discover_files_finds_c_files(self, tmp_path):
        (tmp_path / "main.c").touch()
        (tmp_path / "helper.c").touch()
        (tmp_path / "main.py").touch()

        from archai.bootstrap.file_discovery import discover_files

        result = discover_files(tmp_path, frozenset({".c"}))

        assert len(result) == 2
        assert all(p.suffix == ".c" for p in result)

    def test_discover_files_finds_multiple_extensions(self, tmp_path):
        (tmp_path / "main.c").touch()
        (tmp_path / "header.h").touch()
        (tmp_path / "helper.c").touch()

        from archai.bootstrap.file_discovery import discover_files

        result = discover_files(tmp_path, frozenset({".c", ".h"}))

        assert len(result) == 3
        suffixes = {p.suffix for p in result}
        assert ".c" in suffixes
        assert ".h" in suffixes

    def test_discover_files_excludes_shared_dirs(self, tmp_path):
        (tmp_path / "main.c").touch()
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "lib.c").touch()
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "config.c").touch()

        from archai.bootstrap.file_discovery import discover_files

        result = discover_files(
            tmp_path,
            frozenset({".c"}),
            frozenset({"node_modules", ".git"}),
        )

        assert len(result) == 1
        assert result[0].name == "main.c"

    def test_discover_files_does_not_skip_underscore_files_non_python(self, tmp_path):
        (tmp_path / "_internal.c").touch()
        (tmp_path / "__init__.c").touch()

        from archai.bootstrap.file_discovery import discover_files

        result = discover_files(tmp_path, frozenset({".c"}))

        assert len(result) == 2

    def test_discover_files_return_sorted(self, tmp_path):
        (tmp_path / "z_file.c").touch()
        (tmp_path / "a_file.c").touch()
        (tmp_path / "m_file.c").touch()

        from archai.bootstrap.file_discovery import discover_files

        result = discover_files(tmp_path, frozenset({".c"}))

        names = [p.name for p in result]
        assert names == ["a_file.c", "m_file.c", "z_file.c"]

    def test_discover_files_raises_on_file_path(self, tmp_path):
        file_path = tmp_path / "not_a_dir.c"
        file_path.touch()

        from archai.bootstrap.file_discovery import discover_files

        with pytest.raises(ValueError, match="Path is not a directory"):
            discover_files(file_path, frozenset({".c"}))

    def test_discover_files_excludes_none_uses_empty(self, tmp_path):
        (tmp_path / "main.c").touch()
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "lib.c").touch()

        from archai.bootstrap.file_discovery import discover_files

        result = discover_files(tmp_path, frozenset({".c"}))

        assert len(result) == 2
