"""Tests for LLM providers."""

from typing import Any

import pytest

from sparkagent.providers.base import LLMProvider, LLMResponse, ToolCall


class TestToolCall:
    """Tests for ToolCall dataclass."""

    def test_create_tool_call(self):
        tc = ToolCall(
            id="call_123",
            name="read_file",
            arguments={"path": "/test/file.txt"}
        )

        assert tc.id == "call_123"
        assert tc.name == "read_file"
        assert tc.arguments == {"path": "/test/file.txt"}


class TestLLMResponse:
    """Tests for LLMResponse dataclass."""

    def test_default_values(self):
        response = LLMResponse()

        assert response.content is None
        assert response.tool_calls == []
        assert response.finish_reason == "stop"
        assert response.usage == {}

    def test_with_content(self):
        response = LLMResponse(content="Hello!")

        assert response.content == "Hello!"
        assert response.has_tool_calls is False

    def test_with_tool_calls(self):
        tc = ToolCall(id="1", name="test", arguments={})
        response = LLMResponse(tool_calls=[tc])

        assert response.has_tool_calls is True
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].name == "test"

    def test_has_tool_calls_empty(self):
        response = LLMResponse(tool_calls=[])

        assert response.has_tool_calls is False

    def test_with_usage(self):
        response = LLMResponse(
            content="Response",
            usage={"prompt_tokens": 10, "completion_tokens": 20}
        )

        assert response.usage["prompt_tokens"] == 10
        assert response.usage["completion_tokens"] == 20

    def test_finish_reasons(self):
        stop_response = LLMResponse(finish_reason="stop")
        tool_response = LLMResponse(finish_reason="tool_calls")
        length_response = LLMResponse(finish_reason="length")

        assert stop_response.finish_reason == "stop"
        assert tool_response.finish_reason == "tool_calls"
        assert length_response.finish_reason == "length"


class MockLLMProvider(LLMProvider):
    """A mock LLM provider for testing."""

    def __init__(self, response: LLMResponse | None = None):
        super().__init__(api_key="test-key", api_base="https://test.api.com")
        self._response = response or LLMResponse(content="Mock response")

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        return self._response

    def get_default_model(self) -> str:
        return "mock-model"


class TestLLMProvider:
    """Tests for LLMProvider base class."""

    def test_init(self):
        provider = MockLLMProvider()

        assert provider.api_key == "test-key"
        assert provider.api_base == "https://test.api.com"

    def test_init_none_values(self):
        class SimpleProvider(LLMProvider):
            async def chat(self, messages, tools=None, model=None, max_tokens=4096, temperature=0.7):
                return LLMResponse()

            def get_default_model(self):
                return "simple"

        provider = SimpleProvider()

        assert provider.api_key is None
        assert provider.api_base is None

    def test_get_default_model(self):
        provider = MockLLMProvider()

        assert provider.get_default_model() == "mock-model"

    async def test_chat(self):
        expected = LLMResponse(content="Custom response")
        provider = MockLLMProvider(response=expected)

        result = await provider.chat(messages=[{"role": "user", "content": "Hello"}])

        assert result is expected
        assert result.content == "Custom response"

    async def test_chat_with_tools(self):
        tc = ToolCall(id="1", name="test_tool", arguments={"arg": "value"})
        expected = LLMResponse(tool_calls=[tc], finish_reason="tool_calls")
        provider = MockLLMProvider(response=expected)

        result = await provider.chat(
            messages=[{"role": "user", "content": "Use the tool"}],
            tools=[{"type": "function", "function": {"name": "test_tool"}}]
        )

        assert result.has_tool_calls is True
        assert result.tool_calls[0].name == "test_tool"


class TestLLMProviderInterface:
    """Tests to verify provider interface requirements."""

    def test_provider_is_abstract(self):
        # Should not be able to instantiate directly
        with pytest.raises(TypeError):
            LLMProvider()  # type: ignore

    def test_provider_requires_chat_method(self):
        class IncompleteProvider(LLMProvider):
            def get_default_model(self):
                return "test"

        with pytest.raises(TypeError):
            IncompleteProvider()  # type: ignore

    def test_provider_requires_get_default_model(self):
        class IncompleteProvider(LLMProvider):
            async def chat(self, messages, tools=None, model=None, max_tokens=4096, temperature=0.7):
                return LLMResponse()

        with pytest.raises(TypeError):
            IncompleteProvider()  # type: ignore
