"""Tests for tool registry."""

from typing import Any

import pytest

from sparkagent.agent.tools.base import Tool
from sparkagent.agent.tools.registry import ToolRegistry


class MockTool(Tool):
    """A mock tool for testing."""

    def __init__(self, name: str = "mock_tool"):
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return "A mock tool for testing"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "input": {"type": "string", "description": "Input text"}
            },
            "required": ["input"]
        }

    async def execute(self, input: str, **kwargs: Any) -> str:
        return f"Executed with: {input}"


class FailingTool(Tool):
    """A tool that always fails."""

    @property
    def name(self) -> str:
        return "failing_tool"

    @property
    def description(self) -> str:
        return "A tool that always fails"

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs: Any) -> str:
        raise ValueError("Tool execution failed")


class TestToolRegistry:
    """Tests for ToolRegistry."""

    def test_empty_registry(self):
        registry = ToolRegistry()
        assert len(registry) == 0
        assert registry.list_tools() == []

    def test_register_tool(self):
        registry = ToolRegistry()
        tool = MockTool()

        registry.register(tool)

        assert len(registry) == 1
        assert "mock_tool" in registry
        assert registry.list_tools() == ["mock_tool"]

    def test_register_multiple_tools(self):
        registry = ToolRegistry()

        registry.register(MockTool("tool1"))
        registry.register(MockTool("tool2"))
        registry.register(MockTool("tool3"))

        assert len(registry) == 3
        assert set(registry.list_tools()) == {"tool1", "tool2", "tool3"}

    def test_register_overwrites_existing(self):
        registry = ToolRegistry()
        tool1 = MockTool("same_name")
        tool2 = MockTool("same_name")

        registry.register(tool1)
        registry.register(tool2)

        assert len(registry) == 1
        assert registry.get("same_name") is tool2

    def test_unregister_tool(self):
        registry = ToolRegistry()
        registry.register(MockTool())

        registry.unregister("mock_tool")

        assert len(registry) == 0
        assert "mock_tool" not in registry

    def test_unregister_nonexistent_tool(self):
        registry = ToolRegistry()

        # Should not raise an error
        registry.unregister("nonexistent")
        assert len(registry) == 0

    def test_get_tool(self):
        registry = ToolRegistry()
        tool = MockTool()
        registry.register(tool)

        retrieved = registry.get("mock_tool")

        assert retrieved is tool

    def test_get_nonexistent_tool(self):
        registry = ToolRegistry()

        result = registry.get("nonexistent")

        assert result is None

    def test_contains(self):
        registry = ToolRegistry()
        registry.register(MockTool())

        assert "mock_tool" in registry
        assert "nonexistent" not in registry

    def test_get_schemas(self):
        registry = ToolRegistry()
        registry.register(MockTool("tool1"))
        registry.register(MockTool("tool2"))

        schemas = registry.get_schemas()

        assert len(schemas) == 2
        assert all(s["type"] == "function" for s in schemas)
        names = {s["function"]["name"] for s in schemas}
        assert names == {"tool1", "tool2"}

    async def test_execute_tool(self):
        registry = ToolRegistry()
        registry.register(MockTool())

        result = await registry.execute("mock_tool", {"input": "test"})

        assert result == "Executed with: test"

    async def test_execute_nonexistent_tool(self):
        registry = ToolRegistry()

        result = await registry.execute("nonexistent", {})

        assert "Error" in result
        assert "not found" in result.lower()

    async def test_execute_tool_error_handling(self):
        registry = ToolRegistry()
        registry.register(FailingTool())

        result = await registry.execute("failing_tool", {})

        assert "Error" in result
        assert "failed" in result.lower()


class TestToolBase:
    """Tests for the base Tool class."""

    def test_to_openai_schema(self):
        tool = MockTool()
        schema = tool.to_openai_schema()

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "mock_tool"
        assert schema["function"]["description"] == "A mock tool for testing"
        assert "properties" in schema["function"]["parameters"]
