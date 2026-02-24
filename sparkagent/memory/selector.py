"""LLM-based skill selection (Controller).

Follows the mode_selector.py pattern: module-level prompt + single async function.
"""

import re

from sparkagent.memory.prompts import SKILL_SELECTION_PROMPT
from sparkagent.providers.base import LLMProvider

_DEFAULT_FALLBACK = ["primitive_insert", "primitive_noop"]


async def select_skills(
    provider: LLMProvider,
    model: str,
    conversation_turn: str,
    existing_memories: str,
    skill_descriptions: str,
    top_k: int = 3,
) -> list[str]:
    """Select the most relevant memory skills for a conversation turn.

    Args:
        provider: LLM provider for the classification call.
        model: Model identifier.
        conversation_turn: The current conversation turn text.
        existing_memories: Formatted string of existing memories.
        skill_descriptions: Formatted string of available skill descriptions.
        top_k: Maximum number of skills to select.

    Returns:
        Ordered list of skill IDs, most relevant first.
    """
    prompt = SKILL_SELECTION_PROMPT.format(
        existing_memories=existing_memories or "(no memories yet)",
        skill_descriptions=skill_descriptions,
        conversation_turn=conversation_turn,
        top_k=top_k,
    )

    messages = [
        {"role": "system", "content": "You are a memory management controller."},
        {"role": "user", "content": prompt},
    ]

    response = await provider.chat(
        messages=messages,
        tools=None,
        model=model,
        max_tokens=200,
        temperature=0.0,
    )

    text = response.content or ""
    return _parse_skill_ids(text, top_k)


def _parse_skill_ids(text: str, top_k: int) -> list[str]:
    """Parse numbered list of skill IDs from LLM response.

    Expects lines like:
        1. primitive_insert
        2. capture_activity_details
    """
    # Match patterns like "1. skill_id" or "- skill_id"
    pattern = r"(?:^\d+[\.\)]\s*|^-\s*)(\w+)"
    matches = re.findall(pattern, text.strip(), re.MULTILINE)

    if matches:
        return matches[:top_k]

    # Fallback: try to find any word that looks like a skill ID
    words = re.findall(r"\b(\w+_\w+)\b", text)
    if words:
        return words[:top_k]

    return _DEFAULT_FALLBACK[:top_k]
