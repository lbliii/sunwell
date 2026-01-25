"""Convergence event schemas."""

from typing import TypedDict


class ConvergenceStartData(TypedDict, total=False):
    """Data for convergence_start event."""
    max_iterations: int  # Required


class ConvergenceIterationStartData(TypedDict, total=False):
    """Data for convergence_iteration_start event."""
    iteration: int  # Required


class ConvergenceIterationCompleteData(TypedDict, total=False):
    """Data for convergence_iteration_complete event."""
    iteration: int  # Required
    errors_found: int  # Required


class ConvergenceFixingData(TypedDict, total=False):
    """Data for convergence_fixing event."""
    iteration: int  # Required
    errors_to_fix: int  # Required


class ConvergenceStableData(TypedDict, total=False):
    """Data for convergence_stable event."""
    iterations: int  # Required


class ConvergenceTimeoutData(TypedDict, total=False):
    """Data for convergence_timeout event."""
    elapsed_ms: int  # Required


class ConvergenceStuckData(TypedDict, total=False):
    """Data for convergence_stuck event."""
    iterations: int  # Required
    persistent_errors: int  # Required


class ConvergenceMaxIterationsData(TypedDict, total=False):
    """Data for convergence_max_iterations event."""
    max_iterations: int  # Required


class ConvergenceBudgetExceededData(TypedDict, total=False):
    """Data for convergence_budget_exceeded event."""
    budget_ms: int  # Required
    elapsed_ms: int  # Required
