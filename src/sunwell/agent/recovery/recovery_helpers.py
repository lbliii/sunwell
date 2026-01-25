"""Recovery methods for Agent (extracted from core.py).

Provides crash recovery and resume capabilities:
- Resume from partial execution failures
- Convergence-based recovery loops
- Recovery state management
"""

from collections.abc import AsyncIterator
from pathlib import Path
from time import time
from typing import TYPE_CHECKING, Any

from sunwell.agent.events import (
    AgentEvent,
    EventType,
    complete_event,
    signal_event,
)

if TYPE_CHECKING:
    from sunwell.agent.learning import LearningStore
    from sunwell.agent.signals import AdaptiveSignals
    from sunwell.models import ModelProtocol


async def resume_from_recovery(
    recovery_state: Any,
    model: "ModelProtocol",
    cwd: Path,
    learning_store: "LearningStore",
    extract_signals_fn: Any,
    plan_with_signals_fn: Any,
    user_hint: str | None = None,
) -> AsyncIterator[AgentEvent]:
    """Resume execution from a recovery state (RFC-125).

    When a previous run failed with partial progress, this method
    resumes with full context of what succeeded and what failed,
    focusing only on fixing the failed artifacts.

    Args:
        recovery_state: RecoveryState from a previous failed run
        model: Model for generation
        cwd: Working directory
        learning_store: For tracking learnings
        extract_signals_fn: Function to extract signals
        plan_with_signals_fn: Function to plan with signals
        user_hint: Optional hint from user to guide fixes

    Yields:
        AgentEvent for each step of recovery execution
    """
    from sunwell.agent.recovery import build_healing_context

    start_time = time()

    yield AgentEvent(
        EventType.MEMORY_LOAD,
        {
            "source": "recovery",
            "recovery_id": recovery_state.run_id,
            "passed_count": len(recovery_state.passed_artifacts),
            "failed_count": len(recovery_state.failed_artifacts),
        },
    )

    # Build healing context with full information about what failed
    healing_context = build_healing_context(recovery_state, user_hint)

    # Create focused goal for fixing failed artifacts
    failed_paths = [str(a.path) for a in recovery_state.failed_artifacts]
    fix_goal = (
        f"Fix these files that failed validation: {', '.join(failed_paths)}\n\n"
        f"CONTEXT:\n{healing_context}"
    )

    # Extract signals for the fix task
    yield signal_event("extracting")
    signals = await extract_signals_fn(fix_goal)
    yield signal_event("extracted", signals=signals.to_dict())

    # Plan the fix
    async for event, task_graph, _ in plan_with_signals_fn(
        fix_goal,
        signals,
        {
            "is_recovery": True,
            "original_goal": recovery_state.goal,
            "failed_files": failed_paths,
            "passed_files": [str(a.path) for a in recovery_state.passed_artifacts],
        },
    ):
        yield event
        if event.type == EventType.ERROR:
            return

    # Execute with convergence to ensure we reach a stable state
    async for event in execute_with_convergence_recovery(
        recovery_state, healing_context, model, cwd
    ):
        yield event
        if event.type in (EventType.ERROR, EventType.ESCALATE):
            # Recovery failed again — state preserved for another attempt
            return

    duration = time() - start_time
    yield complete_event(
        tasks_completed=len(recovery_state.failed_artifacts),
        gates_passed=1,
        duration_s=duration,
        learnings=len(learning_store.learnings),
    )


async def execute_with_convergence_recovery(
    recovery_state: Any,
    healing_context: str,
    model: "ModelProtocol",
    cwd: Path,
) -> AsyncIterator[AgentEvent]:
    """Execute recovery with convergence loops.

    Focused execution that only regenerates failed artifacts,
    preserving passed ones.

    Args:
        recovery_state: The recovery state
        healing_context: Context about what failed
        model: Model for generation
        cwd: Working directory

    Yields:
        AgentEvent for each step
    """
    from sunwell.agent.validation.gates import GateType
    from sunwell.agent.convergence import ConvergenceConfig, ConvergenceLoop

    # Get files to fix
    failed_files = [a.path for a in recovery_state.failed_artifacts]

    # Run convergence loop focused on failed files
    config = ConvergenceConfig(
        max_iterations=5,
        enabled_gates=frozenset({GateType.LINT, GateType.TYPE, GateType.SYNTAX}),
    )

    loop = ConvergenceLoop(
        model=model,
        cwd=cwd,
        config=config,
        goal=recovery_state.goal,
        run_id=f"recovery-{recovery_state.run_id}",
    )

    async for event in loop.run(failed_files):
        yield event
