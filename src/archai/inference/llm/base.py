"""Abstract LLM provider interface.

Defines the contract that all LLM providers must implement,
allowing downstream modules (labeler, constraint_inferrer)
to depend on an abstraction rather than a concrete API.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMError(Exception):
    """Base exception for all LLM provider errors.

    Raised when an LLM call fails, times out, returns unexpected
    output, or the provider is misconfigured.
    """


class LLMProvider(ABC):
    """Abstract interface for LLM providers.

    Implementations must provide async text generation via ``generate()``.
    Structured generation (``generate_structured()``) has a default
    implementation that wraps ``generate()`` with JSON parsing;
    subclasses may override it to use native structured-output APIs.
    """

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> str:
        """Generate text from the LLM.

        Args:
            prompt: The user prompt to send.
            system_prompt: Optional system-level instruction.
            temperature: Sampling temperature (0.0-1.0).
            max_tokens: Maximum tokens in the response.

        Returns:
            Generated text content.

        Raises:
            LLMError: If the LLM call fails or returns an empty response.
        """

    async def generate_structured(
        self,
        prompt: str,
        response_model: type[Any],
        system_prompt: str | None = None,
        temperature: float = 0.1,
    ) -> Any:
        """Generate a structured (JSON) response from the LLM.

        Default implementation: appends a JSON instruction to the
        system prompt, calls ``generate()``, and parses the result
        into the given Pydantic model.

        Override in subclasses to use native structured-output APIs
        (e.g. OpenAI ``response_format`` or Anthropic ````).

        Args:
            prompt: The user prompt to send.
            response_model: Pydantic model class for the response.
            system_prompt: Optional system-level instruction.
            temperature: Sampling temperature (0.0-1.0).

        Returns:
            An instance of *response_model* with parsed data.

        Raises:
            LLMError: If the LLM call or JSON parsing fails.
        """
        json_instruction = (
            "You must respond with valid JSON only — no markdown formatting, "
            "no explanation. The JSON must match the requested schema."
        )
        combined_system = (
            f"{system_prompt}\n\n{json_instruction}" if system_prompt else json_instruction
        )

        content = await self.generate(
            prompt=prompt,
            system_prompt=combined_system,
            temperature=temperature,
        )

        try:
            return response_model.model_validate_json(content)
        except Exception as exc:
            raise LLMError(
                f"Failed to parse LLM response as {response_model.__name__}: {exc}"
            ) from exc
