"""Configuration schema using Pydantic."""

import json
from pathlib import Path
from pydantic import BaseModel, Field


class TelegramConfig(BaseModel):
    """Telegram channel configuration."""
    enabled: bool = False
    token: str = ""
    allow_from: list[str] = Field(default_factory=list)


class ChannelsConfig(BaseModel):
    """Chat channels configuration."""
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)


class ProviderConfig(BaseModel):
    """LLM provider configuration."""
    api_key: str = ""
    api_base: str | None = None


class ProvidersConfig(BaseModel):
    """LLM providers configuration."""
    openai: ProviderConfig = Field(default_factory=ProviderConfig)
    openrouter: ProviderConfig = Field(default_factory=ProviderConfig)


class AgentConfig(BaseModel):
    """Agent configuration."""
    workspace: str = "~/.myautoagent/workspace"
    model: str = "gpt-4o"
    max_iterations: int = 20


class WebSearchConfig(BaseModel):
    """Web search configuration."""
    api_key: str = ""  # Brave Search API key


class ToolsConfig(BaseModel):
    """Tools configuration."""
    web_search: WebSearchConfig = Field(default_factory=WebSearchConfig)


class Config(BaseModel):
    """Root configuration."""
    agent: AgentConfig = Field(default_factory=AgentConfig)
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    
    @property
    def workspace_path(self) -> Path:
        """Get expanded workspace path."""
        return Path(self.agent.workspace).expanduser()
    
    def get_api_key(self) -> str | None:
        """Get API key (OpenRouter takes priority)."""
        return (
            self.providers.openrouter.api_key or
            self.providers.openai.api_key or
            None
        )
    
    def get_api_base(self) -> str | None:
        """Get API base URL."""
        if self.providers.openrouter.api_key:
            return self.providers.openrouter.api_base or "https://openrouter.ai/api/v1"
        return self.providers.openai.api_base


def get_config_path() -> Path:
    """Get the config file path."""
    return Path.home() / ".myautoagent" / "config.json"


def load_config() -> Config:
    """Load configuration from file."""
    config_path = get_config_path()
    
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text())
            return Config(**data)
        except Exception:
            pass
    
    return Config()


def save_config(config: Config) -> None:
    """Save configuration to file."""
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(config.model_dump_json(indent=2))
