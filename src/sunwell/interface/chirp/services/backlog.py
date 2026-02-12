"""Backlog and goal management service for Chirp interface."""

from dataclasses import dataclass
from typing import Any


@dataclass
class BacklogService:
    """Service for goal/backlog management."""

    def list_goals(self) -> list[dict[str, Any]]:
        """List all backlog goals.

        Returns:
            List of goal dicts with status, progress, etc.
        """
        import time

        # TODO: Integrate with actual backlog/goal system
        now = time.time()
        return [
            {
                "id": "g1",
                "description": "Implement user authentication",
                "status": "in_progress",
                "priority": "high",
                "progress": 60,
                "tasks_completed": 3,
                "tasks_total": 5,
                "created": now - 86400 * 2,  # 2 days ago
            },
            {
                "id": "g2",
                "description": "Add dark mode support",
                "status": "pending",
                "priority": "medium",
                "progress": 0,
                "tasks_completed": 0,
                "tasks_total": 8,
                "created": now - 86400 * 5,  # 5 days ago
            },
        ]

    def create_goal(self, description: str, priority: str = "medium") -> dict[str, Any]:
        """Create new backlog goal."""
        # TODO: Implement actual goal creation
        return {
            "id": "g-new",
            "description": description,
            "status": "pending",
            "priority": priority,
            "progress": 0,
            "tasks_completed": 0,
            "tasks_total": 0,
        }
