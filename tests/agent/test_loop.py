"""Tests for sparkagent.agent.loop — the core processing engine."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sparkagent.agent.loop import AgentLoop
from sparkagent.bus import InboundMessage, MessageBus, OutboundMessage
from sparkagent.config.schema import MemoryConfig
from sparkagent.providers.base import LLMProvider, LLMResponse, ToolCall


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _MockProvider(LLMProvider):
    """Provider that returns canned responses in sequence."""

    def __init__(self, responses: list[LLMResponse] | None = None):
        super().__init__(api_key="fake")
        self._responses = list(responses or [])
        self._call_count = 0

    async def chat(self, messages, tools=None, model=None, **kwargs) -> LLMResponse:
        if self._call_count < len(self._responses):
            resp = self._responses[self._call_count]
        else:
            resp = LLMResponse(content="(fallback)")
        self._call_count += 1
        return resp

    def get_default_model(self) -> str:
        return "mock-model"


def _make_loop(
    tmp_path: Path,
    responses: list[LLMResponse] | None = None,
    execution_mode: str = "function_calling",
    memory_config: MemoryConfig | None = None,
) -> AgentLoop:
    bus = MessageBus()
    provider = _MockProvider(responses)
    return AgentLoop(
        bus=bus,
        provider=provider,
        workspace=tmp_path,
        execution_mode=execution_mode,
        memory_config=memory_config,
    )


# ---------------------------------------------------------------------------
# Setup and construction
# ---------------------------------------------------------------------------


class TestInit:
    def test_registers_tools(self, tmp_path: Path) -> None:
        loop = _make_loop(tmp_path)
        names = set(loop.tools.list_tools())
        expected = {
            "read_file", "write_file", "list_directory", "edit_file",
            "shell", "web_search", "web_fetch",
        }
        assert names == expected

    def test_memory_disabled(self, tmp_path: Path) -> None:
        loop = _make_loop(tmp_path)
        assert loop._memory_store is None
        assert loop._skill_bank is None
        assert loop._skill_designer is None

    def test_memory_enabled(self, tmp_path: Path) -> None:
        mc = MemoryConfig(enabled=True)
        loop = _make_loop(tmp_path, memory_config=mc)
        assert loop._memory_store is not None
        assert loop._skill_bank is not None
        assert loop._skill_designer is not None


# ---------------------------------------------------------------------------
# Mode resolution
# ---------------------------------------------------------------------------


class TestResolveMode:
    @pytest.mark.asyncio
    async def test_fixed_function_calling(self, tmp_path: Path) -> None:
        loop = _make_loop(tmp_path, execution_mode="function_calling")
        mode = await loop._resolve_execution_mode("hello")
        assert mode == "function_calling"

    @pytest.mark.asyncio
    async def test_fixed_code_act(self, tmp_path: Path) -> None:
        loop = _make_loop(tmp_path, execution_mode="code_act")
        mode = await loop._resolve_execution_mode("hello")
        assert mode == "code_act"

    @pytest.mark.asyncio
    async def test_auto_delegates(self, tmp_path: Path) -> None:
        loop = _make_loop(tmp_path, execution_mode="auto")
        with patch(
            "sparkagent.agent.loop.select_execution_mode",
            new_callable=AsyncMock,
            return_value="code_act",
        ) as mock_select:
            mode = await loop._resolve_execution_mode("write a script")
            mock_select.assert_called_once_with(loop.provider, loop.model, "write a script")
            assert mode == "code_act"


# ---------------------------------------------------------------------------
# Function-calling flow
# ---------------------------------------------------------------------------


class TestFunctionCallingFlow:
    @pytest.mark.asyncio
    async def test_simple_response(self, tmp_path: Path) -> None:
        loop = _make_loop(tmp_path, responses=[LLMResponse(content="Hello!")])
        result = await loop.process_direct("hi")
        assert result == "Hello!"

    @pytest.mark.asyncio
    async def test_with_tool_call(self, tmp_path: Path) -> None:
        # First response: tool call, second response: final text
        tool_call = ToolCall(id="tc1", name="read_file", arguments={"path": str(tmp_path)})
        responses = [
            LLMResponse(content=None, tool_calls=[tool_call]),
            LLMResponse(content="Done reading."),
        ]
        loop = _make_loop(tmp_path, responses=responses)
        result = await loop.process_direct("read workspace")
        assert result == "Done reading."

    @pytest.mark.asyncio
    async def test_max_iterations(self, tmp_path: Path) -> None:
        # Provider always returns tool calls → hits iteration limit
        tool_call = ToolCall(id="tc1", name="list_directory", arguments={"path": str(tmp_path)})
        endless = [LLMResponse(content=None, tool_calls=[tool_call])] * 25
        loop = _make_loop(tmp_path, responses=endless)
        loop.max_iterations = 3
        result = await loop.process_direct("loop forever")
        # When max_iterations hit, final_content is None → fallback message
        assert "no response" in result.lower() or "completed" in result.lower()


# ---------------------------------------------------------------------------
# CodeAct flow
# ---------------------------------------------------------------------------


class TestCodeActFlow:
    @pytest.mark.asyncio
    async def test_codeact_mode(self, tmp_path: Path) -> None:
        responses = [
            LLMResponse(content='<execute>\nprint("hello")\n</execute>'),
            LLMResponse(content="The result is hello."),
        ]
        loop = _make_loop(tmp_path, responses=responses, execution_mode="code_act")
        result = await loop.process_direct("say hello")
        assert "result is hello" in result.lower() or "hello" in result.lower()


# ---------------------------------------------------------------------------
# Session & memory
# ---------------------------------------------------------------------------


class TestSessionAndMemory:
    @pytest.mark.asyncio
    async def test_saves_session(self, tmp_path: Path) -> None:
        loop = _make_loop(tmp_path, responses=[LLMResponse(content="saved!")])
        # process_direct always uses session_key="cli:direct" internally
        await loop.process_direct("remember this")
        session = loop.sessions.get_or_create("cli:direct")
        history = session.get_history()
        roles = [m["role"] for m in history]
        assert "user" in roles
        assert "assistant" in roles

    @pytest.mark.asyncio
    async def test_memory_error_non_fatal(self, tmp_path: Path) -> None:
        mc = MemoryConfig(enabled=True)
        loop = _make_loop(tmp_path, responses=[LLMResponse(content="ok")], memory_config=mc)
        # Make memory processing raise
        with patch.object(loop, "_process_memory", side_effect=Exception("boom")):
            # Should not raise — error is caught in _process_message
            result = await loop.process_direct("test")
            assert result == "ok"
