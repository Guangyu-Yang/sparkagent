"""Tests for message bus."""

import asyncio
from datetime import datetime

import pytest

from sparkagent.bus import MessageBus
from sparkagent.bus.events import InboundMessage, OutboundMessage


class TestInboundMessage:
    """Tests for InboundMessage dataclass."""

    def test_create_message(self):
        msg = InboundMessage(
            channel="telegram",
            sender_id="user123",
            chat_id="chat456",
            content="Hello!"
        )

        assert msg.channel == "telegram"
        assert msg.sender_id == "user123"
        assert msg.chat_id == "chat456"
        assert msg.content == "Hello!"
        assert isinstance(msg.timestamp, datetime)
        assert msg.media == []
        assert msg.metadata == {}

    def test_session_key(self):
        msg = InboundMessage(
            channel="telegram",
            sender_id="user123",
            chat_id="chat456",
            content="Hello!"
        )

        assert msg.session_key == "telegram:chat456"

    def test_with_media_and_metadata(self):
        msg = InboundMessage(
            channel="cli",
            sender_id="user",
            chat_id="session1",
            content="Check this image",
            media=["/path/to/image.jpg"],
            metadata={"key": "value"}
        )

        assert msg.media == ["/path/to/image.jpg"]
        assert msg.metadata == {"key": "value"}


class TestOutboundMessage:
    """Tests for OutboundMessage dataclass."""

    def test_create_message(self):
        msg = OutboundMessage(
            channel="telegram",
            chat_id="chat456",
            content="Hello back!"
        )

        assert msg.channel == "telegram"
        assert msg.chat_id == "chat456"
        assert msg.content == "Hello back!"
        assert msg.reply_to is None
        assert msg.media == []
        assert msg.metadata == {}

    def test_with_reply_to(self):
        msg = OutboundMessage(
            channel="telegram",
            chat_id="chat456",
            content="Response",
            reply_to="msg123"
        )

        assert msg.reply_to == "msg123"


class TestMessageBus:
    """Tests for MessageBus class."""

    def test_create_bus(self):
        bus = MessageBus()
        assert bus._outbound_handlers == []

    async def test_publish_and_consume_inbound(self):
        bus = MessageBus()
        msg = InboundMessage(
            channel="cli",
            sender_id="user",
            chat_id="session",
            content="Test message"
        )

        await bus.publish_inbound(msg)
        received = await bus.consume_inbound()

        assert received is msg
        assert received.content == "Test message"

    async def test_publish_and_consume_outbound(self):
        bus = MessageBus()
        msg = OutboundMessage(
            channel="cli",
            chat_id="session",
            content="Response"
        )

        await bus.publish_outbound(msg)
        received = await bus.consume_outbound()

        assert received is msg
        assert received.content == "Response"

    async def test_inbound_queue_ordering(self):
        bus = MessageBus()

        for i in range(3):
            msg = InboundMessage(
                channel="cli",
                sender_id="user",
                chat_id="session",
                content=f"Message {i}"
            )
            await bus.publish_inbound(msg)

        for i in range(3):
            received = await bus.consume_inbound()
            assert received.content == f"Message {i}"

    async def test_outbound_handler(self):
        bus = MessageBus()
        received_messages = []

        async def handler(msg: OutboundMessage):
            received_messages.append(msg)

        bus.on_outbound(handler)

        msg = OutboundMessage(
            channel="cli",
            chat_id="session",
            content="Test"
        )
        await bus.publish_outbound(msg)

        assert len(received_messages) == 1
        assert received_messages[0] is msg

    async def test_multiple_outbound_handlers(self):
        bus = MessageBus()
        handler1_messages = []
        handler2_messages = []

        async def handler1(msg: OutboundMessage):
            handler1_messages.append(msg)

        async def handler2(msg: OutboundMessage):
            handler2_messages.append(msg)

        bus.on_outbound(handler1)
        bus.on_outbound(handler2)

        msg = OutboundMessage(
            channel="cli",
            chat_id="session",
            content="Test"
        )
        await bus.publish_outbound(msg)

        assert len(handler1_messages) == 1
        assert len(handler2_messages) == 1

    async def test_handler_error_does_not_break_bus(self):
        bus = MessageBus()
        good_handler_messages = []

        async def failing_handler(msg: OutboundMessage):
            raise ValueError("Handler failed")

        async def good_handler(msg: OutboundMessage):
            good_handler_messages.append(msg)

        bus.on_outbound(failing_handler)
        bus.on_outbound(good_handler)

        msg = OutboundMessage(
            channel="cli",
            chat_id="session",
            content="Test"
        )

        # Should not raise an error
        await bus.publish_outbound(msg)

        # Good handler should still receive the message
        assert len(good_handler_messages) == 1

    async def test_consume_inbound_blocks_until_available(self):
        bus = MessageBus()
        result = []

        async def producer():
            await asyncio.sleep(0.1)
            msg = InboundMessage(
                channel="cli",
                sender_id="user",
                chat_id="session",
                content="Delayed message"
            )
            await bus.publish_inbound(msg)

        async def consumer():
            msg = await bus.consume_inbound()
            result.append(msg)

        await asyncio.gather(producer(), consumer())

        assert len(result) == 1
        assert result[0].content == "Delayed message"
