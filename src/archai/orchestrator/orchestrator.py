"""ArchaiOrchestrator - Orchestrates bootstrap + inference + focus resolution.

This module provides the main orchestrator that connects the middleware
pipeline with focus resolution to produce architecture-aware context packets.
"""

import asyncio

from archai.http.models import ContextPacket, FileMetadata, SubsystemConstraints
from archai.middleware.pipeline import PipelineResult
from archai.orchestrator.focus_resolver import resolve_focus


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

        relevant_files = [
            FileMetadata(path=file, reason="part of focus subsystem", importance=1.0)
            for file in subgraph
        ]

        constraints = SubsystemConstraints()

        metadata = {
            "source": "orchestrator",
            "cluster_count": len(pipeline_result.clusters),
        }

        return ContextPacket(
            focus=focus,
            focus_reasoning=focus_reasoning,
            constraints=constraints,
            subgraph=subgraph,
            relevant_files=relevant_files,
            metadata=metadata,
        )
