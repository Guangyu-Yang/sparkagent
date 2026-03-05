# Docstring Conventions

## Format

All `sparkagent/` source files use **Google-style** docstrings.

## Two-Tier System

### Full Google-style
Use for public methods with 2+ parameters or non-obvious behavior:

```python
def execute(self, args: dict[str, Any]) -> ToolResult:
    """Run the shell command in a sandboxed environment.

    Args:
        args: Tool arguments containing "command" key.

    Returns:
        Result with stdout/stderr output.

    Raises:
        ToolError: If the command is blocked by safety guards.
    """
```

### One-liner
Use for simple properties, dunder methods, trivial helpers, and `__init__` where the class docstring suffices:

```python
@property
def name(self) -> str:
    """Return the tool display name."""
```

## Style Rules

1. **Imperative mood** for the first line: "Return", not "Returns the".
2. **No type duplication** — types belong in annotations, not docstrings.
3. **Blank line** between the summary line and Args/Returns/Raises sections.
4. **No trailing period** on the summary line unless it is a full sentence.
5. **Args descriptions** start lowercase, no trailing period.
6. **One blank line** before the closing `"""` only for multi-line docstrings.

## Scope

- **Required:** all `sparkagent/` source files.
- **Not required:** tests (`tests/`), `conftest.py`, `__init__.py` re-export modules.
