"""Backlog context for planning (RFC-094).

Provides existing work context to planners so they can:
- Avoid creating duplicate goals
- Reference existing artifacts instead of recreating
- Understand what's in progress
"""

from dataclasses import dataclass

from sunwell.features.backlog.goals import Goal


@dataclass(frozen=True, slots=True)
class BacklogContext:
    """Existing work context for planning.

    Passed to planners so they can:
    - Avoid creating duplicate goals
    - Reference existing artifacts instead of recreating
    - Understand what's in progress
    """

    existing_goals: tuple[Goal, ...]
    """Goals already in backlog."""

    completed_artifacts: frozenset[str]
    """Artifact IDs already created."""

    in_progress: str | None
    """Goal ID currently being executed."""

    def artifact_exists(self, artifact_id: str) -> bool:
        """Check if artifact already exists."""
        return artifact_id in self.completed_artifacts

    def has_similar_goal(self, description: str, threshold: float = 0.8) -> Goal | None:
        """Find existing goal similar to description.

        Uses simple keyword overlap. Could use embeddings for better matching.
        """
        desc_words = set(description.lower().split())

        for goal in self.existing_goals:
            goal_words = set(goal.description.lower().split())
            if not goal_words:
                continue
            overlap = len(desc_words & goal_words) / len(goal_words)
            if overlap >= threshold:
                return goal

        return None
