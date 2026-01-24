"""Memory context types for unified memory facade (RFC-MEMORY).

These types represent query results from PersistentMemory:
- MemoryContext: All memory relevant to a goal (used during planning)
- TaskMemoryContext: Memory relevant to a specific task (used during execution)
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


@dataclass(frozen=True, slots=True)
class MemoryContext:
    """All memory relevant to a goal — used during planning.

    Aggregates results from multiple memory stores:
    - SimulacrumStore → learnings
    - DecisionMemory → constraints (from rejected options)
    - FailureMemory → dead_ends (approaches that failed)
    - TeamKnowledgeStore → team_decisions
    - PatternProfile → patterns

    Example:
        >>> ctx = await memory.get_relevant("add caching")
        >>> if ctx.constraints:
        ...     print("Avoid:", ctx.constraints)
    """

    learnings: tuple[Any, ...] = field(default_factory=tuple)
    """Facts learned from past executions."""

    facts: tuple[str, ...] = field(default_factory=tuple)
    """Extracted facts about the codebase."""

    constraints: tuple[str, ...] = field(default_factory=tuple)
    """Things we decided NOT to do: 'Don't use Redis - too complex for our scale'."""

    dead_ends: tuple[str, ...] = field(default_factory=tuple)
    """Approaches that failed before: 'Async SQLAlchemy caused connection pool issues'."""

    team_decisions: tuple[str, ...] = field(default_factory=tuple)
    """Team-level decisions: 'Team uses Pydantic v2 for all models'."""

    patterns: tuple[str, ...] = field(default_factory=tuple)
    """Style preferences: 'Use snake_case for functions'."""

    def to_prompt(self) -> str:
        """Format for inclusion in planning prompt.

        Generates a structured markdown section that injects constraints,
        dead ends, team decisions, and learnings into the planning context.
        """
        sections: list[str] = []

        if self.constraints:
            sections.append("## Constraints (DO NOT violate)")
            for c in self.constraints:
                sections.append(f"- ⛔ {c}")

        if self.dead_ends:
            sections.append("\n## Known Dead Ends (DO NOT repeat)")
            for d in self.dead_ends:
                sections.append(f"- ⚠️ {d}")

        if self.team_decisions:
            sections.append("\n## Team Decisions (follow these)")
            for t in self.team_decisions:
                sections.append(f"- ✓ {t}")

        if self.learnings:
            sections.append("\n## Known Facts")
            for learning in self.learnings[:10]:  # Limit to top 10
                if hasattr(learning, "fact") and hasattr(learning, "category"):
                    sections.append(f"- [{learning.category}] {learning.fact}")
                else:
                    sections.append(f"- {learning}")

        if self.patterns:
            sections.append("\n## Style Patterns")
            for p in self.patterns:
                sections.append(f"- {p}")

        return "\n".join(sections) if sections else ""

    @property
    def has_constraints(self) -> bool:
        """Whether there are any constraints or dead ends."""
        return bool(self.constraints or self.dead_ends)

    @property
    def constraint_count(self) -> int:
        """Total number of constraints and dead ends."""
        return len(self.constraints) + len(self.dead_ends)

    def __bool__(self) -> bool:
        """True if any memory content exists."""
        return bool(
            self.learnings
            or self.facts
            or self.constraints
            or self.dead_ends
            or self.team_decisions
            or self.patterns
        )


@dataclass(frozen=True, slots=True)
class TaskMemoryContext:
    """Memory relevant to a specific task — used during execution.

    More focused than MemoryContext, filtered to what's relevant
    for a specific file/path or task type.

    Example:
        >>> task_ctx = memory.get_task_context(task)
        >>> if task_ctx.hazards:
        ...     print("Watch out for:", task_ctx.hazards)
    """

    constraints: tuple[str, ...] = field(default_factory=tuple)
    """Constraints for this file/path."""

    hazards: tuple[str, ...] = field(default_factory=tuple)
    """Past failures involving this path."""

    patterns: tuple[str, ...] = field(default_factory=tuple)
    """Style patterns for this type of task."""

    def to_prompt(self) -> str:
        """Format for inclusion in task prompt.

        Generates a concise reminder of constraints and patterns
        relevant to the specific task being executed.
        """
        sections: list[str] = []

        if self.constraints:
            sections.append("CONSTRAINTS for this task:")
            for c in self.constraints:
                sections.append(f"  - {c}")

        if self.hazards:
            sections.append("HAZARDS (past failures with similar tasks):")
            for h in self.hazards:
                sections.append(f"  - {h}")

        if self.patterns:
            sections.append("PATTERNS to follow:")
            for p in self.patterns:
                sections.append(f"  - {p}")

        return "\n".join(sections) if sections else ""

    def __bool__(self) -> bool:
        """True if any task-specific memory exists."""
        return bool(self.constraints or self.hazards or self.patterns)


@dataclass(frozen=True, slots=True)
class SyncResult:
    """Result of syncing memory to disk.

    Tracks which components succeeded/failed during sync.
    """

    results: tuple[tuple[str, bool, str | None], ...]
    """Tuple of (component_name, success, error_message)."""

    @property
    def all_succeeded(self) -> bool:
        """Whether all components synced successfully."""
        return all(success for _, success, _ in self.results)

    @property
    def failed_components(self) -> list[str]:
        """Names of components that failed to sync."""
        return [name for name, success, _ in self.results if not success]

    def __bool__(self) -> bool:
        """True if sync was fully successful."""
        return self.all_succeeded
