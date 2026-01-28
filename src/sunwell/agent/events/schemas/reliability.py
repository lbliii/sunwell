"""Reliability event schemas (Solo Dev Hardening).

These schemas define the structure for reliability-related events that help
detect and respond to execution failures, budget exhaustion, and health issues.
"""

from typing import TypedDict


class ReliabilityWarningData(TypedDict, total=False):
    """Data for reliability_warning event.

    Emitted when a reliability concern is detected but execution continues.
    """

    warning: str  # Required: Warning message
    context: str


class ReliabilityHallucinationData(TypedDict, total=False):
    """Data for reliability_hallucination event.

    Emitted when the model appears to hallucinate tool usage or capabilities.
    """

    detected_pattern: str  # Required: What was detected
    evidence: str
    severity: str  # "low" | "medium" | "high"


class CircuitBreakerOpenData(TypedDict, total=False):
    """Data for circuit_breaker_open event.

    Emitted when consecutive failures exceed threshold, stopping execution.
    """

    state: str  # Required: Current state
    consecutive_failures: int  # Required
    failure_threshold: int  # Required


class BudgetExhaustedData(TypedDict, total=False):
    """Data for budget_exhausted event.

    Emitted when token budget is fully consumed, stopping execution.
    """

    spent: int  # Required
    budget: int  # Required
    percentage_used: float


class BudgetWarningData(TypedDict, total=False):
    """Data for budget_warning event.

    Emitted when token budget is running low (below warning threshold).
    """

    remaining: int  # Required
    percentage_remaining: float


class HealthCheckFailedData(TypedDict, total=False):
    """Data for health_check_failed event.

    Emitted when pre-flight health check fails, blocking autonomous execution.
    """

    errors: list[str]  # Required
    error_count: int


class HealthWarningData(TypedDict, total=False):
    """Data for health_warning event.

    Emitted when health check passes but with warnings.
    """

    warnings: list[str]  # Required
    warning_count: int


class TimeoutData(TypedDict, total=False):
    """Data for timeout event.

    Emitted when an operation exceeds its allowed time.
    """

    operation: str  # Required: What timed out
    timeout_seconds: float
    elapsed_seconds: float
