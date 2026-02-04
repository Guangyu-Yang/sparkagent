"""Message bus for routing messages between components."""

import asyncio
from typing import Callable, Awaitable

from myautoagent.bus.events import InboundMessage, OutboundMessage


class MessageBus:
    """
    Async message bus for routing messages.
    
    Provides queues for inbound (user → agent) and outbound (agent → user) messages.
    """
    
    def __init__(self):
        self._inbound: asyncio.Queue[InboundMessage] = asyncio.Queue()
        self._outbound: asyncio.Queue[OutboundMessage] = asyncio.Queue()
        self._outbound_handlers: list[Callable[[OutboundMessage], Awaitable[None]]] = []
    
    async def publish_inbound(self, msg: InboundMessage) -> None:
        """Publish an inbound message to the queue."""
        await self._inbound.put(msg)
    
    async def consume_inbound(self) -> InboundMessage:
        """Consume the next inbound message (blocks until available)."""
        return await self._inbound.get()
    
    async def publish_outbound(self, msg: OutboundMessage) -> None:
        """Publish an outbound message and notify handlers."""
        await self._outbound.put(msg)
        for handler in self._outbound_handlers:
            try:
                await handler(msg)
            except Exception:
                pass  # Don't let handler errors break the bus
    
    async def consume_outbound(self) -> OutboundMessage:
        """Consume the next outbound message."""
        return await self._outbound.get()
    
    def on_outbound(self, handler: Callable[[OutboundMessage], Awaitable[None]]) -> None:
        """Register a handler for outbound messages."""
        self._outbound_handlers.append(handler)


__all__ = ["MessageBus", "InboundMessage", "OutboundMessage"]
