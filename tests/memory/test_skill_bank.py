"""Tests for skill bank."""

from datetime import datetime

from sparkagent.memory.models import MemorySkill
from sparkagent.memory.skill_bank import SkillBank, _parse_frontmatter


class TestParseFrontmatter:
    def test_basic_frontmatter(self):
        text = """---
description: Test skill
is_primitive: true
version: 2
---

# Content here"""
        meta, body = _parse_frontmatter(text)
        assert meta["description"] == "Test skill"
        assert meta["is_primitive"] == "true"
        assert meta["version"] == "2"
        assert "# Content here" in body

    def test_no_frontmatter(self):
        text = "# Just content\nNo frontmatter here"
        meta, body = _parse_frontmatter(text)
        assert meta == {}
        assert "Just content" in body

    def test_quoted_values(self):
        text = '---\ncreated_at: "2026-01-01T00:00:00"\n---\nBody'
        meta, body = _parse_frontmatter(text)
        assert meta["created_at"] == "2026-01-01T00:00:00"

    def test_empty_text(self):
        meta, body = _parse_frontmatter("")
        assert meta == {}
        assert body == ""


class TestSkillBank:
    def test_creates_primitives(self, temp_dir):
        SkillBank(skills_dir=temp_dir)
        files = list(temp_dir.glob("*.md"))
        assert len(files) == 4

        names = {f.stem for f in files}
        assert "primitive_insert" in names
        assert "primitive_update" in names
        assert "primitive_delete" in names
        assert "primitive_noop" in names

    def test_primitives_are_marked(self, temp_dir):
        bank = SkillBank(skills_dir=temp_dir)
        for skill in bank.get_all():
            assert skill.is_primitive is True

    def test_get_all(self, temp_dir):
        bank = SkillBank(skills_dir=temp_dir)
        skills = bank.get_all()
        assert len(skills) == 4

    def test_get_by_id(self, temp_dir):
        bank = SkillBank(skills_dir=temp_dir)
        skill = bank.get("primitive_insert")
        assert skill is not None
        assert skill.id == "primitive_insert"
        assert "Insert" in skill.description or "insert" in skill.description.lower()

    def test_get_nonexistent(self, temp_dir):
        bank = SkillBank(skills_dir=temp_dir)
        assert bank.get("nonexistent") is None

    def test_get_descriptions(self, temp_dir):
        bank = SkillBank(skills_dir=temp_dir)
        desc = bank.get_descriptions()
        assert "primitive_insert" in desc
        assert "primitive_noop" in desc
        assert "[primitive]" in desc

    def test_add_skill(self, temp_dir):
        bank = SkillBank(skills_dir=temp_dir)
        skill = MemorySkill(
            id="capture_details",
            description="Capture activity details",
            content="# Capture Details\n\nInstructions here.",
            created_at=datetime.now(),
        )

        bank.add_skill(skill)

        # Check file was created
        assert (temp_dir / "capture_details.md").exists()

        # Check it's retrievable
        loaded = bank.get("capture_details")
        assert loaded is not None
        assert loaded.description == "Capture activity details"
        assert loaded.is_primitive is False

    def test_remove_skill(self, temp_dir):
        bank = SkillBank(skills_dir=temp_dir)
        skill = MemorySkill(
            id="to_remove",
            description="Temporary skill",
            content="# Temp",
            created_at=datetime.now(),
        )
        bank.add_skill(skill)

        result = bank.remove_skill("to_remove")
        assert result is True
        assert not (temp_dir / "to_remove.md").exists()
        assert bank.get("to_remove") is None

    def test_cannot_remove_primitive(self, temp_dir):
        bank = SkillBank(skills_dir=temp_dir)
        result = bank.remove_skill("primitive_insert")
        assert result is False
        assert bank.get("primitive_insert") is not None

    def test_remove_nonexistent(self, temp_dir):
        bank = SkillBank(skills_dir=temp_dir)
        assert bank.remove_skill("nonexistent") is False

    def test_record_usage(self, temp_dir):
        bank = SkillBank(skills_dir=temp_dir)
        bank.record_usage("primitive_insert", success=True)
        bank.record_usage("primitive_insert", success=True)
        bank.record_usage("primitive_insert", success=False)

        skill = bank.get("primitive_insert")
        assert skill.usage_count == 3
        assert skill.success_count == 2

    def test_record_usage_persists(self, temp_dir):
        bank = SkillBank(skills_dir=temp_dir)
        bank.record_usage("primitive_insert", success=True)

        # Reload from disk
        bank2 = SkillBank(skills_dir=temp_dir)
        skill = bank2.get("primitive_insert")
        assert skill.usage_count == 1
        assert skill.success_count == 1

    def test_rollback_low_success(self, temp_dir):
        bank = SkillBank(skills_dir=temp_dir)
        skill = MemorySkill(
            id="bad_skill",
            description="A bad skill",
            content="# Bad",
            created_at=datetime.now(),
            usage_count=6,
            success_count=1,  # <30% success
        )
        bank.add_skill(skill)

        result = bank.rollback_skill("bad_skill")
        assert result is True
        assert bank.get("bad_skill") is None

    def test_no_rollback_high_success(self, temp_dir):
        bank = SkillBank(skills_dir=temp_dir)
        skill = MemorySkill(
            id="good_skill",
            description="A good skill",
            content="# Good",
            created_at=datetime.now(),
            usage_count=10,
            success_count=8,
        )
        bank.add_skill(skill)

        result = bank.rollback_skill("good_skill")
        assert result is False
        assert bank.get("good_skill") is not None

    def test_no_rollback_too_few_uses(self, temp_dir):
        bank = SkillBank(skills_dir=temp_dir)
        skill = MemorySkill(
            id="new_skill",
            description="New skill",
            content="# New",
            created_at=datetime.now(),
            usage_count=3,
            success_count=0,
        )
        bank.add_skill(skill)

        result = bank.rollback_skill("new_skill")
        assert result is False

    def test_does_not_recreate_primitives(self, temp_dir):
        """If primitives exist, they should not be overwritten."""
        bank = SkillBank(skills_dir=temp_dir)
        # Record usage to modify primitive
        bank.record_usage("primitive_insert", success=True)

        # Reload — should not reset usage count
        bank2 = SkillBank(skills_dir=temp_dir)
        skill = bank2.get("primitive_insert")
        assert skill.usage_count == 1

    def test_add_skill_shows_evolved_tag(self, temp_dir):
        bank = SkillBank(skills_dir=temp_dir)
        skill = MemorySkill(
            id="evolved_one",
            description="An evolved skill",
            content="# Evolved",
            created_at=datetime.now(),
        )
        bank.add_skill(skill)

        desc = bank.get_descriptions()
        assert "[evolved]" in desc
