"""Chat channel implementations."""

from sparkagent.channels.base import BaseChannel
from sparkagent.channels.telegram import TelegramChannel

__all__ = ["BaseChannel", "TelegramChannel"]
