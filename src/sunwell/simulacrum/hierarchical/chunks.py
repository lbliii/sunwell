"""Granularity levels and units for hierarchical conversation memory."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.simulacrum.core.turn import Turn


class ChunkType(Enum):
    """Granularity levels in the memory pyramid."""
    MICRO = "micro"   # e.g., 10 turns
    MINI = "mini"     # e.g., 25 turns (2-3 micro-chunks consolidated)
    MACRO = "macro"   # e.g., 100 turns (4 mini-chunks consolidated)


@dataclass(frozen=True, slots=True)
class Chunk:
    """A compressed unit of conversation history."""
    
    id: str
    chunk_type: ChunkType
    turn_range: tuple[int, int]  # (start_turn_index, end_turn_index)
    
    # Content (mutually exclusive based on tier)
    turns: tuple[Turn, ...] | None = None  # HOT: full turns
    content_ctf: str | None = None           # WARM: CTF-encoded (Compact Turn Format)
    content_ref: str | None = None           # COLD: reference to archive
    
    # Always present metadata
    summary: str = ""
    token_count: int = 0
    embedding: tuple[float, ...] | None = None
    
    # Time and semantic markers
    timestamp_start: str = ""
    timestamp_end: str = ""
    themes: tuple[str, ...] = ()
    key_facts: tuple[str, ...] = ()
    
    # Hierarchy
    parent_chunk_id: str | None = None       # ID of the mini/macro chunk that consolidates this
    child_chunk_ids: tuple[str, ...] = ()    # IDs of chunks this consolidates


@dataclass(frozen=True, slots=True)
class ChunkSummary:
    """Lightweight summary for retrieval without loading full chunk content."""
    
    chunk_id: str
    chunk_type: ChunkType
    turn_range: tuple[int, int]
    summary: str
    themes: tuple[str, ...]
    token_count: int
    embedding: tuple[float, ...] | None = None
