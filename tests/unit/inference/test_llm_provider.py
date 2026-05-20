"""Tests for LLM provider abstraction."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from archai.inference.llm.base import LLMError, LLMProvider
from archai.inference.llm.litellm_provider import LiteLLMProvider


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def sample_model() -> type[BaseModel]:
    """A simple Pydantic model for structured output tests."""

    class SampleModel(BaseModel):
        name: str
        count: int

    return SampleModel


@pytest.fixture
def mock_litellm_response() -> MagicMock:
    """Simulate a litellm acompletion response."""
    choice = MagicMock()
    choice.message.content = "Hello, world!"

    response = MagicMock()
    response.choices = [choice]
    return response


# ── ABC Contract Tests ────────────────────────────────────────────────


class TestLLMProviderABC:
    """Verify the abstract base class enforces the expected contract."""

    def test_cannot_instantiate_abc_directly(self):
        """LLMProvider should not be instantiable directly."""
        with pytest.raises(TypeError):
            LLMProvider()  # type: ignore[abstract]

    def test_subclass_must_implement_generate(self):
        """Subclasses without generate() should not be instantiable."""

        class IncompleteProvider(LLMProvider):
            pass

        with pytest.raises(TypeError):
            IncompleteProvider()  # type: ignore[abstract]


# ── LiteLLMProvider Tests ─────────────────────────────────────────────


class TestLiteLLMProviderInit:
    """Provider initialization."""

    def test_default_model(self):
        provider = LiteLLMProvider()
        assert provider.model == LiteLLMProvider.DEFAULT_MODEL

    def test_custom_model(self):
        provider = LiteLLMProvider(model="gpt-4o-mini")
        assert provider.model == "gpt-4o-mini"

    def test_custom_timeout(self):
        provider = LiteLLMProvider(request_timeout=30)
        assert provider.request_timeout == 30

    def test_is_llm_provider(self):
        provider = LiteLLMProvider()
        assert isinstance(provider, LLMProvider)


class TestLiteLLMProviderGenerate:
    """Text generation."""

    @patch("archai.inference.llm.litellm_provider.litellm.acompletion")
    async def test_generate_returns_text(
        self, mock_acompletion: AsyncMock, mock_litellm_response: MagicMock
    ):
        mock_acompletion.return_value = mock_litellm_response
        provider = LiteLLMProvider(model="gpt-4o-mini")

        result = await provider.generate(prompt="Say hello")

        assert result == "Hello, world!"
        mock_acompletion.assert_awaited_once()

    @patch("archai.inference.llm.litellm_provider.litellm.acompletion")
    async def test_generate_with_system_prompt(
        self, mock_acompletion: AsyncMock, mock_litellm_response: MagicMock
    ):
        mock_acompletion.return_value = mock_litellm_response
        provider = LiteLLMProvider(model="gpt-4o-mini")

        await provider.generate(
            prompt="Summarize this",
            system_prompt="You are a helpful assistant",
        )

        kwargs = mock_acompletion.await_args.kwargs
        messages = kwargs.get("messages", [])
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are a helpful assistant"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Summarize this"

    @patch("archai.inference.llm.litellm_provider.litellm.acompletion")
    async def test_generate_passes_parameters(
        self, mock_acompletion: AsyncMock, mock_litellm_response: MagicMock
    ):
        mock_acompletion.return_value = mock_litellm_response
        provider = LiteLLMProvider(model="gpt-4o-mini", request_timeout=30)

        await provider.generate(
            prompt="Test",
            temperature=0.7,
            max_tokens=512,
        )

        kwargs = mock_acompletion.await_args.kwargs
        assert kwargs.get("model") == "gpt-4o-mini"
        assert kwargs.get("temperature") == 0.7
        assert kwargs.get("max_tokens") == 512
        assert kwargs.get("timeout") == 30

    @patch("archai.inference.llm.litellm_provider.litellm.acompletion")
    async def test_generate_raises_llm_error_on_api_failure(self, mock_acompletion: AsyncMock):
        mock_acompletion.side_effect = ConnectionError("API unreachable")
        provider = LiteLLMProvider(model="gpt-4o-mini")

        with pytest.raises(LLMError, match="LLM call failed"):
            await provider.generate(prompt="Test")

    @patch("archai.inference.llm.litellm_provider.litellm.acompletion")
    async def test_generate_raises_llm_error_on_empty_response(self, mock_acompletion: AsyncMock):
        choice = MagicMock()
        choice.message.content = None
        response = MagicMock()
        response.choices = [choice]
        mock_acompletion.return_value = response
        provider = LiteLLMProvider(model="gpt-4o-mini")

        with pytest.raises(LLMError, match="empty response"):
            await provider.generate(prompt="Test")

    @patch("archai.inference.llm.litellm_provider.litellm.acompletion")
    async def test_generate_raises_llm_error_on_empty_choices(self, mock_acompletion: AsyncMock):
        response = MagicMock()
        response.choices = []
        mock_acompletion.return_value = response
        provider = LiteLLMProvider(model="gpt-4o-mini")

        with pytest.raises(LLMError, match="Malformed response from LLM"):
            await provider.generate(prompt="Test")

    @patch("archai.inference.llm.litellm_provider.litellm.acompletion")
    async def test_generate_raises_llm_error_on_missing_choices(self, mock_acompletion: AsyncMock):
        response = MagicMock(spec=[])  # no .choices attribute
        mock_acompletion.return_value = response
        provider = LiteLLMProvider(model="gpt-4o-mini")

        with pytest.raises(LLMError, match="Malformed response from LLM"):
            await provider.generate(prompt="Test")

    @patch("archai.inference.llm.litellm_provider.litellm.acompletion")
    async def test_generate_raises_llm_error_on_no_message(self, mock_acompletion: AsyncMock):
        choice = MagicMock(spec=[])  # no .message attribute
        response = MagicMock()
        response.choices = [choice]
        mock_acompletion.return_value = response
        provider = LiteLLMProvider(model="gpt-4o-mini")

        with pytest.raises(LLMError, match="Malformed response from LLM"):
            await provider.generate(prompt="Test")

    @patch("archai.inference.llm.litellm_provider.litellm.acompletion")
    async def test_generate_raises_llm_error_on_none_message(self, mock_acompletion: AsyncMock):
        choice = MagicMock()
        choice.message = None
        response = MagicMock()
        response.choices = [choice]
        mock_acompletion.return_value = response
        provider = LiteLLMProvider(model="gpt-4o-mini")

        with pytest.raises(LLMError, match="Malformed response from LLM"):
            await provider.generate(prompt="Test")


class TestLiteLLMProviderGenerateStructured:
    """Structured (JSON) generation."""

    @patch("archai.inference.llm.litellm_provider.litellm.acompletion")
    async def test_generate_structured_returns_model(
        self,
        mock_acompletion: AsyncMock,
        sample_model: type[BaseModel],
    ):
        choice = MagicMock()
        choice.message.content = '{"name": "test", "count": 42}'
        response = MagicMock()
        response.choices = [choice]
        mock_acompletion.return_value = response
        provider = LiteLLMProvider(model="gpt-4o-mini")

        result = await provider.generate_structured(
            prompt="Generate data",
            response_model=sample_model,
        )

        assert isinstance(result, sample_model)
        assert result.name == "test"
        assert result.count == 42

    @patch("archai.inference.llm.litellm_provider.litellm.acompletion")
    async def test_generate_structured_includes_json_instruction(
        self,
        mock_acompletion: AsyncMock,
        sample_model: type[BaseModel],
    ):
        choice = MagicMock()
        choice.message.content = '{"name": "x", "count": 1}'
        response = MagicMock()
        response.choices = [choice]
        mock_acompletion.return_value = response
        provider = LiteLLMProvider(model="gpt-4o-mini")

        await provider.generate_structured(
            prompt="Generate data",
            response_model=sample_model,
            system_prompt="You are a data generator",
        )

        kwargs = mock_acompletion.await_args.kwargs
        messages = kwargs.get("messages", [])
        system_content = messages[0]["content"]
        assert "JSON" in system_content
        assert "You are a data generator" in system_content

    @patch("archai.inference.llm.litellm_provider.litellm.acompletion")
    async def test_generate_structured_parsing_error(
        self,
        mock_acompletion: AsyncMock,
        sample_model: type[BaseModel],
    ):
        choice = MagicMock()
        choice.message.content = "not valid json"
        response = MagicMock()
        response.choices = [choice]
        mock_acompletion.return_value = response
        provider = LiteLLMProvider(model="gpt-4o-mini")

        with pytest.raises(LLMError, match="Failed to parse"):
            await provider.generate_structured(
                prompt="Generate data",
                response_model=sample_model,
            )


class TestLiteLLMProviderEdgeCases:
    """Edge cases and error conditions."""

    @patch("archai.inference.llm.litellm_provider.litellm.acompletion")
    async def test_empty_system_prompt(
        self, mock_acompletion: AsyncMock, mock_litellm_response: MagicMock
    ):
        """Empty system prompt should be treated as no system prompt."""
        mock_acompletion.return_value = mock_litellm_response
        provider = LiteLLMProvider(model="gpt-4o-mini")

        await provider.generate(prompt="Hi", system_prompt="")

        kwargs = mock_acompletion.await_args.kwargs
        messages = kwargs.get("messages", [])
        assert len(messages) == 1  # only user message
        assert messages[0]["role"] == "user"

    @patch("archai.inference.llm.litellm_provider.litellm.acompletion")
    async def test_long_prompt(self, mock_acompletion: AsyncMock):
        """Should handle long prompts without truncation."""
        choice = MagicMock()
        choice.message.content = "done"
        response = MagicMock()
        response.choices = [choice]
        mock_acompletion.return_value = response
        provider = LiteLLMProvider(model="gpt-4o-mini")

        long_prompt = "word " * 10_000
        result = await provider.generate(prompt=long_prompt)

        assert result == "done"

    async def test_default_timeout(self):
        provider = LiteLLMProvider()
        assert provider.request_timeout == 120
