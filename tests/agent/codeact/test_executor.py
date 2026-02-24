"""Tests for the CodeAct executor."""

from typing import Any

from sparkagent.agent.codeact.executor import CodeActExecutor
from sparkagent.agent.tools.base import Tool
from sparkagent.agent.tools.registry import ToolRegistry

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

class EchoTool(Tool):
    """Simple tool that echoes its input."""

    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "Echoes the input"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to echo"},
            },
            "required": ["text"],
        }

    async def execute(self, text: str, **kwargs: Any) -> str:
        return f"ECHO: {text}"


class AddTool(Tool):
    """Tool that adds two numbers."""

    @property
    def name(self) -> str:
        return "add"

    @property
    def description(self) -> str:
        return "Adds two numbers"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "a": {"type": "integer"},
                "b": {"type": "integer"},
            },
            "required": ["a", "b"],
        }

    async def execute(self, a: int, b: int, **kwargs: Any) -> str:
        return str(int(a) + int(b))


def _make_registry(*tools: Tool) -> ToolRegistry:
    reg = ToolRegistry()
    for t in tools:
        reg.register(t)
    return reg


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------

class TestCodeActExecutor:
    def test_simple_print(self):
        executor = CodeActExecutor(_make_registry())
        result = executor.execute('print("hello")')
        assert "hello" in result

    def test_variable_persistence(self):
        executor = CodeActExecutor(_make_registry())
        executor.execute("x = 42")
        result = executor.execute("print(x)")
        assert "42" in result

    def test_tool_call(self):
        executor = CodeActExecutor(_make_registry(EchoTool()))
        result = executor.execute('result = echo(text="hi")\nprint(result)')
        assert "ECHO: hi" in result

    def test_tool_call_add(self):
        executor = CodeActExecutor(_make_registry(AddTool()))
        result = executor.execute('result = add(a=3, b=4)\nprint(result)')
        assert "7" in result

    def test_multi_tool_composition(self):
        executor = CodeActExecutor(_make_registry(EchoTool(), AddTool()))
        code = (
            'total = add(a=10, b=20)\n'
            'msg = echo(text=f"Total is {total}")\n'
            'print(msg)'
        )
        result = executor.execute(code)
        assert "Total is 30" in result

    def test_error_returns_traceback(self):
        executor = CodeActExecutor(_make_registry())
        result = executor.execute("1 / 0")
        assert "ZeroDivisionError" in result

    def test_syntax_error(self):
        executor = CodeActExecutor(_make_registry())
        result = executor.execute("def foo(")
        assert "SyntaxError" in result

    def test_blocked_import(self):
        executor = CodeActExecutor(_make_registry())
        result = executor.execute("import os")
        assert "not allowed" in result

    def test_allowed_import(self):
        executor = CodeActExecutor(_make_registry())
        result = executor.execute("import json\nprint(json.dumps({'a': 1}))")
        assert '{"a": 1}' in result

    def test_blocked_builtin_open(self):
        executor = CodeActExecutor(_make_registry())
        result = executor.execute('f = open("/etc/passwd")')
        assert "NameError" in result or "not defined" in result

    def test_no_output(self):
        executor = CodeActExecutor(_make_registry())
        result = executor.execute("x = 1")
        assert result == "(no output)"

    def test_reset_clears_namespace(self):
        executor = CodeActExecutor(_make_registry())
        executor.execute("secret = 42")
        executor.reset()
        result = executor.execute("print(secret)")
        assert "NameError" in result

    def test_output_truncation(self):
        executor = CodeActExecutor(_make_registry(), max_output=100)
        result = executor.execute('print("x" * 500)')
        assert "truncated" in result
        assert len(result) <= 200  # some overhead from the truncation message

    def test_loop_in_code(self):
        executor = CodeActExecutor(_make_registry())
        code = "total = 0\nfor i in range(5):\n    total += i\nprint(total)"
        result = executor.execute(code)
        assert "10" in result

    def test_conditional_in_code(self):
        executor = CodeActExecutor(_make_registry())
        code = 'x = 5\nif x > 3:\n    print("big")\nelse:\n    print("small")'
        result = executor.execute(code)
        assert "big" in result
