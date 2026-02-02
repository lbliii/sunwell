"""Convergence event schemas."""

from typing import Any, TypedDict


class ConvergenceStartData(TypedDict, total=False):
    """Data for convergence_start event."""

    files: list[str]
    gates: list[str]
    max_iterations: int  # Required


class ConvergenceIterationStartData(TypedDict, total=False):
    """Data for convergence_iteration_start event."""

    iteration: int  # Required
    files: list[str]


class ConvergenceIterationCompleteData(TypedDict, total=False):
    """Data for convergence_iteration_complete event.

    Note: Factory provides total_errors, all_passed, gate_results.
    """

    iteration: int  # Required
    all_passed: bool
    total_errors: int
    gate_results: list[dict[str, Any]]


class ConvergenceFixingData(TypedDict, total=False):
    """Data for convergence_fixing event.

    Note: Factory provides error_count.
    """

    iteration: int  # Required
    error_count: int


class ConvergenceStableData(TypedDict, total=False):
    """Data for convergence_stable event."""

    iterations: int  # Required
    duration_ms: int


class ConvergenceTimeoutData(TypedDict, total=False):
    """Data for convergence_timeout event."""

    iterations: int


class ConvergenceStuckData(TypedDict, total=False):
    """Data for convergence_stuck event.

    Note: Factory provides repeated_errors (list).
    """

    iterations: int  # Required
    repeated_errors: list[str]


class ConvergenceMaxIterationsData(TypedDict, total=False):
    """Data for convergence_max_iterations event."""

    iterations: int


class ConvergenceBudgetExceededData(TypedDict, total=False):
    """Data for convergence_budget_exceeded event.

    Note: Factory provides tokens_used/max_tokens.
    """

    tokens_used: int
    max_tokens: int
