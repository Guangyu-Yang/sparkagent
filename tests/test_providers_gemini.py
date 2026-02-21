"""Tests for the Gemini LLM provider."""

import sys
import types as builtin_types
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Mock the google.genai SDK so that the test suite works even when the
# optional `google-genai` package is not installed.
# ---------------------------------------------------------------------------

# Create mock modules before importing GeminiProvider
_genai_module = MagicMock()
_types_module = MagicMock()

# Make types.Content / types.Part.from_text return distinguishable objects
# so we can verify the conversion logic in _convert_messages.
_types_module.Content = MagicMock(side_effect=lambda **kw: {"__Content__": True, **kw})
_types_module.Part.from_text = MagicMock(side_effect=lambda text: {"__Part__": True, "text": text})
_types_module.FunctionDeclaration = MagicMock(
    side_effect=lambda **kw: {"__FunctionDeclaration__": True, **kw}
)
_types_module.Tool = MagicMock(
    side_effect=lambda **kw: {"__Tool__": True, **kw}
)
_types_module.GenerateContentConfig = MagicMock(
    side_effect=lambda **kw: MagicMock(**kw)
)

# Wire the mock into sys.modules so `from google import genai` works.
_google_module = builtin_types.ModuleType("google")
_google_module.genai = _genai_module  # type: ignore[attr-defined]

sys.modules.setdefault("google", _google_module)
sys.modules.setdefault("google.genai", _genai_module)
sys.modules.setdefault("google.genai.types", _types_module)

_genai_module.Client = MagicMock()
_genai_module.types = _types_module

# Now it is safe to import the provider under test.
from sparkagent.providers.base import LLMResponse  # noqa: E402, I001
from sparkagent.providers.gemini import GeminiProvider  # noqa: E402, I001


# ---------------------------------------------------------------------------
# Helpers for building mock Gemini responses
# ---------------------------------------------------------------------------


def _make_text_part(text: str) -> MagicMock:
    """Return a mock Gemini Part that contains text only."""
    part = MagicMock()
    part.text = text
    part.function_call = None
    return part


def _make_function_call_part(
    name: str, args: dict | None = None
) -> MagicMock:
    """Return a mock Gemini Part that contains a function_call."""
    part = MagicMock()
    part.text = None
    part.function_call.name = name
    part.function_call.args = args
    return part


def _make_gemini_response(
    parts: list[MagicMock],
    finish_reason_name: str = "STOP",
    prompt_tokens: int = 10,
    completion_tokens: int = 20,
    total_tokens: int = 30,
) -> MagicMock:
    """Build a full mock Gemini API response."""
    candidate = MagicMock()
    candidate.content.parts = parts
    candidate.finish_reason.name = finish_reason_name

    response = MagicMock()
    response.candidates = [candidate]
    response.usage_metadata.prompt_token_count = prompt_tokens
    response.usage_metadata.candidates_token_count = completion_tokens
    response.usage_metadata.total_token_count = total_tokens
    return response


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGeminiProviderInit:
    """Tests for provider construction."""

    def test_default_model(self):
        provider = GeminiProvider(api_key="test-key")
        assert provider.get_default_model() == "gemini-2.5-flash"

    def test_custom_default_model(self):
        provider = GeminiProvider(api_key="test-key", default_model="gemini-2.0-pro")
        assert provider.get_default_model() == "gemini-2.0-pro"

    def test_stores_api_key(self):
        provider = GeminiProvider(api_key="my-api-key")
        assert provider.api_key == "my-api-key"

    def test_creates_client(self):
        _genai_module.Client.reset_mock()
        GeminiProvider(api_key="key-123")
        _genai_module.Client.assert_called_once_with(api_key="key-123")

    def test_default_timeout(self):
        provider = GeminiProvider(api_key="k")
        assert provider.timeout == 120.0

    def test_custom_timeout(self):
        provider = GeminiProvider(api_key="k", timeout=60.0)
        assert provider.timeout == 60.0


class TestConvertMessages:
    """Tests for _convert_messages (OpenAI format -> Gemini format)."""

    def setup_method(self):
        self.provider = GeminiProvider(api_key="test-key")

    def test_system_message_extracted(self):
        messages = [{"role": "system", "content": "You are helpful."}]
        system_instruction, contents = self.provider._convert_messages(messages)

        assert system_instruction == "You are helpful."
        assert contents == []

    def test_user_message(self):
        messages = [{"role": "user", "content": "Hello"}]
        system_instruction, contents = self.provider._convert_messages(messages)

        assert system_instruction is None
        assert len(contents) == 1
        _types_module.Content.assert_called()
        # Verify the role passed was "user"
        call_kwargs = _types_module.Content.call_args_list[-1].kwargs
        assert call_kwargs["role"] == "user"

    def test_assistant_mapped_to_model(self):
        messages = [{"role": "assistant", "content": "Hi there"}]
        _, contents = self.provider._convert_messages(messages)

        assert len(contents) == 1
        call_kwargs = _types_module.Content.call_args_list[-1].kwargs
        assert call_kwargs["role"] == "model"

    def test_tool_role_mapped_to_user(self):
        messages = [{"role": "tool", "content": "tool result"}]
        _, contents = self.provider._convert_messages(messages)

        assert len(contents) == 1
        call_kwargs = _types_module.Content.call_args_list[-1].kwargs
        assert call_kwargs["role"] == "user"

    def test_mixed_messages(self):
        messages = [
            {"role": "system", "content": "Be concise."},
            {"role": "user", "content": "What is 2+2?"},
            {"role": "assistant", "content": "4"},
            {"role": "user", "content": "Thanks"},
        ]
        system_instruction, contents = self.provider._convert_messages(messages)

        assert system_instruction == "Be concise."
        # 3 non-system messages
        assert len(contents) == 3

    def test_empty_content_defaults_to_empty_string(self):
        messages = [{"role": "user", "content": None}]
        _, contents = self.provider._convert_messages(messages)

        assert len(contents) == 1
        _types_module.Part.from_text.assert_called()
        call_kwargs = _types_module.Part.from_text.call_args_list[-1].kwargs
        assert call_kwargs["text"] == ""

    def test_missing_content_key_defaults_to_empty_string(self):
        messages = [{"role": "user"}]
        _, contents = self.provider._convert_messages(messages)

        assert len(contents) == 1
        call_kwargs = _types_module.Part.from_text.call_args_list[-1].kwargs
        assert call_kwargs["text"] == ""


class TestConvertTools:
    """Tests for _convert_tools (OpenAI tool schema -> Gemini FunctionDeclaration)."""

    def setup_method(self):
        self.provider = GeminiProvider(api_key="test-key")

    def test_single_tool(self):
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read a file",
                    "parameters": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"],
                    },
                },
            }
        ]
        self.provider._convert_tools(tools)

        _types_module.FunctionDeclaration.assert_called_once_with(
            name="read_file",
            description="Read a file",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        )
        _types_module.Tool.assert_called_once()
        call_kwargs = _types_module.Tool.call_args.kwargs
        assert len(call_kwargs["function_declarations"]) == 1

    def test_multiple_tools(self):
        _types_module.FunctionDeclaration.reset_mock()
        tools = [
            {
                "type": "function",
                "function": {"name": "tool_a", "description": "A", "parameters": {}},
            },
            {
                "type": "function",
                "function": {"name": "tool_b", "description": "B", "parameters": {}},
            },
        ]
        self.provider._convert_tools(tools)

        assert _types_module.FunctionDeclaration.call_count == 2

    def test_missing_description_defaults_to_empty(self):
        _types_module.FunctionDeclaration.reset_mock()
        tools = [
            {
                "type": "function",
                "function": {"name": "no_desc"},
            }
        ]
        self.provider._convert_tools(tools)

        call_kwargs = _types_module.FunctionDeclaration.call_args.kwargs
        assert call_kwargs["description"] == ""
        assert call_kwargs["parameters"] is None

    def test_missing_parameters_defaults_to_none(self):
        _types_module.FunctionDeclaration.reset_mock()
        tools = [
            {
                "type": "function",
                "function": {"name": "no_params", "description": "d"},
            }
        ]
        self.provider._convert_tools(tools)

        call_kwargs = _types_module.FunctionDeclaration.call_args.kwargs
        assert call_kwargs["parameters"] is None


class TestParseResponse:
    """Tests for _parse_response."""

    def setup_method(self):
        self.provider = GeminiProvider(api_key="test-key")

    def test_text_only_response(self):
        response = _make_gemini_response([_make_text_part("Hello, world!")])

        result = self.provider._parse_response(response)

        assert isinstance(result, LLMResponse)
        assert result.content == "Hello, world!"
        assert result.tool_calls == []
        assert result.finish_reason == "stop"

    def test_multi_text_parts_joined(self):
        parts = [_make_text_part("Hello, "), _make_text_part("world!")]
        response = _make_gemini_response(parts)

        result = self.provider._parse_response(response)

        assert result.content == "Hello, \nworld!"

    def test_tool_call_response(self):
        part = _make_function_call_part("read_file", {"path": "/tmp/x"})
        response = _make_gemini_response([part])

        result = self.provider._parse_response(response)

        assert result.content is None
        assert len(result.tool_calls) == 1
        tc = result.tool_calls[0]
        assert tc.name == "read_file"
        assert tc.arguments == {"path": "/tmp/x"}
        # ID should be an 8-char hex string
        assert len(tc.id) == 8

    def test_tool_call_no_args(self):
        part = _make_function_call_part("get_time", None)
        response = _make_gemini_response([part])

        result = self.provider._parse_response(response)

        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].arguments == {}

    def test_multiple_tool_calls(self):
        parts = [
            _make_function_call_part("tool_a", {"x": 1}),
            _make_function_call_part("tool_b", {"y": 2}),
        ]
        response = _make_gemini_response(parts)

        result = self.provider._parse_response(response)

        assert len(result.tool_calls) == 2
        assert result.tool_calls[0].name == "tool_a"
        assert result.tool_calls[1].name == "tool_b"
        # IDs should be unique
        assert result.tool_calls[0].id != result.tool_calls[1].id

    def test_mixed_text_and_tool_call(self):
        parts = [
            _make_text_part("Let me check that."),
            _make_function_call_part("read_file", {"path": "/tmp"}),
        ]
        response = _make_gemini_response(parts)

        result = self.provider._parse_response(response)

        assert result.content == "Let me check that."
        assert len(result.tool_calls) == 1

    def test_usage_metadata_parsed(self):
        response = _make_gemini_response(
            [_make_text_part("ok")],
            prompt_tokens=5,
            completion_tokens=15,
            total_tokens=20,
        )

        result = self.provider._parse_response(response)

        assert result.usage == {
            "prompt_tokens": 5,
            "completion_tokens": 15,
            "total_tokens": 20,
        }

    def test_usage_metadata_none(self):
        response = _make_gemini_response([_make_text_part("ok")])
        response.usage_metadata = None

        result = self.provider._parse_response(response)

        assert result.usage == {}

    def test_usage_metadata_partial_none_counts(self):
        response = _make_gemini_response([_make_text_part("ok")])
        response.usage_metadata.prompt_token_count = None
        response.usage_metadata.candidates_token_count = None
        response.usage_metadata.total_token_count = None

        result = self.provider._parse_response(response)

        assert result.usage == {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

    def test_finish_reason_mapped_to_lowercase(self):
        response = _make_gemini_response(
            [_make_text_part("ok")], finish_reason_name="MAX_TOKENS"
        )

        result = self.provider._parse_response(response)

        assert result.finish_reason == "max_tokens"

    def test_finish_reason_none_defaults_to_stop(self):
        response = _make_gemini_response([_make_text_part("ok")])
        response.candidates[0].finish_reason = None

        result = self.provider._parse_response(response)

        assert result.finish_reason == "stop"

    def test_no_text_content_returns_none(self):
        """When all parts are tool calls, content should be None."""
        response = _make_gemini_response(
            [_make_function_call_part("fn", {"a": 1})]
        )

        result = self.provider._parse_response(response)

        assert result.content is None


class TestChat:
    """Tests for the async chat() method."""

    def setup_method(self):
        self.provider = GeminiProvider(api_key="test-key")

    async def test_text_response(self):
        mock_response = _make_gemini_response([_make_text_part("The answer is 42.")])
        self.provider.client.models.generate_content = MagicMock(
            return_value=mock_response
        )

        result = await self.provider.chat(
            messages=[{"role": "user", "content": "What is the meaning of life?"}],
        )

        assert isinstance(result, LLMResponse)
        assert result.content == "The answer is 42."
        assert result.finish_reason == "stop"
        self.provider.client.models.generate_content.assert_called_once()

    async def test_uses_default_model(self):
        mock_response = _make_gemini_response([_make_text_part("ok")])
        self.provider.client.models.generate_content = MagicMock(
            return_value=mock_response
        )

        await self.provider.chat(
            messages=[{"role": "user", "content": "hi"}],
        )

        call_kwargs = self.provider.client.models.generate_content.call_args.kwargs
        assert call_kwargs["model"] == "gemini-2.5-flash"

    async def test_custom_model_overrides_default(self):
        mock_response = _make_gemini_response([_make_text_part("ok")])
        self.provider.client.models.generate_content = MagicMock(
            return_value=mock_response
        )

        await self.provider.chat(
            messages=[{"role": "user", "content": "hi"}],
            model="gemini-2.0-pro",
        )

        call_kwargs = self.provider.client.models.generate_content.call_args.kwargs
        assert call_kwargs["model"] == "gemini-2.0-pro"

    async def test_tool_call_response(self):
        mock_response = _make_gemini_response(
            [_make_function_call_part("search", {"query": "python"})]
        )
        self.provider.client.models.generate_content = MagicMock(
            return_value=mock_response
        )

        result = await self.provider.chat(
            messages=[{"role": "user", "content": "Search for python"}],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "search",
                        "description": "Search the web",
                        "parameters": {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                        },
                    },
                }
            ],
        )

        assert result.has_tool_calls
        assert result.tool_calls[0].name == "search"
        assert result.tool_calls[0].arguments == {"query": "python"}

    async def test_exception_returns_error_response(self):
        self.provider.client.models.generate_content = MagicMock(
            side_effect=RuntimeError("API timeout")
        )

        result = await self.provider.chat(
            messages=[{"role": "user", "content": "hello"}],
        )

        assert result.finish_reason == "error"
        assert "Gemini request failed" in result.content
        assert "API timeout" in result.content
        assert result.tool_calls == []

    async def test_passes_max_tokens_and_temperature(self):
        mock_response = _make_gemini_response([_make_text_part("ok")])
        self.provider.client.models.generate_content = MagicMock(
            return_value=mock_response
        )

        await self.provider.chat(
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=1024,
            temperature=0.2,
        )

        call_kwargs = self.provider.client.models.generate_content.call_args.kwargs
        config = call_kwargs["config"]
        assert config.max_output_tokens == 1024
        assert config.temperature == 0.2

    async def test_no_tools_skips_tool_conversion(self):
        mock_response = _make_gemini_response([_make_text_part("ok")])
        self.provider.client.models.generate_content = MagicMock(
            return_value=mock_response
        )

        with patch.object(self.provider, "_convert_tools") as mock_convert:
            await self.provider.chat(
                messages=[{"role": "user", "content": "hi"}],
                tools=None,
            )

            mock_convert.assert_not_called()


class TestToolCallIdGeneration:
    """Verify that tool call IDs are 8-char hex strings from uuid4."""

    def test_id_format(self):
        provider = GeminiProvider(api_key="test-key")
        part = _make_function_call_part("fn", {})
        response = _make_gemini_response([part])

        result = provider._parse_response(response)

        tc_id = result.tool_calls[0].id
        assert len(tc_id) == 8
        # Should be valid hex
        int(tc_id, 16)

    def test_ids_are_unique_across_calls(self):
        provider = GeminiProvider(api_key="test-key")
        ids = set()
        for _ in range(50):
            part = _make_function_call_part("fn", {})
            response = _make_gemini_response([part])
            result = provider._parse_response(response)
            ids.add(result.tool_calls[0].id)

        # With 8 hex chars the collision probability is negligible for 50 calls
        assert len(ids) == 50
