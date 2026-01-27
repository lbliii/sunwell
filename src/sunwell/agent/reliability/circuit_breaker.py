"""Circuit breaker pattern for preventing runaway failures.

Stops agent execution after a configurable number of consecutive failures,
preventing endless retry loops that waste resources.

States:
- CLOSED: Normal operation, failures are counted
- OPEN: Circuit tripped, execution blocked
- HALF_OPEN: Testing recovery with limited calls

Example:
    >>> breaker = CircuitBreaker(failure_threshold=5)
    >>> if breaker.can_execute():
    ...     try:
    ...         result = do_work()
    ...         breaker.record_success()
    ...     except Exception:
    ...         if breaker.record_failure():
    ...             print("Circuit opened, stopping execution")
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CircuitState(Enum):
    """Circuit breaker state."""

    CLOSED = "closed"
    """Normal operation - failures are counted."""

    OPEN = "open"
    """Circuit tripped - execution blocked."""

    HALF_OPEN = "half_open"
    """Testing recovery - limited calls allowed."""


@dataclass
class CircuitBreaker:
    """Prevents runaway failures by stopping after threshold.

    Implements the circuit breaker pattern with three states:
    - CLOSED: Normal operation, track failures
    - OPEN: Failing, reject calls until recovery timeout
    - HALF_OPEN: Allow single test call to check recovery

    Attributes:
        failure_threshold: Consecutive failures before opening (default 5)
        recovery_timeout_seconds: Time before attempting recovery (default 60)
        half_open_max_calls: Calls allowed in half-open state (default 1)
    """

    failure_threshold: int = 5
    """Number of consecutive failures before opening circuit."""

    recovery_timeout_seconds: float = 60.0
    """Seconds to wait before attempting recovery."""

    half_open_max_calls: int = 1
    """Maximum calls allowed in half-open state."""

    # Private state (not in __init__)
    _consecutive_failures: int = field(default=0, init=False)
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _last_failure_time: float = field(default=0.0, init=False)
    _half_open_calls: int = field(default=0, init=False)
    _total_failures: int = field(default=0, init=False)
    _total_successes: int = field(default=0, init=False)
    _times_opened: int = field(default=0, init=False)

    @property
    def state(self) -> CircuitState:
        """Current circuit state."""
        return self._state

    @property
    def consecutive_failures(self) -> int:
        """Current consecutive failure count."""
        return self._consecutive_failures

    @property
    def is_open(self) -> bool:
        """Whether circuit is currently open (blocking execution)."""
        return self._state == CircuitState.OPEN

    def record_success(self) -> None:
        """Record successful execution.

        Resets consecutive failure count. If in HALF_OPEN state,
        transitions back to CLOSED.
        """
        self._consecutive_failures = 0
        self._total_successes += 1

        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.CLOSED
            self._half_open_calls = 0

    def record_failure(self) -> bool:
        """Record failed execution.

        Returns:
            True if circuit should open (threshold reached), False otherwise.
        """
        self._consecutive_failures += 1
        self._total_failures += 1
        self._last_failure_time = time.time()

        if self._consecutive_failures >= self.failure_threshold:
            if self._state != CircuitState.OPEN:
                self._state = CircuitState.OPEN
                self._times_opened += 1
            return True
        return False

    def can_execute(self) -> bool:
        """Check if execution is allowed.

        Returns:
            True if execution should proceed, False if blocked.
        """
        if self._state == CircuitState.CLOSED:
            return True

        if self._state == CircuitState.OPEN:
            # Check if recovery timeout elapsed
            elapsed = time.time() - self._last_failure_time
            if elapsed >= self.recovery_timeout_seconds:
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
                return True
            return False

        if self._state == CircuitState.HALF_OPEN:
            if self._half_open_calls < self.half_open_max_calls:
                self._half_open_calls += 1
                return True
            return False

        return False

    def reset(self) -> None:
        """Reset circuit breaker to initial state.

        Use when starting a new session or after manual intervention.
        """
        self._consecutive_failures = 0
        self._state = CircuitState.CLOSED
        self._last_failure_time = 0.0
        self._half_open_calls = 0

    def to_dict(self) -> dict[str, Any]:
        """Export state for events/logging.

        Returns:
            Dictionary with current state and statistics.
        """
        return {
            "state": self._state.value,
            "consecutive_failures": self._consecutive_failures,
            "failure_threshold": self.failure_threshold,
            "total_failures": self._total_failures,
            "total_successes": self._total_successes,
            "times_opened": self._times_opened,
            "recovery_timeout_seconds": self.recovery_timeout_seconds,
        }

    def __repr__(self) -> str:
        return (
            f"CircuitBreaker(state={self._state.value}, "
            f"failures={self._consecutive_failures}/{self.failure_threshold})"
        )
