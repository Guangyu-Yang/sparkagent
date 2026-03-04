# Channels — I/O Channel Integrations

Abstract channel interface and concrete implementations for receiving/sending messages.

## Files

| File | Purpose |
|------|---------|
| `base.py` | `BaseChannel` ABC — defines `start()`, `stop()`, `send()` interface |
| `telegram.py` | `TelegramChannel` — Telegram bot integration with photo support and HTML formatting |

## Key Abstractions

### BaseChannel (ABC)

```python
class BaseChannel(ABC):
    name: str = "base"

    def __init__(self, bus: MessageBus): ...

    async start() -> None      # Begin listening
    async stop() -> None       # Shut down
    async send(msg: OutboundMessage) -> None  # Deliver a response
```

Protected helper: `_publish_inbound(sender_id, chat_id, content, media?, metadata?)` — constructs an `InboundMessage` and publishes it to the bus.

### TelegramChannel

Wraps `python-telegram-bot` (optional dependency — guarded by `TELEGRAM_AVAILABLE` flag).

- Handles text and photo messages
- Converts markdown responses to Telegram-safe HTML via `markdown_to_telegram_html()`
- Supports user allowlisting via `config.channels.telegram.allow_from`
- Downloads photos to `~/.sparkagent/media/`

## Usage

Channels are started by the gateway command. Each channel:
1. Calls `start()` to begin polling/listening
2. Publishes `InboundMessage` to the bus on user input
3. Consumes `OutboundMessage` from the bus via `send()`
