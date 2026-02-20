"""Configuration module."""

from sparkagent.config.schema import (
    Config,
    load_config,
    save_config,
    get_config_path,
)

__all__ = ["Config", "load_config", "save_config", "get_config_path"]
