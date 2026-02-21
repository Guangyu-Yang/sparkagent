"""LLM provider implementations."""

from sparkagent.providers.base import LLMProvider, LLMResponse, ToolCall
from sparkagent.providers.openai_compat import OpenAICompatibleProvider

__all__ = ["LLMProvider", "LLMResponse", "ToolCall", "OpenAICompatibleProvider"]

# Lazy imports to avoid hard dependencies on optional SDKs.
def __getattr__(name: str):  # noqa: N807
    if name == "AnthropicProvider":
        from sparkagent.providers.anthropic import AnthropicProvider
        return AnthropicProvider
    if name == "GeminiProvider":
        from sparkagent.providers.gemini import GeminiProvider
        return GeminiProvider
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
