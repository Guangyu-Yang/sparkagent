"""Tests for configuration schema."""

import json
from pathlib import Path
from unittest.mock import patch

from sparkagent.config.schema import (
    AgentConfig,
    ChannelsConfig,
    Config,
    ProviderConfig,
    ProvidersConfig,
    TelegramConfig,
    ToolsConfig,
    get_config_path,
    load_config,
    save_config,
)


class TestTelegramConfig:
    """Tests for TelegramConfig."""

    def test_default_values(self):
        config = TelegramConfig()
        assert config.enabled is False
        assert config.token == ""
        assert config.allow_from == []

    def test_custom_values(self):
        config = TelegramConfig(
            enabled=True,
            token="my-token",
            allow_from=["user1", "user2"]
        )
        assert config.enabled is True
        assert config.token == "my-token"
        assert config.allow_from == ["user1", "user2"]


class TestProviderConfig:
    """Tests for ProviderConfig."""

    def test_default_values(self):
        config = ProviderConfig()
        assert config.api_key == ""
        assert config.api_base is None
        assert config.refresh_token == ""
        assert config.expires_at == ""
        assert config.token_type == ""

    def test_custom_values(self):
        config = ProviderConfig(
            api_key="sk-test123",
            api_base="https://api.example.com"
        )
        assert config.api_key == "sk-test123"
        assert config.api_base == "https://api.example.com"

    def test_oauth_values(self):
        config = ProviderConfig(
            api_key="sk-ant-oat01-access-token",
            refresh_token="refresh-token-xyz",
            expires_at="2026-03-01T00:00:00+00:00",
            token_type="oauth",
        )
        assert config.api_key == "sk-ant-oat01-access-token"
        assert config.refresh_token == "refresh-token-xyz"
        assert config.expires_at == "2026-03-01T00:00:00+00:00"
        assert config.token_type == "oauth"


class TestProvidersConfig:
    """Tests for ProvidersConfig."""

    def test_default_values(self):
        config = ProvidersConfig()
        assert isinstance(config.openai, ProviderConfig)
        assert isinstance(config.gemini, ProviderConfig)
        assert isinstance(config.anthropic, ProviderConfig)

    def test_has_three_providers(self):
        config = ProvidersConfig()
        assert config.openai.api_key == ""
        assert config.gemini.api_key == ""
        assert config.anthropic.api_key == ""


class TestAgentConfig:
    """Tests for AgentConfig."""

    def test_default_values(self):
        config = AgentConfig()
        assert config.workspace == "~/.sparkagent/workspace"
        assert config.provider == ""
        assert config.model == ""
        assert config.max_iterations == 20

    def test_custom_values(self):
        config = AgentConfig(
            workspace="/custom/workspace",
            provider="openai",
            model="gpt-4.1",
            max_iterations=10
        )
        assert config.workspace == "/custom/workspace"
        assert config.provider == "openai"
        assert config.model == "gpt-4.1"
        assert config.max_iterations == 10


class TestConfig:
    """Tests for the main Config class."""

    def test_default_values(self):
        config = Config()
        assert isinstance(config.agent, AgentConfig)
        assert isinstance(config.providers, ProvidersConfig)
        assert isinstance(config.channels, ChannelsConfig)
        assert isinstance(config.tools, ToolsConfig)

    def test_workspace_path_expansion(self):
        config = Config()
        workspace = config.workspace_path
        assert isinstance(workspace, Path)
        assert "~" not in str(workspace)

    # --- get_api_key routing ---

    def test_get_api_key_openai(self):
        config = Config()
        config.agent.provider = "openai"
        config.providers.openai.api_key = "sk-openai"
        assert config.get_api_key() == "sk-openai"

    def test_get_api_key_gemini(self):
        config = Config()
        config.agent.provider = "gemini"
        config.providers.gemini.api_key = "gemini-key"
        assert config.get_api_key() == "gemini-key"

    def test_get_api_key_anthropic(self):
        config = Config()
        config.agent.provider = "anthropic"
        config.providers.anthropic.api_key = "sk-ant-key"
        assert config.get_api_key() == "sk-ant-key"

    def test_get_api_key_none_when_no_provider(self):
        config = Config()
        assert config.get_api_key() is None

    def test_get_api_key_none_when_empty_key(self):
        config = Config()
        config.agent.provider = "openai"
        assert config.get_api_key() is None

    # --- get_api_base routing ---

    def test_get_api_base_openai_default(self):
        config = Config()
        config.agent.provider = "openai"
        assert config.get_api_base() is None  # None means SDK default

    def test_get_api_base_openai_custom(self):
        config = Config()
        config.agent.provider = "openai"
        config.providers.openai.api_base = "https://openai.custom.com"
        assert config.get_api_base() == "https://openai.custom.com"

    def test_get_api_base_gemini_default(self):
        config = Config()
        config.agent.provider = "gemini"
        assert config.get_api_base() == "https://generativelanguage.googleapis.com/v1beta"

    def test_get_api_base_anthropic_default(self):
        config = Config()
        config.agent.provider = "anthropic"
        assert config.get_api_base() == "https://api.anthropic.com"

    def test_get_api_base_none_when_no_provider(self):
        config = Config()
        assert config.get_api_base() is None

    # --- get_provider_config routing ---

    def test_get_provider_config_openai(self):
        config = Config()
        config.agent.provider = "openai"
        config.providers.openai.api_key = "sk-openai"
        pc = config.get_provider_config()
        assert pc is config.providers.openai
        assert pc.api_key == "sk-openai"

    def test_get_provider_config_gemini(self):
        config = Config()
        config.agent.provider = "gemini"
        pc = config.get_provider_config()
        assert pc is config.providers.gemini

    def test_get_provider_config_anthropic(self):
        config = Config()
        config.agent.provider = "anthropic"
        pc = config.get_provider_config()
        assert pc is config.providers.anthropic

    def test_get_provider_config_none_when_no_provider(self):
        config = Config()
        assert config.get_provider_config() is None

    def test_get_provider_config_none_when_unknown_provider(self):
        config = Config()
        config.agent.provider = "unknown"
        assert config.get_provider_config() is None


class TestConfigPersistence:
    """Tests for config file operations."""

    def test_get_config_path(self):
        path = get_config_path()
        assert path.name == "config.json"
        assert ".sparkagent" in str(path)

    def test_save_and_load_config(self, temp_dir):
        config_path = temp_dir / "config.json"

        with patch("sparkagent.config.schema.get_config_path", return_value=config_path):
            # Create and save config
            config = Config()
            config.agent.provider = "openai"
            config.agent.model = "gpt-4.1"
            config.providers.openai.api_key = "test-key"
            save_config(config)

            # Load config
            loaded = load_config()
            assert loaded.agent.provider == "openai"
            assert loaded.agent.model == "gpt-4.1"
            assert loaded.providers.openai.api_key == "test-key"

    def test_load_config_missing_file(self, temp_dir):
        config_path = temp_dir / "nonexistent.json"

        with patch("sparkagent.config.schema.get_config_path", return_value=config_path):
            config = load_config()
            # Should return default config
            assert config.agent.model == ""

    def test_load_config_invalid_json(self, temp_dir):
        config_path = temp_dir / "config.json"
        config_path.write_text("invalid json {{{")

        with patch("sparkagent.config.schema.get_config_path", return_value=config_path):
            config = load_config()
            # Should return default config on error
            assert config.agent.model == ""

    def test_config_json_serialization(self):
        config = Config()
        config.agent.provider = "anthropic"
        config.agent.model = "claude-sonnet-4-6"

        json_str = config.model_dump_json()
        data = json.loads(json_str)

        assert data["agent"]["provider"] == "anthropic"
        assert data["agent"]["model"] == "claude-sonnet-4-6"
        assert "providers" in data
        assert "gemini" in data["providers"]
        assert "anthropic" in data["providers"]
        assert "channels" in data

    def test_config_json_round_trip(self, temp_dir):
        """Test that all new fields survive save/load cycle."""
        config_path = temp_dir / "config.json"

        with patch("sparkagent.config.schema.get_config_path", return_value=config_path):
            config = Config()
            config.agent.provider = "gemini"
            config.agent.model = "gemini-2.5-flash"
            config.providers.gemini.api_key = "gemini-key-123"
            config.providers.gemini.api_base = "https://custom.gemini.api"
            save_config(config)

            loaded = load_config()
            assert loaded.agent.provider == "gemini"
            assert loaded.agent.model == "gemini-2.5-flash"
            assert loaded.providers.gemini.api_key == "gemini-key-123"
            assert loaded.providers.gemini.api_base == "https://custom.gemini.api"

    def test_config_json_round_trip_with_oauth(self, temp_dir):
        """Test that OAuth fields survive save/load cycle."""
        config_path = temp_dir / "config.json"

        with patch("sparkagent.config.schema.get_config_path", return_value=config_path):
            config = Config()
            config.agent.provider = "anthropic"
            config.agent.model = "claude-opus-4-6"
            config.providers.anthropic.api_key = "sk-ant-oat01-access"
            config.providers.anthropic.refresh_token = "refresh-xyz"
            config.providers.anthropic.expires_at = "2026-03-01T12:00:00+00:00"
            config.providers.anthropic.token_type = "oauth"
            save_config(config)

            loaded = load_config()
            assert loaded.agent.provider == "anthropic"
            assert loaded.providers.anthropic.api_key == "sk-ant-oat01-access"
            assert loaded.providers.anthropic.refresh_token == "refresh-xyz"
            assert loaded.providers.anthropic.expires_at == "2026-03-01T12:00:00+00:00"
            assert loaded.providers.anthropic.token_type == "oauth"

    def test_backward_compat_missing_oauth_fields(self, temp_dir):
        """Loading old config JSON without OAuth fields should use defaults."""
        config_path = temp_dir / "config.json"

        # Write old-style config without refresh_token/expires_at/token_type
        old_config = {
            "agent": {"provider": "anthropic", "model": "claude-sonnet-4-6"},
            "providers": {
                "openai": {"api_key": "", "api_base": None},
                "gemini": {"api_key": "", "api_base": None},
                "anthropic": {"api_key": "sk-ant-api03-old-key", "api_base": None},
            },
            "channels": {"telegram": {"enabled": False, "token": "", "allow_from": []}},
            "tools": {"web_search": {"api_key": ""}},
        }
        config_path.write_text(json.dumps(old_config))

        with patch("sparkagent.config.schema.get_config_path", return_value=config_path):
            loaded = load_config()
            assert loaded.providers.anthropic.api_key == "sk-ant-api03-old-key"
            # New fields should default to empty strings
            assert loaded.providers.anthropic.refresh_token == ""
            assert loaded.providers.anthropic.expires_at == ""
            assert loaded.providers.anthropic.token_type == ""
