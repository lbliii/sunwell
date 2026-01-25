"""Layout Memory (RFC-072).

Tracks successful layouts for future reference.
Layout success is stored as learnings and influences future compositions.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sunwell.surface.types import SurfaceLayout

# Module-level constant for stop words (avoid per-call set rebuild)
_STOP_WORDS: frozenset[str] = frozenset({
    "a", "an", "the", "for", "with", "to", "in", "on", "of", "and", "or"
})


@dataclass(frozen=True, slots=True)
class LayoutMemory:
    """A recorded successful layout.

    Stored when a layout is used for a significant duration
    and the goal is marked complete.
    """

    goal_pattern: str
    """Normalized goal pattern (lowercase, keywords)."""

    layout: SurfaceLayout
    """The layout that worked well."""

    success_score: float
    """Success score 0-1 based on usage duration and completion."""

    timestamp: str
    """ISO timestamp when recorded."""

    project_id: str
    """Project identifier for scoping."""


@dataclass(frozen=True, slots=True)
class InteractionMetrics:
    """Metrics captured during layout usage."""

    duration_seconds: int
    """How long the layout was used."""

    goal_completed: bool
    """Whether the goal was marked complete."""

    manual_overrides: int
    """Number of times user manually changed primitives."""

    primitive_additions: int
    """Number of primitives user added."""

    primitive_removals: int
    """Number of primitives user removed."""


def calculate_layout_success(metrics: InteractionMetrics) -> float:
    """Calculate success score from interaction metrics.

    Score formula:
    - Base: min(duration / 300, 0.4) — up to 0.4 for 5 min usage
    - Completion bonus: +0.4 if goal completed
    - Override penalty: -0.1 per override (max -0.3)

    Args:
        metrics: Interaction metrics

    Returns:
        Success score 0.0-1.0
    """
    # Base score from duration (max 0.4 at 5 minutes)
    base_score = min(metrics.duration_seconds / 300, 0.4)

    # Completion bonus
    completion_bonus = 0.4 if metrics.goal_completed else 0.0

    # Override penalty
    override_count = (
        metrics.manual_overrides + metrics.primitive_additions + metrics.primitive_removals
    )
    override_penalty = min(override_count * 0.1, 0.3)

    return max(0.0, min(1.0, base_score + completion_bonus - override_penalty))


def normalize_goal(goal: str) -> str:
    """Normalize a goal for pattern matching.

    Extracts keywords and normalizes for comparison.

    Args:
        goal: Raw goal string

    Returns:
        Normalized pattern
    """
    # Lowercase
    normalized = goal.lower()

    # Remove common words (uses module-level frozenset for O(1) lookup)
    words = normalized.split()
    keywords = [w for w in words if w not in _STOP_WORDS and len(w) > 2]

    return " ".join(sorted(keywords))


def create_layout_memory(
    layout: SurfaceLayout,
    goal: str,
    metrics: InteractionMetrics,
    project_id: str,
) -> LayoutMemory | None:
    """Create a layout memory if worth recording.

    Only creates memory if success score >= 0.5.

    Args:
        layout: The layout used
        goal: The goal it was used for
        metrics: Interaction metrics
        project_id: Project identifier

    Returns:
        LayoutMemory if worth recording, None otherwise
    """
    success_score = calculate_layout_success(metrics)

    if success_score < 0.5:
        return None

    return LayoutMemory(
        goal_pattern=normalize_goal(goal),
        layout=layout,
        success_score=success_score,
        timestamp=datetime.now(UTC).isoformat(),
        project_id=project_id,
    )


def layout_memory_to_learning(memory: LayoutMemory) -> dict[str, Any]:
    """Convert layout memory to learning format for storage.

    This allows layout memories to be stored in the standard
    memory/learning system.

    Args:
        memory: Layout memory to convert

    Returns:
        Learning dict suitable for MemoryStore
    """
    primitives = [memory.layout.primary.id]
    primitives.extend(p.id for p in memory.layout.secondary)
    primitives.extend(p.id for p in memory.layout.contextual)

    return {
        "fact": f"Layout for '{memory.goal_pattern}' worked well",
        "category": "pattern",
        "confidence": memory.success_score,
        "metadata": {
            "type": "layout_success",
            "primitives": primitives,
            "arrangement": memory.layout.arrangement,
            "project_id": memory.project_id,
        },
    }
