"""MemSkill-based dynamic memory system.

Implements learnable, evolvable memory skills for extracting, consolidating,
and pruning information from conversations. Based on arxiv 2602.02474.
"""

from sparkagent.memory.designer import SkillDesigner
from sparkagent.memory.executor import execute_memory_skills
from sparkagent.memory.models import (
    HardCase,
    MemoryEntry,
    MemoryOperation,
    MemorySkill,
    OperationType,
)
from sparkagent.memory.selector import select_skills
from sparkagent.memory.skill_bank import SkillBank
from sparkagent.memory.store import MemoryStore

__all__ = [
    "HardCase",
    "MemoryEntry",
    "MemoryOperation",
    "MemorySkill",
    "MemoryStore",
    "OperationType",
    "SkillBank",
    "SkillDesigner",
    "execute_memory_skills",
    "select_skills",
]
