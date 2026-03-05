"""Heartbeat service — periodically evaluates scheduled tasks via LLM."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Coroutine

from sparkagent.providers.base import LLMProvider

logger = logging.getLogger(__name__)

_DEFAULT_HEARTBEAT_CONTENT = """\
# Heartbeat — Scheduled Tasks

Define tasks for the heartbeat agent to evaluate periodically.
Each task should specify a cadence and what to do.

## Examples (uncomment to enable)

<!-- ### Daily summary
- Cadence: once per day, morning
- Task: Summarize unread notifications and create a brief report -->

<!-- ### Weekly review
- Cadence: every Monday
- Task: Review the week's activity and draft a summary -->
"""

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
        self._ensure_heartbeat_file()
        logger.info("Heartbeat started (interval=%ds)", self._interval_s)
        await self._loop()

    def stop(self) -> None:
        """Signal the loop to exit after the current sleep."""
        self._running = False
        logger.info("Heartbeat stopping")

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
            except Exception:
                logger.exception("Heartbeat tick error")

    def _ensure_heartbeat_file(self) -> Path:
        """Create HEARTBEAT.md with default template if it doesn't exist."""
        heartbeat_file = self._workspace / "HEARTBEAT.md"
        if not heartbeat_file.exists():
            self._workspace.mkdir(parents=True, exist_ok=True)
            heartbeat_file.write_text(_DEFAULT_HEARTBEAT_CONTENT)
            logger.info("Created HEARTBEAT.md")
        return heartbeat_file

    async def _tick(self) -> None:
        heartbeat_file = self._ensure_heartbeat_file()

        content = heartbeat_file.read_text().strip()
        if not content:
            logger.debug("HEARTBEAT.md is empty, skipping")
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
            logger.debug("LLM did not call heartbeat tool, skipping")
            return

        tc = response.tool_calls[0]
        args = tc.arguments
        action = args.get("action", "skip")
        task = args.get("task", "")
        reason = args.get("reason", "")

        if action != "run":
            logger.debug("Skip: %s", reason)
            return

        logger.info("Run: %s", task)

        if self._on_execute:
            try:
                result = await self._on_execute(task)
            except Exception as e:
                logger.exception("Execute error")
                result = f"Error: {e}"

            if self._on_notify and result:
                try:
                    await self._on_notify(result)
                except Exception:
                    logger.exception("Notify error")
