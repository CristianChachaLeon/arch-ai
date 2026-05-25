"""ArchAI - Cognitive Middleware for Architecture-Aware AI Coding Agents.

Main entry point for the ArchAI library.
"""

from archai.middleware import ArchaiMiddleware
from archai.middleware.pipeline import PipelineResult
from archai.orchestrator import ArchaiOrchestrator

__version__ = "0.1.0"

__all__ = ["ArchaiMiddleware", "PipelineResult", "ArchaiOrchestrator"]
