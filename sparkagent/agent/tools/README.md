# tools — Tool System

Abstract base class, registry, and built-in tool implementations for file, shell, and web operations.

> For a quick overview, see [Built-in Tools](../../../README.md#built-in-tools) in the main README.

## Files

| File | Purpose |
|------|---------|
| `base.py` | `Tool` ABC — defines `name`, `description`, `parameters`, `execute()`, and `to_openai_schema()` |
| `registry.py` | `ToolRegistry` — register/unregister/execute tools by name, produce OpenAI-format schemas |
| `filesystem.py` | `ReadFileTool`, `WriteFileTool`, `ListDirectoryTool`, `EditFileTool` |
| `shell.py` | `ShellTool` — executes shell commands with dangerous-command blocking |
| `web.py` | `WebSearchTool` (Brave API), `WebFetchTool` (HTTP fetch + HTML text extraction) |
| `tavily.py` | `TavilySearchTool`, `TavilyFetchTool` — Tavily web search and content extraction |

## Key Abstractions

### Tool (ABC)

Every tool implements:

| Member | Type | Description |
|--------|------|-------------|
| `name` | property | Unique identifier (e.g. `"read_file"`) |
| `description` | property | Human-readable purpose |
| `parameters` | property | JSON Schema dict for arguments |
| `execute(**kwargs)` | async method | Runs the tool, returns a string result |
| `to_openai_schema()` | method | Converts to OpenAI function-calling format |

### ToolRegistry

```
registry = ToolRegistry()
registry.register(tool)
registry.get_schemas()        # OpenAI-format tool list for LLM calls
await registry.execute(name, params)
```

Supports `len()`, `in`, `list_tools()`, and `unregister()`.

### Safety

`ShellTool` blocks commands matching `DANGEROUS_PATTERNS` (rm -rf, dd, shutdown, fork bombs, etc.) before execution. Commands have a configurable timeout (default 60s) and output is truncated at 10 KB.
