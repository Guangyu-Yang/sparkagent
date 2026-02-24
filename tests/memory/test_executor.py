"""Tests for memory executor."""

import json
from datetime import datetime
from typing import Any

import pytest

from sparkagent.memory.executor import (
    _extract_json,
    _format_indexed_memories,
    execute_memory_skills,
)
from sparkagent.memory.models import MemoryEntry, MemorySkill, OperationType
from sparkagent.providers.base import LLMProvider, LLMResponse


class _MockProvider(LLMProvider):
    def __init__(self, response_text: str):
        super().__init__(api_key="test")
        self._response_text = response_text

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        return LLMResponse(content=self._response_text)

    def get_default_model(self) -> str:
        return "mock"


def _make_entry(id: str, content: str, tags: list[str] | None = None) -> MemoryEntry:
    now = datetime.now()
    return MemoryEntry(
        id=id, content=content, tags=tags or [], created_at=now, updated_at=now,
    )


def _make_skill(id: str = "primitive_insert") -> MemorySkill:
    return MemorySkill(
        id=id,
        description="Test",
        content="# Test skill",
        is_primitive=True,
        created_at=datetime.now(),
    )


class TestExtractJson:
    def test_code_fence(self):
        text = 'Some text\n```json\n[{"type": "INSERT"}]\n```\nMore text'
        assert _extract_json(text) == '[{"type": "INSERT"}]'

    def test_code_fence_no_lang(self):
        text = 'Text\n```\n[{"type": "NOOP"}]\n```'
        assert _extract_json(text) == '[{"type": "NOOP"}]'

    def test_raw_json(self):
        text = '[{"type": "INSERT", "content": "test"}]'
        assert _extract_json(text) == '[{"type": "INSERT", "content": "test"}]'

    def test_no_json(self):
        assert _extract_json("No JSON here") == ""

    def test_json_with_surrounding_text(self):
        text = 'Here are the operations: [{"type": "NOOP"}] done.'
        result = _extract_json(text)
        assert '"NOOP"' in result


class TestFormatIndexedMemories:
    def test_format(self):
        entries = [
            _make_entry("abc12345", "User likes pizza", ["food"]),
            _make_entry("def67890", "Works at Acme", ["work"]),
        ]
        result = _format_indexed_memories(entries)
        assert "0. [abc12345]" in result
        assert "1. [def67890]" in result
        assert "pizza" in result
        assert "food" in result

    def test_empty(self):
        assert _format_indexed_memories([]) == ""


class TestExecuteMemorySkills:
    @pytest.mark.asyncio
    async def test_insert_operation(self):
        response = json.dumps([
            {"type": "INSERT", "content": "User prefers dark mode", "tags": ["preference", "ui"]}
        ])
        provider = _MockProvider(f"```json\n{response}\n```")

        ops = await execute_memory_skills(
            provider, "mock",
            "User: I prefer dark mode\nAssistant: Noted!",
            [], [_make_skill()],
        )
        assert len(ops) == 1
        assert ops[0].type == OperationType.INSERT
        assert ops[0].content == "User prefers dark mode"
        assert ops[0].tags == ["preference", "ui"]

    @pytest.mark.asyncio
    async def test_update_operation(self):
        entries = [_make_entry("entry_abc", "User lives in SF", ["location"])]
        response = json.dumps([
            {"type": "UPDATE", "memory_index": 0, "content": "User lives in NYC",
             "tags": ["location"]}
        ])
        provider = _MockProvider(response)

        ops = await execute_memory_skills(
            provider, "mock",
            "User: I moved to NYC\nAssistant: Cool!",
            entries, [_make_skill("primitive_update")],
        )
        assert len(ops) == 1
        assert ops[0].type == OperationType.UPDATE
        assert ops[0].target_id == "entry_abc"
        assert ops[0].content == "User lives in NYC"

    @pytest.mark.asyncio
    async def test_delete_operation(self):
        entries = [_make_entry("entry_del", "Old fact")]
        response = json.dumps([
            {"type": "DELETE", "memory_index": 0, "reasoning": "Outdated"}
        ])
        provider = _MockProvider(response)

        ops = await execute_memory_skills(
            provider, "mock", "turn", entries, [_make_skill("primitive_delete")],
        )
        assert len(ops) == 1
        assert ops[0].type == OperationType.DELETE
        assert ops[0].target_id == "entry_del"

    @pytest.mark.asyncio
    async def test_noop_operation(self):
        response = json.dumps([
            {"type": "NOOP", "reasoning": "Just a greeting"}
        ])
        provider = _MockProvider(response)

        ops = await execute_memory_skills(
            provider, "mock", "User: Hello\nAssistant: Hi!", [], [_make_skill("primitive_noop")],
        )
        assert len(ops) == 1
        assert ops[0].type == OperationType.NOOP

    @pytest.mark.asyncio
    async def test_multiple_operations(self):
        entries = [_make_entry("e1", "Old fact")]
        response = json.dumps([
            {"type": "INSERT", "content": "New fact", "tags": ["new"]},
            {"type": "DELETE", "memory_index": 0},
        ])
        provider = _MockProvider(response)

        ops = await execute_memory_skills(
            provider, "mock", "turn", entries, [_make_skill()],
        )
        assert len(ops) == 2
        assert ops[0].type == OperationType.INSERT
        assert ops[1].type == OperationType.DELETE

    @pytest.mark.asyncio
    async def test_malformed_json_returns_empty(self):
        provider = _MockProvider("This is not JSON at all")
        ops = await execute_memory_skills(
            provider, "mock", "turn", [], [_make_skill()],
        )
        assert ops == []

    @pytest.mark.asyncio
    async def test_invalid_op_type_skipped(self):
        response = json.dumps([
            {"type": "INVALID", "content": "foo"},
            {"type": "INSERT", "content": "valid", "tags": []},
        ])
        provider = _MockProvider(response)

        ops = await execute_memory_skills(
            provider, "mock", "turn", [], [_make_skill()],
        )
        assert len(ops) == 1
        assert ops[0].type == OperationType.INSERT

    @pytest.mark.asyncio
    async def test_out_of_range_memory_index(self):
        entries = [_make_entry("e1", "Only entry")]
        response = json.dumps([
            {"type": "UPDATE", "memory_index": 5, "content": "foo"}
        ])
        provider = _MockProvider(response)

        ops = await execute_memory_skills(
            provider, "mock", "turn", entries, [_make_skill()],
        )
        assert len(ops) == 1
        assert ops[0].target_id == ""  # Index out of range → no target

    @pytest.mark.asyncio
    async def test_skill_id_assigned(self):
        response = json.dumps([{"type": "INSERT", "content": "test", "tags": []}])
        provider = _MockProvider(response)

        ops = await execute_memory_skills(
            provider, "mock", "turn", [], [_make_skill("my_skill")],
        )
        assert ops[0].skill_id == "my_skill"
