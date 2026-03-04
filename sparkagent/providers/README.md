# Providers — LLM Provider Adapters

Unified interface for calling different LLM APIs. All providers normalize responses into a common `LLMResponse` format.

> For setup instructions, see [Supported Providers](../../README.md#supported-providers) in the main README.

## Files

| File | Purpose |
|------|---------|
| `base.py` | `LLMProvider` ABC, `LLMResponse` and `ToolCall` dataclasses |
| `openai_compat.py` | `OpenAICompatibleProvider` — works with OpenAI, OpenRouter, vLLM, and any compatible endpoint |
| `anthropic.py` | `AnthropicProvider` — Anthropic Messages API with OAuth token refresh support |
| `gemini.py` | `GeminiProvider` — Google Gemini via `google-genai` SDK (sync SDK bridged with `asyncio.to_thread`) |
| `__init__.py` | Lazy imports — providers are only imported when accessed to avoid requiring all SDKs |

## Key Abstractions

### LLMProvider (ABC)

```python
class LLMProvider(ABC):
    def __init__(self, api_key=None, api_base=None): ...
    async def chat(messages, tools, model, max_tokens, temperature) -> LLMResponse: ...
    def get_default_model() -> str: ...
```

### LLMResponse / ToolCall

```python
@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]

@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCall]
    finish_reason: str          # "stop" or "tool_calls"
    usage: dict[str, int]
    has_tool_calls -> bool      # property
```

### Provider Details

| Provider | Default Model | Auth | Notes |
|----------|--------------|------|-------|
| `OpenAICompatibleProvider` | `gpt-4o` | API key | Raw HTTP via httpx |
| `AnthropicProvider` | `claude-sonnet-4-6` | API key or OAuth | SDK-based, auto token refresh |
| `GeminiProvider` | `gemini-2.5-flash` | API key | SDK-based, runs in thread |

Each provider converts tool schemas from OpenAI format to its native format and normalizes API responses back to `LLMResponse`.
