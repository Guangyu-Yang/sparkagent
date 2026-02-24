"""Tests for LLM-driven execution mode selector."""

from typing import Any

import pytest

from sparkagent.agent.mode_selector import CLASSIFICATION_PROMPT, select_execution_mode
from sparkagent.providers.base import LLMProvider, LLMResponse


class _MockProvider(LLMProvider):
    """Provider that returns a predetermined text response."""

    def __init__(self, response_text: str):
        super().__init__(api_key="test")
        self._response_text = response_text

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        return LLMResponse(content=self._response_text)

    def get_default_model(self) -> str:
        return "mock"


class TestSelectExecutionMode:
    """Tests for select_execution_mode."""

    @pytest.mark.asyncio
    async def test_returns_code_act(self):
        provider = _MockProvider("code_act")
        result = await select_execution_mode(provider, "mock", "batch rename files")
        assert result == "code_act"

    @pytest.mark.asyncio
    async def test_returns_function_calling(self):
        provider = _MockProvider("function_calling")
        result = await select_execution_mode(provider, "mock", "read README.md")
        assert result == "function_calling"

    @pytest.mark.asyncio
    async def test_falls_back_on_garbled_response(self):
        provider = _MockProvider("I'm not sure what to pick")
        result = await select_execution_mode(provider, "mock", "hello")
        assert result == "function_calling"

    @pytest.mark.asyncio
    async def test_falls_back_on_empty_response(self):
        provider = _MockProvider("")
        result = await select_execution_mode(provider, "mock", "hello")
        assert result == "function_calling"

    @pytest.mark.asyncio
    async def test_falls_back_on_none_content(self):
        provider = _MockProvider("")
        provider._response_text = None  # type: ignore[assignment]

        async def chat_none(*args: Any, **kwargs: Any) -> LLMResponse:
            return LLMResponse(content=None)

        provider.chat = chat_none  # type: ignore[assignment]
        result = await select_execution_mode(provider, "mock", "hello")
        assert result == "function_calling"

    @pytest.mark.asyncio
    async def test_case_insensitive(self):
        provider = _MockProvider("CODE_ACT")
        result = await select_execution_mode(provider, "mock", "loop over files")
        assert result == "code_act"

    @pytest.mark.asyncio
    async def test_extracts_code_act_from_surrounding_text(self):
        provider = _MockProvider("I think code_act is best here.")
        result = await select_execution_mode(provider, "mock", "transform data")
        assert result == "code_act"


class TestClassificationPrompt:
    """Tests for the classification prompt."""

    def test_prompt_mentions_both_modes(self):
        assert "function_calling" in CLASSIFICATION_PROMPT
        assert "code_act" in CLASSIFICATION_PROMPT

    def test_prompt_is_nonempty(self):
        assert len(CLASSIFICATION_PROMPT.strip()) > 0
