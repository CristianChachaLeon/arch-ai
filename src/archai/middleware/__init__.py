"""ArchAI Middleware - Orchestrates bootstrap + inference pipeline.

This module provides the main entry point for the ArchAI middleware:
- Bootstrapping: File discovery, AST parsing, dependency resolution, graph building
- Inference: Clustering files into logical subsystems
"""

from archai.middleware.pipeline import ArchaiMiddleware

__all__ = ["ArchaiMiddleware"]
