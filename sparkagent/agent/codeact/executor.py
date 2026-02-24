"""CodeAct executor — runs LLM-generated Python with tool functions injected."""

from __future__ import annotations

import asyncio
import io
import traceback
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
from typing import Any

from sparkagent.agent.codeact.sandbox import build_safe_builtins
from sparkagent.agent.tools.registry import ToolRegistry


class CodeActExecutor:
    """Executes Python code blocks produced by the LLM.

    Tools from ToolRegistry are injected as synchronous callables so that
    ``exec()``-ed code can call them naturally (e.g. ``read_file("/etc/hosts")``).

    The namespace persists across calls within the same executor instance,
    allowing variable reuse across turns.
    """

    def __init__(
        self,
        tools: ToolRegistry,
        timeout: int = 30,
        max_output: int = 4000,
    ) -> None:
        self.tools = tools
        self.timeout = timeout
        self.max_output = max_output
        self._namespace: dict[str, Any] = {}
        self._setup_namespace()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute(self, code: str) -> str:
        """Run *code* and return combined stdout + stderr.

        On error the full traceback is returned so the LLM can self-correct.
        """
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()

        try:
            with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
                exec(code, self._namespace)  # noqa: S102
        except Exception:
            stderr_buf.write(traceback.format_exc())

        output = stdout_buf.getvalue()
        errors = stderr_buf.getvalue()

        result = ""
        if output:
            result += output
        if errors:
            if result:
                result += "\n"
            result += errors

        if not result:
            result = "(no output)"

        return self._truncate(result)

    def reset(self) -> None:
        """Clear the namespace (start fresh for a new session)."""
        self._namespace.clear()
        self._setup_namespace()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _setup_namespace(self) -> None:
        """Populate the exec namespace with safe builtins and tool wrappers."""
        self._namespace["__builtins__"] = build_safe_builtins()

        # Inject each registered tool as a plain function
        for tool_name in self.tools.list_tools():
            self._namespace[tool_name] = self._make_tool_wrapper(tool_name)

    def _make_tool_wrapper(self, name: str) -> Any:
        """Return a sync callable that bridges to the async Tool.execute."""
        tools = self.tools
        timeout = self.timeout

        def wrapper(**kwargs: Any) -> str:
            async def _run():
                return await tools.execute(name, kwargs)

            # Run the async tool in a fresh event loop on a background thread
            # to avoid "event loop already running" issues.
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, _run())
                return future.result(timeout=timeout)

        wrapper.__name__ = name
        wrapper.__qualname__ = name
        return wrapper

    def _truncate(self, text: str) -> str:
        if len(text) <= self.max_output:
            return text
        half = self.max_output // 2
        return (
            text[:half]
            + f"\n\n... truncated ({len(text)} chars total) ...\n\n"
            + text[-half:]
        )
