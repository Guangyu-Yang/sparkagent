# Bus — Async Message Bus

Queue-based pub/sub system for routing messages between channels and the agent loop.

## Files

| File | Purpose |
|------|---------|
| `events.py` | `InboundMessage`, `OutboundMessage` dataclasses, `MessageBus` class |

## Key Abstractions

### InboundMessage

Represents a message arriving from any channel.

| Field | Type | Description |
|-------|------|-------------|
| `channel` | `str` | Source channel (`"cli"`, `"telegram"`) |
| `sender_id` | `str` | User identifier |
| `chat_id` | `str` | Chat/conversation identifier |
| `content` | `str` | Message text |
| `timestamp` | `datetime` | Defaults to `now()` |
| `media` | `list[str]` | File paths for attached media |
| `metadata` | `dict` | Arbitrary extra data |

Property: `session_key` → `"{channel}:{chat_id}"` (used as session identifier).

### OutboundMessage

Represents a response going back to a channel.

| Field | Type | Description |
|-------|------|-------------|
| `channel` | `str` | Target channel |
| `chat_id` | `str` | Destination chat |
| `content` | `str` | Response text |
| `reply_to` | `str \| None` | Optional reply reference |
| `media` | `list[str]` | Attached media paths |
| `metadata` | `dict` | Arbitrary extra data |

### MessageBus

Async message router with separate inbound and outbound queues.

- `publish_inbound(msg)` / `get_inbound(timeout)` — channel → agent
- `publish_outbound(msg)` / `get_outbound(timeout)` — agent → channel

## Data Flow

```
Channel → publish_inbound() → [queue] → AgentLoop.run() consumes
AgentLoop → publish_outbound() → [queue] → Channel.send() consumes
```
