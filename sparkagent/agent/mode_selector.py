"""LLM-driven execution mode selector.

Makes a lightweight classification call to decide whether to use
function_calling or code_act mode for a given user message.

Uses structured output (tool_choice) to force the LLM to return a
valid mode selection via a tool call, avoiding brittle text parsing.
"""

import json
import logging
from typing import Literal

from pydantic import BaseModel

from sparkagent.providers.base import LLMProvider

logger = logging.getLogger(__name__)

CLASSIFICATION_PROMPT = """You are a routing assistant. Given a user message, decide which execution mode is best:

- "function_calling": The standard mode for most requests — questions, lookups, file operations, running commands, web searches. Uses structured JSON tool calls with reliable argument parsing. Prefer this unless the task clearly requires programmatic composition.
- "code_act": Only for tasks that explicitly need programmatic logic — iterating over collections, conditional branching on intermediate results, complex data transformations, or chaining 3+ tool calls together. Uses executable Python code.

Default to "function_calling" unless the task clearly requires code composition.

Call the select_mode tool with your choice."""


class ModeSelection(BaseModel):
    """Structured output model for mode selection."""

    mode: Literal["function_calling", "code_act"]


# OpenAI function-calling format tool schema derived from ModeSelection
MODE_SELECTION_TOOL: dict = {
    "type": "function",
    "function": {
        "name": "select_mode",
        "description": "Select the execution mode for the user's message.",
        "parameters": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["function_calling", "code_act"],
                    "description": "The execution mode to use.",
                },
            },
            "required": ["mode"],
        },
    },
}

# Force the LLM to call this specific tool (OpenAI format)
TOOL_CHOICE = {"type": "function", "function": {"name": "select_mode"}}


async def select_execution_mode(
    provider: LLMProvider,
    model: str,
    message: str,
) -> str:
    """Ask the LLM which execution mode to use for this message.

    Uses structured output via tool_choice to force a reliable response.
    Falls back to text-based parsing if the tool call path fails.

    Args:
        provider: The LLM provider to use for classification.
        model: The model identifier.
        message: The user's message to classify.

    Returns:
        Either "function_calling" or "code_act".

    """
    messages = [
        {"role": "system", "content": CLASSIFICATION_PROMPT},
        {"role": "user", "content": message},
    ]
    response = await provider.chat(
        messages=messages,
        tools=[MODE_SELECTION_TOOL],
        model=model,
        max_tokens=100,
        temperature=0.0,
        tool_choice=TOOL_CHOICE,
    )

    # Primary path: extract mode from structured tool call
    if response.has_tool_calls:
        tc = response.tool_calls[0]
        args = tc.arguments
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        mode = args.get("mode", "")
        if mode in ("function_calling", "code_act"):
            return mode
        logger.warning("Mode selector tool call returned invalid mode: %r", mode)

    # Fallback: text-based parsing (in case provider doesn't support tool_choice)
    text = (response.content or "").strip().lower()
    if text.startswith("function_calling"):
        return "function_calling"
    if text.startswith("code_act"):
        return "code_act"

    logger.warning("Mode selector fell back to default (function_calling)")
    return "function_calling"
