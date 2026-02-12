"""Coordinator and worker management service for Chirp interface."""

from dataclasses import dataclass
from typing import Any


@dataclass
class CoordinatorService:
    """Service for worker/coordinator management."""

    def list_workers(self) -> list[dict[str, Any]]:
        """List active workers.

        Returns:
            List of worker dicts with status and task counts
        """
        # TODO: Integrate with actual coordinator
        return [
            {
                "id": "w1",
                "name": "Worker-1",
                "status": "active",
                "tasks_running": 2,
                "tasks_completed": 15,
            },
            {
                "id": "w2",
                "name": "Worker-2",
                "status": "idle",
                "tasks_running": 0,
                "tasks_completed": 8,
            },
        ]
