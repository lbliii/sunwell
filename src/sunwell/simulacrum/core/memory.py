"""Memory types for Simulacrum.

.. deprecated:: 0.5.0
   This module is deprecated. Use SimulacrumStore from sunwell.simulacrum.core.store
   which provides unified memory via the hierarchical tier system (HOT/WARM/COLD).
   See RFC-084 for migration details.

Human-inspired memory architecture:
- Working Memory: Current context, recent turns, active focus
- Long-term Memory: Learnings, facts, patterns that persist forever
- Episodic Memory: Past sessions, attempts, branches, dead ends
- Semantic Memory: Indexed knowledge (codebase, docs, references)
- Procedural Memory: Skills, workflows, heuristics (from Lens)

Each memory type has different:
- Retention: How long it lasts
- Retrieval: How it's accessed (direct, RAG, always-present)
- Capacity: How much it holds
- Compression: How it's compressed when full
"""


import warnings
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Protocol

from sunwell.simulacrum.core.turn import Learning, Turn, TurnType

# RFC-084: Emit deprecation warning when this module is imported
warnings.warn(
    "sunwell.simulacrum.core.memory is deprecated. "
    "Use SimulacrumStore from sunwell.simulacrum.core.store instead. "
    "See RFC-084 for migration details.",
    DeprecationWarning,
    stacklevel=2,
)


class MemoryType(Enum):
    """Types of memory in a simulacrum."""

    WORKING = "working"
    """Current conversation context. Volatile, limited capacity."""

    LONG_TERM = "long_term"
    """Learnings, facts, patterns. Persistent, unlimited."""

    EPISODIC = "episodic"
    """Past sessions, attempts, branches. Compressed over time."""

    SEMANTIC = "semantic"
    """Indexed knowledge (codebase, docs). RAG-searchable."""

    PROCEDURAL = "procedural"
    """Skills, workflows, heuristics. From Lens."""


class Memory(Protocol):
    """Protocol for all memory types."""

    @property
    def memory_type(self) -> MemoryType:
        """The type of this memory."""
        ...

    async def store(self, item: Turn | Learning | str) -> str:
        """Store an item. Returns item ID."""
        ...

    async def retrieve(self, query: str, limit: int = 5) -> list[Turn | Learning | str]:
        """Retrieve relevant items for a query."""
        ...

    def to_context(self, max_tokens: int = 1000) -> str:
        """Format memory contents for LLM context."""
        ...


@dataclass
class WorkingMemory:
    """Current conversation context.

    Properties:
    - Volatile: Lost when session ends (unless saved)
    - Limited capacity: Oldest items compressed/dropped
    - Direct access: Recent items always in context
    - Fast: In-memory, no retrieval needed
    """

    turns: list[Turn] = field(default_factory=list)
    """Recent conversation turns."""

    capacity: int = 20
    """Max turns before compression."""

    @property
    def memory_type(self) -> MemoryType:
        return MemoryType.WORKING

    async def store(self, turn: Turn) -> str:
        """Add a turn to working memory."""
        self.turns.append(turn)

        # Compress if over capacity
        if len(self.turns) > self.capacity:
            self._compress()

        return turn.id

    async def retrieve(self, query: str, limit: int = 5) -> list[Turn]:
        """Get recent turns (no query needed, always returns recent)."""
        return self.turns[-limit:]

    def to_context(self, max_tokens: int = 2000) -> str:
        """Format recent turns for context."""
        lines = ["## Recent Conversation"]

        for turn in self.turns[-10:]:  # Last 10 turns
            role = "User" if turn.turn_type == TurnType.USER else "Assistant"
            lines.append(f"\n**{role}**: {turn.content[:500]}")

        return "\n".join(lines)

    def _compress(self) -> None:
        """Compress old turns into a summary."""
        # Keep last N, compress the rest
        keep = self.capacity // 2
        to_compress = self.turns[:-keep]

        if to_compress:
            summary_content = f"[Summary of {len(to_compress)} earlier turns]"
            summary = Turn(
                content=summary_content,
                turn_type=TurnType.SUMMARY,
                parent_ids=tuple(t.id for t in to_compress),
            )
            self.turns = [summary] + self.turns[-keep:]


@dataclass
class LongTermMemory:
    """Persistent learnings, facts, and patterns.

    Properties:
    - Persistent: Never lost, survives sessions
    - Unlimited capacity: Grows forever
    - Categorized: Facts, preferences, constraints, patterns, dead ends
    - Always present: Key learnings injected into every context
    """

    learnings: dict[str, Learning] = field(default_factory=dict)
    """All learnings indexed by ID."""

    @property
    def memory_type(self) -> MemoryType:
        return MemoryType.LONG_TERM

    async def store(self, learning: Learning) -> str:
        """Add a learning."""
        # Check if this supersedes an existing learning
        for existing in self.learnings.values():
            if existing.fact.lower() in learning.fact.lower():
                # New learning supersedes old
                learning = Learning(
                    fact=learning.fact,
                    source_turns=learning.source_turns,
                    confidence=learning.confidence,
                    category=learning.category,
                    superseded_by=None,
                )
                # Mark old as superseded
                old = Learning(
                    fact=existing.fact,
                    source_turns=existing.source_turns,
                    confidence=existing.confidence,
                    category=existing.category,
                    superseded_by=learning.id,
                )
                self.learnings[existing.id] = old

        self.learnings[learning.id] = learning
        return learning.id

    async def retrieve(self, query: str, limit: int = 10) -> list[Learning]:
        """Get relevant learnings (simple keyword match for now)."""
        query_lower = query.lower()
        matches = []

        for learning in self.get_active():
            if any(word in learning.fact.lower() for word in query_lower.split()):
                matches.append(learning)

        return matches[:limit]

    def get_active(self) -> list[Learning]:
        """Get all non-superseded learnings."""
        return [l for l in self.learnings.values() if l.superseded_by is None]

    def get_by_category(self, category: str) -> list[Learning]:
        """Get learnings by category."""
        return [l for l in self.get_active() if l.category == category]

    def to_context(self, max_tokens: int = 1000) -> str:
        """Format learnings for context injection."""
        active = self.get_active()
        if not active:
            return ""

        lines = ["## Key Learnings (from this problem-solving session)"]

        # Group by category
        by_category: dict[str, list[Learning]] = {}
        for l in active:
            by_category.setdefault(l.category, []).append(l)

        for category, items in by_category.items():
            lines.append(f"\n### {category.title()}")
            for item in items:
                conf = f"({item.confidence:.0%})" if item.confidence < 1.0 else ""
                lines.append(f"- {item.fact} {conf}")

        return "\n".join(lines)


@dataclass
class EpisodicMemory:
    """Past sessions, attempts, and branches.

    Properties:
    - Persistent but compressed: Old episodes archived
    - Searchable: RAG retrieval of relevant past attempts
    - Tracks dead ends: Prevents repeating mistakes
    - Branch-aware: Multiple exploration paths
    """

    episodes: dict[str, Episode] = field(default_factory=dict)
    """Past sessions/attempts indexed by ID."""

    dead_ends: set[str] = field(default_factory=set)
    """Episode IDs marked as dead ends."""

    @property
    def memory_type(self) -> MemoryType:
        return MemoryType.EPISODIC

    async def store(self, episode: Episode) -> str:
        """Add an episode."""
        self.episodes[episode.id] = episode
        return episode.id

    async def retrieve(self, query: str, limit: int = 5) -> list[Episode]:
        """Get relevant past episodes."""
        query_lower = query.lower()
        matches = []

        for episode in self.episodes.values():
            if episode.id in self.dead_ends:
                continue  # Don't retrieve dead ends
            if query_lower in episode.summary.lower():
                matches.append(episode)

        return matches[:limit]

    def mark_dead_end(self, episode_id: str) -> None:
        """Mark an episode as a dead end."""
        self.dead_ends.add(episode_id)

    def get_dead_ends(self) -> list[Episode]:
        """Get all dead end episodes (for reference, not context)."""
        return [self.episodes[eid] for eid in self.dead_ends if eid in self.episodes]

    def to_context(self, max_tokens: int = 500) -> str:
        """Format relevant episodes for context."""
        # Only include dead end warnings, not full episodes
        dead = self.get_dead_ends()
        if not dead:
            return ""

        lines = ["## Dead Ends (don't repeat these approaches)"]
        for ep in dead[:5]:  # Max 5 dead ends
            lines.append(f"- ❌ {ep.summary}")

        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class Episode:
    """A past problem-solving attempt or session."""

    id: str
    summary: str
    outcome: str  # succeeded, failed, partial, abandoned
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    learnings_extracted: tuple[str, ...] = ()
    models_used: tuple[str, ...] = ()
    turn_count: int = 0


@dataclass
class SemanticMemory:
    """Indexed knowledge from codebase, docs, references.

    Properties:
    - External: Comes from workspace, not conversation
    - RAG-searchable: Retrieved based on query relevance
    - Large capacity: Can index entire codebases
    - Refreshable: Re-indexed when source changes
    """

    chunks: dict[str, str] = field(default_factory=dict)
    """Content chunks indexed by ID."""

    # Would integrate with CodebaseIndexer in real implementation

    @property
    def memory_type(self) -> MemoryType:
        return MemoryType.SEMANTIC

    async def store(self, chunk_id: str, content: str) -> str:
        """Add a knowledge chunk."""
        self.chunks[chunk_id] = content
        return chunk_id

    async def retrieve(self, query: str, limit: int = 5) -> list[str]:
        """RAG retrieval (simplified - real impl uses embeddings)."""
        query_lower = query.lower()
        matches = []

        for _chunk_id, content in self.chunks.items():
            if query_lower in content.lower():
                matches.append(content)

        return matches[:limit]

    def to_context(self, max_tokens: int = 2000) -> str:
        """Format retrieved chunks for context."""
        # In real use, this would format the RAG results
        return ""


@dataclass
class ProceduralMemory:
    """Skills, workflows, and heuristics from Lens.

    Properties:
    - From Lens: Loaded from .lens file
    - Always present: Core heuristics always in context
    - Skill execution: Can trigger tool/script execution
    - Domain-specific: Different procedures per lens
    """

    heuristics: list[str] = field(default_factory=list)
    """Thinking patterns and rules."""

    workflows: list[str] = field(default_factory=list)
    """Step-by-step procedures."""

    skills: list[str] = field(default_factory=list)
    """Executable capabilities."""

    @property
    def memory_type(self) -> MemoryType:
        return MemoryType.PROCEDURAL

    async def store(self, item: str) -> str:
        """Add a procedure (typically from lens loading)."""
        self.heuristics.append(item)
        return str(len(self.heuristics) - 1)

    async def retrieve(self, query: str, limit: int = 5) -> list[str]:
        """Get relevant heuristics for a query."""
        # In real impl, this uses RAG over heuristics
        return self.heuristics[:limit]

    def to_context(self, max_tokens: int = 1500) -> str:
        """Format procedures for context (core of lens injection)."""
        lines = ["## Expertise (how to think about this)"]

        for h in self.heuristics[:10]:
            lines.append(f"- {h}")

        return "\n".join(lines)
