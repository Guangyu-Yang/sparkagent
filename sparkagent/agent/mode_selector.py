"""LLM-driven execution mode selector.

Makes a lightweight classification call to decide whether to use
function_calling or code_act mode for a given user message.
"""

from sparkagent.providers.base import LLMProvider

CLASSIFICATION_PROMPT = """You are a routing assistant. Given a user message, decide which execution mode is best:

- "function_calling": Best for simple, single-tool requests (read a file, run a search, fetch a URL). The LLM calls tools via structured JSON, one at a time.
- "code_act": Best for multi-step tasks that benefit from composition — loops, conditionals, variable reuse, chaining tool results, batch operations, or data transformation. The LLM writes executable Python code that calls tools as functions.

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
    if "code_act" in text:
        return "code_act"
    return "function_calling"
