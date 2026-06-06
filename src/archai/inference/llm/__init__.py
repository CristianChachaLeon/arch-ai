"""LLM Provider package.

Provides a pluggable abstraction for LLM interactions used by
downstream inference modules (labeler, constraint_inferrer).

Note: LiteLLMProvider was removed in SDD-003. archai is now a pure
structural analysis engine without LLM dependencies. The LLMProvider
ABC remains for anyone implementing their own provider.
"""

from archai.inference.llm.base import LLMError, LLMProvider

__all__ = [
    "LLMError",
    "LLMProvider",
]
