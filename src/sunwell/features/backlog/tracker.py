"""MilestoneTracker stub (backlog feature removed)."""

from dataclasses import dataclass


@dataclass
class EpicProgress:
    """Minimal progress stub."""

    epic_id: str
    epic_title: str
    total_milestones: int
    completed_milestones: int
    current_milestone_id: str | None
    current_milestone_title: str | None
    current_milestone_tasks_total: int
    current_milestone_tasks_completed: int

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {
            "epic_id": self.epic_id,
            "epic_title": self.epic_title,
            "total_milestones": self.total_milestones,
            "completed_milestones": self.completed_milestones,
            "current_milestone_id": self.current_milestone_id,
            "current_milestone_title": self.current_milestone_title,
        }


class MilestoneTracker:
    """No-op MilestoneTracker stub. Backlog feature was removed."""

    def __init__(self, backlog_manager) -> None:
        self.backlog_manager = backlog_manager

    def get_progress(self, epic_id: str) -> EpicProgress | None:
        """Return None (no epics in stub)."""
        return None

    def get_milestone_timeline(self, epic_id: str) -> list | None:
        """Return None (no milestones in stub)."""
        return None

    def get_context_for_next(self, epic_id: str) -> dict:
        """Return empty context."""
        return {
            "completed_milestones": [],
            "completed_artifacts": [],
            "learnings": [],
        }
