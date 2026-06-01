"""LiteLLM-based LLM provider (T-021).

Concrete ``LLMProvider`` implementation using the ``litellm`` library,
which itself supports OpenAI, Anthropic, Google, and many other providers
through a unified completion interface.

Configuration
-------------
API keys are read from environment variables by litellm automatically:

* ``ANTHROPIC_API_KEY`` – for Anthropic (Claude) models
* ``OPENAI_API_KEY``   – for OpenAI (GPT) models
* ``GEMINI_API_KEY``   – for Google Gemini models
* etc.

See ``litellm`` documentation for the full list.

Usage::

    provider = LiteLLMProvider(model="claude-sonnet-4-20250514")
    text = await provider.generate("Explain dependency injection")
"""

from __future__ import annotations

import logging

import litellm

from archai.inference.llm.base import LLMError, LLMProvider

logger = logging.getLogger(__name__)


class LiteLLMProvider(LLMProvider):
    """LLM provider backed by ``litellm``.

    Parameters
    ----------
    model:
        Model identifier understood by litellm
        (e.g. ``"claude-sonnet-4-20250514"``, ``"gpt-4o"``).
        Defaults to ``DEFAULT_MODEL``.
    api_base:
        Optional base URL for the API provider.
    api_key:
        Optional API key (overrides environment variable).
    request_timeout:
        Time-out in seconds for each API call.
    """

    DEFAULT_MODEL = "claude-sonnet-4-20250514"

    def __init__(
        self,
        model: str | None = None,
        api_base: str | None = None,
        api_key: str | None = None,
        request_timeout: int = 120,
    ) -> None:
        self.model = model or self.DEFAULT_MODEL
        self.api_base = api_base
        self.api_key = api_key
        self.request_timeout = request_timeout
        logger.info(
            "LiteLLMProvider initialized with model=%s api_base=%s",
            self.model,
            self.api_base or "default",
        )

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        """Generate text via ``litellm.acompletion``."""
        messages = self._build_messages(prompt, system_prompt)

        completion_kwargs = dict(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=self.request_timeout,
        )
        if self.api_base is not None:
            completion_kwargs["api_base"] = self.api_base
        if self.api_key is not None:
            completion_kwargs["api_key"] = self.api_key

        try:
            response = await litellm.acompletion(**completion_kwargs)
        except Exception as exc:
            raise LLMError(f"LLM call failed: {exc}") from exc

        try:
            content = response.choices[0].message.content
        except (IndexError, AttributeError, KeyError, TypeError) as exc:
            raise LLMError(f"Malformed response from LLM: {exc}") from exc

        if content is None:
            raise LLMError("LLM returned empty response")
        return content

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_messages(prompt: str, system_prompt: str | None = None) -> list[dict[str, str]]:
        """Build the messages array expected by litellm."""
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages
