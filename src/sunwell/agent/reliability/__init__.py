"""Reliability primitives for solo dev agent safety (RFC-xxx).

This module provides mechanisms to prevent runaway agent behavior:
- Circuit breaker: Stop after consecutive failures
- Backoff: Exponential backoff with jitter for retries
- Health check: Pre-flight validation before autonomous runs
- Cost tracker: Session cost aggregation
- Intervention: Detect when human intervention is needed

Philosophy: Graceful degradation > hard failure
"""

from sunwell.agent.reliability.backoff import (
    BackoffPolicy,
    compute_backoff,
    sleep_with_backoff,
)
from sunwell.agent.reliability.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
)
from sunwell.agent.reliability.cost_tracker import (
    CostEntry,
    ModelCost,
    MODEL_COSTS,
    SessionCostTracker,
)
from sunwell.agent.reliability.health import (
    check_health,
    HealthStatus,
)
from sunwell.agent.reliability.intervention import (
    InterventionDetector,
    InterventionReason,
    InterventionSignal,
)

__all__ = [
    # Circuit breaker
    "CircuitBreaker",
    "CircuitState",
    # Backoff
    "BackoffPolicy",
    "compute_backoff",
    "sleep_with_backoff",
    # Health
    "HealthStatus",
    "check_health",
    # Cost
    "ModelCost",
    "MODEL_COSTS",
    "CostEntry",
    "SessionCostTracker",
    # Intervention
    "InterventionReason",
    "InterventionSignal",
    "InterventionDetector",
]
