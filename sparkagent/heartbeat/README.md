# Heartbeat — Scheduled Task Service

Periodic timer that reads a task schedule from the workspace and uses the LLM to decide whether to execute tasks.

## Files

| File | Purpose |
|------|---------|
| `service.py` | `HeartbeatService` — timer loop that ticks at a configurable interval |

## Key Abstractions

### HeartbeatService

```python
HeartbeatService(
    provider,             # LLM provider
    model,                # model name
    workspace,            # workspace Path (reads HEARTBEAT.md)
    interval_minutes=30,  # tick interval
    on_execute=None,      # async callback to run a task
    on_notify=None,       # async callback to send results
)
```

- `run()` — long-running coroutine that ticks periodically
- `stop()` — signals the loop to exit
- `trigger_now()` — runs a single tick immediately

### Tick Behavior

Each tick:
1. Reads `HEARTBEAT.md` from the workspace
2. Sends the file content + current time to the LLM with a heartbeat tool schema
3. LLM returns a tool call with `action` (`"skip"` or `"run"`), `task`, and `reason`
4. If `"run"` → calls `on_execute(task)` → calls `on_notify(result)` with the output

The heartbeat tool schema defines two actions:
- **skip** — no task needs to run right now
- **run** — execute the described task
