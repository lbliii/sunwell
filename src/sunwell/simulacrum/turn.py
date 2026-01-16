"""Turn - The atomic unit of conversation.

Each turn is content-addressable (hash-based identity) enabling:
- O(1) deduplication
- Immutable history
- DAG construction
- Compression without loss
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Literal


class TurnType(Enum):
    """Types of conversation turns."""
    
    USER = "user"
    """User message."""
    
    ASSISTANT = "assistant"
    """Assistant response."""
    
    SYSTEM = "system"
    """System context/instructions."""
    
    TOOL_CALL = "tool_call"
    """Tool invocation."""
    
    TOOL_RESULT = "tool_result"
    """Tool execution result."""
    
    SUMMARY = "summary"
    """Compressed summary of multiple turns."""
    
    LEARNING = "learning"
    """Extracted insight/fact."""
    
    CHECKPOINT = "checkpoint"
    """Saved state marker."""


@dataclass(frozen=True, slots=True)
class Turn:
    """A single turn in a conversation.
    
    Immutable and content-addressable - the hash uniquely identifies
    the content, enabling deduplication and DAG construction.
    """
    
    content: str
    """The actual message content."""
    
    turn_type: TurnType
    """Type of this turn."""
    
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    """When this turn occurred."""
    
    # Provenance
    parent_ids: tuple[str, ...] = ()
    """IDs of parent turns (enables DAG structure)."""
    
    source: str | None = None
    """Where this content came from (file, tool, model, etc)."""
    
    # Metadata
    token_count: int = 0
    """Estimated tokens in this turn."""
    
    model: str | None = None
    """Model that generated this (for assistant turns)."""
    
    confidence: float | None = None
    """Confidence score (for learnings)."""
    
    tags: tuple[str, ...] = ()
    """Semantic tags for retrieval."""
    
    # Computed (cached)
    _hash: str | None = field(default=None, compare=False, hash=False)
    
    def __post_init__(self) -> None:
        """Estimate tokens if not provided."""
        if self.token_count == 0 and self.content:
            object.__setattr__(self, "token_count", self.estimate_tokens(self.content))

    @property
    def id(self) -> str:
        """Content-addressable ID (blake2b hash).
        
        Same content = same ID, enabling O(1) deduplication.
        """
        if self._hash:
            return self._hash
        
        # Hash content + type + parents for uniqueness
        data = f"{self.turn_type.value}:{self.content}:{','.join(self.parent_ids)}"
        return hashlib.blake2b(data.encode(), digest_size=16).hexdigest()
    
    @property
    def is_compressible(self) -> bool:
        """Can this turn be compressed/summarized?"""
        return self.turn_type in {
            TurnType.USER,
            TurnType.ASSISTANT,
            TurnType.TOOL_RESULT,
        }
    
    def __hash__(self) -> int:
        return hash(self.id)
    
    def __eq__(self, other: object) -> bool:
        if isinstance(other, Turn):
            return self.id == other.id
        return False
    
    def to_message(self) -> dict:
        """Convert to LLM message format."""
        role_map = {
            TurnType.USER: "user",
            TurnType.ASSISTANT: "assistant",
            TurnType.SYSTEM: "system",
            TurnType.TOOL_CALL: "assistant",
            TurnType.TOOL_RESULT: "tool",
            TurnType.SUMMARY: "system",
            TurnType.LEARNING: "system",
            TurnType.CHECKPOINT: "system",
        }
        
        return {
            "role": role_map.get(self.turn_type, "user"),
            "content": self.content,
        }

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Roughly estimate token count (words * 1.3)."""
        if not text:
            return 0
        word_count = len(text.split())
        return max(1, int(word_count * 1.3))
    
    def compress(self, summary: str) -> "Turn":
        """Create a compressed version of this turn."""
        return Turn(
            content=summary,
            turn_type=TurnType.SUMMARY,
            parent_ids=(self.id,),
            source=f"compressed:{self.id}",
            tags=self.tags,
        )


@dataclass(frozen=True, slots=True)
class Learning:
    """An extracted piece of knowledge from the conversation.
    
    Learnings are first-class citizens that persist even when
    the original conversation is compressed away.
    """
    
    fact: str
    """The actual learning/insight."""
    
    source_turns: tuple[str, ...]
    """Turn IDs this was extracted from."""
    
    confidence: float
    """How confident we are in this learning (0-1)."""
    
    category: Literal["fact", "preference", "constraint", "pattern", "dead_end"]
    """Type of learning."""
    
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    superseded_by: str | None = None
    """If this learning was updated, pointer to newer version."""
    
    @property
    def id(self) -> str:
        """Content-addressable ID."""
        data = f"{self.category}:{self.fact}"
        return hashlib.blake2b(data.encode(), digest_size=12).hexdigest()
    
    def to_turn(self) -> Turn:
        """Convert to a Turn for context injection."""
        return Turn(
            content=f"[{self.category.upper()}] {self.fact}",
            turn_type=TurnType.LEARNING,
            parent_ids=self.source_turns,
            confidence=self.confidence,
        )
