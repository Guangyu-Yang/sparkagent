"""Heartbeat service — periodically evaluates scheduled tasks via LLM."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Coroutine

from sparkagent.providers.base import LLMProvider

_HEARTBEAT_TOOL: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "heartbeat",
            "description": "Report heartbeat decision after reviewing scheduled tasks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["skip", "run"],
                        "description": "skip = nothing to do now, run = execute a task",
                    },
                    "task": {
                        "type": "string",
                        "description": (
                            "Natural-language description of the task to execute "
                            "(required when action is run)"
                        ),
                    },
                    "reason": {
                        "type": "string",
                        "description": "Brief explanation for the decision",
                    },
                },
                "required": ["action"],
            },
        },
    }
]

_HEARTBEAT_SYSTEM_PROMPT = (
    "You are a heartbeat agent. The current time is {now}.\n\n"
    "Review the HEARTBEAT.md content below. It describes scheduled tasks with "
    "their cadences and conditions. Decide whether any task should run RIGHT NOW "
    "based on the current time and the task schedule.\n\n"
    "Call the heartbeat tool with action='run' and a task description if a task "
    "should execute, or action='skip' if nothing needs to run."
)


class HeartbeatService:
    """Periodically reads HEARTBEAT.md and uses the LLM to decide whether
    scheduled tasks should run."""

    def __init__(
        self,
        provider: LLMProvider,
        model: str,
        workspace: Path,
        interval_minutes: int = 30,
        on_execute: Callable[[str], Coroutine[Any, Any, str]] | None = None,
        on_notify: Callable[[str], Coroutine[Any, Any, None]] | None = None,
    ):
        self._provider = provider
        self._model = model
        self._workspace = workspace
        self._interval_s = interval_minutes * 60
        self._on_execute = on_execute
        self._on_notify = on_notify
        self._running = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Long-running coroutine — use with ``asyncio.gather()``."""
        self._running = True
        print(f"Heartbeat started (interval={self._interval_s}s)")
        await self._loop()

    def stop(self) -> None:
        """Signal the loop to exit after the current sleep."""
        self._running = False
        print("Heartbeat stopping")

    async def trigger_now(self) -> None:
        """Run a single tick immediately (useful for manual triggers)."""
        await self._tick()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _loop(self) -> None:
        while self._running:
            await asyncio.sleep(self._interval_s)
            if not self._running:
                break
            try:
                await self._tick()
            except Exception as e:
                print(f"Heartbeat tick error: {e}")

    async def _tick(self) -> None:
        heartbeat_file = self._workspace / "HEARTBEAT.md"
        if not heartbeat_file.exists():
            print("Heartbeat: no HEARTBEAT.md found, skipping")
            return

        content = heartbeat_file.read_text().strip()
        if not content:
            print("Heartbeat: HEARTBEAT.md is empty, skipping")
            return

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": _HEARTBEAT_SYSTEM_PROMPT.format(now=now)},
            {"role": "user", "content": content},
        ]

        response = await self._provider.chat(
            messages=messages,
            tools=_HEARTBEAT_TOOL,
            model=self._model,
            temperature=0.3,
        )

        if not response.has_tool_calls:
            print("Heartbeat: LLM did not call heartbeat tool, skipping")
            return

        tc = response.tool_calls[0]
        args = tc.arguments
        action = args.get("action", "skip")
        task = args.get("task", "")
        reason = args.get("reason", "")

        if action != "run":
            print(f"Heartbeat: skip — {reason}")
            return

        print(f"Heartbeat: run — {task}")

        if self._on_execute:
            try:
                result = await self._on_execute(task)
            except Exception as e:
                print(f"Heartbeat execute error: {e}")
                result = f"Error: {e}"

            if self._on_notify and result:
                try:
                    await self._on_notify(result)
                except Exception as e:
                    print(f"Heartbeat notify error: {e}")
