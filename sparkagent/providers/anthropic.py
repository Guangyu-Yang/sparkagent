"""Anthropic LLM provider using the official SDK."""

from collections.abc import Callable
from typing import Any

import anthropic

from sparkagent.providers.base import LLMProvider, LLMResponse, ToolCall


def _classify_anthropic_credential(
    credential: str | None,
) -> tuple[str | None, str | None]:
    """Classify an Anthropic credential as an API key or OAuth token.

    Returns:
        A tuple of ``(api_key, auth_token)``.  Exactly one will be non-None.
        OAuth tokens (prefix ``sk-ant-oat``) are routed to ``auth_token``;
        everything else is treated as a standard API key.
    """
    if not credential:
        return None, None
    if credential.startswith("sk-ant-oat"):
        return None, credential
    return credential, None


class AnthropicProvider(LLMProvider):
    """
    LLM provider for the Anthropic Messages API.

    Uses the official anthropic Python SDK with async support.
    Automatically detects OAuth tokens vs API keys and routes
    them to the correct SDK parameter.

    When configured with ``token_type="oauth"``, the provider will
    automatically refresh expired access tokens before each API call.
    """

    DEFAULT_BASE_URL = "https://api.anthropic.com"

    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        default_model: str = "claude-sonnet-4-6",
        timeout: float = 120.0,
        # OAuth support
        refresh_token: str | None = None,
        expires_at: str | None = None,
        token_type: str | None = None,
        on_token_refresh: Callable[[str, str, str], None] | None = None,
    ):
        super().__init__(api_key, api_base)
        self.default_model = default_model
        self._base_url = api_base or self.DEFAULT_BASE_URL
        self._timeout = timeout

        # OAuth state
        self._refresh_token = refresh_token
        self._expires_at = expires_at
        self._token_type = token_type
        self._on_token_refresh = on_token_refresh

        resolved_api_key, resolved_auth_token = _classify_anthropic_credential(api_key)
        self.client = anthropic.AsyncAnthropic(
            api_key=resolved_api_key,
            auth_token=resolved_auth_token,
            base_url=self._base_url,
            timeout=timeout,
        )

    async def _ensure_valid_token(self) -> None:
        """Refresh the OAuth token if it has expired.

        Only runs when ``token_type`` is ``"oauth"``. Transparently
        recreates the SDK client with the new access token and invokes
        the ``on_token_refresh`` callback so the caller can persist
        the updated credentials.
        """
        if self._token_type != "oauth":
            return

        from sparkagent.auth.oauth import (
            compute_expires_at,
            is_token_expired,
            refresh_access_token,
        )

        if not is_token_expired(self._expires_at):
            return

        if not self._refresh_token:
            from sparkagent.auth.oauth import OAuthError

            raise OAuthError(
                "OAuth token expired and no refresh token available. "
                "Run `sparkagent login` to re-authenticate."
            )

        tokens = await refresh_access_token(self._refresh_token)
        new_expires_at = compute_expires_at(tokens.expires_in)

        # Update internal state
        self._expires_at = new_expires_at
        self._refresh_token = tokens.refresh_token

        # Recreate the SDK client with the new token
        _, resolved_auth_token = _classify_anthropic_credential(tokens.access_token)
        self.client = anthropic.AsyncAnthropic(
            api_key=None,
            auth_token=resolved_auth_token,
            base_url=self._base_url,
            timeout=self._timeout,
        )

        # Notify caller to persist the new tokens
        if self._on_token_refresh:
            self._on_token_refresh(
                tokens.access_token, tokens.refresh_token, new_expires_at
            )

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Send a chat completion request."""
        await self._ensure_valid_token()

        model = model or self.default_model

        # Extract system messages — Anthropic takes system as a top-level parameter.
        system_parts: list[str] = []
        non_system: list[dict[str, Any]] = []
        for msg in messages:
            if msg.get("role") == "system":
                system_parts.append(msg["content"])
            else:
                non_system.append(msg)

        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": non_system,
            "temperature": temperature,
        }
        if system_parts:
            kwargs["system"] = "\n\n".join(system_parts)
        if tools:
            kwargs["tools"] = [self._convert_tool(t) for t in tools]

        try:
            response = await self.client.messages.create(**kwargs)
            return self._parse_response(response)
        except anthropic.APIStatusError as e:
            return LLMResponse(
                content=f"API error ({e.status_code}): {str(e.message)[:500]}",
                finish_reason="error",
            )
        except Exception as e:
            return LLMResponse(
                content=f"Request failed: {str(e)}",
                finish_reason="error",
            )

    @staticmethod
    def _convert_tool(tool: dict[str, Any]) -> dict[str, Any]:
        """Convert an OpenAI-style tool schema to Anthropic format."""
        fn = tool["function"]
        return {
            "name": fn["name"],
            "description": fn.get("description", ""),
            "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
        }

    @staticmethod
    def _parse_response(response: Any) -> LLMResponse:
        """Parse an Anthropic Message into our standard format."""
        content_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        for block in response.content:
            if block.type == "text":
                content_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=block.input,
                ))

        usage = {}
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
            }

        return LLMResponse(
            content="\n\n".join(content_parts) if content_parts else None,
            tool_calls=tool_calls,
            finish_reason="tool_calls" if tool_calls else response.stop_reason or "stop",
            usage=usage,
        )

    def get_default_model(self) -> str:
        """Get the default model."""
        return self.default_model
