"""Data types for the memory subsystem."""

from dataclasses import dataclass
from enum import Enum


class MemoryType(Enum):
    EPISODIC = "episodic"    # Full filing + analysis records
    ENTITY = "entity"        # Knowledge about regs, agencies, biz lines
    PRECEDENT = "precedent"  # Correction / feedback signals


@dataclass
class MemoryRecord:
    id: str
    memory_type: MemoryType
    namespace: str          # e.g. "sec", "cfpb", or "global"
    key: str                # Filing ID, entity name, or precedent label
    content: dict           # Arbitrary JSON payload
    embedding_text: str     # Text used for similarity search
    created_at: str
    updated_at: str
    access_count: int = 0
    relevance_score: float = 1.0
