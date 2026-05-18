"""File Discovery - RED (test before implementation)"""


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
