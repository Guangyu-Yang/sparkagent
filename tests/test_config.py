"""Tests for configuration schema."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from sparkagent.config.schema import (
    AgentConfig,
    ChannelsConfig,
    Config,
    ProviderConfig,
    ProvidersConfig,
    TelegramConfig,
    ToolsConfig,
    WebSearchConfig,
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

    def test_custom_values(self):
        config = ProviderConfig(
            api_key="sk-test123",
            api_base="https://api.example.com"
        )
        assert config.api_key == "sk-test123"
        assert config.api_base == "https://api.example.com"


class TestAgentConfig:
    """Tests for AgentConfig."""

    def test_default_values(self):
        config = AgentConfig()
        assert config.workspace == "~/.sparkagent/workspace"
        assert config.model == "gpt-4o"
        assert config.max_iterations == 20

    def test_custom_values(self):
        config = AgentConfig(
            workspace="/custom/workspace",
            model="gpt-3.5-turbo",
            max_iterations=10
        )
        assert config.workspace == "/custom/workspace"
        assert config.model == "gpt-3.5-turbo"
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

    def test_get_api_key_openrouter_priority(self):
        config = Config()
        config.providers.openrouter.api_key = "openrouter-key"
        config.providers.openai.api_key = "openai-key"
        assert config.get_api_key() == "openrouter-key"

    def test_get_api_key_openai_fallback(self):
        config = Config()
        config.providers.openai.api_key = "openai-key"
        assert config.get_api_key() == "openai-key"

    def test_get_api_key_none(self):
        config = Config()
        assert config.get_api_key() is None

    def test_get_api_base_openrouter(self):
        config = Config()
        config.providers.openrouter.api_key = "key"
        assert config.get_api_base() == "https://openrouter.ai/api/v1"

    def test_get_api_base_openrouter_custom(self):
        config = Config()
        config.providers.openrouter.api_key = "key"
        config.providers.openrouter.api_base = "https://custom.api.com"
        assert config.get_api_base() == "https://custom.api.com"

    def test_get_api_base_openai(self):
        config = Config()
        config.providers.openai.api_key = "key"
        config.providers.openai.api_base = "https://openai.custom.com"
        assert config.get_api_base() == "https://openai.custom.com"


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
            config.agent.model = "test-model"
            config.providers.openai.api_key = "test-key"
            save_config(config)

            # Load config
            loaded = load_config()
            assert loaded.agent.model == "test-model"
            assert loaded.providers.openai.api_key == "test-key"

    def test_load_config_missing_file(self, temp_dir):
        config_path = temp_dir / "nonexistent.json"

        with patch("sparkagent.config.schema.get_config_path", return_value=config_path):
            config = load_config()
            # Should return default config
            assert config.agent.model == "gpt-4o"

    def test_load_config_invalid_json(self, temp_dir):
        config_path = temp_dir / "config.json"
        config_path.write_text("invalid json {{{")

        with patch("sparkagent.config.schema.get_config_path", return_value=config_path):
            config = load_config()
            # Should return default config on error
            assert config.agent.model == "gpt-4o"

    def test_config_json_serialization(self):
        config = Config()
        config.agent.model = "custom-model"

        json_str = config.model_dump_json()
        data = json.loads(json_str)

        assert data["agent"]["model"] == "custom-model"
        assert "providers" in data
        assert "channels" in data
