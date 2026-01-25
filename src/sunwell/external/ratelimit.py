"""Rate Limiting for External Integration (RFC-049).

Sliding window rate limiter with per-source buckets.
"""

import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sunwell.external.policy import ExternalGoalPolicy
from sunwell.external.types import ExternalEvent


@dataclass(slots=True)
class RateLimitBucket:
    """Sliding window rate limit bucket."""

    window_seconds: int = 3600  # 1 hour
    max_events: int = 50
    events: deque[datetime] = field(default_factory=deque)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def allow(self) -> bool:
        """Check if event is allowed under rate limit.

        Returns:
            True if event is allowed, False if rate limited
        """
        now = datetime.now()
        window_start = now - timedelta(seconds=self.window_seconds)

        with self._lock:
            # Remove events outside window
            while self.events and self.events[0] < window_start:
                self.events.popleft()

            # Check limit
            if len(self.events) >= self.max_events:
                return False

            # Record event
            self.events.append(now)
            return True

    @property
    def remaining(self) -> int:
        """Events remaining in current window."""
        now = datetime.now()
        window_start = now - timedelta(seconds=self.window_seconds)

        with self._lock:
            while self.events and self.events[0] < window_start:
                self.events.popleft()
            return max(0, self.max_events - len(self.events))


class RateLimiter:
    """Per-source rate limiter with multiple limit types."""

    def __init__(self, policy: ExternalGoalPolicy):
        """Initialize rate limiter.

        Args:
            policy: External goal policy with rate limit settings
        """
        self.policy = policy
        self._buckets: dict[str, RateLimitBucket] = {}
        self._daily_count: dict[str, int] = {}  # date → count
        self._cooldowns: dict[str, datetime] = {}  # external_ref → last_goal_time
        self._lock = threading.Lock()

    def allow(self, event: ExternalEvent) -> tuple[bool, str]:
        """Check if event is allowed.

        Args:
            event: The external event to check

        Returns:
            Tuple of (allowed, reason) — reason explains why blocked
        """
        # 1. Per-source hourly limit
        bucket_key = event.source.value
        with self._lock:
            if bucket_key not in self._buckets:
                self._buckets[bucket_key] = RateLimitBucket(
                    max_events=self.policy.max_events_per_hour
                )
        bucket = self._buckets[bucket_key]

        if not bucket.allow():
            return False, f"Rate limited: {event.source.value} ({bucket.remaining} remaining)"

        # 2. Daily goal limit
        today = datetime.now().date().isoformat()
        with self._lock:
            daily = self._daily_count.get(today, 0)
        if daily >= self.policy.max_goals_per_day:
            return False, f"Daily limit reached: {daily}/{self.policy.max_goals_per_day}"

        # 3. Cooldown per external ref
        if event.external_ref:
            with self._lock:
                last_time = self._cooldowns.get(event.external_ref)
            if last_time:
                elapsed = (datetime.now() - last_time).total_seconds() / 60
                if elapsed < self.policy.cooldown_minutes:
                    remaining = self.policy.cooldown_minutes - elapsed
                    return False, f"Cooldown: {event.external_ref} ({remaining:.1f}m remaining)"

        return True, "allowed"

    def record_goal_created(self, event: ExternalEvent) -> None:
        """Record that a goal was created (for daily limit and cooldown).

        Args:
            event: The event that triggered the goal
        """
        today = datetime.now().date().isoformat()

        with self._lock:
            self._daily_count[today] = self._daily_count.get(today, 0) + 1

            if event.external_ref:
                self._cooldowns[event.external_ref] = datetime.now()

    def reset_daily(self) -> None:
        """Reset daily counters. Called at midnight."""
        today = datetime.now().date().isoformat()
        with self._lock:
            # Keep only today's count
            self._daily_count = {k: v for k, v in self._daily_count.items() if k == today}

    def get_stats(self) -> dict:
        """Get current rate limit statistics.

        Returns:
            Dictionary with rate limit stats
        """
        today = datetime.now().date().isoformat()

        with self._lock:
            return {
                "daily_goals": self._daily_count.get(today, 0),
                "daily_limit": self.policy.max_goals_per_day,
                "buckets": {
                    source: bucket.remaining
                    for source, bucket in self._buckets.items()
                },
                "active_cooldowns": len(self._cooldowns),
            }
