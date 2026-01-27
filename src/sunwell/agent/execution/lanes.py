"""Execution lanes for workload isolation.

Provides lane-aware execution queues with independent concurrency limits.
Prevents resource starvation between different workload types (main agent,
subagents, background tasks).

Inspired by moltbot's command-queue.ts but adapted for Python async patterns
and free-threading awareness (Python 3.14t).
"""

import asyncio
import logging
import threading
import time
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from sunwell.agent.loop.config import DEFAULT_LANE_CONCURRENCY, ExecutionLane

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class QueueEntry:
    """An entry in the execution queue."""

    task: Callable[[], Awaitable[Any]]
    """The async task to execute."""

    future: asyncio.Future[Any]
    """Future to resolve with the result."""

    enqueued_at: float
    """Timestamp when the entry was enqueued."""

    warn_after_seconds: float = 5.0
    """Emit warning if waiting longer than this."""

    label: str | None = None
    """Optional label for debugging."""


@dataclass
class LaneState:
    """State for a single execution lane."""

    lane: ExecutionLane
    """Which lane this is."""

    queue: deque[QueueEntry] = field(default_factory=deque)
    """Pending tasks waiting to execute."""

    active: int = 0
    """Number of currently executing tasks."""

    max_concurrent: int = 1
    """Maximum concurrent tasks for this lane."""

    draining: bool = False
    """Whether the drain loop is currently running."""

    @property
    def pending(self) -> int:
        """Number of tasks waiting in queue."""
        return len(self.queue)

    @property
    def total(self) -> int:
        """Total tasks (active + pending)."""
        return self.active + self.pending


class ExecutionLanes:
    """Lane-aware execution queue with independent concurrency limits.

    Thread-safe implementation supporting Python 3.14t free-threading.

    Usage:
        lanes = ExecutionLanes()

        # Enqueue work in the main lane
        result = await lanes.enqueue(
            ExecutionLane.MAIN,
            lambda: some_async_work(),
            label="process_request",
        )

        # Enqueue background work
        await lanes.enqueue(
            ExecutionLane.BACKGROUND,
            lambda: extract_learnings(),
        )

        # Check queue status
        size = lanes.get_queue_size(ExecutionLane.MAIN)
    """

    def __init__(
        self,
        concurrency: dict[str, int] | None = None,
    ) -> None:
        """Initialize execution lanes.

        Args:
            concurrency: Optional concurrency overrides per lane.
                If None, uses DEFAULT_LANE_CONCURRENCY.
        """
        self._lock = threading.Lock()
        self._lanes: dict[ExecutionLane, LaneState] = {}
        self._concurrency = concurrency or DEFAULT_LANE_CONCURRENCY

    def _get_lane_state(self, lane: ExecutionLane) -> LaneState:
        """Get or create state for a lane (must hold lock)."""
        if lane not in self._lanes:
            max_concurrent = self._concurrency.get(lane.value, 1)
            self._lanes[lane] = LaneState(
                lane=lane,
                max_concurrent=max_concurrent,
            )
        return self._lanes[lane]

    def set_concurrency(self, lane: ExecutionLane, max_concurrent: int) -> None:
        """Set concurrency limit for a lane.

        Args:
            lane: The execution lane
            max_concurrent: Maximum concurrent tasks (minimum 1)
        """
        with self._lock:
            state = self._get_lane_state(lane)
            state.max_concurrent = max(1, max_concurrent)
            self._concurrency[lane.value] = state.max_concurrent

    def get_queue_size(self, lane: ExecutionLane | None = None) -> int:
        """Get total queue size (active + pending).

        Args:
            lane: Specific lane, or None for all lanes

        Returns:
            Total tasks in queue
        """
        with self._lock:
            if lane is not None:
                if lane not in self._lanes:
                    return 0
                return self._lanes[lane].total
            return sum(state.total for state in self._lanes.values())

    def get_active_count(self, lane: ExecutionLane | None = None) -> int:
        """Get count of actively executing tasks.

        Args:
            lane: Specific lane, or None for all lanes

        Returns:
            Number of active tasks
        """
        with self._lock:
            if lane is not None:
                if lane not in self._lanes:
                    return 0
                return self._lanes[lane].active
            return sum(state.active for state in self._lanes.values())

    def get_pending_count(self, lane: ExecutionLane | None = None) -> int:
        """Get count of pending (queued) tasks.

        Args:
            lane: Specific lane, or None for all lanes

        Returns:
            Number of pending tasks
        """
        with self._lock:
            if lane is not None:
                if lane not in self._lanes:
                    return 0
                return self._lanes[lane].pending
            return sum(state.pending for state in self._lanes.values())

    async def enqueue(
        self,
        lane: ExecutionLane,
        task: Callable[[], Awaitable[T]],
        label: str | None = None,
        warn_after_seconds: float = 5.0,
    ) -> T:
        """Enqueue a task for execution in a lane.

        The task will execute when:
        1. A slot is available (active < max_concurrent)
        2. It reaches the front of the queue

        Args:
            lane: Which lane to execute in
            task: Async callable to execute
            label: Optional label for debugging
            warn_after_seconds: Emit warning if waiting longer than this

        Returns:
            Result of the task

        Raises:
            Exception: Any exception raised by the task
        """
        loop = asyncio.get_running_loop()
        future: asyncio.Future[T] = loop.create_future()

        entry = QueueEntry(
            task=task,
            future=future,
            enqueued_at=time.time(),
            warn_after_seconds=warn_after_seconds,
            label=label,
        )

        with self._lock:
            state = self._get_lane_state(lane)
            state.queue.append(entry)
            logger.debug(
                "Enqueued task in lane %s: pending=%d active=%d label=%s",
                lane.value,
                state.pending,
                state.active,
                label,
            )

        # Start draining if not already running
        self._maybe_drain(lane)

        return await future

    def _maybe_drain(self, lane: ExecutionLane) -> None:
        """Start draining the lane if not already draining."""
        with self._lock:
            state = self._get_lane_state(lane)
            if state.draining:
                return
            state.draining = True

        # Schedule drain in the event loop
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._drain_loop(lane))
        except RuntimeError:
            # No event loop running - will be drained on next enqueue
            with self._lock:
                state = self._get_lane_state(lane)
                state.draining = False

    async def _drain_loop(self, lane: ExecutionLane) -> None:
        """Continuously drain the queue for a lane."""
        while True:
            entry: QueueEntry | None = None

            with self._lock:
                state = self._get_lane_state(lane)

                # Check if we can execute more
                if state.active >= state.max_concurrent or not state.queue:
                    state.draining = False
                    return

                entry = state.queue.popleft()
                state.active += 1

                # Check for long waits
                waited_seconds = time.time() - entry.enqueued_at
                if waited_seconds >= entry.warn_after_seconds:
                    logger.warning(
                        "Lane %s: task waited %.1fs in queue (pending=%d)",
                        lane.value,
                        waited_seconds,
                        state.pending,
                    )

            # Execute outside lock
            if entry is not None:
                await self._execute_entry(lane, entry)

    async def _execute_entry(self, lane: ExecutionLane, entry: QueueEntry) -> None:
        """Execute a single queue entry."""
        start_time = time.time()
        try:
            result = await entry.task()
            entry.future.set_result(result)

            duration_ms = (time.time() - start_time) * 1000
            logger.debug(
                "Lane %s: task completed in %.0fms label=%s",
                lane.value,
                duration_ms,
                entry.label,
            )
        except Exception as e:
            entry.future.set_exception(e)

            duration_ms = (time.time() - start_time) * 1000
            logger.debug(
                "Lane %s: task failed after %.0fms label=%s error=%s",
                lane.value,
                duration_ms,
                entry.label,
                str(e),
            )
        finally:
            with self._lock:
                state = self._get_lane_state(lane)
                state.active -= 1

            # Continue draining
            self._maybe_drain(lane)

    def clear(self, lane: ExecutionLane | None = None) -> int:
        """Clear pending tasks from queue(s).

        Does not cancel active tasks.

        Args:
            lane: Specific lane, or None for all lanes

        Returns:
            Number of tasks removed
        """
        removed = 0
        with self._lock:
            if lane is not None:
                if lane in self._lanes:
                    state = self._lanes[lane]
                    removed = len(state.queue)
                    # Cancel all pending futures
                    for entry in state.queue:
                        entry.future.cancel()
                    state.queue.clear()
            else:
                for state in self._lanes.values():
                    removed += len(state.queue)
                    for entry in state.queue:
                        entry.future.cancel()
                    state.queue.clear()
        return removed

    def get_stats(self) -> dict[str, dict[str, int]]:
        """Get statistics for all lanes.

        Returns:
            Dict mapping lane name to stats dict
        """
        with self._lock:
            return {
                lane.value: {
                    "active": state.active,
                    "pending": state.pending,
                    "max_concurrent": state.max_concurrent,
                }
                for lane, state in self._lanes.items()
            }


# =============================================================================
# Global Instance
# =============================================================================

_global_lanes: ExecutionLanes | None = None
_global_lanes_lock = threading.Lock()


def get_lanes() -> ExecutionLanes:
    """Get the global ExecutionLanes instance.

    Lazily initialized on first access. Thread-safe.
    """
    global _global_lanes
    if _global_lanes is None:
        with _global_lanes_lock:
            if _global_lanes is None:
                _global_lanes = ExecutionLanes()
    return _global_lanes


def reset_lanes_for_tests() -> None:
    """Reset the global lanes instance (for testing only)."""
    global _global_lanes
    with _global_lanes_lock:
        if _global_lanes is not None:
            _global_lanes.clear()
        _global_lanes = None
