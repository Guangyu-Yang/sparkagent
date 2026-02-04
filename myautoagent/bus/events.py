"""Message events for the communication bus."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class InboundMessage:
    """Message received from a user or channel."""
    
    channel: str          # Source channel (cli, telegram, etc.)
    sender_id: str        # User identifier
    chat_id: str          # Chat/conversation identifier
    content: str          # Message text
    timestamp: datetime = field(default_factory=datetime.now)
    media: list[str] = field(default_factory=list)  # Media file paths
    metadata: dict[str, Any] = field(default_factory=dict)
    
    @property
    def session_key(self) -> str:
        """Generate unique session key."""
        return f"{self.channel}:{self.chat_id}"


@dataclass
class OutboundMessage:
    """Message to send to a user or channel."""
    
    channel: str
    chat_id: str
    content: str
    reply_to: str | None = None
    media: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
