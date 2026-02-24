"""Data models for the memory skill system."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class OperationType(str, Enum):
    """Types of memory operations."""

    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"
    NOOP = "noop"


@dataclass
class MemorySkill:
    """A memory skill — instructions for how to extract/manage memories.

    Skills are stored as individual .md files with YAML frontmatter (metadata)
    and markdown body (instructions for the executor).
    """

    id: str
    description: str
    content: str
    created_at: datetime
    is_primitive: bool = False
    version: int = 1
    usage_count: int = 0
    success_count: int = 0


@dataclass
class MemoryEntry:
    """A single memory entry stored in JSONL."""

    id: str
    content: str
    tags: list[str] = field(default_factory=list)
    source_session: str = ""
    source_skill: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    access_count: int = 0


@dataclass
class MemoryOperation:
    """An operation to perform on the memory store."""

    type: OperationType
    content: str = ""
    target_id: str = ""
    tags: list[str] = field(default_factory=list)
    skill_id: str = ""
    reasoning: str = ""


@dataclass
class HardCase:
    """A hard case for the designer to analyze."""

    id: str
    conversation_snippet: str
    selected_skills: list[str] = field(default_factory=list)
    operations: list[MemoryOperation] = field(default_factory=list)
    failure_type: str = ""
    created_at: datetime = field(default_factory=datetime.now)
