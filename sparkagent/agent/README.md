# agent — Core Processing Engine

The main agent loop that receives messages, calls LLMs, executes tools, and returns responses.

## Files

| File | Purpose |
|------|---------|
| `loop.py` | `AgentLoop` — receives messages from the bus, orchestrates LLM calls and tool execution |
| `context.py` | `ContextBuilder` — assembles system prompts from workspace files, memory, and conversation history |
| `mode_selector.py` | `select_execution_mode()` — asks the LLM to classify a message as `function_calling` or `code_act` |
| `codeact/` | CodeAct execution mode — LLM generates Python code instead of tool calls (see [codeact/README.md](codeact/README.md)) |
| `tools/` | Tool system — ABC, registry, and built-in tools (see [tools/README.md](tools/README.md)) |

## Key Abstractions

### AgentLoop

The central processing engine. Supports two execution modes:

- **function_calling** — LLM returns structured tool calls, loop executes them and feeds results back
- **code_act** — LLM generates Python code that is executed in a sandboxed namespace with tools injected as functions

```
AgentLoop(bus, provider, workspace, model?, max_iterations=20, execution_mode="function_calling", memory_config?)
```

Public API:
- `run()` — long-running coroutine consuming from `MessageBus`
- `stop()` — signals the loop to exit
- `process_direct(content, session_key)` — one-shot message processing for CLI use

### ContextBuilder

Builds the `messages` list sent to the LLM provider. Loads workspace files (`AGENTS.md`, `SOUL.md`, `USER.md`, `TOOLS.md`), injects dynamic memory, and handles image attachments.

```
ContextBuilder(workspace, memory_store?)
```

- `build_system_prompt(current_message)` — full system prompt string
- `build_messages(history, current_message, media?, execution_mode, tool_schemas?)` — complete message list for the LLM

## Data Flow

```
InboundMessage → AgentLoop.run()
  → ContextBuilder assembles prompt + history
  → LLMProvider.chat() with tool schemas
  → Tool execution loop (up to max_iterations)
  → Final response → OutboundMessage published to bus
  → Session saved
```
