"""Semantic checkpointing for Agent (RFC-130).

Enables intelligent resume from meaningful workflow points by saving
checkpoints at semantic phase boundaries.
"""

import uuid
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sunwell.agent.events import checkpoint_saved_event
from sunwell.planning.naaru.checkpoint import AgentCheckpoint, CheckpointPhase

if TYPE_CHECKING:
    from sunwell.agent.core.task_graph import TaskGraph
    from sunwell.agent.events import AgentEvent
    from sunwell.foundation.core.lens import Lens
    from sunwell.memory.briefing import Briefing


class CheckpointManager:
    """Manages semantic checkpoints for Agent execution (RFC-130).

    Checkpoints are saved at semantic phase boundaries:
    - ORIENT_COMPLETE: After memory context loaded
    - PLAN_COMPLETE: After task graph generated
    - EXECUTION_PROGRESS: During task execution
    - GATES_PASSED: After validation gates pass
    - COMPLETE: After successful completion

    Attributes:
        cwd: Working directory for checkpoint storage
        checkpoint_count: Number of checkpoints saved this run
        current_phase: Current semantic phase
        user_decisions: User decisions recorded during run
    """

    def __init__(self, cwd: Path) -> None:
        """Initialize checkpoint manager.

        Args:
            cwd: Working directory for checkpoint storage
        """
        self.cwd = cwd
        self.checkpoint_count = 0
        self.current_phase = CheckpointPhase.ORIENT_COMPLETE
        self.user_decisions: list[str] = []

    def save_phase_checkpoint(
        self,
        phase: CheckpointPhase,
        phase_summary: str,
        goal: str,
        task_graph: TaskGraph | None,
        files_changed: list[str],
        context: dict[str, Any],
        spawned_specialist_ids: list[str],
    ) -> AgentEvent:
        """Save checkpoint at semantic phase boundary.

        RFC-130: Enables intelligent resume from meaningful workflow points.

        Args:
            phase: The phase being completed
            phase_summary: Human-readable summary of progress
            goal: The current goal
            task_graph: Current task graph (if available)
            files_changed: Files modified during this run
            context: Context snapshot
            spawned_specialist_ids: IDs of spawned specialists

        Returns:
            CheckpointSaved event
        """
        # Build checkpoint
        checkpoint = AgentCheckpoint(
            goal=goal,
            started_at=datetime.now(),  # Would track actual start in production
            checkpoint_at=datetime.now(),
            tasks=task_graph.tasks if task_graph else [],
            completed_ids=task_graph.completed_ids if task_graph else set(),
            artifacts=[Path(f) for f in files_changed],
            working_directory=str(self.cwd),
            context=context,
            phase=phase,
            phase_summary=phase_summary,
            user_decisions=tuple(self.user_decisions),
            spawned_specialists=tuple(spawned_specialist_ids),
        )

        # Save to disk
        from sunwell.knowledge.project.state import resolve_state_dir
        checkpoint_dir = resolve_state_dir(self.cwd) / "checkpoints"
        checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # Use phase-based filename for easier discovery
        checkpoint_id = uuid.uuid4().hex[:8]
        checkpoint_path = checkpoint_dir / f"agent-{phase.value}-{checkpoint_id}.json"
        checkpoint.save(checkpoint_path)

        self.checkpoint_count += 1
        self.current_phase = phase

        # Return event
        return checkpoint_saved_event(
            phase=phase.value,
            summary=phase_summary,
            tasks_completed=len(task_graph.completed_ids) if task_graph else 0,
        )

    def check_for_resumable_checkpoint(self, goal: str) -> AgentCheckpoint | None:
        """Check for existing checkpoint for this goal.

        RFC-130: Enables crash recovery and session resume.

        Args:
            goal: The current goal

        Returns:
            Checkpoint if found, None otherwise
        """
        return AgentCheckpoint.find_latest_for_goal(self.cwd, goal)

    def record_user_decision(self, decision: str) -> None:
        """Record a user decision for checkpoint tracking.

        RFC-130: User decisions are preserved in checkpoints for resume context.

        Args:
            decision: Description of the user's decision
        """
        self.user_decisions.append(decision)

    def get_context_snapshot(
        self,
        goal: str,
        learning_store: Any,
        workspace_context: str | None,
        lens: Lens | None,
        briefing: Briefing | None,
    ) -> dict[str, Any]:
        """Get current context snapshot for checkpoint or specialist.

        Args:
            goal: Current goal
            learning_store: Learning store for formatting learnings
            workspace_context: Workspace context string
            lens: Active lens (if any)
            briefing: Current briefing (if any)

        Returns:
            Dict with relevant context keys
        """
        context: dict[str, Any] = {
            "goal": goal,
        }

        # Add learnings context
        learnings_context = learning_store.format_for_prompt()
        if learnings_context:
            context["learnings"] = learnings_context

        # Add workspace context
        if workspace_context:
            context["workspace_context"] = workspace_context

        # Add lens context
        if lens:
            context["lens_context"] = lens.to_context()

        # Add briefing context
        if briefing:
            context["briefing"] = briefing.to_prompt()

        return context
