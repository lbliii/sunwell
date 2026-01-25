"""Milestone Tracking for Hierarchical Goals (RFC-115).

Tracks milestone progress and handles transitions between milestones.
Builds context for planning the next milestone based on completed work.

Example:
    tracker = MilestoneTracker(backlog_manager)

    # When milestone completes
    next_milestone = await tracker.complete_milestone(milestone_id)
    if next_milestone:
        # Build context for planning next milestone
        context = tracker.get_context_for_next(epic_id)
        # Plan next milestone with HarmonicPlanner using this context
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sunwell.foundation.types.protocol import Serializable as DictSerializable

if TYPE_CHECKING:
    from sunwell.features.backlog.goals import Goal
    from sunwell.features.backlog.manager import BacklogManager

__all__ = ["DictSerializable", "MilestoneProgress", "MilestoneTracker"]


@dataclass(frozen=True, slots=True)
class MilestoneProgress:
    """Progress summary for an epic."""

    epic_id: str
    epic_title: str
    total_milestones: int
    completed_milestones: int
    current_milestone_id: str | None
    current_milestone_title: str | None
    current_milestone_tasks_total: int
    current_milestone_tasks_completed: int
    percent_complete: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "epic_id": self.epic_id,
            "epic_title": self.epic_title,
            "total_milestones": self.total_milestones,
            "completed_milestones": self.completed_milestones,
            "current_milestone_id": self.current_milestone_id,
            "current_milestone_title": self.current_milestone_title,
            "current_milestone_tasks_total": self.current_milestone_tasks_total,
            "current_milestone_tasks_completed": self.current_milestone_tasks_completed,
            "percent_complete": self.percent_complete,
        }


@dataclass(frozen=True, slots=True)
class MilestoneLearning:
    """A learning extracted from milestone completion."""

    milestone_id: str
    milestone_title: str
    learning_type: str  # "artifact", "pattern", "challenge", "decision"
    content: str
    created_at: datetime

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "milestone_id": self.milestone_id,
            "milestone_title": self.milestone_title,
            "learning_type": self.learning_type,
            "content": self.content,
            "created_at": self.created_at.isoformat(),
        }


@dataclass(slots=True)
class LearningStore:
    """Stores learnings extracted from milestone completions."""

    store_path: Path
    """Path to learnings storage directory."""

    def __post_init__(self) -> None:
        """Ensure storage directory exists."""
        self.store_path.mkdir(parents=True, exist_ok=True)

    def _epic_path(self, epic_id: str) -> Path:
        """Get path to learnings file for an epic."""
        return self.store_path / f"{epic_id}.jsonl"

    def add_learning(self, epic_id: str, learning: MilestoneLearning) -> None:
        """Add a learning for an epic."""
        path = self._epic_path(epic_id)
        with path.open("a") as f:
            f.write(json.dumps(learning.to_dict()) + "\n")

    def get_learnings(self, epic_id: str) -> list[MilestoneLearning]:
        """Get all learnings for an epic."""
        path = self._epic_path(epic_id)
        if not path.exists():
            return []

        learnings: list[MilestoneLearning] = []
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                learnings.append(
                    MilestoneLearning(
                        milestone_id=data["milestone_id"],
                        milestone_title=data["milestone_title"],
                        learning_type=data["learning_type"],
                        content=data["content"],
                        created_at=datetime.fromisoformat(data["created_at"]),
                    ),
                )
            except (json.JSONDecodeError, KeyError):
                continue

        return learnings

    def get_learnings_for_milestone(
        self, epic_id: str, milestone_id: str
    ) -> list[MilestoneLearning]:
        """Get learnings from a specific milestone."""
        return [
            l for l in self.get_learnings(epic_id) if l.milestone_id == milestone_id
        ]


@dataclass(slots=True)
class MilestoneTracker:
    """Tracks milestone progress and handles transitions (RFC-115).

    Responsibilities:
    1. Track progress across milestones
    2. Extract learnings at milestone boundaries
    3. Build context for planning next milestone
    4. Record milestone completion history
    """

    backlog_manager: "BacklogManager"
    """BacklogManager for goal access."""

    learning_store: LearningStore | None = None
    """Optional store for learnings (created if None)."""

    def __post_init__(self) -> None:
        """Initialize learning store if not provided."""
        if self.learning_store is None:
            store_path = self.backlog_manager.backlog_path / "learnings"
            self.learning_store = LearningStore(store_path)

    def get_progress(self, epic_id: str) -> MilestoneProgress | None:
        """Get progress summary for an epic.

        Args:
            epic_id: ID of the epic

        Returns:
            MilestoneProgress or None if epic not found
        """
        backlog = self.backlog_manager.backlog

        epic = backlog.get_epic(epic_id)
        if not epic:
            return None

        completed, total = backlog.get_epic_progress(epic_id)
        current = backlog.get_current_milestone()

        current_id = None
        current_title = None
        tasks_completed = 0
        tasks_total = 0

        if current and current.parent_goal_id == epic_id:
            current_id = current.id
            current_title = current.title
            tasks_completed, tasks_total = backlog.get_milestone_progress(current.id)

        # Calculate overall percent
        if total == 0:
            percent = 0.0
        else:
            # Milestones contribute equally, current milestone progress counts partially
            milestone_weight = 1.0 / total
            milestone_progress = 0.0
            if tasks_total > 0:
                milestone_progress = tasks_completed / tasks_total
            percent = (completed + milestone_progress) * milestone_weight * 100

        return MilestoneProgress(
            epic_id=epic_id,
            epic_title=epic.title,
            total_milestones=total,
            completed_milestones=completed,
            current_milestone_id=current_id,
            current_milestone_title=current_title,
            current_milestone_tasks_total=tasks_total,
            current_milestone_tasks_completed=tasks_completed,
            percent_complete=round(percent, 1),
        )

    async def complete_milestone(
        self,
        milestone_id: str,
        learnings: list[MilestoneLearning] | None = None,
    ) -> "Goal | None":
        """Mark milestone complete and advance to next.

        Args:
            milestone_id: ID of the completed milestone
            learnings: Optional learnings to store

        Returns:
            The next milestone, or None if epic is complete
        """
        backlog = self.backlog_manager.backlog
        milestone = backlog.goals.get(milestone_id)

        if not milestone or not milestone.parent_goal_id:
            return None

        epic_id = milestone.parent_goal_id

        # Store learnings if provided
        if learnings and self.learning_store:
            for learning in learnings:
                self.learning_store.add_learning(epic_id, learning)

        # Record milestone artifacts as learnings
        if self.learning_store and milestone.milestone_produces:
            for artifact in milestone.milestone_produces:
                self.learning_store.add_learning(
                    epic_id,
                    MilestoneLearning(
                        milestone_id=milestone_id,
                        milestone_title=milestone.title,
                        learning_type="artifact",
                        content=f"Produced artifact: {artifact}",
                        created_at=datetime.now(),
                    ),
                )

        # Advance to next milestone
        return await self.backlog_manager.advance_milestone()

    def get_context_for_next(self, epic_id: str) -> dict[str, Any]:
        """Build context for planning the next milestone.

        Context includes:
        - Completed milestones and their artifacts
        - Learnings from previous milestones
        - Current project state

        Args:
            epic_id: ID of the epic

        Returns:
            Context dict for HarmonicPlanner
        """
        backlog = self.backlog_manager.backlog

        # Get epic and milestones
        epic = backlog.get_epic(epic_id)
        if not epic:
            return {}

        milestones = backlog.get_milestones(epic_id)

        # Collect completed milestone info
        completed_milestones: list[dict[str, Any]] = []
        completed_artifacts: list[str] = []

        for m in milestones:
            if m.id in backlog.completed:
                completed_milestones.append({
                    "id": m.id,
                    "title": m.title,
                    "produces": list(m.milestone_produces),
                })
                completed_artifacts.extend(m.milestone_produces)

        # Get learnings
        learnings: list[dict[str, Any]] = []
        if self.learning_store:
            for learning in self.learning_store.get_learnings(epic_id):
                learnings.append({
                    "milestone": learning.milestone_title,
                    "type": learning.learning_type,
                    "content": learning.content,
                })

        # Get current milestone
        current = backlog.get_current_milestone()
        current_info = None
        if current and current.parent_goal_id == epic_id:
            current_info = {
                "id": current.id,
                "title": current.title,
                "description": current.description,
                "produces": list(current.milestone_produces),
                "requires": list(current.requires),
            }

        return {
            "epic_id": epic_id,
            "epic_title": epic.title,
            "completed_milestones": completed_milestones,
            "completed_artifacts": completed_artifacts,
            "learnings": learnings,
            "current_milestone": current_info,
            "milestones_remaining": len(milestones) - len(completed_milestones),
        }

    def get_milestone_timeline(self, epic_id: str) -> list[dict[str, Any]]:
        """Get timeline view of milestones for UI.

        Args:
            epic_id: ID of the epic

        Returns:
            List of milestone info dicts with status
        """
        backlog = self.backlog_manager.backlog

        milestones = backlog.get_milestones(epic_id)
        timeline: list[dict[str, Any]] = []

        for m in milestones:
            # Determine status
            if m.id in backlog.completed:
                status = "completed"
            elif m.id in backlog.blocked:
                status = "blocked"
            elif m.id == backlog.active_milestone:
                status = "active"
            else:
                status = "pending"

            # Get task progress if active
            tasks_completed = 0
            tasks_total = 0
            if status == "active":
                tasks_completed, tasks_total = backlog.get_milestone_progress(m.id)

            timeline.append({
                "id": m.id,
                "title": m.title,
                "description": m.description,
                "produces": list(m.milestone_produces),
                "status": status,
                "index": m.milestone_index,
                "tasks_completed": tasks_completed,
                "tasks_total": tasks_total,
            })

        return timeline
