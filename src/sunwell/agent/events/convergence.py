"""Convergence event factories (RFC-123).

Event factories for convergence loop lifecycle:
- convergence_start_event: Starting convergence loop
- convergence_iteration_start_event, convergence_iteration_complete_event
- convergence_fixing_event: Agent fixing errors
- convergence_stable_event: All gates pass
- convergence_timeout_event, convergence_stuck_event
- convergence_max_iterations_event, convergence_budget_exceeded_event
"""

from typing import Any

from sunwell.agent.events.types import AgentEvent, EventType


def convergence_start_event(
    files: list[str],
    gates: list[str],
    max_iterations: int,
    **kwargs: Any,
) -> AgentEvent:
    """Create a convergence start event (RFC-123).

    Emitted when starting convergence loop.

    Args:
        files: Files to validate
        gates: Gate types enabled (e.g., ["lint", "type"])
        max_iterations: Maximum iterations allowed
    """
    return AgentEvent(
        EventType.CONVERGENCE_START,
        {
            "files": files,
            "gates": gates,
            "max_iterations": max_iterations,
            **kwargs,
        },
    )


def convergence_iteration_start_event(
    iteration: int,
    files: list[str],
    **kwargs: Any,
) -> AgentEvent:
    """Create a convergence iteration start event (RFC-123).

    Args:
        iteration: Iteration number (1-based)
        files: Files being validated
    """
    return AgentEvent(
        EventType.CONVERGENCE_ITERATION_START,
        {
            "iteration": iteration,
            "files": files,
            **kwargs,
        },
    )


def convergence_iteration_complete_event(
    iteration: int,
    all_passed: bool,
    total_errors: int,
    gate_results: list[dict[str, Any]],
    **kwargs: Any,
) -> AgentEvent:
    """Create a convergence iteration complete event (RFC-123).

    Args:
        iteration: Iteration number
        all_passed: Whether all gates passed
        total_errors: Total error count
        gate_results: List of gate results with gate, passed, errors
    """
    return AgentEvent(
        EventType.CONVERGENCE_ITERATION_COMPLETE,
        {
            "iteration": iteration,
            "all_passed": all_passed,
            "total_errors": total_errors,
            "gate_results": gate_results,
            **kwargs,
        },
    )


def convergence_fixing_event(
    iteration: int,
    error_count: int,
    **kwargs: Any,
) -> AgentEvent:
    """Create a convergence fixing event (RFC-123).

    Emitted when agent starts fixing errors.

    Args:
        iteration: Current iteration
        error_count: Number of errors to fix
    """
    return AgentEvent(
        EventType.CONVERGENCE_FIXING,
        {
            "iteration": iteration,
            "error_count": error_count,
            **kwargs,
        },
    )


def convergence_stable_event(
    iterations: int,
    duration_ms: int,
    **kwargs: Any,
) -> AgentEvent:
    """Create a convergence stable event (RFC-123).

    Emitted when all gates pass — code is stable.

    Args:
        iterations: Total iterations taken
        duration_ms: Total time in milliseconds
    """
    return AgentEvent(
        EventType.CONVERGENCE_STABLE,
        {
            "iterations": iterations,
            "duration_ms": duration_ms,
            **kwargs,
        },
    )


def convergence_timeout_event(
    iterations: int,
    **kwargs: Any,
) -> AgentEvent:
    """Create a convergence timeout event (RFC-123).

    Args:
        iterations: Iterations completed before timeout
    """
    return AgentEvent(
        EventType.CONVERGENCE_TIMEOUT,
        {
            "iterations": iterations,
            **kwargs,
        },
    )


def convergence_stuck_event(
    iterations: int,
    repeated_errors: list[str],
    **kwargs: Any,
) -> AgentEvent:
    """Create a convergence stuck event (RFC-123).

    Emitted when the same error keeps recurring.

    Args:
        iterations: Iterations completed
        repeated_errors: Errors that kept repeating
    """
    return AgentEvent(
        EventType.CONVERGENCE_STUCK,
        {
            "iterations": iterations,
            "repeated_errors": repeated_errors,
            **kwargs,
        },
    )


def convergence_max_iterations_event(
    iterations: int,
    **kwargs: Any,
) -> AgentEvent:
    """Create a convergence max iterations event (RFC-123).

    Args:
        iterations: Max iterations reached
    """
    return AgentEvent(
        EventType.CONVERGENCE_MAX_ITERATIONS,
        {
            "iterations": iterations,
            **kwargs,
        },
    )


def convergence_budget_exceeded_event(
    tokens_used: int,
    max_tokens: int,
    **kwargs: Any,
) -> AgentEvent:
    """Create a convergence budget exceeded event (RFC-123).

    Args:
        tokens_used: Tokens consumed
        max_tokens: Token budget limit
    """
    return AgentEvent(
        EventType.CONVERGENCE_BUDGET_EXCEEDED,
        {
            "tokens_used": tokens_used,
            "max_tokens": max_tokens,
            **kwargs,
        },
    )
