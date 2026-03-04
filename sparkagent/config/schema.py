"""Configuration schema using Pydantic."""

import json
import logging
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


class TelegramConfig(BaseModel):
    """Telegram channel configuration."""

    enabled: bool = False
    token: str = Field(default="", repr=False)
    allow_from: list[str] = Field(default_factory=list)


class ChannelsConfig(BaseModel):
    """Chat channels configuration."""

    telegram: TelegramConfig = Field(default_factory=TelegramConfig)


class ProviderConfig(BaseModel):
    """LLM provider configuration."""

    api_key: str = Field(default="", repr=False)
    api_base: str | None = None
    refresh_token: str = Field(default="", repr=False)  # OAuth refresh token
    expires_at: str = ""  # ISO 8601 expiry of access_token (empty for API key auth)
    token_type: Literal["oauth", ""] = ""  # "oauth" when using OAuth, empty for API key auth

    @field_validator("api_base")
    @classmethod
    def validate_api_base(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip().rstrip("/")
        if not v.startswith(("https://", "http://")):
            raise ValueError("api_base must use http:// or https:// scheme")
        return v


class ProvidersConfig(BaseModel):
    """LLM providers configuration."""

    openai: ProviderConfig = Field(default_factory=ProviderConfig)
    gemini: ProviderConfig = Field(default_factory=ProviderConfig)
    anthropic: ProviderConfig = Field(default_factory=ProviderConfig)


class AgentConfig(BaseModel):
    """Agent configuration."""

    workspace: str = "~/.sparkagent/workspace"
    provider: Literal["openai", "gemini", "anthropic", ""] = ""
    model: str = ""
    max_iterations: int = Field(default=20, ge=1, le=100)
    execution_mode: Literal["function_calling", "code_act", "auto"] = "function_calling"


class MemoryConfig(BaseModel):
    """Memory skill system configuration."""

    enabled: bool = False
    top_k_skills: int = Field(default=3, ge=1, le=20)
    max_memories_in_context: int = Field(default=10, ge=1, le=50)
    max_memory_chars: int = Field(default=2000, ge=100, le=50_000)
    hard_case_threshold: int = Field(default=10, ge=1, le=100)
    auto_evolve: bool = True


class HeartbeatConfig(BaseModel):
    """Heartbeat / scheduled task service configuration."""

    enabled: bool = False
    interval_minutes: int = Field(default=30, ge=1, le=1440)
    notify_chat_id: str = ""  # Optional Telegram chat_id for notifications


class WebSearchConfig(BaseModel):
    """Web search configuration."""

    api_key: str = Field(default="", repr=False)  # Brave Search API key


class TavilyConfig(BaseModel):
    """Tavily search and extract configuration."""

    api_key: str = Field(default="", repr=False)


class ToolsConfig(BaseModel):
    """Tools configuration."""

    web_search: WebSearchConfig = Field(default_factory=WebSearchConfig)
    tavily: TavilyConfig = Field(default_factory=TavilyConfig)


class Config(BaseModel):
    """Root configuration."""

    agent: AgentConfig = Field(default_factory=AgentConfig)
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    heartbeat: HeartbeatConfig = Field(default_factory=HeartbeatConfig)

    @property
    def workspace_path(self) -> Path:
        """Get expanded workspace path."""
        return Path(self.agent.workspace).expanduser()

    def get_provider_config(self) -> ProviderConfig | None:
        """Get the ProviderConfig for the active provider."""
        p = self.agent.provider
        return getattr(self.providers, p, None) if p else None

    def get_api_key(self) -> str | None:
        """Get API key based on active provider."""
        pc = self.get_provider_config()
        return (pc.api_key or None) if pc else None

    def get_api_base(self) -> str | None:
        """Get API base URL based on active provider."""
        pc = self.get_provider_config()
        if pc is None:
            return None
        if pc.api_base:
            return pc.api_base
        defaults = {
            "gemini": "https://generativelanguage.googleapis.com/v1beta",
            "anthropic": "https://api.anthropic.com",
        }
        return defaults.get(self.agent.provider)


def get_config_path() -> Path:
    """Get the config file path."""
    return Path.home() / ".sparkagent" / "config.json"


def load_config() -> Config:
    """Load configuration from file."""
    config_path = get_config_path()

    if config_path.exists():
        try:
            data = json.loads(config_path.read_text())
            return Config(**data)
        except Exception as exc:
            logger.warning("Failed to load config from %s: %s", config_path, exc)

    return Config()


def save_config(config: Config) -> None:
    """Save configuration to file."""
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(config.model_dump_json(indent=2))
    config_path.chmod(0o600)
