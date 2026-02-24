"""LLM-based memory operation generation (Executor)."""

import json
import re

from sparkagent.memory.models import MemoryEntry, MemoryOperation, MemorySkill, OperationType
from sparkagent.memory.prompts import EXECUTOR_PROMPT
from sparkagent.providers.base import LLMProvider


async def execute_memory_skills(
    provider: LLMProvider,
    model: str,
    conversation_turn: str,
    relevant_memories: list[MemoryEntry],
    selected_skills: list[MemorySkill],
) -> list[MemoryOperation]:
    """Generate memory operations from selected skills.

    Args:
        provider: LLM provider for the generation call.
        model: Model identifier.
        conversation_turn: The current conversation turn text.
        relevant_memories: Retrieved memory entries (for UPDATE/DELETE targeting).
        selected_skills: The skills selected by the controller.

    Returns:
        List of memory operations to apply.
    """
    # Format memories as indexed list
    indexed_memories = _format_indexed_memories(relevant_memories)

    # Format skill instructions
    skill_instructions = _format_skill_instructions(selected_skills)

    prompt = EXECUTOR_PROMPT.format(
        indexed_memories=indexed_memories or "(no existing memories)",
        skill_instructions=skill_instructions,
        conversation_turn=conversation_turn,
    )

    messages = [
        {"role": "system", "content": "You are a memory executor."},
        {"role": "user", "content": prompt},
    ]

    response = await provider.chat(
        messages=messages,
        tools=None,
        model=model,
        max_tokens=1000,
        temperature=0.0,
    )

    text = response.content or ""
    return _parse_operations(text, relevant_memories, selected_skills)


def _format_indexed_memories(memories: list[MemoryEntry]) -> str:
    """Format memories as a numbered list with IDs and tags."""
    if not memories:
        return ""

    lines = []
    for i, entry in enumerate(memories):
        tags_str = ", ".join(entry.tags) if entry.tags else "none"
        lines.append(f"{i}. [{entry.id[:8]}] {entry.content} (tags: {tags_str})")
    return "\n".join(lines)


def _format_skill_instructions(skills: list[MemorySkill]) -> str:
    """Format selected skill contents for the executor prompt."""
    parts = []
    for skill in skills:
        parts.append(f"### Skill: {skill.id}\n{skill.content}")
    return "\n\n".join(parts)


def _parse_operations(
    text: str,
    memories: list[MemoryEntry],
    skills: list[MemorySkill],
) -> list[MemoryOperation]:
    """Parse JSON array of operations from LLM response."""
    # Extract JSON from potential markdown code fences
    json_str = _extract_json(text)
    if not json_str:
        return []

    try:
        raw_ops = json.loads(json_str)
    except json.JSONDecodeError:
        return []

    if not isinstance(raw_ops, list):
        return []

    skill_id = skills[0].id if skills else ""
    operations: list[MemoryOperation] = []

    for raw in raw_ops:
        if not isinstance(raw, dict):
            continue

        op_type_str = raw.get("type", "").upper()
        try:
            op_type = OperationType(op_type_str.lower())
        except ValueError:
            continue

        target_id = ""
        if op_type in (OperationType.UPDATE, OperationType.DELETE):
            mem_idx = raw.get("memory_index")
            if mem_idx is not None and isinstance(mem_idx, int) and 0 <= mem_idx < len(memories):
                target_id = memories[mem_idx].id

        operations.append(
            MemoryOperation(
                type=op_type,
                content=raw.get("content", ""),
                target_id=target_id,
                tags=raw.get("tags", []),
                skill_id=skill_id,
                reasoning=raw.get("reasoning", ""),
            )
        )

    return operations


def _extract_json(text: str) -> str:
    """Extract JSON array from text, handling markdown code fences."""
    # Try to find ```json ... ``` block
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if fence_match:
        return fence_match.group(1).strip()

    # Try to find raw JSON array
    bracket_match = re.search(r"\[.*\]", text, re.DOTALL)
    if bracket_match:
        return bracket_match.group(0).strip()

    return ""
