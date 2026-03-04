"""Tests for sparkagent.heartbeat.service."""

from __future__ import annotations

from pathlib import Path

import pytest

from sparkagent.heartbeat.service import HeartbeatService
from sparkagent.providers.base import LLMProvider, LLMResponse, ToolCall

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _MockProvider(LLMProvider):
    """Provider that returns canned responses."""

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


def _make_service(
    workspace: Path,
    responses: list[LLMResponse] | None = None,
    on_execute=None,
    on_notify=None,
) -> HeartbeatService:
    provider = _MockProvider(responses)
    return HeartbeatService(
        provider=provider,
        model="mock-model",
        workspace=workspace,
        interval_minutes=1,
        on_execute=on_execute,
        on_notify=on_notify,
    )


def _skip_response(reason: str = "nothing to do") -> LLMResponse:
    return LLMResponse(
        tool_calls=[
            ToolCall(
                id="hb1",
                name="heartbeat",
                arguments={"action": "skip", "reason": reason},
            )
        ]
    )


def _run_response(task: str = "do the thing") -> LLMResponse:
    return LLMResponse(
        tool_calls=[
            ToolCall(
                id="hb1",
                name="heartbeat",
                arguments={"action": "run", "task": task, "reason": "it is time"},
            )
        ]
    )


# ---------------------------------------------------------------------------
# Tick logic
# ---------------------------------------------------------------------------


class TestHeartbeatTick:
    @pytest.mark.asyncio
    async def test_creates_heartbeat_file_when_missing(self, tmp_path: Path) -> None:
        executed: list[str] = []

        async def on_exec(task: str) -> str:
            executed.append(task)
            return "done"

        svc = _make_service(tmp_path, on_execute=on_exec)
        await svc.trigger_now()
        assert (tmp_path / "HEARTBEAT.md").exists()
        # Still no execution (template has only commented-out examples)
        assert executed == []

    @pytest.mark.asyncio
    async def test_skip_when_empty_file(self, tmp_path: Path) -> None:
        (tmp_path / "HEARTBEAT.md").write_text("")
        executed = []

        async def on_exec(task: str) -> str:
            executed.append(task)
            return "done"

        svc = _make_service(tmp_path, on_execute=on_exec)
        await svc.trigger_now()
        assert executed == []

    @pytest.mark.asyncio
    async def test_skip_decision(self, tmp_path: Path) -> None:
        (tmp_path / "HEARTBEAT.md").write_text("# Tasks\n- check mail daily")
        executed = []

        async def on_exec(task: str) -> str:
            executed.append(task)
            return "done"

        svc = _make_service(
            tmp_path,
            responses=[_skip_response()],
            on_execute=on_exec,
        )
        await svc.trigger_now()
        assert executed == []

    @pytest.mark.asyncio
    async def test_run_decision_calls_execute(self, tmp_path: Path) -> None:
        (tmp_path / "HEARTBEAT.md").write_text("# Tasks\n- check mail daily")
        executed = []
        notified = []

        async def on_exec(task: str) -> str:
            executed.append(task)
            return "mail checked"

        async def on_notify(result: str) -> None:
            notified.append(result)

        svc = _make_service(
            tmp_path,
            responses=[_run_response("check mail")],
            on_execute=on_exec,
            on_notify=on_notify,
        )
        await svc.trigger_now()
        assert executed == ["check mail"]
        assert notified == ["mail checked"]

    @pytest.mark.asyncio
    async def test_no_tool_calls_skips(self, tmp_path: Path) -> None:
        (tmp_path / "HEARTBEAT.md").write_text("# Tasks\n- something")
        executed = []

        async def on_exec(task: str) -> str:
            executed.append(task)
            return "done"

        svc = _make_service(
            tmp_path,
            responses=[LLMResponse(content="I have no tasks to run.")],
            on_execute=on_exec,
        )
        await svc.trigger_now()
        assert executed == []

    @pytest.mark.asyncio
    async def test_execute_error_is_handled(self, tmp_path: Path) -> None:
        (tmp_path / "HEARTBEAT.md").write_text("# Tasks\n- do stuff")
        notified = []

        async def on_exec(task: str) -> str:
            raise RuntimeError("boom")

        async def on_notify(result: str) -> None:
            notified.append(result)

        svc = _make_service(
            tmp_path,
            responses=[_run_response("do stuff")],
            on_execute=on_exec,
            on_notify=on_notify,
        )
        # Should not raise
        await svc.trigger_now()
        # Notify is called with the error message
        assert len(notified) == 1
        assert "Error" in notified[0]

    @pytest.mark.asyncio
    async def test_run_without_on_execute(self, tmp_path: Path) -> None:
        """run action with no on_execute callback should not crash."""
        (tmp_path / "HEARTBEAT.md").write_text("# Tasks\n- do stuff")
        svc = _make_service(
            tmp_path,
            responses=[_run_response("do stuff")],
            on_execute=None,
        )
        await svc.trigger_now()  # Should not raise


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


class TestHeartbeatLifecycle:
    @pytest.mark.asyncio
    async def test_trigger_now(self, tmp_path: Path) -> None:
        (tmp_path / "HEARTBEAT.md").write_text("# Tasks\n- check")
        executed = []

        async def on_exec(task: str) -> str:
            executed.append(task)
            return "ok"

        svc = _make_service(
            tmp_path,
            responses=[_run_response("check")],
            on_execute=on_exec,
        )
        await svc.trigger_now()
        assert len(executed) == 1

    def test_ensure_heartbeat_file_creates_on_startup(self, tmp_path: Path) -> None:
        svc = _make_service(tmp_path)
        svc._ensure_heartbeat_file()
        assert (tmp_path / "HEARTBEAT.md").exists()

    def test_stop_sets_running_false(self, tmp_path: Path) -> None:
        svc = _make_service(tmp_path)
        svc._running = True
        svc.stop()
        assert svc._running is False
