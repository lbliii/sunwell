"""Simulacrum - Your portable problem-solving context.

.. deprecated:: 0.5.0
   This module is deprecated. Use SimulacrumStore from sunwell.simulacrum.core.store
   which provides the unified Simulacrum class with RFC-084 features:
   - Hierarchical memory (HOT/WARM/COLD tiers)
   - Automatic topology extraction
   - Focus-weighted retrieval
   - CTF encoding for warm tier

A simulacrum is your complete cognitive context for solving a problem:
- Working Memory: What you're actively thinking about
- Long-term Memory: What you've learned (persists forever)
- Episodic Memory: What you've tried (dead ends, branches)
- Semantic Memory: What you know about the codebase
- Procedural Memory: How to think (from your Lens)

Key properties:
- Portable across models: /switch anthropic:claude-sonnet-4-20250514
- Persistent across sessions: Resume any session anytime
- Smart context assembly: Never exceed token limits
- Provenance tracking: Know where every insight came from
"""


import json
import warnings
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.simulacrum.context.focus import Focus, FocusFilter
from sunwell.simulacrum.core.memory import (
    Episode,
    EpisodicMemory,
    LongTermMemory,
    ProceduralMemory,
    SemanticMemory,
    WorkingMemory,
)
from sunwell.simulacrum.core.turn import Learning, Turn, TurnType
from sunwell.simulacrum.parallel.retriever import ParallelRetriever
from sunwell.types.memory import RetrievalResult

if TYPE_CHECKING:
    from sunwell.core.lens import Lens

# RFC-084: Emit deprecation warning when this module is imported
warnings.warn(
    "sunwell.simulacrum.core.core is deprecated. "
    "Use Simulacrum from sunwell.simulacrum.core (which aliases SimulacrumStore). "
    "See RFC-084 for migration details.",
    DeprecationWarning,
    stacklevel=2,
)


@dataclass(slots=True)
class Simulacrum:
    """Your complete problem-solving context.

    Aggregates all memory types and handles:
    - Context assembly (what goes to the LLM)
    - Memory coordination (what gets stored where)
    - Model switching (preserve state across models)
    - Session persistence (save/load)
    """

    name: str
    """Simulacrum/session name."""

    # Memory systems
    working: WorkingMemory = field(default_factory=WorkingMemory)
    long_term: LongTermMemory = field(default_factory=LongTermMemory)
    episodic: EpisodicMemory = field(default_factory=EpisodicMemory)
    semantic: SemanticMemory = field(default_factory=SemanticMemory)
    procedural: ProceduralMemory = field(default_factory=ProceduralMemory)

    # Attention mechanism (replaces vectors)
    focus: Focus = field(default_factory=Focus)
    """Current attention focus for memory retrieval."""

    # Model tracking
    current_model: str = ""
    models_used: list[str] = field(default_factory=list)

    # Metadata
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    @classmethod
    def create(cls, name: str, lens: Lens | None = None) -> Simulacrum:
        """Create a new simulacrum, optionally loading procedural memory from lens."""
        hs = cls(name=name)

        if lens:
            # Load heuristics into procedural memory
            for h in lens.heuristics:
                hs.procedural.heuristics.append(h.to_prompt_fragment())

            # Load workflows
            for w in lens.workflows:
                hs.procedural.workflows.append(w.name)

        return hs

    # === Core Operations ===

    async def add_user_message(self, content: str) -> str:
        """Add a user message to working memory."""
        turn = Turn(
            content=content,
            turn_type=TurnType.USER,
        )
        return await self.working.store(turn)

    async def add_assistant_message(self, content: str, model: str = "") -> str:
        """Add an assistant message to working memory."""
        turn = Turn(
            content=content,
            turn_type=TurnType.ASSISTANT,
            model=model or self.current_model,
        )
        return await self.working.store(turn)

    async def add_learning(
        self,
        fact: str,
        category: str = "fact",
        confidence: float = 1.0,
    ) -> str:
        """Add a learning to long-term memory."""
        learning = Learning(
            fact=fact,
            source_turns=tuple(t.id for t in self.working.turns[-3:]),
            confidence=confidence,
            category=category,
        )
        return await self.long_term.store(learning)

    def mark_dead_end(self, summary: str) -> str:
        """Mark current approach as a dead end."""
        episode = Episode(
            id=f"dead-{datetime.now().strftime('%H%M%S')}",
            summary=summary,
            outcome="failed",
            models_used=tuple(self.models_used + [self.current_model]),
            turn_count=len(self.working.turns),
        )
        self.episodic.episodes[episode.id] = episode
        self.episodic.mark_dead_end(episode.id)
        return episode.id

    def switch_model(self, new_model: str) -> str:
        """Switch to a different model, preserving all memory."""
        old_model = self.current_model
        if old_model:
            self.models_used.append(old_model)
        self.current_model = new_model
        self.updated_at = datetime.now().isoformat()
        return old_model

    # === Context Assembly ===

    async def assemble_context(
        self,
        query: str,
        max_tokens: int = 8000,
        parallel: bool = True,
    ) -> tuple[str, RetrievalResult]:
        """Assemble context from all memory types for LLM.

        Uses focus-based filtering with parallel retrieval:
        1. Update focus from query
        2. Query all memory types in parallel (4 threads)
        3. Merge results by relevance
        4. Include full text (no embedding loss)

        Args:
            query: Current user query.
            max_tokens: Token budget for context.
            parallel: If True, query memory types in parallel.

        Returns (context_string, RetrievalResult).
        """
        if parallel:
            # Parallel retrieval across all memory types
            retriever = ParallelRetriever(focus=self.focus)

            result = await retriever.retrieve(
                query=query,
                working=self.working,
                long_term=self.long_term,
                episodic=self.episodic,
                semantic=self.semantic,
                procedural=self.procedural,
            )

            context = result.to_context(max_tokens=max_tokens)
            return context, result

        else:
            # Sequential fallback (simpler, for debugging)
            return await self._assemble_sequential(query, max_tokens)

    async def _assemble_sequential(
        self,
        query: str,
        max_tokens: int,
    ) -> tuple[str, RetrievalResult]:
        """Sequential assembly (fallback, for debugging)."""
        parts = []

        # Update focus from query
        self.focus.update_from_query(query)
        focus_filter = FocusFilter(self.focus)

        # Collect results
        learnings_result = []
        episodes_result = []
        turns_result = []

        # 1. Procedural memory
        proc_ctx = self.procedural.to_context(max_tokens=1500)
        if proc_ctx:
            parts.append(proc_ctx)

        # 2. Long-term memory
        active_learnings = self.long_term.get_active()
        if active_learnings:
            learnings_result = focus_filter.filter_learnings(active_learnings, min_relevance=0.2)
            if learnings_result:
                parts.append("## Learnings")
                for learning, _score in learnings_result[:15]:
                    parts.append(f"- [{learning.category}] {learning.fact}")

        # 3. Episodic memory (dead ends)
        dead_ends = self.episodic.get_dead_ends()
        if dead_ends:
            parts.append("## Dead Ends")
            for ep in dead_ends[:5]:
                parts.append(f"❌ {ep.summary}")
                episodes_result.append((ep, 0.8))

        # 4. Working memory
        if self.working.turns:
            turns_result = focus_filter.filter_turns(self.working.turns, min_relevance=0.1)
            parts.append("## Recent Conversation")
            for turn, _ in self.working.turns[-10:]:
                role = "User" if turn.turn_type.value == "user" else "Assistant"
                parts.append(f"**{role}**: {turn.content[:300]}")

        result = RetrievalResult(
            learnings=learnings_result,
            episodes=episodes_result,
            turns=turns_result,
            heuristics=self.procedural.heuristics[:15],
            focus_topics=self.focus.active_topics,
        )

        return "\n\n".join(parts), result

    def set_focus(self, topic: str, weight: float = 1.0) -> None:
        """Explicitly set focus on a topic."""
        self.focus.set_explicit(topic, weight)

    def clear_focus(self, topic: str | None = None) -> None:
        """Clear focus. If topic is None, clears all."""
        if topic:
            self.focus.clear_explicit(topic)
        else:
            self.focus.clear_all()

    # === Persistence ===

    def save(self, path: Path) -> None:
        """Save simulacrum to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "name": self.name,
            "created_at": self.created_at,
            "updated_at": datetime.now().isoformat(),
            "current_model": self.current_model,
            "models_used": self.models_used,

            # Working memory
            "working": {
                "turns": [
                    {
                        "id": t.id,
                        "content": t.content,
                        "turn_type": t.turn_type.value,
                        "timestamp": t.timestamp,
                        "model": t.model,
                    }
                    for t in self.working.turns
                ],
            },

            # Long-term memory
            "long_term": {
                "learnings": [
                    {
                        "id": l.id,
                        "fact": l.fact,
                        "category": l.category,
                        "confidence": l.confidence,
                        "source_turns": list(l.source_turns),
                        "superseded_by": l.superseded_by,
                    }
                    for l in self.long_term.learnings.values()
                ],
            },

            # Episodic memory
            "episodic": {
                "episodes": [
                    {
                        "id": e.id,
                        "summary": e.summary,
                        "outcome": e.outcome,
                        "timestamp": e.timestamp,
                        "models_used": list(e.models_used),
                        "turn_count": e.turn_count,
                    }
                    for e in self.episodic.episodes.values()
                ],
                "dead_ends": list(self.episodic.dead_ends),
            },

            # Procedural (reference only - loaded from lens)
            "procedural": {
                "heuristic_count": len(self.procedural.heuristics),
                "workflow_count": len(self.procedural.workflows),
                "skill_count": len(self.procedural.skills),
            },
        }

        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, path: Path, lens: Lens | None = None) -> Simulacrum:
        """Load simulacrum from disk."""
        with open(path) as f:
            data = json.load(f)

        hs = cls(name=data["name"])
        hs.created_at = data["created_at"]
        hs.updated_at = data.get("updated_at", hs.created_at)
        hs.current_model = data.get("current_model", "")
        hs.models_used = data.get("models_used", [])

        # Restore working memory
        for t_data in data.get("working", {}).get("turns", []):
            turn = Turn(
                content=t_data["content"],
                turn_type=TurnType(t_data["turn_type"]),
                timestamp=t_data.get("timestamp", ""),
                model=t_data.get("model"),
            )
            hs.working.turns.append(turn)

        # Restore long-term memory
        for l_data in data.get("long_term", {}).get("learnings", []):
            learning = Learning(
                fact=l_data["fact"],
                category=l_data["category"],
                confidence=l_data["confidence"],
                source_turns=tuple(l_data.get("source_turns", [])),
                superseded_by=l_data.get("superseded_by"),
            )
            hs.long_term.learnings[learning.id] = learning

        # Restore episodic memory
        for e_data in data.get("episodic", {}).get("episodes", []):
            episode = Episode(
                id=e_data["id"],
                summary=e_data["summary"],
                outcome=e_data["outcome"],
                timestamp=e_data.get("timestamp", ""),
                models_used=tuple(e_data.get("models_used", [])),
                turn_count=e_data.get("turn_count", 0),
            )
            hs.episodic.episodes[episode.id] = episode

        hs.episodic.dead_ends = set(data.get("episodic", {}).get("dead_ends", []))

        # Load procedural from lens if provided
        if lens:
            for h in lens.heuristics:
                hs.procedural.heuristics.append(h.to_prompt_fragment())

        return hs

    # === Stats ===

    @property
    def stats(self) -> dict:
        """Simulacrum statistics."""
        return {
            "name": self.name,
            "current_model": self.current_model,
            "models_used": len(self.models_used),
            "working_turns": len(self.working.turns),
            "learnings": len(self.long_term.get_active()),
            "episodes": len(self.episodic.episodes),
            "dead_ends": len(self.episodic.dead_ends),
            "heuristics": len(self.procedural.heuristics),
        }
