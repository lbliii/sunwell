"""Briefing prefetch types (RFC-071).

Types for prefetch planning and context pre-loading.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from sunwell.memory.briefing.briefing import Briefing, BriefingStatus

if TYPE_CHECKING:
    from sunwell.agent.learning import Learning


@dataclass(frozen=True, slots=True)
class PrefetchPlan:
    """What to pre-load based on briefing signals."""

    files_to_read: tuple[str, ...]
    """Code files to pre-read into context."""

    learnings_to_load: tuple[str, ...]
    """Learning IDs to retrieve."""

    skills_needed: tuple[str, ...]
    """Skills/heuristics to activate."""

    dag_nodes_to_fetch: tuple[str, ...]
    """DAG node IDs to pre-traverse."""

    suggested_lens: str | None
    """Lens that best matches the work type."""

    # RFC-130: Memory-informed hints
    memory_hints: Mapping[str, Any] | None = None
    """Hints from similar past goals.

    May contain:
    - similar_goals: List of similar past goal descriptions
    - patterns: Success patterns from similar goals
    - user_preferences: Learned user preferences
    """


@dataclass(frozen=True, slots=True)
class PrefetchedContext:
    """Pre-loaded context ready for main agent.

    Result of executing a PrefetchPlan. Contains all the
    context that was pre-loaded before the main agent starts.
    """

    files: MappingProxyType[str, str]
    """Map of file path → file content (immutable)."""

    learnings: tuple[Any, ...]  # tuple[Learning, ...] at runtime
    """Pre-loaded learnings from memory store."""

    dag_context: tuple[Any, ...]  # tuple[Turn, ...] at runtime
    """Pre-fetched DAG nodes for conversation history."""

    active_skills: tuple[str, ...]
    """Skills that have been activated."""

    lens: str | None
    """Lens that was selected (or None for default)."""


def briefing_to_learning(briefing: Briefing) -> Learning | None:
    """Generate a learning from a completed briefing.

    When a mission completes, we extract a summary learning that
    persists in the unified memory store. This bridges the transient
    briefing with the accumulated learning system.

    Returns:
        Learning if briefing is complete, None otherwise
    """
    if briefing.status != BriefingStatus.COMPLETE:
        return None

    from sunwell.agent.learning import Learning

    return Learning(
        fact=f"Completed: {briefing.mission}. {briefing.progress}",
        category="task_completion",
        confidence=1.0,  # Briefing completions are high confidence
        source_file=briefing.goal_hash,
    )
