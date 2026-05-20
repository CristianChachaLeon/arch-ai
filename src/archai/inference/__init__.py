"""Inference Engine - Cognitive middleware for architecture-aware AI coding agents.

This package contains the inference engine components that analyze code structure
and detect patterns, clusters, and relationships.
"""

from archai.inference.clustering import cluster_files
from archai.inference.labeler import label_clusters
from archai.inference.llm.base import LLMError, LLMProvider
from archai.inference.llm.litellm_provider import LiteLLMProvider

__all__ = [
    "cluster_files",
    "label_clusters",
    "LLMError",
    "LLMProvider",
    "LiteLLMProvider",
]
