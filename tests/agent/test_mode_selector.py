"""Tests for LLM-driven execution mode selector."""

from typing import Any

import pytest

from sparkagent.agent.mode_selector import (
    CLASSIFICATION_PROMPT,
    MODE_SELECTION_TOOL,
    TOOL_CHOICE,
    select_execution_mode,
)
from sparkagent.providers.base import LLMProvider, LLMResponse, ToolCall


class _MockProvider(LLMProvider):
    """Provider that returns a predetermined response (tool call or text)."""

    def __init__(
        self,
        response_text: str | None = None,
        tool_calls: list[ToolCall] | None = None,
    ):
        super().__init__(api_key="test")
        self._response_text = response_text
        self._tool_calls = tool_calls or []

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        tool_choice: dict[str, Any] | str | None = None,
    ) -> LLMResponse:
        return LLMResponse(
            content=self._response_text,
            tool_calls=self._tool_calls,
        )

    def get_default_model(self) -> str:
        return "mock"


def _mode_tool_call(mode: str) -> list[ToolCall]:
    """Helper to create a tool call response for select_mode."""
    return [ToolCall(id="call_1", name="select_mode", arguments={"mode": mode})]


class TestStructuredOutput:
    """Tests for the structured output (tool call) path."""

    @pytest.mark.asyncio
    async def test_returns_function_calling_via_tool_call(self):
        provider = _MockProvider(tool_calls=_mode_tool_call("function_calling"))
        result = await select_execution_mode(provider, "mock", "read README.md")
        assert result == "function_calling"

    @pytest.mark.asyncio
    async def test_returns_code_act_via_tool_call(self):
        provider = _MockProvider(tool_calls=_mode_tool_call("code_act"))
        result = await select_execution_mode(provider, "mock", "batch rename files")
        assert result == "code_act"

    @pytest.mark.asyncio
    async def test_invalid_mode_in_tool_call_falls_back(self):
        tc = [ToolCall(id="call_1", name="select_mode", arguments={"mode": "invalid"})]
        provider = _MockProvider(tool_calls=tc)
        result = await select_execution_mode(provider, "mock", "hello")
        assert result == "function_calling"

    @pytest.mark.asyncio
    async def test_empty_arguments_falls_back(self):
        tc = [ToolCall(id="call_1", name="select_mode", arguments={})]
        provider = _MockProvider(tool_calls=tc)
        result = await select_execution_mode(provider, "mock", "hello")
        assert result == "function_calling"

    @pytest.mark.asyncio
    async def test_tool_choice_passed_to_provider(self):
        """Verify that tool_choice is actually passed through to the provider."""
        captured: dict[str, Any] = {}

        class _CapturingProvider(_MockProvider):
            async def chat(self, **kwargs: Any) -> LLMResponse:
                captured.update(kwargs)
                return LLMResponse(
                    tool_calls=_mode_tool_call("function_calling"),
                )

        provider = _CapturingProvider()
        await select_execution_mode(provider, "mock", "hello")
        assert captured["tool_choice"] == TOOL_CHOICE
        assert captured["tools"] == [MODE_SELECTION_TOOL]


class TestTextFallback:
    """Tests for the text-based fallback path (no tool calls)."""

    @pytest.mark.asyncio
    async def test_returns_code_act_from_text(self):
        provider = _MockProvider(response_text="code_act")
        result = await select_execution_mode(provider, "mock", "batch rename files")
        assert result == "code_act"

    @pytest.mark.asyncio
    async def test_returns_function_calling_from_text(self):
        provider = _MockProvider(response_text="function_calling")
        result = await select_execution_mode(provider, "mock", "read README.md")
        assert result == "function_calling"

    @pytest.mark.asyncio
    async def test_falls_back_on_garbled_response(self):
        provider = _MockProvider(response_text="I'm not sure what to pick")
        result = await select_execution_mode(provider, "mock", "hello")
        assert result == "function_calling"

    @pytest.mark.asyncio
    async def test_falls_back_on_empty_response(self):
        provider = _MockProvider(response_text="")
        result = await select_execution_mode(provider, "mock", "hello")
        assert result == "function_calling"

    @pytest.mark.asyncio
    async def test_falls_back_on_none_content(self):
        provider = _MockProvider(response_text=None)
        result = await select_execution_mode(provider, "mock", "hello")
        assert result == "function_calling"

    @pytest.mark.asyncio
    async def test_case_insensitive(self):
        provider = _MockProvider(response_text="CODE_ACT")
        result = await select_execution_mode(provider, "mock", "loop over files")
        assert result == "code_act"

    @pytest.mark.asyncio
    async def test_non_prefixed_response_defaults_to_function_calling(self):
        provider = _MockProvider(response_text="I think code_act is best here.")
        result = await select_execution_mode(provider, "mock", "transform data")
        assert result == "function_calling"


class TestClassificationPrompt:
    """Tests for the classification prompt."""

    def test_prompt_mentions_both_modes(self):
        assert "function_calling" in CLASSIFICATION_PROMPT
        assert "code_act" in CLASSIFICATION_PROMPT

    def test_prompt_is_nonempty(self):
        assert len(CLASSIFICATION_PROMPT.strip()) > 0

    def test_tool_schema_has_correct_enum(self):
        params = MODE_SELECTION_TOOL["function"]["parameters"]
        assert params["properties"]["mode"]["enum"] == ["function_calling", "code_act"]
