"""Tests for sparkagent.agent.context — the system prompt builder."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from sparkagent.agent.context import ContextBuilder


# ---------------------------------------------------------------------------
# System prompt assembly
# ---------------------------------------------------------------------------


class TestBuildSystemPrompt:
    def test_includes_identity(self, tmp_path: Path) -> None:
        cb = ContextBuilder(tmp_path)
        prompt = cb.build_system_prompt()
        assert "SparkAgent" in prompt
        assert str(tmp_path.resolve()) in prompt

    def test_loads_bootstrap_files(self, tmp_path: Path) -> None:
        (tmp_path / "AGENTS.md").write_text("Custom agent instructions")
        cb = ContextBuilder(tmp_path)
        prompt = cb.build_system_prompt()
        assert "Custom agent instructions" in prompt
        assert "AGENTS.md" in prompt

    def test_skips_missing_bootstrap(self, tmp_path: Path) -> None:
        """No crash when workspace files don't exist."""
        cb = ContextBuilder(tmp_path)
        prompt = cb.build_system_prompt()
        # Should still have identity section
        assert "SparkAgent" in prompt

    def test_loads_memory_md(self, tmp_path: Path) -> None:
        mem_dir = tmp_path / "memory"
        mem_dir.mkdir()
        (mem_dir / "MEMORY.md").write_text("User prefers dark mode.")
        cb = ContextBuilder(tmp_path)
        prompt = cb.build_system_prompt()
        assert "User prefers dark mode." in prompt
        assert "# Memory" in prompt

    def test_dynamic_memory(self, tmp_path: Path) -> None:
        store = MagicMock()
        store.retrieve_for_context.return_value = "Recalled: likes Python"
        cb = ContextBuilder(tmp_path, memory_store=store)
        prompt = cb.build_system_prompt(current_message="Tell me about Python")
        store.retrieve_for_context.assert_called_once_with("Tell me about Python")
        assert "Recalled: likes Python" in prompt
        assert "# Dynamic Memory" in prompt

    def test_dynamic_memory_not_called_without_message(self, tmp_path: Path) -> None:
        store = MagicMock()
        cb = ContextBuilder(tmp_path, memory_store=store)
        cb.build_system_prompt()  # no current_message
        store.retrieve_for_context.assert_not_called()


# ---------------------------------------------------------------------------
# Message assembly
# ---------------------------------------------------------------------------


class TestBuildMessages:
    def test_structure(self, tmp_path: Path) -> None:
        cb = ContextBuilder(tmp_path)
        msgs = cb.build_messages(history=[], current_message="hi")
        assert msgs[0]["role"] == "system"
        assert msgs[-1]["role"] == "user"
        assert msgs[-1]["content"] == "hi"

    def test_includes_history(self, tmp_path: Path) -> None:
        cb = ContextBuilder(tmp_path)
        history = [
            {"role": "user", "content": "old q"},
            {"role": "assistant", "content": "old a"},
        ]
        msgs = cb.build_messages(history=history, current_message="new q")
        assert msgs[1] == {"role": "user", "content": "old q"}
        assert msgs[2] == {"role": "assistant", "content": "old a"}
        assert msgs[-1]["content"] == "new q"

    def test_codeact_mode(self, tmp_path: Path) -> None:
        cb = ContextBuilder(tmp_path)
        schemas = [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read a file",
                    "parameters": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"],
                    },
                },
            }
        ]
        msgs = cb.build_messages(
            history=[],
            current_message="hi",
            execution_mode="code_act",
            tool_schemas=schemas,
        )
        system = msgs[0]["content"]
        assert "Code Execution Environment" in system
        assert "read_file" in system

    def test_function_calling_no_codeact(self, tmp_path: Path) -> None:
        cb = ContextBuilder(tmp_path)
        msgs = cb.build_messages(history=[], current_message="hi")
        system = msgs[0]["content"]
        assert "Code Execution Environment" not in system


# ---------------------------------------------------------------------------
# CodeAct helpers
# ---------------------------------------------------------------------------


class TestSchemaToSignature:
    def test_required_params(self) -> None:
        sig = ContextBuilder._schema_to_signature(
            "my_tool",
            {
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        )
        assert sig == "my_tool(path: str)"

    def test_optional_params(self) -> None:
        sig = ContextBuilder._schema_to_signature(
            "my_tool",
            {
                "properties": {"path": {"type": "string"}, "limit": {"type": "integer"}},
                "required": ["path"],
            },
        )
        assert "path: str" in sig
        assert "limit: int | None = None" in sig

    def test_type_mapping(self) -> None:
        sig = ContextBuilder._schema_to_signature(
            "t",
            {
                "properties": {
                    "a": {"type": "string"},
                    "b": {"type": "integer"},
                    "c": {"type": "number"},
                    "d": {"type": "boolean"},
                    "e": {"type": "array"},
                    "f": {"type": "object"},
                },
                "required": ["a", "b", "c", "d", "e", "f"],
            },
        )
        assert "a: str" in sig
        assert "b: int" in sig
        assert "c: float" in sig
        assert "d: bool" in sig
        assert "e: list" in sig
        assert "f: dict" in sig

    def test_get_codeact_instructions_lists_tools(self, tmp_path: Path) -> None:
        cb = ContextBuilder(tmp_path)
        schemas = [
            {
                "function": {
                    "name": "shell",
                    "description": "Run a command",
                    "parameters": {
                        "properties": {"cmd": {"type": "string"}},
                        "required": ["cmd"],
                    },
                }
            },
        ]
        text = cb._get_codeact_instructions(schemas)
        assert "shell(cmd: str)" in text
        assert "Run a command" in text


# ---------------------------------------------------------------------------
# Multimodal / helpers
# ---------------------------------------------------------------------------


class TestBuildUserContent:
    def test_text_only(self, tmp_path: Path) -> None:
        cb = ContextBuilder(tmp_path)
        result = cb._build_user_content("hello", None)
        assert result == "hello"

    def test_with_image(self, tmp_path: Path) -> None:
        img = tmp_path / "test.png"
        # 1x1 red PNG
        png_bytes = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4"
            "nGP4z8BQDwAEgAF/pooBPQAAAABJRU5ErkJggg=="
        )
        img.write_bytes(png_bytes)

        cb = ContextBuilder(tmp_path)
        result = cb._build_user_content("describe this", [str(img)])
        assert isinstance(result, list)
        assert result[-1] == {"type": "text", "text": "describe this"}
        assert result[0]["type"] == "image_url"
        assert result[0]["image_url"]["url"].startswith("data:image/png;base64,")

    def test_invalid_media_path_returns_text(self, tmp_path: Path) -> None:
        cb = ContextBuilder(tmp_path)
        result = cb._build_user_content("hello", ["/nonexistent/img.png"])
        assert result == "hello"


class TestHelperMethods:
    def test_add_assistant_message(self, tmp_path: Path) -> None:
        cb = ContextBuilder(tmp_path)
        msgs: list[dict[str, Any]] = []
        tool_calls = [{"id": "tc1", "type": "function", "function": {"name": "foo"}}]
        cb.add_assistant_message(msgs, "thinking...", tool_calls)
        assert len(msgs) == 1
        assert msgs[0]["role"] == "assistant"
        assert msgs[0]["content"] == "thinking..."
        assert msgs[0]["tool_calls"] == tool_calls

    def test_add_tool_result(self, tmp_path: Path) -> None:
        cb = ContextBuilder(tmp_path)
        msgs: list[dict[str, Any]] = []
        cb.add_tool_result(msgs, "tc1", "read_file", "file contents")
        assert len(msgs) == 1
        assert msgs[0]["role"] == "tool"
        assert msgs[0]["tool_call_id"] == "tc1"
        assert msgs[0]["name"] == "read_file"
        assert msgs[0]["content"] == "file contents"
