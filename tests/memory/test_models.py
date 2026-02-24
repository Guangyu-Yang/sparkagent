"""Tests for memory data models."""

from datetime import datetime

from sparkagent.memory.models import (
    HardCase,
    MemoryEntry,
    MemoryOperation,
    MemorySkill,
    OperationType,
)


class TestOperationType:
    def test_values(self):
        assert OperationType.INSERT == "insert"
        assert OperationType.UPDATE == "update"
        assert OperationType.DELETE == "delete"
        assert OperationType.NOOP == "noop"

    def test_from_string(self):
        assert OperationType("insert") == OperationType.INSERT
        assert OperationType("delete") == OperationType.DELETE


class TestMemorySkill:
    def test_create(self):
        now = datetime.now()
        skill = MemorySkill(
            id="test_skill",
            description="A test skill",
            content="# Test\nInstructions here",
            created_at=now,
        )
        assert skill.id == "test_skill"
        assert skill.description == "A test skill"
        assert skill.content == "# Test\nInstructions here"
        assert skill.is_primitive is False
        assert skill.version == 1
        assert skill.usage_count == 0
        assert skill.success_count == 0
        assert skill.created_at == now

    def test_primitive_flag(self):
        skill = MemorySkill(
            id="primitive_insert",
            description="Insert",
            content="",
            is_primitive=True,
            created_at=datetime.now(),
        )
        assert skill.is_primitive is True


class TestMemoryEntry:
    def test_create_minimal(self):
        entry = MemoryEntry(id="abc123", content="User likes pizza")
        assert entry.id == "abc123"
        assert entry.content == "User likes pizza"
        assert entry.tags == []
        assert entry.source_session == ""
        assert entry.access_count == 0

    def test_create_full(self):
        now = datetime.now()
        entry = MemoryEntry(
            id="abc123",
            content="User likes pizza",
            tags=["food", "preference"],
            source_session="cli:default",
            source_skill="primitive_insert",
            created_at=now,
            updated_at=now,
            access_count=5,
        )
        assert entry.tags == ["food", "preference"]
        assert entry.source_session == "cli:default"
        assert entry.access_count == 5


class TestMemoryOperation:
    def test_insert_operation(self):
        op = MemoryOperation(
            type=OperationType.INSERT,
            content="New fact",
            tags=["fact"],
        )
        assert op.type == OperationType.INSERT
        assert op.content == "New fact"
        assert op.target_id == ""

    def test_update_operation(self):
        op = MemoryOperation(
            type=OperationType.UPDATE,
            content="Updated fact",
            target_id="entry123",
            tags=["fact"],
        )
        assert op.type == OperationType.UPDATE
        assert op.target_id == "entry123"

    def test_delete_operation(self):
        op = MemoryOperation(type=OperationType.DELETE, target_id="entry123")
        assert op.type == OperationType.DELETE

    def test_noop_operation(self):
        op = MemoryOperation(type=OperationType.NOOP, reasoning="Just a greeting")
        assert op.type == OperationType.NOOP
        assert op.reasoning == "Just a greeting"


class TestHardCase:
    def test_create(self):
        case = HardCase(
            id="hc1",
            conversation_snippet="User: I moved to NYC\nAssistant: That's great!",
            selected_skills=["primitive_insert"],
            failure_type="missing_info",
        )
        assert case.id == "hc1"
        assert case.failure_type == "missing_info"
        assert case.selected_skills == ["primitive_insert"]
        assert case.operations == []
