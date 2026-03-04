"""LLM-driven execution mode selector.

Makes a lightweight classification call to decide whether to use
function_calling or code_act mode for a given user message.
"""

from sparkagent.providers.base import LLMProvider

CLASSIFICATION_PROMPT = """You are a routing assistant. Given a user message, decide which execution mode is best:

- "function_calling": The standard mode for most requests — questions, lookups, file operations, running commands, web searches. Uses structured JSON tool calls with reliable argument parsing. Prefer this unless the task clearly requires programmatic composition.
- "code_act": Only for tasks that explicitly need programmatic logic — iterating over collections, conditional branching on intermediate results, complex data transformations, or chaining 3+ tool calls together. Uses executable Python code.

Default to "function_calling" unless the task clearly requires code composition.

Respond with ONLY "function_calling" or "code_act". Nothing else."""


async def select_execution_mode(
    provider: LLMProvider,
    model: str,
    message: str,
) -> str:
    """Ask the LLM which execution mode to use for this message.

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
        tools=None,
        model=model,
        max_tokens=20,
        temperature=0.0,
    )
    text = (response.content or "").strip().lower()
    if text.startswith("function_calling"):
        return "function_calling"
    if text.startswith("code_act"):
        return "code_act"
    return "function_calling"
