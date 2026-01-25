"""Agent constellation event factories (RFC-130).

Event factories for multi-agent constellation lifecycle:
- specialist_spawned_event: Specialist agent spawned
- specialist_completed_event: Specialist finished
- checkpoint_found_event, checkpoint_saved_event: Checkpoint management
- phase_complete_event: Semantic phase completed
- autonomous_action_blocked_event: Action blocked by guardrails
- guard_evolution_suggested_event: Guard improvement suggested
"""

from typing import Any

from sunwell.agent.events.types import AgentEvent, EventType


def specialist_spawned_event(
    specialist_id: str,
    task_id: str,
    parent_id: str,
    role: str,
    focus: str,
    budget_tokens: int = 5_000,
    **kwargs: Any,
) -> AgentEvent:
    """Create a specialist spawned event (RFC-130).

    Emitted when the agent delegates a complex subtask to a specialist.

    Args:
        specialist_id: Unique specialist ID
        task_id: ID of the task that triggered spawning
        parent_id: ID of the parent agent/specialist
        role: Specialist role (e.g., "code_reviewer", "architect")
        focus: What the specialist is working on
        budget_tokens: Token budget for this specialist
    """
    return AgentEvent(
        EventType.SPECIALIST_SPAWNED,
        {
            "specialist_id": specialist_id,
            "task_id": task_id,
            "parent_id": parent_id,
            "role": role,
            "focus": focus,
            "budget_tokens": budget_tokens,
            **kwargs,
        },
    )


def specialist_completed_event(
    specialist_id: str,
    success: bool,
    summary: str,
    tokens_used: int,
    duration_seconds: float = 0.0,
    **kwargs: Any,
) -> AgentEvent:
    """Create a specialist completed event (RFC-130).

    Emitted when a spawned specialist finishes (success or failure).

    Args:
        specialist_id: Unique specialist ID
        success: Whether the specialist succeeded
        summary: Brief summary of what was accomplished
        tokens_used: Tokens consumed by the specialist
        duration_seconds: How long the specialist ran
    """
    return AgentEvent(
        EventType.SPECIALIST_COMPLETED,
        {
            "specialist_id": specialist_id,
            "success": success,
            "summary": summary,
            "tokens_used": tokens_used,
            "duration_seconds": duration_seconds,
            **kwargs,
        },
    )


def checkpoint_found_event(
    phase: str,
    checkpoint_at: str,
    goal: str,
    **kwargs: Any,
) -> AgentEvent:
    """Create a checkpoint found event (RFC-130).

    Emitted when a resumable checkpoint is discovered at session start.

    Args:
        phase: The checkpoint phase (e.g., "implementation_complete")
        checkpoint_at: ISO timestamp of when checkpoint was saved
        goal: The goal this checkpoint is for
    """
    return AgentEvent(
        EventType.CHECKPOINT_FOUND,
        {
            "phase": phase,
            "checkpoint_at": checkpoint_at,
            "goal": goal,
            **kwargs,
        },
    )


def checkpoint_saved_event(
    phase: str,
    summary: str,
    tasks_completed: int = 0,
    **kwargs: Any,
) -> AgentEvent:
    """Create a checkpoint saved event (RFC-130).

    Emitted when checkpoint is saved at phase boundary.

    Args:
        phase: The checkpoint phase
        summary: Human-readable summary of what was accomplished
        tasks_completed: Number of tasks completed so far
    """
    return AgentEvent(
        EventType.CHECKPOINT_SAVED,
        {
            "phase": phase,
            "summary": summary,
            "tasks_completed": tasks_completed,
            **kwargs,
        },
    )


def phase_complete_event(
    phase: str,
    duration_seconds: float,
    **kwargs: Any,
) -> AgentEvent:
    """Create a phase complete event (RFC-130).

    Emitted when agent completes a semantic phase.

    Args:
        phase: The completed phase (orient, exploration, design, etc.)
        duration_seconds: How long the phase took
    """
    return AgentEvent(
        EventType.PHASE_COMPLETE,
        {
            "phase": phase,
            "duration_seconds": duration_seconds,
            **kwargs,
        },
    )


def autonomous_action_blocked_event(
    action_type: str,
    path: str | None,
    reason: str,
    blocking_rule: str,
    risk_level: str,
    **kwargs: Any,
) -> AgentEvent:
    """Create an autonomous action blocked event (RFC-130).

    Emitted when an action fails guard check in autonomous mode.

    Args:
        action_type: Type of action (file_write, shell_exec, etc.)
        path: File path if applicable
        reason: Why the action was blocked
        blocking_rule: Which guardrail triggered the block
        risk_level: Risk classification (safe, moderate, dangerous, forbidden)
    """
    return AgentEvent(
        EventType.AUTONOMOUS_ACTION_BLOCKED,
        {
            "action_type": action_type,
            "path": path,
            "reason": reason,
            "blocking_rule": blocking_rule,
            "risk_level": risk_level,
            **kwargs,
        },
    )


def guard_evolution_suggested_event(
    guard_id: str,
    evolution_type: str,
    reason: str,
    confidence: float,
    **kwargs: Any,
) -> AgentEvent:
    """Create a guard evolution suggested event (RFC-130).

    Emitted when adaptive learning suggests guard improvement.

    Args:
        guard_id: ID of the guard to evolve
        evolution_type: Type of evolution (refine_pattern, add_exception, etc.)
        reason: Why this evolution is suggested
        confidence: Confidence in the suggestion (0.0-1.0)
    """
    return AgentEvent(
        EventType.GUARD_EVOLUTION_SUGGESTED,
        {
            "guard_id": guard_id,
            "evolution_type": evolution_type,
            "reason": reason,
            "confidence": confidence,
            **kwargs,
        },
    )
