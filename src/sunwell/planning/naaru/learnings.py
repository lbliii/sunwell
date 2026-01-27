"""Learning extraction and persistence (RFC-053/RFC-054).

Extracts learnings from task execution and persists them for future use.
"""


import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sunwell.planning.naaru.events import NaaruEventEmitterProtocol


class LearningExtractor:
    """Extract and persist learnings from execution (RFC-054).

    Learnings are extracted from completed tasks and persisted
    to .sunwell/learnings/ for future reference.
    """

    def __init__(
        self,
        workspace: Path,
        event_emitter: NaaruEventEmitterProtocol | None = None,
    ) -> None:
        """Initialize extractor.

        Args:
            workspace: Root path for user's project (.sunwell directory)
            event_emitter: Optional event emitter for learning events
        """
        self._root = workspace
        self._emitter = event_emitter

    async def extract_from_tasks(
        self,
        tasks: list[Any],
        goal: str,
    ) -> list[dict[str, Any]]:
        """Extract learnings from completed tasks.

        Args:
            tasks: List of executed tasks
            goal: The goal that was being pursued

        Returns:
            List of learning dictionaries
        """
        from sunwell.planning.naaru.types import TaskStatus

        learnings: list[dict[str, Any]] = []

        for task in tasks:
            if task.status == TaskStatus.COMPLETED and task.output:
                learning = {
                    "type": "task_completion",
                    "goal": goal,
                    "task_id": task.id,
                    "task_description": task.description,
                    "output": task.output[:500],  # Truncate for storage
                    "timestamp": datetime.now().isoformat(),
                }
                learnings.append(learning)

                # Emit learning event if emitter available
                if self._emitter:
                    self._emitter.emit_learning(**learning)

        # Persist learnings
        if learnings:
            await self.persist(learnings)

        return learnings

    async def persist(self, learnings: list[dict[str, Any]]) -> Path:
        """Persist learnings to storage.

        Args:
            learnings: List of learning dictionaries

        Returns:
            Path to the persisted learnings file
        """
        learnings_dir = self._root / ".sunwell" / "learnings"
        learnings_dir.mkdir(parents=True, exist_ok=True)

        learnings_file = learnings_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(learnings_file, "w") as f:
            json.dump(learnings, f, indent=2)

        return learnings_file

    async def persist_execution_state(
        self,
        goal: str,
        tasks: list[Any],
        artifacts: list[Path],
        completed: int,
        failed: int,
        elapsed: float,
    ) -> Path:
        """Persist execution state to .sunwell/plans/ (RFC-040).

        Args:
            goal: The execution goal
            tasks: List of executed tasks
            artifacts: List of produced artifacts
            completed: Number of completed tasks
            failed: Number of failed tasks
            elapsed: Execution time in seconds

        Returns:
            Path to the persisted plan file
        """
        import hashlib

        plans_path = self._root / ".sunwell" / "plans"
        plans_path.mkdir(parents=True, exist_ok=True)

        goal_hash = hashlib.sha256(goal.encode()).hexdigest()[:16]

        execution_state = {
            "goal": goal,
            "goal_hash": goal_hash,
            "tasks": [t.to_dict() if hasattr(t, "to_dict") else str(t) for t in tasks],
            "artifacts": [str(a) for a in artifacts],
            "stats": {
                "completed": completed,
                "failed": failed,
                "total": len(tasks),
                "duration_seconds": elapsed,
            },
            "created_at": datetime.now().isoformat(),
        }

        plan_file = plans_path / f"{goal_hash}.json"
        with open(plan_file, "w") as f:
            json.dump(execution_state, f, indent=2)

        return plan_file
