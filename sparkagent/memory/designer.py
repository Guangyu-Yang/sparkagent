"""LLM-based skill evolution (Designer).

Analyzes hard cases where memory operations failed and proposes
skill refinements or new skills.
"""

import json
import re
from datetime import datetime
from pathlib import Path

from sparkagent.memory.models import HardCase, MemoryOperation, MemorySkill
from sparkagent.memory.prompts import DESIGNER_PROMPT
from sparkagent.memory.skill_bank import SkillBank
from sparkagent.providers.base import LLMProvider


class SkillDesigner:
    """Evolves the skill bank by analyzing hard cases (failures)."""

    def __init__(
        self,
        skill_bank: SkillBank,
        storage_dir: Path | None = None,
        hard_case_threshold: int = 10,
    ):
        self.skill_bank = skill_bank
        self.storage_dir = storage_dir or (Path.home() / ".sparkagent" / "memory")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._hard_cases_path = self.storage_dir / "hard_cases.jsonl"
        self.hard_case_threshold = hard_case_threshold
        self._hard_cases: list[HardCase] | None = None

    def _ensure_loaded(self) -> list[HardCase]:
        """Lazy-load hard cases from disk."""
        if self._hard_cases is not None:
            return self._hard_cases

        self._hard_cases = []
        if not self._hard_cases_path.exists():
            return self._hard_cases

        try:
            with open(self._hard_cases_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        case = self._dict_to_hard_case(data)
                        self._hard_cases.append(case)
                    except (json.JSONDecodeError, KeyError):
                        continue
        except OSError:
            pass

        return self._hard_cases

    def _save_hard_cases(self) -> None:
        """Persist hard cases to disk."""
        cases = self._ensure_loaded()
        with open(self._hard_cases_path, "w") as f:
            for case in cases:
                f.write(json.dumps(self._hard_case_to_dict(case)) + "\n")

    @staticmethod
    def _hard_case_to_dict(case: HardCase) -> dict:
        return {
            "id": case.id,
            "conversation_snippet": case.conversation_snippet,
            "selected_skills": case.selected_skills,
            "operations": [
                {
                    "type": op.type.value,
                    "content": op.content,
                    "target_id": op.target_id,
                    "tags": op.tags,
                    "skill_id": op.skill_id,
                    "reasoning": op.reasoning,
                }
                for op in case.operations
            ],
            "failure_type": case.failure_type,
            "created_at": case.created_at.isoformat(),
        }

    @staticmethod
    def _dict_to_hard_case(data: dict) -> HardCase:
        from sparkagent.memory.models import OperationType

        operations = []
        for op_data in data.get("operations", []):
            operations.append(
                MemoryOperation(
                    type=OperationType(op_data["type"]),
                    content=op_data.get("content", ""),
                    target_id=op_data.get("target_id", ""),
                    tags=op_data.get("tags", []),
                    skill_id=op_data.get("skill_id", ""),
                    reasoning=op_data.get("reasoning", ""),
                )
            )

        return HardCase(
            id=data["id"],
            conversation_snippet=data["conversation_snippet"],
            selected_skills=data.get("selected_skills", []),
            operations=operations,
            failure_type=data.get("failure_type", ""),
            created_at=datetime.fromisoformat(data["created_at"])
            if "created_at" in data
            else datetime.now(),
        )

    def record_hard_case(self, case: HardCase) -> None:
        """Record a hard case for future analysis."""
        cases = self._ensure_loaded()
        cases.append(case)
        self._save_hard_cases()

    def should_evolve(self) -> bool:
        """Check whether enough hard cases have accumulated to trigger evolution."""
        cases = self._ensure_loaded()
        return len(cases) >= self.hard_case_threshold

    async def evolve_skills(
        self, provider: LLMProvider, model: str
    ) -> list[MemorySkill]:
        """Analyze hard cases and propose/create new or refined skills.

        Returns the list of newly created or updated skills.
        """
        cases = self._ensure_loaded()
        if not cases:
            return []

        # Format hard cases for the prompt
        hard_cases_text = self._format_hard_cases(cases)
        skill_descriptions = self.skill_bank.get_descriptions()

        prompt = DESIGNER_PROMPT.format(
            skill_descriptions=skill_descriptions,
            hard_cases=hard_cases_text,
        )

        messages = [
            {"role": "system", "content": "You are a memory skill designer."},
            {"role": "user", "content": prompt},
        ]

        response = await provider.chat(
            messages=messages,
            tools=None,
            model=model,
            max_tokens=2000,
            temperature=0.3,
        )

        text = response.content or ""
        proposals = self._parse_proposals(text)

        new_skills: list[MemorySkill] = []
        for proposal in proposals:
            action = proposal.get("action", "")
            skill_id = proposal.get("id", "")
            if not skill_id:
                continue

            if action == "add_new":
                skill = MemorySkill(
                    id=skill_id,
                    description=proposal.get("description", ""),
                    content=proposal.get("content", ""),
                    is_primitive=False,
                    created_at=datetime.now(),
                )
                self.skill_bank.add_skill(skill)
                new_skills.append(skill)
            elif action == "refine_existing":
                existing = self.skill_bank.get(skill_id)
                if existing and not existing.is_primitive:
                    existing.description = proposal.get("description", existing.description)
                    existing.content = proposal.get("content", existing.content)
                    existing.version += 1
                    self.skill_bank.add_skill(existing)
                    new_skills.append(existing)

        # Clear hard case buffer after evolution
        self._hard_cases = []
        self._save_hard_cases()

        return new_skills

    def check_rollbacks(self) -> list[str]:
        """Check all evolved skills for low success rates and roll back.

        Returns list of rolled-back skill IDs.
        """
        rolled_back: list[str] = []
        for skill in self.skill_bank.get_all():
            if skill.is_primitive:
                continue
            if self.skill_bank.rollback_skill(skill.id):
                rolled_back.append(skill.id)
        return rolled_back

    @staticmethod
    def _format_hard_cases(cases: list[HardCase]) -> str:
        """Format hard cases for the designer prompt."""
        parts = []
        for i, case in enumerate(cases):
            ops = ", ".join(f"{op.type.value}({op.reasoning})" for op in case.operations)
            parts.append(
                f"### Case {i + 1}\n"
                f"- Failure type: {case.failure_type or 'unknown'}\n"
                f"- Skills used: {', '.join(case.selected_skills)}\n"
                f"- Operations: {ops or 'none'}\n"
                f"- Conversation: {case.conversation_snippet[:200]}"
            )
        return "\n\n".join(parts)

    @staticmethod
    def _parse_proposals(text: str) -> list[dict]:
        """Parse JSON array of skill proposals from LLM response."""
        # Extract JSON from code fences
        fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if fence_match:
            json_str = fence_match.group(1).strip()
        else:
            bracket_match = re.search(r"\[.*\]", text, re.DOTALL)
            json_str = bracket_match.group(0).strip() if bracket_match else ""

        if not json_str:
            return []

        try:
            proposals = json.loads(json_str)
            return proposals if isinstance(proposals, list) else []
        except json.JSONDecodeError:
            return []
