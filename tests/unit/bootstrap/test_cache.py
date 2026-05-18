"""Cache - Tests for disk cache with hash invalidation.

SRP: cache module handles only caching logic, not graph construction.
"""

import os
import tempfile
from pathlib import Path

from archai.bootstrap.cache import (
    get_cache_path,
    compute_repo_hash,
    save_cache,
    load_cache,
    cache_exists,
    invalidate_cache,
)


class TestCachePath:
    """Test suite for cache path generation."""

    def test_get_cache_path_returns_path_in_cache_dir(self):
        """Should return path inside ~/.archai/cache/."""
        repo_path = "/some/repo"
        result = get_cache_path(repo_path)

        assert str(result).startswith(os.path.expanduser("~/.archai/cache/"))

    def test_get_cache_path_uses_sha256_hash(self):
        """Should use SHA256 hash of repo path for filename."""
        repo_path = "/test/repo/path"
        result = get_cache_path(repo_path)

        import hashlib

        expected_hash = hashlib.sha256(repo_path.encode()).hexdigest()
        assert expected_hash in str(result)
        assert str(result).endswith(".pkl")


class TestComputeRepoHash:
    """Test suite for repository hash computation."""

    def test_compute_repo_hash_returns_same_for_same_content(self):
        """Should return identical hash for identical content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = Path(tmpdir) / "file1.py"
            file1.write_text("import os\nprint('hello')")

            hash1 = compute_repo_hash(tmpdir)
            hash2 = compute_repo_hash(tmpdir)

            assert hash1 == hash2

    def test_compute_repo_hash_differs_for_different_content(self):
        """Should return different hash when file content changes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = Path(tmpdir) / "file1.py"
            file1.write_text("import os")

            hash1 = compute_repo_hash(tmpdir)

            file1.write_text("import sys")

            hash2 = compute_repo_hash(tmpdir)

            assert hash1 != hash2

    def test_compute_repo_hash_differs_for_different_files(self):
        """Should return different hash when files are added/removed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = Path(tmpdir) / "file1.py"
            file1.write_text("import os")

            hash1 = compute_repo_hash(tmpdir)

            file2 = Path(tmpdir) / "file2.py"
            file2.write_text("import sys")

            hash2 = compute_repo_hash(tmpdir)

            assert hash1 != hash2

    def test_compute_repo_hash_ignores_non_python_files(self):
        """Should ignore non-.py files when computing hash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "file.py"
            py_file.write_text("import os")

            txt_file = Path(tmpdir) / "readme.txt"
            txt_file.write_text("Some documentation")

            hash1 = compute_repo_hash(tmpdir)

            txt_file.write_text("Different content")

            hash2 = compute_repo_hash(tmpdir)

            assert hash1 == hash2


class TestCacheExists:
    """Test suite for cache existence check."""

    def test_cache_exists_returns_false_when_not_cached(self):
        """Should return False when no cache exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            assert cache_exists(tmpdir) is False

    def test_cache_exists_returns_true_when_cached(self):
        """Should return True when cache file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = get_cache_path(tmpdir)
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_bytes(b"mock cache data")

            assert cache_exists(tmpdir) is True


class TestSaveAndLoadCache:
    """Test suite for cache save and load operations."""

    def test_save_and_load_cache_roundtrip(self):
        """Should save and load FileGraph correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from archai.bootstrap.graph_builder import FileNode, build_graph

            file_nodes = [
                FileNode(path="main.py", imports=["utils.py"], functions=["main"], classes=[]),
                FileNode(path="utils.py", imports=[], functions=["helper"], classes=[]),
            ]
            graph = build_graph(file_nodes)

            save_cache(tmpdir, graph)

            loaded = load_cache(tmpdir)

            assert loaded is not None
            assert loaded.graph.number_of_nodes() == 2

    def test_load_cache_returns_none_when_no_cache(self):
        """Should return None when no cache exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = load_cache(tmpdir)
            assert result is None


class TestCacheInvalidation:
    """Test suite for cache invalidation based on hash."""

    def test_cache_invalidates_on_file_change(self):
        """Should detect that cache is stale when files change."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from archai.bootstrap.graph_builder import FileNode, build_graph

            file1 = Path(tmpdir) / "main.py"
            file1.write_text("import os\n")

            file_nodes = [FileNode(path="main.py", imports=["os"], functions=[], classes=[])]
            graph = build_graph(file_nodes)

            save_cache(tmpdir, graph)

            file1.write_text("import sys\n")

            loaded = load_cache(tmpdir)
            assert loaded is None

    def test_invalidate_cache_removes_cache_file(self):
        """Should remove cache file when invalidated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from archai.bootstrap.graph_builder import FileNode, build_graph

            file_nodes = [FileNode(path="main.py", imports=[], functions=[], classes=[])]
            graph = build_graph(file_nodes)

            save_cache(tmpdir, graph)

            assert cache_exists(tmpdir)

            invalidate_cache(tmpdir)

            assert cache_exists(tmpdir) is False
