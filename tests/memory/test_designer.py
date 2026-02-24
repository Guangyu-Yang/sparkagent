"""Tests for skill designer."""

import json
from datetime import datetime
from typing import Any

import pytest

from sparkagent.memory.designer import SkillDesigner
from sparkagent.memory.models import HardCase, MemoryOperation, MemorySkill, OperationType
from sparkagent.memory.skill_bank import SkillBank
from sparkagent.providers.base import LLMProvider, LLMResponse


class _MockProvider(LLMProvider):
    def __init__(self, response_text: str):
        super().__init__(api_key="test")
        self._response_text = response_text

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        return LLMResponse(content=self._response_text)

    def get_default_model(self) -> str:
        return "mock"


def _make_hard_case(id: str = "hc1", failure_type: str = "missing_info") -> HardCase:
    return HardCase(
        id=id,
        conversation_snippet="User: I went hiking at Yosemite\nAssistant: Sounds fun!",
        selected_skills=["primitive_insert"],
        operations=[
            MemoryOperation(type=OperationType.NOOP, reasoning="No action taken")
        ],
        failure_type=failure_type,
        created_at=datetime.now(),
    )


class TestSkillDesigner:
    def test_record_hard_case(self, temp_dir):
        bank = SkillBank(skills_dir=temp_dir / "skills")
        designer = SkillDesigner(bank, storage_dir=temp_dir)

        case = _make_hard_case()
        designer.record_hard_case(case)

        cases = designer._ensure_loaded()
        assert len(cases) == 1
        assert cases[0].id == "hc1"

    def test_hard_cases_persist(self, temp_dir):
        bank = SkillBank(skills_dir=temp_dir / "skills")
        designer = SkillDesigner(bank, storage_dir=temp_dir)
        designer.record_hard_case(_make_hard_case("hc1"))
        designer.record_hard_case(_make_hard_case("hc2"))

        # Reload from disk
        designer2 = SkillDesigner(bank, storage_dir=temp_dir)
        cases = designer2._ensure_loaded()
        assert len(cases) == 2

    def test_should_evolve_false(self, temp_dir):
        bank = SkillBank(skills_dir=temp_dir / "skills")
        designer = SkillDesigner(bank, storage_dir=temp_dir, hard_case_threshold=5)

        for i in range(4):
            designer.record_hard_case(_make_hard_case(f"hc{i}"))

        assert designer.should_evolve() is False

    def test_should_evolve_true(self, temp_dir):
        bank = SkillBank(skills_dir=temp_dir / "skills")
        designer = SkillDesigner(bank, storage_dir=temp_dir, hard_case_threshold=5)

        for i in range(5):
            designer.record_hard_case(_make_hard_case(f"hc{i}"))

        assert designer.should_evolve() is True

    @pytest.mark.asyncio
    async def test_evolve_adds_new_skill(self, temp_dir):
        bank = SkillBank(skills_dir=temp_dir / "skills")
        designer = SkillDesigner(bank, storage_dir=temp_dir, hard_case_threshold=2)

        designer.record_hard_case(_make_hard_case("hc1"))
        designer.record_hard_case(_make_hard_case("hc2"))

        response = json.dumps([{
            "action": "add_new",
            "id": "capture_activity_details",
            "description": "Capture activity details from conversation",
            "content": "# Capture Activity Details\n\nCapture activity info.",
        }])
        provider = _MockProvider(f"```json\n{response}\n```")

        new_skills = await designer.evolve_skills(provider, "mock")

        assert len(new_skills) == 1
        assert new_skills[0].id == "capture_activity_details"

        # Skill should be in the bank
        loaded = bank.get("capture_activity_details")
        assert loaded is not None
        assert loaded.is_primitive is False

    @pytest.mark.asyncio
    async def test_evolve_refines_existing(self, temp_dir):
        bank = SkillBank(skills_dir=temp_dir / "skills")
        # Add a skill to refine
        existing = MemorySkill(
            id="my_skill",
            description="Original description",
            content="# Original",
            created_at=datetime.now(),
            version=1,
        )
        bank.add_skill(existing)

        designer = SkillDesigner(bank, storage_dir=temp_dir, hard_case_threshold=1)
        designer.record_hard_case(_make_hard_case())

        response = json.dumps([{
            "action": "refine_existing",
            "id": "my_skill",
            "description": "Improved description",
            "content": "# Improved\n\nBetter instructions.",
        }])
        provider = _MockProvider(response)

        new_skills = await designer.evolve_skills(provider, "mock")

        assert len(new_skills) == 1
        refined = bank.get("my_skill")
        assert refined.description == "Improved description"
        assert refined.version == 2

    @pytest.mark.asyncio
    async def test_evolve_clears_hard_cases(self, temp_dir):
        bank = SkillBank(skills_dir=temp_dir / "skills")
        designer = SkillDesigner(bank, storage_dir=temp_dir, hard_case_threshold=1)
        designer.record_hard_case(_make_hard_case())

        provider = _MockProvider("[]")
        await designer.evolve_skills(provider, "mock")

        assert designer.should_evolve() is False
        assert len(designer._ensure_loaded()) == 0

    @pytest.mark.asyncio
    async def test_evolve_empty_hard_cases(self, temp_dir):
        bank = SkillBank(skills_dir=temp_dir / "skills")
        designer = SkillDesigner(bank, storage_dir=temp_dir)

        provider = _MockProvider("[]")
        result = await designer.evolve_skills(provider, "mock")
        assert result == []

    @pytest.mark.asyncio
    async def test_evolve_does_not_refine_primitives(self, temp_dir):
        bank = SkillBank(skills_dir=temp_dir / "skills")
        designer = SkillDesigner(bank, storage_dir=temp_dir, hard_case_threshold=1)
        designer.record_hard_case(_make_hard_case())

        response = json.dumps([{
            "action": "refine_existing",
            "id": "primitive_insert",
            "description": "Modified primitive",
            "content": "# Modified",
        }])
        provider = _MockProvider(response)

        new_skills = await designer.evolve_skills(provider, "mock")
        # Primitives should not be refined
        assert len(new_skills) == 0
        prim = bank.get("primitive_insert")
        assert "Modified" not in prim.description

    def test_check_rollbacks(self, temp_dir):
        bank = SkillBank(skills_dir=temp_dir / "skills")
        # Add a low-success evolved skill
        bad = MemorySkill(
            id="bad_skill",
            description="Bad skill",
            content="# Bad",
            created_at=datetime.now(),
            usage_count=10,
            success_count=1,
        )
        bank.add_skill(bad)

        # Add a good evolved skill
        good = MemorySkill(
            id="good_skill",
            description="Good skill",
            content="# Good",
            created_at=datetime.now(),
            usage_count=10,
            success_count=9,
        )
        bank.add_skill(good)

        designer = SkillDesigner(bank, storage_dir=temp_dir)
        rolled_back = designer.check_rollbacks()

        assert "bad_skill" in rolled_back
        assert "good_skill" not in rolled_back
        assert bank.get("bad_skill") is None
        assert bank.get("good_skill") is not None

    @pytest.mark.asyncio
    async def test_malformed_response(self, temp_dir):
        bank = SkillBank(skills_dir=temp_dir / "skills")
        designer = SkillDesigner(bank, storage_dir=temp_dir, hard_case_threshold=1)
        designer.record_hard_case(_make_hard_case())

        provider = _MockProvider("This is not JSON")
        new_skills = await designer.evolve_skills(provider, "mock")
        assert new_skills == []

    def test_hard_case_operations_persist(self, temp_dir):
        bank = SkillBank(skills_dir=temp_dir / "skills")
        designer = SkillDesigner(bank, storage_dir=temp_dir)

        case = HardCase(
            id="hc_ops",
            conversation_snippet="test",
            selected_skills=["primitive_insert"],
            operations=[
                MemoryOperation(
                    type=OperationType.INSERT,
                    content="test content",
                    tags=["tag1"],
                    reasoning="test reason",
                )
            ],
            failure_type="storage_failure",
        )
        designer.record_hard_case(case)

        # Reload
        designer2 = SkillDesigner(bank, storage_dir=temp_dir)
        loaded = designer2._ensure_loaded()
        assert len(loaded) == 1
        assert len(loaded[0].operations) == 1
        assert loaded[0].operations[0].type == OperationType.INSERT
        assert loaded[0].operations[0].content == "test content"
