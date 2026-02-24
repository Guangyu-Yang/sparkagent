"""Skill bank — manages memory skills as individual markdown files."""

from datetime import datetime
from pathlib import Path

from sparkagent.memory.models import MemorySkill

# Primitive skill definitions (written to disk on first init)
_PRIMITIVES: dict[str, dict] = {
    "primitive_insert": {
        "description": "Insert a new memory capturing durable facts from the conversation",
        "content": """# Insert Memory

## Purpose
Capture new, durable facts that are not already present in memory.

## When to Use
- The conversation contains new factual information worth remembering.
- The information is not already captured in existing memories.

## How to Apply
- Identify the key fact or preference stated in the conversation.
- Write a concise, self-contained memory entry.
- Add relevant keyword tags for future retrieval.

## Constraints
- Only capture information explicitly stated or clearly implied.
- Do not duplicate information already in memory.

Action type: INSERT only.
""",
    },
    "primitive_update": {
        "description": "Update an existing memory with corrections or new details",
        "content": """# Update Memory

## Purpose
Revise an existing memory with corrections, clarifications, or additional details.

## When to Use
- New information modifies or extends an existing memory.
- A previously stored fact has been corrected by the user.

## How to Apply
- Identify which existing memory needs updating (by MEMORY_INDEX).
- Rewrite the memory content to incorporate the new information.
- Update tags if the scope of the memory has changed.

## Constraints
- Preserve the core identity of the original memory.
- Only update based on explicitly stated information.

Action type: UPDATE only.
""",
    },
    "primitive_delete": {
        "description": "Delete memories that are wrong, outdated, or superseded",
        "content": """# Delete Memory

## Purpose
Remove memories that are incorrect, outdated, or have been superseded.

## When to Use
- The user explicitly contradicts a stored memory.
- A memory has been fully superseded by a newer, more complete entry.
- A memory is clearly wrong or no longer relevant.

## How to Apply
- Identify which existing memory to delete (by MEMORY_INDEX).
- Provide reasoning for why this memory should be removed.

## Constraints
- Do not delete memories that might still be partially relevant.
- Prefer updating over deleting when the memory has some valid content.

Action type: DELETE only.
""",
    },
    "primitive_noop": {
        "description": "No memory changes needed for this conversation turn",
        "content": """# No Operation

## Purpose
Confirm that no memory changes are needed for this conversation turn.

## When to Use
- The conversation is purely transactional (greetings, small talk).
- All relevant information is already captured in existing memories.
- The conversation does not contain any new durable facts.

## How to Apply
- Return a NOOP operation with brief reasoning.

Action type: NOOP only.
""",
    },
}


def _format_frontmatter(skill: MemorySkill) -> str:
    """Format skill metadata as YAML-like frontmatter."""
    lines = [
        "---",
        f"description: {skill.description}",
        f"is_primitive: {'true' if skill.is_primitive else 'false'}",
        f"version: {skill.version}",
        f"usage_count: {skill.usage_count}",
        f"success_count: {skill.success_count}",
        f'created_at: "{skill.created_at.isoformat()}"',
        "---",
    ]
    return "\n".join(lines)


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Parse YAML-like frontmatter from a markdown file.

    Returns (metadata_dict, body_text). Uses simple key-value parsing
    to avoid requiring PyYAML.
    """
    text = text.strip()
    if not text.startswith("---"):
        return {}, text

    # Find closing ---
    end_idx = text.find("---", 3)
    if end_idx == -1:
        return {}, text

    frontmatter_text = text[3:end_idx].strip()
    body = text[end_idx + 3:].strip()

    metadata: dict[str, str] = {}
    for line in frontmatter_text.split("\n"):
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        metadata[key] = value

    return metadata, body


class SkillBank:
    """Manages the inventory of memory skills stored as markdown files."""

    def __init__(self, skills_dir: Path | None = None):
        self.skills_dir = skills_dir or (Path.home() / ".sparkagent" / "memory" / "skills")
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self._skills: dict[str, MemorySkill] | None = None
        self._ensure_primitives()
        self._load_skills()

    def _ensure_primitives(self) -> None:
        """Write primitive skill .md files if they don't exist."""
        for skill_id, definition in _PRIMITIVES.items():
            path = self.skills_dir / f"{skill_id}.md"
            if path.exists():
                continue

            skill = MemorySkill(
                id=skill_id,
                description=definition["description"],
                content=definition["content"],
                is_primitive=True,
                created_at=datetime.now(),
            )
            self._write_skill_file(skill)

    def _load_skills(self) -> None:
        """Scan skills directory and parse all .md files."""
        self._skills = {}
        for path in sorted(self.skills_dir.glob("*.md")):
            try:
                skill = self._parse_skill_md(path)
                self._skills[skill.id] = skill
            except Exception:
                continue

    def _parse_skill_md(self, path: Path) -> MemorySkill:
        """Parse a skill markdown file into a MemorySkill."""
        text = path.read_text(encoding="utf-8")
        metadata, body = _parse_frontmatter(text)

        skill_id = path.stem
        return MemorySkill(
            id=skill_id,
            description=metadata.get("description", ""),
            content=body,
            is_primitive=metadata.get("is_primitive", "false").lower() == "true",
            version=int(metadata.get("version", "1")),
            usage_count=int(metadata.get("usage_count", "0")),
            success_count=int(metadata.get("success_count", "0")),
            created_at=datetime.fromisoformat(metadata["created_at"])
            if "created_at" in metadata
            else datetime.now(),
        )

    def _write_skill_file(self, skill: MemorySkill) -> None:
        """Write a skill to its .md file."""
        path = self.skills_dir / f"{skill.id}.md"
        frontmatter = _format_frontmatter(skill)
        path.write_text(f"{frontmatter}\n\n{skill.content}", encoding="utf-8")

    def get(self, skill_id: str) -> MemorySkill | None:
        """Get a skill by ID."""
        if self._skills is None:
            self._load_skills()
        return self._skills.get(skill_id)

    def get_all(self) -> list[MemorySkill]:
        """Get all skills."""
        if self._skills is None:
            self._load_skills()
        return list(self._skills.values())

    def get_descriptions(self) -> str:
        """Format skill descriptions for the selector prompt."""
        if self._skills is None:
            self._load_skills()

        lines = []
        for skill in self._skills.values():
            tag = "[primitive]" if skill.is_primitive else "[evolved]"
            lines.append(f"- {skill.id}: {skill.description} {tag}")
        return "\n".join(lines)

    def add_skill(self, skill: MemorySkill) -> None:
        """Add a new skill (write .md file to disk)."""
        if self._skills is None:
            self._load_skills()

        self._write_skill_file(skill)
        self._skills[skill.id] = skill

    def remove_skill(self, skill_id: str) -> bool:
        """Remove a skill (delete its .md file). Cannot remove primitives."""
        if self._skills is None:
            self._load_skills()

        skill = self._skills.get(skill_id)
        if skill is None or skill.is_primitive:
            return False

        path = self.skills_dir / f"{skill_id}.md"
        if path.exists():
            path.unlink()
        del self._skills[skill_id]
        return True

    def record_usage(self, skill_id: str, success: bool = True) -> None:
        """Update usage/success counters and rewrite the skill file."""
        if self._skills is None:
            self._load_skills()

        skill = self._skills.get(skill_id)
        if skill is None:
            return

        skill.usage_count += 1
        if success:
            skill.success_count += 1
        self._write_skill_file(skill)

    def rollback_skill(self, skill_id: str) -> bool:
        """Remove an evolved skill if its success rate is below threshold.

        Returns True if the skill was removed.
        """
        if self._skills is None:
            self._load_skills()

        skill = self._skills.get(skill_id)
        if skill is None or skill.is_primitive:
            return False

        if skill.usage_count >= 5:
            success_rate = skill.success_count / skill.usage_count
            if success_rate < 0.3:
                return self.remove_skill(skill_id)

        return False
