"""Exponential backoff with jitter for retry resilience.

Prevents thundering herd on retries by adding randomized delays.
Based on patterns from Moltbot infra/backoff.ts.

Example:
    >>> policy = BackoffPolicy(initial_ms=500, max_ms=10_000, factor=2.0, jitter=0.25)
    >>> delay = compute_backoff(policy, attempt=3)  # ~2000ms + jitter
    >>> await sleep_with_backoff(policy, attempt=3)

Formula: base = initial * factor^(attempt-1), then add random jitter
"""

import asyncio
import random
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BackoffPolicy:
    """Configuration for exponential backoff with jitter.

    Attributes:
        initial_ms: Initial delay in milliseconds (default 300)
        max_ms: Maximum delay cap in milliseconds (default 30,000)
        factor: Multiplier for each attempt (default 2.0)
        jitter: Random jitter as ratio of base delay (default 0.25)
    """

    initial_ms: int = 300
    """Initial delay in milliseconds."""

    max_ms: int = 30_000
    """Maximum delay cap in milliseconds."""

    factor: float = 2.0
    """Multiplier for exponential growth."""

    jitter: float = 0.25
    """Random jitter as ratio of base delay (0.0-1.0)."""

    def __post_init__(self) -> None:
        """Validate policy parameters."""
        if self.initial_ms <= 0:
            raise ValueError("initial_ms must be positive")
        if self.max_ms < self.initial_ms:
            raise ValueError("max_ms must be >= initial_ms")
        if self.factor < 1.0:
            raise ValueError("factor must be >= 1.0")
        if not 0.0 <= self.jitter <= 1.0:
            raise ValueError("jitter must be between 0.0 and 1.0")


# Common backoff policies
DEFAULT_RETRY_BACKOFF = BackoffPolicy(
    initial_ms=500,
    max_ms=10_000,
    factor=2.0,
    jitter=0.25,
)
"""Default policy for tool retries: 500ms -> 1s -> 2s -> 4s -> 8s (capped at 10s)."""

AGGRESSIVE_BACKOFF = BackoffPolicy(
    initial_ms=100,
    max_ms=5_000,
    factor=2.0,
    jitter=0.3,
)
"""Aggressive policy for fast retries: 100ms -> 200ms -> 400ms (capped at 5s)."""

CONSERVATIVE_BACKOFF = BackoffPolicy(
    initial_ms=1_000,
    max_ms=60_000,
    factor=2.0,
    jitter=0.2,
)
"""Conservative policy for rate-limited APIs: 1s -> 2s -> 4s (capped at 60s)."""


def compute_backoff(policy: BackoffPolicy, attempt: int) -> int:
    """Compute backoff delay in milliseconds.

    Formula: base = initial * factor^(attempt-1), then add random jitter

    Args:
        policy: Backoff policy configuration
        attempt: Attempt number (1-indexed, first attempt = 1)

    Returns:
        Delay in milliseconds, capped at policy.max_ms
    """
    # Calculate base delay
    exponent = max(attempt - 1, 0)
    base = policy.initial_ms * (policy.factor ** exponent)

    # Add jitter (random portion of base)
    jitter_amount = base * policy.jitter * random.random()
    delay = base + jitter_amount

    # Cap at maximum
    return min(policy.max_ms, int(delay))


async def sleep_with_backoff(
    policy: BackoffPolicy,
    attempt: int,
    abort_event: asyncio.Event | None = None,
) -> bool:
    """Sleep with exponential backoff, supporting early abort.

    Args:
        policy: Backoff policy configuration
        attempt: Attempt number (1-indexed)
        abort_event: Optional event to signal early abort

    Returns:
        True if sleep completed normally, False if aborted
    """
    delay_ms = compute_backoff(policy, attempt)
    delay_s = delay_ms / 1000

    if abort_event:
        try:
            # Wait for abort or timeout
            await asyncio.wait_for(abort_event.wait(), timeout=delay_s)
            return False  # Aborted
        except asyncio.TimeoutError:
            return True  # Normal completion
    else:
        await asyncio.sleep(delay_s)
        return True


def compute_backoff_sequence(policy: BackoffPolicy, max_attempts: int) -> list[int]:
    """Compute the full sequence of backoff delays.

    Useful for logging or displaying expected retry behavior.

    Args:
        policy: Backoff policy configuration
        max_attempts: Number of attempts to compute

    Returns:
        List of delays in milliseconds (without jitter)
    """
    delays = []
    for attempt in range(1, max_attempts + 1):
        # Compute without jitter for deterministic preview
        exponent = attempt - 1
        base = policy.initial_ms * (policy.factor ** exponent)
        delays.append(min(policy.max_ms, int(base)))
    return delays
