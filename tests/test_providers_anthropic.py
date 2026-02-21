"""Tests for the Anthropic LLM provider."""

import sys
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sparkagent.providers.base import LLMResponse, ToolCall  # noqa: I001

# ---------------------------------------------------------------------------
# Fake anthropic module -- the real SDK may not be installed, so we build a
# lightweight stand-in that satisfies every import the provider needs.
# ---------------------------------------------------------------------------

def _build_fake_anthropic_module() -> MagicMock:
    """Create a minimal fake ``anthropic`` package for import-time patching."""
    mod = MagicMock()

    # anthropic.AsyncAnthropic must be a class we can assert on later.
    mod.AsyncAnthropic = MagicMock()

    # anthropic.APIStatusError must behave like a real exception class.
    class FakeAPIStatusError(Exception):
        def __init__(self, message: str, *, status_code: int, body: Any = None):
            self.message = message
            self.status_code = status_code
            self.body = body
            super().__init__(message)

    mod.APIStatusError = FakeAPIStatusError
    return mod


# Inject the fake module *before* importing the provider so that
# ``import anthropic`` inside anthropic.py resolves to our fake.
_fake_anthropic = _build_fake_anthropic_module()
sys.modules.setdefault("anthropic", _fake_anthropic)

from sparkagent.providers.anthropic import (  # noqa: E402, I001
    AnthropicProvider,
    _classify_anthropic_credential,
)


# ---------------------------------------------------------------------------
# Helpers for building fake Anthropic SDK response objects
# ---------------------------------------------------------------------------

def _text_block(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=text)


def _tool_use_block(
    tool_id: str, name: str, input_data: dict[str, Any]
) -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", id=tool_id, name=name, input=input_data)


def _usage(input_tokens: int, output_tokens: int) -> SimpleNamespace:
    return SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens)


def _anthropic_response(
    content: list[SimpleNamespace],
    stop_reason: str = "end_turn",
    usage: SimpleNamespace | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        content=content,
        stop_reason=stop_reason,
        usage=usage,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_client() -> AsyncMock:
    """Return an ``AsyncMock`` that stands in for ``AsyncAnthropic``."""
    client = AsyncMock()
    client.messages = AsyncMock()
    client.messages.create = AsyncMock()
    return client


@pytest.fixture
def provider(mock_client: AsyncMock) -> AnthropicProvider:
    """Create an ``AnthropicProvider`` whose internal client is the mock."""
    with patch.object(_fake_anthropic, "AsyncAnthropic", return_value=mock_client):
        p = AnthropicProvider(api_key="test-key", api_base="https://test.api.com")
    # Replace the client attribute to be sure.
    p.client = mock_client
    return p


# ---------------------------------------------------------------------------
# Tests: initialisation & defaults
# ---------------------------------------------------------------------------

class TestAnthropicProviderInit:
    """Tests for provider construction and default values."""

    def test_default_model(self, provider: AnthropicProvider):
        assert provider.get_default_model() == "claude-sonnet-4-6"

    def test_custom_default_model(self, mock_client: AsyncMock):
        with patch.object(_fake_anthropic, "AsyncAnthropic", return_value=mock_client):
            p = AnthropicProvider(
                api_key="k",
                default_model="claude-opus-4-6",
            )
        assert p.get_default_model() == "claude-opus-4-6"

    def test_api_key_and_base_stored(self, provider: AnthropicProvider):
        assert provider.api_key == "test-key"
        assert provider.api_base == "https://test.api.com"

    def test_default_base_url_used_when_none(self, mock_client: AsyncMock):
        with patch.object(
            _fake_anthropic, "AsyncAnthropic", return_value=mock_client
        ) as mock_cls:
            AnthropicProvider(api_key="k", api_base=None)
            mock_cls.assert_called_once_with(
                api_key="k",
                auth_token=None,
                base_url=AnthropicProvider.DEFAULT_BASE_URL,
                timeout=120.0,
            )

    def test_oauth_token_passed_as_auth_token(self, mock_client: AsyncMock):
        with patch.object(
            _fake_anthropic, "AsyncAnthropic", return_value=mock_client
        ) as mock_cls:
            AnthropicProvider(api_key="sk-ant-oat01-test-token", api_base=None)
            mock_cls.assert_called_once_with(
                api_key=None,
                auth_token="sk-ant-oat01-test-token",
                base_url=AnthropicProvider.DEFAULT_BASE_URL,
                timeout=120.0,
            )


# ---------------------------------------------------------------------------
# Tests: _convert_tool
# ---------------------------------------------------------------------------

class TestConvertTool:
    """Tests for the OpenAI-to-Anthropic tool schema conversion."""

    def test_basic_conversion(self):
        openai_tool: dict[str, Any] = {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read the contents of a file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path"},
                    },
                    "required": ["path"],
                },
            },
        }

        result = AnthropicProvider._convert_tool(openai_tool)

        assert result["name"] == "read_file"
        assert result["description"] == "Read the contents of a file."
        assert result["input_schema"]["type"] == "object"
        assert "path" in result["input_schema"]["properties"]

    def test_missing_description_defaults_to_empty(self):
        tool: dict[str, Any] = {
            "type": "function",
            "function": {
                "name": "no_desc",
                "parameters": {"type": "object", "properties": {}},
            },
        }

        result = AnthropicProvider._convert_tool(tool)

        assert result["description"] == ""

    def test_missing_parameters_defaults_to_empty_object(self):
        tool: dict[str, Any] = {
            "type": "function",
            "function": {
                "name": "no_params",
                "description": "A tool without parameters.",
            },
        }

        result = AnthropicProvider._convert_tool(tool)

        assert result["input_schema"] == {"type": "object", "properties": {}}


# ---------------------------------------------------------------------------
# Tests: _parse_response
# ---------------------------------------------------------------------------

class TestParseResponse:
    """Tests for Anthropic response parsing."""

    def test_text_only_response(self):
        resp = _anthropic_response(
            content=[_text_block("Hello, world!")],
            stop_reason="end_turn",
            usage=_usage(10, 5),
        )

        result = AnthropicProvider._parse_response(resp)

        assert result.content == "Hello, world!"
        assert result.tool_calls == []
        assert result.finish_reason == "end_turn"
        assert result.usage == {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        }

    def test_multiple_text_blocks_joined(self):
        resp = _anthropic_response(
            content=[_text_block("Part 1"), _text_block("Part 2")],
            usage=_usage(1, 1),
        )

        result = AnthropicProvider._parse_response(resp)

        assert result.content == "Part 1\n\nPart 2"

    def test_tool_use_response(self):
        resp = _anthropic_response(
            content=[
                _tool_use_block("call_1", "read_file", {"path": "/tmp/x"}),
            ],
            stop_reason="tool_use",
            usage=_usage(20, 10),
        )

        result = AnthropicProvider._parse_response(resp)

        assert result.content is None
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0] == ToolCall(
            id="call_1", name="read_file", arguments={"path": "/tmp/x"}
        )
        assert result.finish_reason == "tool_calls"

    def test_mixed_text_and_tool_use(self):
        resp = _anthropic_response(
            content=[
                _text_block("I will read the file for you."),
                _tool_use_block("call_2", "read_file", {"path": "/etc/hosts"}),
            ],
            stop_reason="tool_use",
            usage=_usage(15, 8),
        )

        result = AnthropicProvider._parse_response(resp)

        assert result.content == "I will read the file for you."
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "read_file"
        assert result.finish_reason == "tool_calls"

    def test_multiple_tool_calls(self):
        resp = _anthropic_response(
            content=[
                _tool_use_block("c1", "tool_a", {"x": 1}),
                _tool_use_block("c2", "tool_b", {"y": 2}),
            ],
            stop_reason="tool_use",
            usage=_usage(5, 5),
        )

        result = AnthropicProvider._parse_response(resp)

        assert len(result.tool_calls) == 2
        assert result.tool_calls[0].name == "tool_a"
        assert result.tool_calls[1].name == "tool_b"

    def test_no_usage(self):
        resp = _anthropic_response(
            content=[_text_block("Hi")],
            stop_reason="end_turn",
            usage=None,
        )

        result = AnthropicProvider._parse_response(resp)

        assert result.usage == {}

    def test_empty_content_returns_none(self):
        resp = _anthropic_response(content=[], stop_reason="end_turn", usage=_usage(0, 0))

        result = AnthropicProvider._parse_response(resp)

        assert result.content is None

    def test_stop_reason_passthrough(self):
        resp = _anthropic_response(
            content=[_text_block("done")],
            stop_reason="max_tokens",
            usage=_usage(1, 1),
        )

        result = AnthropicProvider._parse_response(resp)

        assert result.finish_reason == "max_tokens"

    def test_none_stop_reason_defaults_to_stop(self):
        resp = _anthropic_response(
            content=[_text_block("hmm")],
            stop_reason=None,
            usage=_usage(1, 1),
        )

        result = AnthropicProvider._parse_response(resp)

        assert result.finish_reason == "stop"


# ---------------------------------------------------------------------------
# Tests: chat() — integration with the mock client
# ---------------------------------------------------------------------------

class TestChat:
    """Tests for the async chat() method."""

    async def test_text_response(
        self, provider: AnthropicProvider, mock_client: AsyncMock
    ):
        mock_client.messages.create.return_value = _anthropic_response(
            content=[_text_block("Hi there!")],
            stop_reason="end_turn",
            usage=_usage(10, 5),
        )

        result = await provider.chat(
            messages=[{"role": "user", "content": "Hello"}],
        )

        assert isinstance(result, LLMResponse)
        assert result.content == "Hi there!"
        assert result.finish_reason == "end_turn"
        assert result.usage["total_tokens"] == 15

    async def test_tool_call_response(
        self, provider: AnthropicProvider, mock_client: AsyncMock
    ):
        mock_client.messages.create.return_value = _anthropic_response(
            content=[_tool_use_block("tc_1", "shell", {"cmd": "ls"})],
            stop_reason="tool_use",
            usage=_usage(8, 12),
        )

        result = await provider.chat(
            messages=[{"role": "user", "content": "List files"}],
            tools=[{
                "type": "function",
                "function": {
                    "name": "shell",
                    "description": "Run a shell command.",
                    "parameters": {
                        "type": "object",
                        "properties": {"cmd": {"type": "string"}},
                    },
                },
            }],
        )

        assert result.has_tool_calls
        assert result.tool_calls[0].name == "shell"
        assert result.tool_calls[0].arguments == {"cmd": "ls"}

    async def test_system_message_extraction(
        self, provider: AnthropicProvider, mock_client: AsyncMock
    ):
        mock_client.messages.create.return_value = _anthropic_response(
            content=[_text_block("OK")],
            stop_reason="end_turn",
            usage=_usage(5, 3),
        )

        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "system", "content": "Be concise."},
            {"role": "user", "content": "Hi"},
        ]

        await provider.chat(messages=messages)

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["system"] == "You are helpful.\n\nBe concise."
        # Only the user message should remain in the messages list.
        assert len(call_kwargs["messages"]) == 1
        assert call_kwargs["messages"][0]["role"] == "user"

    async def test_no_system_message_omits_system_kwarg(
        self, provider: AnthropicProvider, mock_client: AsyncMock
    ):
        mock_client.messages.create.return_value = _anthropic_response(
            content=[_text_block("Sure")],
            stop_reason="end_turn",
            usage=_usage(2, 2),
        )

        await provider.chat(messages=[{"role": "user", "content": "ping"}])

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert "system" not in call_kwargs

    async def test_tools_converted_and_passed(
        self, provider: AnthropicProvider, mock_client: AsyncMock
    ):
        mock_client.messages.create.return_value = _anthropic_response(
            content=[_text_block("done")],
            stop_reason="end_turn",
            usage=_usage(1, 1),
        )

        openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Write to a file.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "content": {"type": "string"},
                        },
                        "required": ["path", "content"],
                    },
                },
            },
        ]

        await provider.chat(
            messages=[{"role": "user", "content": "write"}],
            tools=openai_tools,
        )

        call_kwargs = mock_client.messages.create.call_args.kwargs
        converted = call_kwargs["tools"]
        assert len(converted) == 1
        assert converted[0]["name"] == "write_file"
        assert "input_schema" in converted[0]

    async def test_no_tools_omits_tools_kwarg(
        self, provider: AnthropicProvider, mock_client: AsyncMock
    ):
        mock_client.messages.create.return_value = _anthropic_response(
            content=[_text_block("ok")],
            stop_reason="end_turn",
            usage=_usage(1, 1),
        )

        await provider.chat(
            messages=[{"role": "user", "content": "hi"}],
            tools=None,
        )

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert "tools" not in call_kwargs

    async def test_model_temperature_max_tokens_forwarded(
        self, provider: AnthropicProvider, mock_client: AsyncMock
    ):
        mock_client.messages.create.return_value = _anthropic_response(
            content=[_text_block("x")],
            stop_reason="end_turn",
            usage=_usage(1, 1),
        )

        await provider.chat(
            messages=[{"role": "user", "content": "x"}],
            model="claude-haiku-4-5",
            max_tokens=1024,
            temperature=0.2,
        )

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-haiku-4-5"
        assert call_kwargs["max_tokens"] == 1024
        assert call_kwargs["temperature"] == 0.2

    async def test_default_model_used_when_none(
        self, provider: AnthropicProvider, mock_client: AsyncMock
    ):
        mock_client.messages.create.return_value = _anthropic_response(
            content=[_text_block("y")],
            stop_reason="end_turn",
            usage=_usage(1, 1),
        )

        await provider.chat(
            messages=[{"role": "user", "content": "y"}],
            model=None,
        )

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# Tests: error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    """Tests for graceful error handling in chat()."""

    async def test_api_status_error(
        self, provider: AnthropicProvider, mock_client: AsyncMock
    ):
        error = _fake_anthropic.APIStatusError(
            "Rate limit exceeded", status_code=429
        )
        mock_client.messages.create.side_effect = error

        result = await provider.chat(
            messages=[{"role": "user", "content": "boom"}],
        )

        assert result.finish_reason == "error"
        assert "429" in (result.content or "")
        assert "Rate limit exceeded" in (result.content or "")

    async def test_api_status_error_truncates_long_message(
        self, provider: AnthropicProvider, mock_client: AsyncMock
    ):
        long_msg = "x" * 1000
        error = _fake_anthropic.APIStatusError(long_msg, status_code=500)
        mock_client.messages.create.side_effect = error

        result = await provider.chat(
            messages=[{"role": "user", "content": "fail"}],
        )

        assert result.finish_reason == "error"
        # The message portion should be truncated to at most 500 chars.
        assert len(result.content or "") <= 600  # "API error (500): " + 500

    async def test_generic_exception(
        self, provider: AnthropicProvider, mock_client: AsyncMock
    ):
        mock_client.messages.create.side_effect = RuntimeError("connection lost")

        result = await provider.chat(
            messages=[{"role": "user", "content": "oops"}],
        )

        assert result.finish_reason == "error"
        assert "connection lost" in (result.content or "")
        assert result.content is not None
        assert result.content.startswith("Request failed:")


# ---------------------------------------------------------------------------
# Tests: _classify_anthropic_credential
# ---------------------------------------------------------------------------


class TestClassifyAnthropicCredential:
    """Tests for the credential type auto-detection."""

    def test_api_key_detected(self):
        api_key, auth_token = _classify_anthropic_credential("sk-ant-api03-abc123")
        assert api_key == "sk-ant-api03-abc123"
        assert auth_token is None

    def test_oauth_token_detected(self):
        api_key, auth_token = _classify_anthropic_credential("sk-ant-oat01-xyz789")
        assert api_key is None
        assert auth_token == "sk-ant-oat01-xyz789"

    def test_future_oauth_version_detected(self):
        api_key, auth_token = _classify_anthropic_credential("sk-ant-oat02-future")
        assert api_key is None
        assert auth_token == "sk-ant-oat02-future"

    def test_none_credential(self):
        api_key, auth_token = _classify_anthropic_credential(None)
        assert api_key is None
        assert auth_token is None

    def test_empty_credential(self):
        api_key, auth_token = _classify_anthropic_credential("")
        assert api_key is None
        assert auth_token is None

    def test_unknown_prefix_treated_as_api_key(self):
        api_key, auth_token = _classify_anthropic_credential("some-other-key")
        assert api_key == "some-other-key"
        assert auth_token is None


# ---------------------------------------------------------------------------
# Tests: _ensure_valid_token (OAuth auto-refresh)
# ---------------------------------------------------------------------------


class TestEnsureValidToken:
    """Tests for the OAuth token auto-refresh logic."""

    async def test_skips_for_non_oauth(self, mock_client: AsyncMock):
        """Provider without token_type='oauth' should never try to refresh."""
        with patch.object(_fake_anthropic, "AsyncAnthropic", return_value=mock_client):
            p = AnthropicProvider(api_key="sk-ant-api03-key", token_type=None)
        p.client = mock_client

        # Should not raise or call anything
        with patch("sparkagent.auth.oauth.refresh_access_token") as mock_refresh:
            await p._ensure_valid_token()
            mock_refresh.assert_not_called()

    async def test_skips_when_not_expired(self, mock_client: AsyncMock):
        """Provider with a future expiry should not refresh."""
        from datetime import datetime, timedelta, timezone

        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()

        with patch.object(_fake_anthropic, "AsyncAnthropic", return_value=mock_client):
            p = AnthropicProvider(
                api_key="sk-ant-oat01-valid",
                token_type="oauth",
                expires_at=future,
                refresh_token="refresh-tok",
            )
        p.client = mock_client

        with patch("sparkagent.auth.oauth.refresh_access_token") as mock_refresh:
            await p._ensure_valid_token()
            mock_refresh.assert_not_called()

    async def test_refreshes_when_expired(self, mock_client: AsyncMock):
        """Provider with a past expiry should call refresh_access_token."""
        from datetime import datetime, timedelta, timezone

        from sparkagent.auth.oauth import OAuthTokens

        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

        with patch.object(_fake_anthropic, "AsyncAnthropic", return_value=mock_client):
            p = AnthropicProvider(
                api_key="sk-ant-oat01-old",
                token_type="oauth",
                expires_at=past,
                refresh_token="refresh-tok",
            )
        p.client = mock_client

        new_tokens = OAuthTokens(
            access_token="sk-ant-oat01-new",
            refresh_token="new-refresh",
            expires_in=28800,
        )

        with (
            patch(
                "sparkagent.auth.oauth.refresh_access_token",
                return_value=new_tokens,
            ) as mock_refresh,
            patch.object(_fake_anthropic, "AsyncAnthropic", return_value=mock_client),
        ):
            await p._ensure_valid_token()
            mock_refresh.assert_called_once_with("refresh-tok")

        # Internal state should be updated
        assert p._refresh_token == "new-refresh"
        assert p._expires_at is not None

    async def test_invokes_callback_on_refresh(self, mock_client: AsyncMock):
        """on_token_refresh callback should be called with new tokens."""
        from datetime import datetime, timedelta, timezone

        from sparkagent.auth.oauth import OAuthTokens

        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        callback = MagicMock()

        with patch.object(_fake_anthropic, "AsyncAnthropic", return_value=mock_client):
            p = AnthropicProvider(
                api_key="sk-ant-oat01-old",
                token_type="oauth",
                expires_at=past,
                refresh_token="refresh-tok",
                on_token_refresh=callback,
            )
        p.client = mock_client

        new_tokens = OAuthTokens(
            access_token="sk-ant-oat01-refreshed",
            refresh_token="new-refresh-2",
            expires_in=28800,
        )

        with (
            patch(
                "sparkagent.auth.oauth.refresh_access_token",
                return_value=new_tokens,
            ),
            patch.object(_fake_anthropic, "AsyncAnthropic", return_value=mock_client),
        ):
            await p._ensure_valid_token()

        callback.assert_called_once()
        call_args = callback.call_args[0]
        assert call_args[0] == "sk-ant-oat01-refreshed"
        assert call_args[1] == "new-refresh-2"
        # Third arg is expires_at string
        assert isinstance(call_args[2], str)

    async def test_raises_without_refresh_token(self, mock_client: AsyncMock):
        """Expired token with no refresh_token should raise OAuthError."""
        from datetime import datetime, timedelta, timezone

        from sparkagent.auth.oauth import OAuthError

        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

        with patch.object(_fake_anthropic, "AsyncAnthropic", return_value=mock_client):
            p = AnthropicProvider(
                api_key="sk-ant-oat01-expired",
                token_type="oauth",
                expires_at=past,
                refresh_token=None,
            )
        p.client = mock_client

        with pytest.raises(OAuthError, match="no refresh token"):
            await p._ensure_valid_token()

    async def test_chat_calls_ensure_valid_token(
        self, provider: AnthropicProvider, mock_client: AsyncMock
    ):
        """chat() should call _ensure_valid_token() before making the API call."""
        mock_client.messages.create.return_value = _anthropic_response(
            content=[_text_block("ok")],
            stop_reason="end_turn",
            usage=_usage(1, 1),
        )

        with patch.object(
            provider, "_ensure_valid_token", new_callable=AsyncMock
        ) as mock_ensure:
            await provider.chat(messages=[{"role": "user", "content": "test"}])
            mock_ensure.assert_called_once()
