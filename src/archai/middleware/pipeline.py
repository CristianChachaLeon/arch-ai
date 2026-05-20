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
    discover_python_files,
    parse_python_file,
    get_imports,
    get_functions,
    get_classes,
    resolve_imports,
    FileNode,
    FileGraph,
    build_graph,
)
from archai.inference.clustering import cluster_files
from archai.inference.labeler import LabeledCluster, label_clusters
from archai.inference.llm.base import LLMProvider

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
            labeled_clusters = await label_clusters(clusters, self.llm_provider)
            logger.info(f"Labeled {len(labeled_clusters)} clusters")

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
        1. File Discovery - find all .py files
        2. AST Parsing - extract imports, functions, classes
        3. Dependency Resolution - resolve imports to relative paths
        4. Graph Building - create NetworkX graph
        """
        logger.info("Running bootstrap pipeline...")

        # Step 1: File Discovery
        repo = Path(repo_path)
        files = discover_python_files(repo)
        logger.debug(f"Discovered {len(files)} Python files")

        # Step 2: AST Parsing
        file_nodes: List[FileNode] = []
        errors: List[tuple[str, str]] = []

        for f in files:
            try:
                tree = parse_python_file(f)
                imports = get_imports(tree)
                functions = get_functions(tree)
                classes = get_classes(tree)

                rel_path = str(f.relative_to(repo))
                node = FileNode(
                    path=rel_path,
                    imports=imports,
                    functions=functions,
                    classes=classes,
                )
                file_nodes.append(node)

            except (SyntaxError, UnicodeDecodeError, OSError) as e:
                errors.append((f.name, str(e)))
                logger.warning(f"Failed to parse {f.name}: {e}")
            except Exception:
                logger.exception("Unexpected bootstrap failure while parsing %s", f)
                raise

        logger.debug(f"Parsed {len(file_nodes)} files, {len(errors)} errors")

        # Step 3: Dependency Resolution
        resolved_nodes = resolve_imports(file_nodes)
        logger.debug(f"Resolved imports for {len(resolved_nodes)} files")

        # Step 4: Graph Building
        graph = build_graph(resolved_nodes)
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
        return data

    def __repr__(self) -> str:
        return (
            f"PipelineResult(files={self.file_count}, "
            f"edges={self.edge_count}, clusters={self.cluster_count})"
        )
