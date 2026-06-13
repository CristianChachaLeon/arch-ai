"""Tests for the ArchAI Middleware Pipeline."""

import pytest

from archai.middleware.pipeline import ArchaiMiddleware, PipelineResult


class TestArchaiMiddleware:
    """Test suite for ArchaiMiddleware."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create a temporary repository with Python files."""
        # Create some Python files with imports
        (tmp_path / "main.py").write_text(
            """
import utils
from models import User

def run():
    pass
"""
        )

        (tmp_path / "utils.py").write_text(
            """
def helper():
    pass
"""
        )

        (tmp_path / "models").mkdir()
        (tmp_path / "models" / "__init__.py").write_text("")
        (tmp_path / "models" / "user.py").write_text(
            """
class User:
    pass
"""
        )

        (tmp_path / "services").mkdir()
        (tmp_path / "services" / "__init__.py").write_text("")
        (tmp_path / "services" / "auth.py").write_text(
            """
from models import User

def authenticate():
    pass
"""
        )

        return tmp_path

    async def test_middleware_processes_repository(self, temp_repo):
        """Middleware should process repository through full pipeline."""
        middleware = ArchaiMiddleware()
        result = await middleware.process(temp_repo)

        assert isinstance(result, PipelineResult)
        assert result.file_count > 0
        assert result.graph is not None

    async def test_pipeline_creates_clusters(self, temp_repo):
        """Pipeline should create clusters from the graph."""
        middleware = ArchaiMiddleware()
        result = await middleware.process(temp_repo)

        assert isinstance(result.clusters, dict)
        assert result.cluster_count > 0
        # At least some files should be clustered
        total_files_in_clusters = sum(len(files) for files in result.clusters.values())
        assert total_files_in_clusters > 0

    async def test_pipeline_result_to_dict(self, temp_repo):
        """PipelineResult should serialize to dict."""
        middleware = ArchaiMiddleware()
        result = await middleware.process(temp_repo)

        data = result.to_dict()

        assert "repo_path" in data
        assert "file_count" in data
        assert "edge_count" in data
        assert "cluster_count" in data
        assert "clusters" in data

    async def test_get_cluster_for_file(self, temp_repo):
        """Should find which cluster a file belongs to."""
        middleware = ArchaiMiddleware()
        result = await middleware.process(temp_repo)

        # Find a file that's in a cluster
        found_any = False
        for cluster_name, files in result.clusters.items():
            if files:
                # Test with the first file in the cluster
                found = result.get_cluster_for_file(files[0])
                assert found == cluster_name
                found_any = True
                break

        assert found_any, "Expected at least one clustered file for lookup assertion"

    async def test_middleware_handles_empty_directory(self, tmp_path):
        """Middleware should handle empty directory gracefully."""
        middleware = ArchaiMiddleware()
        result = await middleware.process(tmp_path)

        assert result.file_count == 0
        assert result.edge_count == 0
        assert result.cluster_count == 0
        assert result.clusters == {}

    async def test_middleware_handles_nonexistent_path(self, tmp_path):
        """Middleware should raise error for nonexistent path."""
        middleware = ArchaiMiddleware()

        missing_path = tmp_path / "definitely_missing_dir"
        # discover_python_files raises ValueError for invalid paths
        with pytest.raises(ValueError, match="Path is not a directory"):
            await middleware.process(missing_path)


class TestVarAccessPipeline:
    """Tests for var_access flow through the pipeline."""

    @pytest.fixture
    def c_repo(self, tmp_path):
        """Create a temporary C repository with global variables."""
        (tmp_path / "main.c").write_text(
            "int cfg;\n"
            "int debug;\n"
            "\n"
            "void init(void) {\n"
            "    cfg = 42;\n"
            "}\n"
            "\n"
            "void process(void) {\n"
            "    if (debug) {\n"
            "        cfg = 0;\n"
            "    }\n"
            "}\n"
        )
        (tmp_path / "Makefile").touch()
        return tmp_path

    async def test_var_access_present_in_file_node(self, c_repo):
        """Verifies var_access flows from ParsedFile through to FileNode."""
        try:
            import tree_sitter_c  # noqa: F401
        except ImportError:
            pytest.skip("tree-sitter-c not installed")

        middleware = ArchaiMiddleware()
        file_nodes, _ = middleware._run_bootstrap(str(c_repo))

        main_node = None
        for fn in file_nodes:
            if fn.path == "main.c":
                main_node = fn
                break

        assert main_node is not None
        assert main_node.var_access is not None
        assert "init" in main_node.var_access
        assert "process" in main_node.var_access

        init_writes = main_node.var_access["init"]["writes"]
        assert any(w["name"] == "cfg" for w in init_writes)

        process_reads = main_node.var_access["process"]["reads"]
        assert any(r["name"] == "debug" for r in process_reads)


class TestImportDeduplication:
    """Tests for import deduplication in FileNode."""

    @pytest.fixture
    def repo_with_multi_imports(self, tmp_path):
        """Create a repo where a file imports multiple symbols from the same module."""
        (tmp_path / "iterutils.py").write_text("def first(): pass\ndef second(): pass\ndef third(): pass\n")

        (tmp_path / "main.py").write_text(
            """from iterutils import first, second

from iterutils import third


def run():
    pass
"""
        )
        return tmp_path

    @pytest.fixture
    def repo_with_dup_import_lines(self, tmp_path):
        """Create a repo with repeated same-line imports."""
        (tmp_path / "mylib.py").write_text("def a(): pass\n")

        (tmp_path / "main.py").write_text(
            """from mylib import a
from mylib import a


def run():
    pass
"""
        )
        return tmp_path

    async def test_no_duplicate_imports_from_multi_symbol(self, repo_with_multi_imports):
        """Multiple symbols from same module should be deduped to one entry."""
        middleware = ArchaiMiddleware()
        file_nodes, _ = middleware._run_bootstrap(str(repo_with_multi_imports))

        main_node = next((fn for fn in file_nodes if fn.path == "main.py"), None)
        assert main_node is not None
        assert len(main_node.imports) == len(set(main_node.imports)), (
            f"Expected no duplicates, got: {main_node.imports}"
        )

    async def test_no_duplicate_imports_from_repeated_lines(self, repo_with_dup_import_lines):
        """Repeated import lines for same module should be deduped."""
        middleware = ArchaiMiddleware()
        file_nodes, _ = middleware._run_bootstrap(str(repo_with_dup_import_lines))

        main_node = next((fn for fn in file_nodes if fn.path == "main.py"), None)
        assert main_node is not None
        assert len(main_node.imports) == len(set(main_node.imports)), (
            f"Expected no duplicates, got: {main_node.imports}"
        )
