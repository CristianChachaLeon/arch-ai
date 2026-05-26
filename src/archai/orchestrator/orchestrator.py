"""ArchaiOrchestrator - Orchestrates bootstrap + inference + focus resolution.

This module provides the main orchestrator that connects the middleware
pipeline with focus resolution to produce architecture-aware context packets.
"""

import asyncio
import re

from archai.http.models import ContextPacket, FileMetadata, SubsystemConstraints
from archai.middleware.pipeline import PipelineResult
from archai.orchestrator.focus_resolver import resolve_focus

# Regex patterns for test file detection
_TEST_FILE_PATTERNS = re.compile(r"(test_.*\.py|.*_test\.py|conftest\.py)$")


def _find_related_test_files(
    focus_files: list[str],
    all_clusters: dict[str, list[str]],
) -> list[str]:
    """Find test files related to the focus subsystem.

    A test file is considered related if:
    - Its name matches test patterns (test_*.py, *_test.py, conftest.py)
    - It's inside a tests/ directory
    - Its basename (after removing test_ prefix) matches a focus file basename
      OR it shares a directory prefix with a focus file

    Args:
        focus_files: Files in the focused subsystem
        all_clusters: All clusters from the pipeline result

    Returns:
        Sorted list of related test file paths
    """
    all_files: set[str] = set()
    for files in all_clusters.values():
        all_files.update(files)

    # Build directory prefixes from focus files
    # e.g., "src/api/routes.py" → "src", "src/api"
    focus_dirs: set[str] = set()
    for f in focus_files:
        parts = f.split("/")
        for i in range(1, len(parts)):
            focus_dirs.add("/".join(parts[:i]))

    related: list[str] = []
    for file in all_files:
        # Skip non-test files
        if (
            not _TEST_FILE_PATTERNS.search(file)
            and "/tests/" not in file
            and not file.startswith("tests/")
        ):
            continue

        # Normalize test path to source-equivalent form
        # "tests/api/test_routes.py" → "api/test_routes.py"
        # "src/tests/api/test_routes.py" → "src/api/test_routes.py"
        if file.startswith("tests/"):
            file_path = file[len("tests/") :]
        elif "/tests/" in file:
            file_path = file.replace("/tests/", "/", 1)
        else:
            file_path = file
        test_name = file_path.split("/")[-1].replace(".py", "")

        # Extract the subdirectory within tests/ for directory matching
        # "tests/api/test_routes.py" → "api", "tests/conftest.py" → ""
        if file.startswith("tests/"):
            _rest = file[len("tests/") :]
            test_subdir = _rest.rsplit("/", 1)[0] if "/" in _rest else ""
        elif "/tests/" in file:
            test_subdir = file.split("/tests/", 1)[1].rsplit("/", 1)[0]
        else:
            test_subdir = ""

        for focus_file in focus_files:
            focus_name = focus_file.split("/")[-1].replace(".py", "")

            # Match by basename: "routes" is a substring of "test_routes"
            if focus_name in test_name or test_name in focus_name:
                related.append(file)
                break

            # Match by directory: test file's subdirectory matches focus dir
            # e.g., "tests/api/test_routes.py" shares "api" with "src/api/routes.py"
            if test_subdir and any(fd.endswith("/" + test_subdir) for fd in focus_dirs):
                related.append(file)
                break

    return sorted(set(related))


class ArchaiOrchestrator:
    """Orchestrates the bootstrap + inference + focus resolution pipeline."""

    def __init__(self, middleware):
        """Initialize with an ArchaiMiddleware instance."""
        self.middleware = middleware
        self._cache: dict[str, PipelineResult] = {}
        self._inflight: dict[str, asyncio.Task] = {}

    async def get_context(self, query: str, repo_path: str, force: bool = False) -> ContextPacket:
        """Process a repo and query, return an architecture-governed ContextPacket.

        The PipelineResult is cached by repo_path so subsequent queries against
        the same repo skip the bootstrap + inference pipeline. Concurrent
        requests for the same repo are de-duplicated via an in-flight task tracker.

        Args:
            query: User query to resolve focus for
            repo_path: Path to the repository
            force: If True, bypass cache and re-process the repo
        """
        if force:
            if repo_path in self._inflight:
                self._inflight[repo_path].cancel()
                del self._inflight[repo_path]
            pipeline_result = await self.middleware.process(repo_path)
            self._cache[repo_path] = pipeline_result
        elif repo_path in self._cache:
            pipeline_result = self._cache[repo_path]
        elif repo_path in self._inflight:
            pipeline_result = await self._inflight[repo_path]
        else:
            task = asyncio.ensure_future(self.middleware.process(repo_path))
            self._inflight[repo_path] = task
            try:
                pipeline_result = await task
            finally:
                del self._inflight[repo_path]
            self._cache[repo_path] = pipeline_result

        cluster_descriptions = None
        if pipeline_result.labeled_clusters is not None:
            cluster_descriptions = {
                lc.cluster_id: lc.description for lc in pipeline_result.labeled_clusters
            }

        focus, focus_reasoning = resolve_focus(
            query,
            pipeline_result.clusters,
            cluster_descriptions,
        )

        subgraph = pipeline_result.clusters.get(focus, [])

        # Find related test files across all clusters and include them
        test_files = _find_related_test_files(subgraph, pipeline_result.clusters)
        # Remove duplicates: test files already in the focus subgraph
        test_files = [tf for tf in test_files if tf not in subgraph]
        all_focus_files = list(subgraph) + test_files

        relevant_files = [
            FileMetadata(path=file, reason="part of focus subsystem", importance=1.0)
            for file in subgraph
        ]
        if test_files:
            relevant_files.extend(
                [
                    FileMetadata(path=tf, reason="related test file", importance=0.8)
                    for tf in test_files
                ]
            )

        constraints = SubsystemConstraints()
        if pipeline_result.labeled_clusters is not None:
            for lc in pipeline_result.labeled_clusters:
                if lc.cluster_id == focus:
                    constraints = SubsystemConstraints(
                        async_only=lc.async_only,
                        no_blocking_io=lc.no_blocking_io,
                        forbidden_dependencies=lc.forbidden_dependencies,
                        allowed_dependencies=lc.allowed_dependencies,
                    )
                    break

        metadata = {
            "source": "orchestrator",
            "cluster_count": len(pipeline_result.clusters),
        }

        return ContextPacket(
            focus=focus,
            focus_reasoning=focus_reasoning,
            constraints=constraints,
            subgraph=all_focus_files,
            relevant_files=relevant_files,
            metadata=metadata,
        )
