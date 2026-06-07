"""ArchAI Middleware Pipeline - Orchestrates bootstrap + inference.

This module provides the main middleware that connects:
1. Bootstrapping Engine (file discovery -> graph building)
2. Inference Engine (clustering)

Usage:
    from archai.middleware import ArchaiMiddleware

    middleware = ArchaiMiddleware()
    result = middleware.process("/path/to/repo")
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

from archai.bootstrap import (
    discover_files,
    FileNode,
    FileGraph,
    build_graph,
    detect_languages,
    ParsedFile,
    LangHandler,
)
from archai.inference.clustering import cluster_files
from archai.inference.labeler import LabeledCluster, label_clusters
from archai.inference.llm.base import LLMError, LLMProvider

logger = logging.getLogger(__name__)


class ArchaiMiddleware:
    """Main middleware that orchestrates the bootstrap + inference pipeline."""

    def __init__(self, llm_provider: LLMProvider | None = None):
        """Initialize the middleware.

        Args:
            llm_provider: Optional LLM provider for semantic labeling of clusters.
        """
        self.llm_provider = llm_provider
        logger.info("ArchaiMiddleware initialized")

    async def process(self, repo_path: str | Path) -> PipelineResult:
        """Process a repository through the full pipeline.

        Args:
            repo_path: Path to the repository to process

        Returns:
            PipelineResult containing graph, clusters, and metadata
        """
        logger.info(f"Processing repository: {repo_path}")

        # Step 1-4: Bootstrap
        graph = self._run_bootstrap(repo_path)

        # Step 5: Inference (clustering)
        clusters = self._run_inference(graph)

        # Step 6: Semantic labeling (optional)
        labeled_clusters = None
        if self.llm_provider is not None:
            logger.info("Labeling clusters using LLM...")
            try:
                labeled_clusters = await label_clusters(clusters, self.llm_provider)
                logger.info(f"Labeled {len(labeled_clusters)} clusters")
            except LLMError:
                logger.exception("Failed to label clusters, proceeding without labels")

        result = PipelineResult(
            repo_path=str(repo_path),
            graph=graph,
            clusters=clusters,
            file_count=graph.graph.number_of_nodes(),
            edge_count=graph.graph.number_of_edges(),
            cluster_count=len(clusters),
            labeled_clusters=labeled_clusters,
        )

        logger.info(
            f"Pipeline complete: {result.file_count} files, "
            f"{result.edge_count} edges, {result.cluster_count} clusters"
        )

        return result

    def _run_bootstrap(self, repo_path: str | Path) -> FileGraph:
        """Run the bootstrapping pipeline.

        Steps:
        1. Language Detection - detect which languages are used
        2. File Discovery + AST Parsing (per language)
        3. Dependency Resolution (second pass)
        4. Graph Building - create NetworkX graph
        """
        logger.info("Running bootstrap pipeline...")
        repo = Path(repo_path)

        if not repo.is_dir():
            raise ValueError(f"Path is not a directory: {repo}")

        # Step 1: Detect languages
        handlers = detect_languages(repo)
        if not handlers:
            logger.warning(f"No known languages detected in {repo}")
            return build_graph([])

        # Build extension -> handler mapping for resolution
        handler_by_ext: dict[str, LangHandler] = {}
        for h in handlers:
            for ext in h.extensions:
                if ext in handler_by_ext:
                    logger.warning(
                        "Extension %s already registered by %s, skipping %s",
                        ext,
                        handler_by_ext[ext].language,
                        h.language,
                    )
                    continue
                handler_by_ext[ext] = h

        # Step 2-3: Discover + Parse files for each language
        all_parsed: list[ParsedFile] = []
        all_file_paths: set[str] = set()
        errors_count = 0

        for handler in handlers:
            files = discover_files(repo, handler.extensions, handler.excluded_dirs)

            for f in files:
                try:
                    parsed = handler.parse(f)
                    rel_path = str(f.relative_to(repo))
                    parsed.path = rel_path  # Use relative path for resolution
                    all_parsed.append(parsed)
                    all_file_paths.add(rel_path)

                except (SyntaxError, UnicodeDecodeError, OSError) as e:
                    errors_count += 1
                    logger.warning(f"Failed to parse {f.name}: {e}")
                except Exception:
                    logger.exception("Unexpected bootstrap failure while parsing %s", f)
                    raise

        logger.debug("Parsed %d files with %d errors", len(all_parsed), errors_count)

        # Step 4: Resolve imports (second pass — needs all parsed files)
        file_nodes: list[FileNode] = []
        for parsed in all_parsed:
            ext = Path(parsed.path).suffix
            h = handler_by_ext.get(ext)
            if h is None:
                logger.warning(f"No handler for extension {ext} in {parsed.path}")
                file_nodes.append(
                    FileNode(
                        path=parsed.path,
                        imports=[],
                        functions=parsed.functions,
                        classes=parsed.classes,
                    )
                )
                continue

            resolved_imports: list[str] = []
            for imp in parsed.imports:
                resolved = h.resolve_import(imp, parsed.path, all_file_paths, repo)
                if resolved:
                    resolved_imports.append(resolved)

            file_nodes.append(
                FileNode(
                    path=parsed.path,
                    imports=resolved_imports,
                    functions=parsed.functions,
                    classes=parsed.classes,
                )
            )

        logger.debug(f"Resolved imports for {len(file_nodes)} files")

        # Step 5: Graph Building
        graph = build_graph(file_nodes)
        logger.debug(f"Built graph with {graph.graph.number_of_nodes()} nodes")

        return graph

    def _run_inference(self, graph: "FileGraph") -> Dict[str, List[str]]:
        """Run the inference pipeline (clustering).

        Args:
            graph: The FileGraph from bootstrapping

        Returns:
            Dict mapping cluster names to lists of file paths
        """
        logger.info("Running inference (clustering)...")

        clusters = cluster_files(graph)
        logger.debug(f"Found {len(clusters)} clusters")

        return clusters


class PipelineResult:
    """Result of the middleware pipeline."""

    def __init__(
        self,
        repo_path: str,
        graph: FileGraph,
        clusters: Dict[str, List[str]],
        file_count: int,
        edge_count: int,
        cluster_count: int,
        labeled_clusters: list[LabeledCluster] | None = None,
    ):
        self.repo_path = repo_path
        self.graph = graph
        self.clusters = clusters
        self.file_count = file_count
        self.edge_count = edge_count
        self.cluster_count = cluster_count
        self.labeled_clusters = labeled_clusters

    def get_cluster_for_file(self, file_path: str) -> Optional[str]:
        """Find which cluster a file belongs to."""
        for cluster_name, files in self.clusters.items():
            if file_path in files:
                return cluster_name
        return None

    def get_files_in_cluster(self, cluster_name: str) -> List[str]:
        """Get all files in a specific cluster."""
        return list(self.clusters.get(cluster_name, []))

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        data = {
            "repo_path": self.repo_path,
            "file_count": self.file_count,
            "edge_count": self.edge_count,
            "cluster_count": self.cluster_count,
            "clusters": {name: sorted(files) for name, files in self.clusters.items()},
        }
        if self.labeled_clusters is not None:
            data["cluster_names"] = {lc.cluster_id: lc.name for lc in self.labeled_clusters}
            data["cluster_descriptions"] = {
                lc.cluster_id: lc.description for lc in self.labeled_clusters
            }
            data["cluster_reasonings"] = {
                lc.cluster_id: lc.reasoning for lc in self.labeled_clusters
            }
        return data

    def __repr__(self) -> str:
        return (
            f"PipelineResult(files={self.file_count}, "
            f"edges={self.edge_count}, clusters={self.cluster_count})"
        )
