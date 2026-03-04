# CodeAct — CodeAct Execution Mode

Lets the LLM generate and execute Python code instead of structured tool calls. Tools are injected as callable functions into a sandboxed namespace.

## Files

| File | Purpose |
|------|---------|
| `parser.py` | `CodeActParser` — extracts executable code blocks from LLM output (`<execute>` tags or markdown fences) |
| `executor.py` | `CodeActExecutor` — runs Python code in a persistent namespace with tool wrappers and output capture |
| `sandbox.py` | `build_safe_builtins()`, `IMPORT_ALLOWLIST` — restricts builtins and imports for safe execution |

## Key Abstractions

### CodeActParser

Stateless parser that splits LLM output into typed blocks.

- `parse(text) -> list[CodeActBlock]` — returns blocks of kind `"thought"`, `"execute"`, or `"text"`
- `has_code(text) -> bool` — quick check for executable content
- `extract_code(text) -> str | None` — first executable block
- `extract_text_response(text) -> str` — prose only, tags stripped

`CodeActBlock` is a dataclass with fields `kind` (Literal) and `content` (str).

### CodeActExecutor

Maintains a persistent `_namespace` dict per session. Tools from `ToolRegistry` are wrapped as synchronous callables (async bridged via `ThreadPoolExecutor`).

```
CodeActExecutor(tools: ToolRegistry, timeout=30, max_output=4000)
```

- `execute(code) -> str` — runs code, returns stdout + stderr (truncated to `max_output`)
- `reset()` — clears namespace for a fresh session

### Sandbox

- **`IMPORT_ALLOWLIST`** — `frozenset` of safe stdlib modules (`json`, `re`, `math`, `datetime`, `pathlib`, etc.)
- **`IMPORT_BLOCKLIST`** — `frozenset` of dangerous modules (`os`, `sys`, `subprocess`, `shutil`, etc.)
- **`build_safe_builtins()`** — returns a dict with safe builtins only; `__import__` replaced by a guarded version that enforces the allow/blocklists
