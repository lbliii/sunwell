"""Planning context for RFC-122: Compound Learning."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sunwell.foundation.types.memory import Episode
from sunwell.memory.simulacrum.core.turn import Learning

if TYPE_CHECKING:
    from sunwell.planning.naaru.convergence import Slot


@dataclass(frozen=True, slots=True)
class PlanningContext:
    """All knowledge relevant to a planning task (RFC-122).

    Structured context for HarmonicPlanner that categorizes retrieved
    learnings for injection via Convergence slots.

    RFC-022 Enhancement: Now includes episode tracking for learning from
    past sessions and avoiding dead ends.

    Example:
        >>> context = await store.retrieve_for_planning("Build CRUD API")
        >>> print(context.best_template.template_data.name)
        'CRUD Endpoint'
        >>> slots = context.to_convergence_slots()
    """

    facts: tuple[Learning, ...]
    """Factual knowledge about the codebase."""

    constraints: tuple[Learning, ...]
    """Constraints that must be followed."""

    dead_ends: tuple[Learning, ...]
    """Approaches that didn't work (avoid these)."""

    templates: tuple[Learning, ...]
    """Structural task patterns."""

    heuristics: tuple[Learning, ...]
    """Ordering/strategy hints."""

    patterns: tuple[Learning, ...]
    """Code patterns used in the codebase."""

    goal: str
    """The planning goal this context was retrieved for."""

    # RFC-022 Enhancement: Episode tracking
    episodes: tuple[Episode, ...] = ()
    """Past sessions with their outcomes and learnings."""

    dead_end_summaries: tuple[str, ...] = ()
    """Summary strings from failed episodes for quick injection."""

    def to_convergence_slots(self) -> list[Slot]:
        """Convert to Convergence slots for HarmonicPlanner injection."""
        from sunwell.planning.naaru.convergence import Slot, SlotSource

        slots: list[Slot] = []

        if self.facts:
            slots.append(Slot(
                id="knowledge:facts",
                content=[f.fact for f in self.facts],
                relevance=0.9,
                source=SlotSource.MEMORY_FETCHER,
            ))

        if self.constraints:
            slots.append(Slot(
                id="knowledge:constraints",
                content=[f"⚠️ I must: {c.fact}" for c in self.constraints],
                relevance=1.0,  # Constraints are high priority
                source=SlotSource.MEMORY_FETCHER,
            ))

        if self.dead_ends:
            slots.append(Slot(
                id="knowledge:dead_ends",
                content=[f"❌ I tried: {d.fact}" for d in self.dead_ends],
                relevance=0.95,  # Dead ends are important to avoid
                source=SlotSource.MEMORY_FETCHER,
            ))

        if self.templates:
            slots.append(Slot(
                id="knowledge:templates",
                content=self.templates,  # Full Learning objects for template matching
                relevance=0.85,
                source=SlotSource.MEMORY_FETCHER,
            ))

        if self.heuristics:
            slots.append(Slot(
                id="knowledge:heuristics",
                content=[f"💡 I've found: {h.fact}" for h in self.heuristics],
                relevance=0.7,
                source=SlotSource.MEMORY_FETCHER,
            ))

        if self.patterns:
            slots.append(Slot(
                id="knowledge:patterns",
                content=[p.fact for p in self.patterns],
                relevance=0.8,
                source=SlotSource.MEMORY_FETCHER,
            ))

        # RFC-022: Episode-based dead ends from past sessions
        if self.dead_end_summaries:
            slots.append(Slot(
                id="knowledge:episode_dead_ends",
                content=[f"❌ {s}" for s in self.dead_end_summaries],  # Already first-person
                relevance=0.92,  # High priority to avoid past mistakes
                source=SlotSource.MEMORY_FETCHER,
            ))

        return slots

    def to_prompt_section(self) -> str:
        """Format for injection into planner prompt.

        Uses first-person voice to reduce epistemic distance.
        """
        sections: list[str] = []

        if self.facts or self.patterns:
            sections.append("## What I Know About This Project")
            for f in self.facts[:10]:
                sections.append(f"- I know: {f.fact}")
            for p in self.patterns[:5]:
                sections.append(f"- I use: {p.fact}")

        if self.constraints:
            sections.append("\n## Constraints (I must follow)")
            for c in self.constraints[:5]:
                sections.append(f"- ⚠️ I must: {c.fact}")

        if self.dead_ends:
            sections.append("\n## Dead Ends (I tried these and they failed)")
            for d in self.dead_ends[:5]:
                sections.append(f"- ❌ I tried: {d.fact}")

        if self.templates:
            sections.append("\n## Patterns I Follow")
            for t in self.templates[:3]:
                if t.template_data:
                    sections.append(f"- **{t.template_data.name}**: {t.fact}")

        if self.heuristics:
            sections.append("\n## What I've Found Works")
            for h in self.heuristics[:5]:
                sections.append(f"- 💡 I've found: {h.fact}")

        # RFC-022: Episode-based dead ends (already first-person from episode summaries)
        if self.dead_end_summaries:
            sections.append("\n## Past Session Failures")
            for s in self.dead_end_summaries[:5]:
                sections.append(f"- ❌ {s}")

        return "\n".join(sections)

    @property
    def best_template(self) -> Learning | None:
        """Get the highest-confidence matching template."""
        if not self.templates:
            return None
        return max(self.templates, key=lambda t: t.confidence)

    @property
    def all_learnings(self) -> tuple[Learning, ...]:
        """Get all learnings for usage tracking."""
        return (
            self.facts +
            self.constraints +
            self.dead_ends +
            self.templates +
            self.heuristics +
            self.patterns
        )
