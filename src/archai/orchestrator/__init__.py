"""Context Orchestrator - Focus resolution, subgraph extraction, and constraint injection.

This package contains the context orchestrator components that build
architecture-aware context packets from user queries.
"""

from archai.orchestrator.focus_resolver import resolve_focus
from archai.orchestrator.orchestrator import ArchaiOrchestrator

__all__ = [
    "resolve_focus",
    "ArchaiOrchestrator",
]
