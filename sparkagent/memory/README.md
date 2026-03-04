# memory — Dynamic Memory / MemSkill System

LLM-driven memory management that learns what to remember across conversations. Uses "skills" (markdown templates) to guide memory extraction, and evolves new skills from failure cases.

> For setup and overview, see [Dynamic Memory](../../README.md#dynamic-memory) in the main README.

## Files

| File | Purpose |
|------|---------|
| `models.py` | Data models: `MemorySkill`, `MemoryEntry`, `MemoryOperation`, `HardCase`, `OperationType` enum |
| `store.py` | `MemoryStore` — JSONL-backed memory storage with keyword-based retrieval |
| `skill_bank.py` | `SkillBank` — loads/saves skill markdown files, manages 4 built-in primitives |
| `selector.py` | `select_skills()` — LLM picks the most relevant skills for a conversation turn |
| `executor.py` | `execute_memory_skills()` — LLM generates memory operations (insert/update/delete/noop) |
| `designer.py` | `SkillDesigner` — collects hard cases and evolves new skills via LLM |
| `prompts.py` | Prompt templates for skill selection, execution, and design |

## Key Abstractions

### MemoryStore

```python
MemoryStore(storage_dir=~/.sparkagent/memory)
```

- `insert(content, tags, source_session, source_skill) -> MemoryEntry`
- `update(entry_id, content?, tags?)`
- `delete(entry_id) -> bool`
- `retrieve(query, max_results=10) -> list[MemoryEntry]` — keyword scoring with tag weighting and recency bonus
- `retrieve_for_context(query, max_entries, max_chars) -> str` — formatted for injection into system prompt

### SkillBank

Manages skill definitions stored as markdown files with YAML frontmatter. Ships with 4 primitives: `primitive_insert`, `primitive_update`, `primitive_delete`, `primitive_noop`.

```python
SkillBank(skills_dir=~/.sparkagent/memory/skills)
```

- `get_descriptions()` — formatted skill list for the selector prompt
- `record_usage(skill_id, success)` — tracks usage/success counts
- `rollback_skill(skill_id)` — removes evolved skills with success rate < 30%

### SkillDesigner

Collects `HardCase` failures. When enough accumulate (`hard_case_threshold`, default 10), calls the LLM to propose new or improved skills.

- `record_hard_case(case)` — saves a failure for later analysis
- `should_evolve() -> bool` — checks threshold
- `evolve_skills(provider, model) -> list[MemorySkill]` — generates new skills from hard cases
- `check_rollbacks() -> list[str]` — removes underperforming evolved skills

## Pipeline

```
Conversation turn
  → select_skills() picks relevant skills
  → execute_memory_skills() generates operations (INSERT/UPDATE/DELETE/NOOP)
  → AgentLoop applies operations to MemoryStore
  → On failure → SkillDesigner records HardCase
  → When threshold reached → evolve_skills() creates better skills
```
