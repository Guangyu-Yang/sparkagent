# Session — Conversation Persistence

JSONL-based storage for conversation history, with in-memory caching.

## Files

| File | Purpose |
|------|---------|
| `manager.py` | `Session` dataclass and `SessionManager` class |

## Key Abstractions

### Session

Holds the message history for one conversation.

```python
@dataclass
class Session:
    key: str                          # e.g. "cli:default", "telegram:12345"
    messages: list[dict[str, Any]]    # [{role, content, timestamp}, ...]
    created_at: datetime
    updated_at: datetime
```

- `add_message(role, content)` — appends a message
- `get_history(max_messages=50)` — returns recent messages as `[{role, content}]`
- `clear()` — wipes all messages

### SessionManager

Manages session lifecycle and disk persistence.

```python
SessionManager(storage_dir=~/.sparkagent/sessions)
```

- `get_or_create(key)` — returns cached session, loads from disk, or creates new
- `save(session)` — writes to JSONL (metadata line + one message per line)
- `delete(key)` — removes from cache and disk
- `list_sessions()` — lists all stored session keys

### Storage Format

Each session is a `.jsonl` file:
```
{"_type": "metadata", "created_at": "...", "updated_at": "..."}
{"role": "user", "content": "...", "timestamp": "..."}
{"role": "assistant", "content": "...", "timestamp": "..."}
```

Session keys are converted to safe filenames (non-word characters → `_`).
