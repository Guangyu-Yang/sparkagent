"""Tests for the CLI provider/model registry."""

import dataclasses

import pytest

from sparkagent.cli.providers import PROVIDERS, ModelOption, ProviderOption, get_provider


class TestProvidersRegistry:
    """Tests for the PROVIDERS registry list."""

    def test_providers_count(self):
        assert len(PROVIDERS) == 3

    def test_each_provider_has_required_fields(self):
        for provider in PROVIDERS:
            assert isinstance(provider.key, str) and provider.key
            assert isinstance(provider.label, str) and provider.label
            assert isinstance(provider.key_url_hint, str) and provider.key_url_hint
            assert isinstance(provider.models, list) and len(provider.models) > 0

    def test_provider_keys_are_unique(self):
        keys = [p.key for p in PROVIDERS]
        assert len(keys) == len(set(keys))

    def test_model_ids_unique_within_each_provider(self):
        for provider in PROVIDERS:
            model_ids = [m.id for m in provider.models]
            assert len(model_ids) == len(set(model_ids)), (
                f"Duplicate model IDs in provider '{provider.key}'"
            )


class TestModelCounts:
    """Tests for the expected number of models per provider."""

    @pytest.mark.parametrize(
        ("provider_key", "expected_count"),
        [
            ("openai", 5),
            ("gemini", 3),
            ("anthropic", 3),
        ],
    )
    def test_model_count_per_provider(self, provider_key: str, expected_count: int):
        provider = get_provider(provider_key)
        assert provider is not None
        assert len(provider.models) == expected_count


class TestGetProvider:
    """Tests for the get_provider() lookup function."""

    @pytest.mark.parametrize("key", ["openai", "gemini", "anthropic"])
    def test_returns_correct_provider(self, key: str):
        provider = get_provider(key)
        assert provider is not None
        assert provider.key == key

    def test_returns_none_for_unknown_key(self):
        assert get_provider("unknown") is None

    def test_returns_none_for_empty_string(self):
        assert get_provider("") is None


class TestModelOptionImmutability:
    """Tests that ModelOption instances are frozen (immutable)."""

    def test_cannot_set_id(self):
        model = ModelOption("test-id", "Test", "A test model")
        with pytest.raises(dataclasses.FrozenInstanceError):
            model.id = "other-id"  # type: ignore[misc]

    def test_cannot_set_label(self):
        model = ModelOption("test-id", "Test", "A test model")
        with pytest.raises(dataclasses.FrozenInstanceError):
            model.label = "Other"  # type: ignore[misc]

    def test_cannot_set_description(self):
        model = ModelOption("test-id", "Test", "A test model")
        with pytest.raises(dataclasses.FrozenInstanceError):
            model.description = "changed"  # type: ignore[misc]


class TestProviderOptionImmutability:
    """Tests that ProviderOption instances are frozen (immutable)."""

    def test_cannot_set_key(self):
        provider = ProviderOption(key="k", label="L", key_url_hint="https://example.com")
        with pytest.raises(dataclasses.FrozenInstanceError):
            provider.key = "other"  # type: ignore[misc]

    def test_cannot_set_label(self):
        provider = ProviderOption(key="k", label="L", key_url_hint="https://example.com")
        with pytest.raises(dataclasses.FrozenInstanceError):
            provider.label = "Other"  # type: ignore[misc]

    def test_cannot_set_key_url_hint(self):
        provider = ProviderOption(key="k", label="L", key_url_hint="https://example.com")
        with pytest.raises(dataclasses.FrozenInstanceError):
            provider.key_url_hint = "https://other.com"  # type: ignore[misc]

    def test_cannot_set_models(self):
        provider = ProviderOption(key="k", label="L", key_url_hint="https://example.com")
        with pytest.raises(dataclasses.FrozenInstanceError):
            provider.models = []  # type: ignore[misc]
