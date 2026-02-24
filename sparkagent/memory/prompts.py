"""Prompt templates for the memory skill system."""

SKILL_SELECTION_PROMPT = """You are a memory management controller. Given a conversation turn, existing memories, and available memory skills, select the most relevant skills to apply.

## Existing Memories
{existing_memories}

## Available Skills
{skill_descriptions}

## Conversation Turn
{conversation_turn}

## Instructions
Select up to {top_k} skills from the list above that should be applied to process this conversation turn. Consider:
- What new information is present that should be captured?
- Do any existing memories need updating or removing?
- Is this a purely transactional turn with no memory-worthy content?

Respond with ONLY a numbered list of skill IDs, most relevant first. Example:
1. primitive_insert
2. primitive_noop"""

EXECUTOR_PROMPT = """You are a memory executor. Given a conversation turn, existing memories, and selected memory skills, generate the appropriate memory operations.

## Existing Memories
{indexed_memories}

## Selected Skills
{skill_instructions}

## Conversation Turn
{conversation_turn}

## Instructions
Based on the selected skills and their instructions, generate memory operations as a JSON array.

Each operation must be one of:
- INSERT: Create a new memory. Provide "content" and "tags".
- UPDATE: Modify existing memory. Provide "memory_index" (from the numbered list above), "content", and "tags".
- DELETE: Remove a memory. Provide "memory_index" (from the numbered list above).
- NOOP: No changes needed. Provide "reasoning".

Respond with ONLY a JSON array. Example:
```json
[
  {{"type": "INSERT", "content": "User prefers dark mode", "tags": ["preference", "ui"], "reasoning": "New preference stated"}},
  {{"type": "UPDATE", "memory_index": 2, "content": "User works at Acme Corp as senior engineer", "tags": ["work", "role"], "reasoning": "Role updated"}},
  {{"type": "NOOP", "reasoning": "Greeting only, no new information"}}
]
```"""

DESIGNER_PROMPT = """You are a memory skill designer. Analyze the following hard cases where the memory system performed poorly, and propose improvements to the skill bank.

## Current Skills
{skill_descriptions}

## Hard Cases
{hard_cases}

## Instructions
Analyze the hard cases above and:

1. Classify each failure as one of:
   - storage_failure: Important information was not captured
   - retrieval_failure: Relevant memories were not found
   - memory_quality_failure: Captured information was too vague or incorrect

2. Identify patterns across failures.

3. Propose skill improvements as a JSON array. Each proposal should be:
   - "action": "add_new" or "refine_existing"
   - "id": skill ID (new name for add_new, existing ID for refine_existing)
   - "description": short description for skill selection
   - "content": full markdown instructions for the executor

Respond with ONLY a JSON array of proposals. Example:
```json
[
  {{
    "action": "add_new",
    "id": "capture_activity_details",
    "description": "Capture detailed information about activities mentioned in conversation",
    "content": "# Capture Activity Details\\n\\n## Purpose\\nCapture detailed information about activities...\\n\\n## When to Use\\n- Activity mentioned with contextual details\\n\\n## How to Apply\\n- Identify key elements (type, location, participants, time)\\n\\nAction type: INSERT only."
  }}
]
```"""
