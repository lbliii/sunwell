"""Memory-related type definitions - context budgets, retrieval results, etc."""


from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.simulacrum.core.memory import Episode
    from sunwell.simulacrum.core.turn import Learning, Turn


@dataclass(slots=True)
class ContextBudget:
    """Token budget for context assembly.

    This is the single source of truth for context budgeting.
    Supports both traditional RAG (retrieved_tokens) and
    multi-topology memory (memory_tokens) patterns.
    """

    total_tokens: int = 8000
    """Total tokens available for context."""

    system_tokens: int = 1000
    """Reserved for system prompt."""

    recent_tokens: int = 2000
    """Reserved for recent conversation."""

    # Support both patterns: retrieved_tokens (traditional) and memory_tokens (multi-topology)
    retrieved_tokens: int = 2000
    """Reserved for retrieved relevant turns (traditional RAG)."""

    memory_tokens: int = 3000
    """Reserved for multi-topology memory retrieval (RFC-014)."""

    learnings_tokens: int = 1000
    """Reserved for learnings/insights."""

    response_tokens: int = 1000
    """Reserved for model response."""

    @property
    def available(self) -> int:
        """Tokens available after reservations."""
        return self.total_tokens - self.response_tokens


@dataclass(slots=True)
class MemoryRetrievalResult:
    """Results from parallel memory retrieval (simulacrum).

    This is the canonical type for memory retrieval results.
    The runtime/retriever.py version is different (expertise retrieval)
    and should be renamed to ExpertiseRetrievalResult.
    """

    learnings: list[tuple[Learning, float]] = field(default_factory=list)
    """(Learning, relevance_score) tuples."""

    episodes: list[tuple[Episode, float]] = field(default_factory=list)
    """(Episode, relevance_score) tuples."""

    turns: list[tuple[Turn, float]] = field(default_factory=list)
    """(Turn, relevance_score) tuples from working memory."""

    code_chunks: list[tuple[str, float]] = field(default_factory=list)
    """(chunk_content, relevance_score) from semantic memory."""

    heuristics: list[str] = field(default_factory=list)
    """Relevant heuristics from procedural memory."""

    focus_topics: list[str] = field(default_factory=list)
    """Topics that drove this retrieval."""

    @property
    def total_items(self) -> int:
        """Total items retrieved across all memory types."""
        return (
            len(self.learnings) +
            len(self.episodes) +
            len(self.turns) +
            len(self.code_chunks) +
            len(self.heuristics)
        )

    def to_context(self, max_tokens: int = 6000) -> str:
        """Format all results into context string."""
        parts = []

        # Focus hint
        if self.focus_topics:
            parts.append(f"**Focus**: {', '.join(self.focus_topics[:5])}")

        # Procedural (always first - how to think)
        if self.heuristics:
            parts.append("\n## How to Think About This")
            for h in self.heuristics[:10]:
                parts.append(f"- {h}")

        # Learnings (high relevance first)
        if self.learnings:
            parts.append("\n## What We've Learned")
            for learning, score in sorted(self.learnings, key=lambda x: -x[1])[:15]:
                marker = "●" if score > 0.7 else "○"
                parts.append(f"{marker} [{learning.category}] {learning.fact}")

        # Dead ends from episodes
        dead_ends = [(e, s) for e, s in self.episodes if e.outcome == "failed"]
        if dead_ends:
            parts.append("\n## Dead Ends (don't repeat)")
            for ep, _ in dead_ends[:5]:
                parts.append(f"❌ {ep.summary}")

        # Recent conversation
        if self.turns:
            parts.append("\n## Recent Conversation")
            for turn, _ in self.turns[-10:]:
                role = "User" if turn.turn_type.value == "user" else "Assistant"
                content = turn.content[:300] + "..." if len(turn.content) > 300 else turn.content
                parts.append(f"\n**{role}**: {content}")

        # Code context
        if self.code_chunks:
            parts.append("\n## Relevant Code")
            for chunk, score in sorted(self.code_chunks, key=lambda x: -x[1])[:5]:
                parts.append(f"\n```\n{chunk[:500]}\n```")

        return "\n".join(parts)


# Alias for backward compatibility during migration
RetrievalResult = MemoryRetrievalResult
