"""Specialist execution for Agent Constellation (RFC-130).

Provides specialist spawning and execution:
- Delegate complex tasks to specialists
- Context sharing between agent and specialists
- Result collection and integration
- Recursive subplanner spawning for complex goals

The subplanner pattern (inspired by Cursor self-driving codebases):
- When a planner encounters a goal exceeding complexity threshold,
  it spawns a subplanner instead of directly spawning workers
- Subplanners own a narrowed scope slice and can spawn their own workers
- This enables recursive decomposition up to max depth 3
"""

from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sunwell.agent.context.session import PlannerMode
from sunwell.agent.coordination.handoff import Handoff, Finding, HandoffUrgency
from sunwell.agent.core.task_graph import sanitize_code_content
from sunwell.agent.events import (
    AgentEvent,
    specialist_completed_event,
    specialist_spawned_event,
)
from sunwell.agent.utils.spawn import SpawnRequest

if TYPE_CHECKING:
    from sunwell.agent.context.session import SessionContext
    from sunwell.agent.learning import LearningStore
    from sunwell.foundation.core.lens import Lens
    from sunwell.memory.briefing import Briefing
    from sunwell.planning.naaru.types import Task


async def execute_via_specialist(
    task: Task,
    naaru: Any,
    lens: Lens | None,
    cwd: Path,
    context_snapshot: dict[str, Any],
    specialist_count: int,
    files_changed_tracker: list[str],
) -> AsyncIterator[AgentEvent]:
    """Execute task by delegating to a spawned specialist.

    Args:
        task: The task to delegate
        naaru: Naaru instance for spawning
        lens: Current lens (for budget calculation)
        cwd: Working directory
        context_snapshot: Context to pass to specialist
        specialist_count: Current count of spawned specialists
        files_changed_tracker: List to append file changes to

    Yields:
        AgentEvent instances. The SPECIALIST_SPAWNED event contains specialist_id
        in its data dict for consumers to extract.
    """
    from sunwell.agent.execution import determine_specialist_role

    # Determine specialist role based on task
    role = determine_specialist_role(task)

    # Calculate budget
    if lens:
        budget_tokens = min(
            lens.spawn_budget_tokens // max(1, lens.max_children),
            5_000,
        )
    else:
        budget_tokens = 5_000

    # Create spawn request
    spawn_request = SpawnRequest(
        parent_id="agent-main",
        role=role,
        focus=task.description,
        reason="Task complexity or requirements exceed current lens capabilities",
        tools=tuple(getattr(task, "required_tools", [])),
        context_keys=("goal", "learnings", "workspace_context"),
        budget_tokens=budget_tokens,
    )

    # Spawn specialist
    specialist_id = await naaru.spawn_specialist(spawn_request, context_snapshot)

    # Emit spawn event (specialist_id already in event data via specialist_spawned_event)
    yield specialist_spawned_event(
        specialist_id=specialist_id,
        task_id=task.id,
        parent_id="agent-main",
        role=role,
        focus=task.description,
        budget_tokens=spawn_request.budget_tokens,
    )

    # Wait for specialist to complete
    result = await naaru.wait_specialist(specialist_id)

    # Emit completion event
    yield specialist_completed_event(
        specialist_id=specialist_id,
        success=result.success,
        summary=result.summary,
        tokens_used=result.tokens_used,
        duration_seconds=result.duration_seconds,
    )

    # If specialist produced output and task has target, write it
    if result.success and result.output and task.target_path:
        path = cwd / task.target_path
        path.parent.mkdir(parents=True, exist_ok=True)
        # Sanitize before writing (defense-in-depth)
        sanitized = sanitize_code_content(str(result.output))
        path.write_text(sanitized)
        files_changed_tracker.append(task.target_path)


def get_context_snapshot(
    goal: str,
    learning_store: LearningStore,
    workspace_context: str | None,
    lens: Lens | None,
    briefing: Briefing | None,
) -> dict[str, Any]:
    """Get current context snapshot to pass to specialist.

    Args:
        goal: Current goal
        learning_store: For formatting learnings
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


# =============================================================================
# Recursive Subplanner Pattern
# =============================================================================

# Thresholds for deciding when to spawn a subplanner vs. a worker
SUBPLANNER_COMPLEXITY_THRESHOLD = 3
"""Number of parallel groups that triggers subplanner spawning."""

SUBPLANNER_TASK_THRESHOLD = 5
"""Number of subtasks that triggers subplanner spawning."""


def should_spawn_subplanner(
    session: SessionContext,
    task: Task,
    parallel_group_count: int = 0,
    subtask_count: int = 0,
) -> bool:
    """Decide whether a task warrants a subplanner instead of a worker.

    A subplanner is appropriate when:
    1. The session can still spawn subplanners (not at max depth)
    2. The task is complex enough to benefit from decomposition
    3. The current session is a planner (ROOT or SUBPLANNER)

    Args:
        session: Current session context
        task: The task being evaluated
        parallel_group_count: Number of parallel groups in the task
        subtask_count: Number of subtasks in the task

    Returns:
        True if a subplanner should be spawned
    """
    # Workers never spawn subplanners
    if not session.can_spawn_subplanners:
        return False

    # Check complexity indicators
    if parallel_group_count >= SUBPLANNER_COMPLEXITY_THRESHOLD:
        return True

    if subtask_count >= SUBPLANNER_TASK_THRESHOLD:
        return True

    # Check task mode -- composite tasks are subplanner candidates
    if hasattr(task, "mode") and hasattr(task.mode, "value"):
        if task.mode.value == "composite":
            return True

    return False


async def execute_via_subplanner(
    task: Task,
    parent_session: SessionContext,
    naaru: Any,
    lens: Lens | None,
    context_snapshot: dict[str, Any],
    files_changed_tracker: list[str],
) -> AsyncIterator[AgentEvent]:
    """Execute task by spawning a subplanner that owns a narrowed scope.

    Unlike execute_via_specialist (which spawns a worker), this spawns
    a subplanner that can further decompose and delegate. The subplanner
    produces a Handoff on completion.

    Args:
        task: The task to delegate (should be complex/composite)
        parent_session: Parent session for spawning
        naaru: Naaru instance for spawning
        lens: Current lens
        context_snapshot: Context to pass to subplanner
        files_changed_tracker: List to append file changes to

    Yields:
        AgentEvent instances for the spawning and completion lifecycle
    """
    from sunwell.agent.context.session import SessionContext
    from sunwell.agent.execution import determine_specialist_role

    # Determine role
    role = determine_specialist_role(task)

    # Calculate budget (subplanners get more budget than workers)
    if lens:
        budget_tokens = min(
            lens.spawn_budget_tokens // max(1, lens.max_children // 2),
            10_000,  # Higher budget for subplanners
        )
    else:
        budget_tokens = 10_000

    # Create spawn request with subplanner designation
    spawn_request = SpawnRequest(
        parent_id=parent_session.session_id,
        role=f"subplanner:{role}",
        focus=task.description,
        reason="Task complexity warrants recursive decomposition",
        tools=tuple(getattr(task, "required_tools", [])),
        context_keys=("goal", "learnings", "workspace_context"),
        budget_tokens=budget_tokens,
    )

    # Spawn as subplanner (key difference from execute_via_specialist)
    specialist_id = await naaru.spawn_specialist(spawn_request, context_snapshot)

    # Emit spawn event
    yield specialist_spawned_event(
        specialist_id=specialist_id,
        task_id=task.id,
        parent_id=parent_session.session_id,
        role=f"subplanner:{role}",
        focus=task.description,
        budget_tokens=spawn_request.budget_tokens,
    )

    # Wait for subplanner to complete
    result = await naaru.wait_specialist(specialist_id)

    # Emit completion event
    yield specialist_completed_event(
        specialist_id=specialist_id,
        success=result.success,
        summary=result.summary,
        tokens_used=result.tokens_used,
        duration_seconds=result.duration_seconds,
    )

    # If subplanner produced output and task has target, write it
    if result.success and result.output and task.target_path:
        path = parent_session.cwd / task.target_path
        path.parent.mkdir(parents=True, exist_ok=True)
        sanitized = sanitize_code_content(str(result.output))
        path.write_text(sanitized)
        files_changed_tracker.append(task.target_path)
