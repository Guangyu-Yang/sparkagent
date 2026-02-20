"""Base class for chat channels."""

from abc import ABC, abstractmethod
from typing import Any

from sparkagent.bus import MessageBus, InboundMessage, OutboundMessage


class BaseChannel(ABC):
    """Abstract base class for chat channels."""
    
    name: str = "base"
    
    def __init__(self, bus: MessageBus):
        self.bus = bus
        self._running = False
    
    @abstractmethod
    async def start(self) -> None:
        """Start the channel."""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """Stop the channel."""
        pass
    
    @abstractmethod
    async def send(self, msg: OutboundMessage) -> None:
        """Send a message through this channel."""
        pass
    
    async def _publish_inbound(
        self,
        sender_id: str,
        chat_id: str,
        content: str,
        media: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Helper to publish an inbound message to the bus."""
        msg = InboundMessage(
            channel=self.name,
            sender_id=sender_id,
            chat_id=chat_id,
            content=content,
            media=media or [],
            metadata=metadata or {},
        )
        await self.bus.publish_inbound(msg)
