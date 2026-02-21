"""Provider and model registry for the SparkAgent CLI.

Pure data module defining the available LLM providers and their models,
used by the onboarding and configuration flows.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ModelOption:
    """A single model offered by a provider."""

    id: str
    label: str
    description: str


@dataclass(frozen=True, slots=True)
class ProviderOption:
    """An LLM provider with its API-key hint and available models."""

    key: str
    label: str
    key_url_hint: str
    models: list[ModelOption] = field(default_factory=list)


PROVIDERS: list[ProviderOption] = [
    ProviderOption(
        key="openai",
        label="OpenAI",
        key_url_hint="https://platform.openai.com/api-keys",
        models=[
            ModelOption("gpt-4.1", "GPT-4.1", "Smartest non-reasoning model, 1M context"),
            ModelOption("gpt-4.1-mini", "GPT-4.1 Mini", "Fast and affordable"),
            ModelOption("gpt-4.1-nano", "GPT-4.1 Nano", "Cheapest and fastest"),
            ModelOption("o3", "o3", "Reasoning model for complex tasks"),
            ModelOption("o4-mini", "o4-mini", "Fast, cost-efficient reasoning"),
        ],
    ),
    ProviderOption(
        key="gemini",
        label="Google Gemini",
        key_url_hint="https://aistudio.google.com/apikey",
        models=[
            ModelOption(
                "gemini-2.5-pro", "Gemini 2.5 Pro", "Most capable, complex reasoning"
            ),
            ModelOption(
                "gemini-2.5-flash", "Gemini 2.5 Flash", "Best price-performance for reasoning"
            ),
            ModelOption(
                "gemini-2.5-flash-lite",
                "Gemini 2.5 Flash Lite",
                "Fastest, most budget-friendly",
            ),
        ],
    ),
    ProviderOption(
        key="anthropic",
        label="Anthropic",
        key_url_hint="https://console.anthropic.com/settings/keys",
        models=[
            ModelOption(
                "claude-opus-4-6", "Claude Opus 4.6", "Most intelligent, agents and coding"
            ),
            ModelOption(
                "claude-sonnet-4-6",
                "Claude Sonnet 4.6",
                "Best speed and intelligence balance",
            ),
            ModelOption(
                "claude-haiku-4-5", "Claude Haiku 4.5", "Fastest, near-frontier intelligence"
            ),
        ],
    ),
]


def get_provider(key: str) -> ProviderOption | None:
    """Look up a provider by its unique key.

    Args:
        key: The provider key (e.g. ``"openai"``, ``"gemini"``, ``"anthropic"``).

    Returns:
        The matching ``ProviderOption``, or ``None`` if no provider has that key.
    """
    for provider in PROVIDERS:
        if provider.key == key:
            return provider
    return None
