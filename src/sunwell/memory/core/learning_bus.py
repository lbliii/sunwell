"""LearningBus — In-process pub/sub for learning events.

Phase 2.1 of Unified Memory Coordination: Enables real-time learning
sharing between in-process agents (subagents, Naaru workers).

For cross-process coordination (multi-instance workers), see JournalWatcher.

Architecture:
    Worker A extracts learning → Journal.append() → LearningBus.publish()
                                                          ↓
    Worker B subscribes → callback receives learning → adds to LearningStore

Thread-safe for Python 3.14t free-threading.
"""

import logging
import threading
import weakref
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.agent.learning.learning import Learning

logger = logging.getLogger(__name__)


# Type alias for subscriber callbacks
LearningCallback = Callable[["Learning"], None]


@dataclass(slots=True)
class LearningBus:
    """In-process pub/sub for learning events (thread-safe).

    Subscribers receive learning events in real-time as they're published.
    Uses weak references to avoid memory leaks when subscribers are garbage collected.

    Usage:
        bus = LearningBus()

        # Subscribe
        def on_learning(learning: Learning) -> None:
            print(f"New learning: {learning.fact}")
        bus.subscribe(on_learning)

        # Publish
        bus.publish(learning)  # All subscribers notified

        # Unsubscribe (optional - weak refs auto-clean)
        bus.unsubscribe(on_learning)
    """

    _subscribers: list[LearningCallback] = field(default_factory=list, init=False)
    """List of subscriber callbacks."""

    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    """Lock for thread-safe mutations (3.14t compatible)."""

    _publish_count: int = field(default=0, init=False)
    """Count of learnings published (for metrics)."""

    _error_count: int = field(default=0, init=False)
    """Count of subscriber callback errors."""

    def publish(self, learning: Learning) -> int:
        """Publish a learning to all subscribers (thread-safe).

        Callbacks are invoked synchronously in the publishing thread.
        Errors in callbacks are caught and logged, not propagated.

        Args:
            learning: The learning to broadcast

        Returns:
            Number of subscribers notified
        """
        with self._lock:
            subscribers = list(self._subscribers)

        notified = 0
        for callback in subscribers:
            try:
                callback(learning)
                notified += 1
            except Exception as e:
                self._error_count += 1
                logger.warning(
                    "LearningBus subscriber error: %s (callback: %s)",
                    e,
                    getattr(callback, "__name__", str(callback)),
                )

        with self._lock:
            self._publish_count += 1

        return notified

    def subscribe(self, callback: LearningCallback) -> bool:
        """Subscribe to learning events (thread-safe).

        Args:
            callback: Function to call with each learning

        Returns:
            True if subscribed, False if already subscribed
        """
        with self._lock:
            if callback not in self._subscribers:
                self._subscribers.append(callback)
                return True
            return False

    def unsubscribe(self, callback: LearningCallback) -> bool:
        """Unsubscribe from learning events (thread-safe).

        Args:
            callback: The callback to remove

        Returns:
            True if removed, False if not found
        """
        with self._lock:
            try:
                self._subscribers.remove(callback)
                return True
            except ValueError:
                return False

    def subscriber_count(self) -> int:
        """Get current subscriber count (thread-safe)."""
        with self._lock:
            return len(self._subscribers)

    @property
    def stats(self) -> dict[str, int]:
        """Get bus statistics."""
        with self._lock:
            return {
                "subscribers": len(self._subscribers),
                "published": self._publish_count,
                "errors": self._error_count,
            }

    def clear(self) -> int:
        """Remove all subscribers (thread-safe).

        Returns:
            Number of subscribers removed
        """
        with self._lock:
            count = len(self._subscribers)
            self._subscribers.clear()
            return count


# =============================================================================
# Global Bus (Singleton Pattern)
# =============================================================================

# Module-level bus instance for process-wide sharing
_global_bus: LearningBus | None = None
_global_bus_lock = threading.Lock()


def get_learning_bus() -> LearningBus:
    """Get the global LearningBus instance.

    Creates the bus on first call. Thread-safe.

    Returns:
        The global LearningBus instance
    """
    global _global_bus

    if _global_bus is not None:
        return _global_bus

    with _global_bus_lock:
        # Double-check after acquiring lock
        if _global_bus is None:
            _global_bus = LearningBus()
        return _global_bus


def reset_learning_bus() -> None:
    """Reset the global bus (for testing).

    Clears all subscribers and resets statistics.
    """
    global _global_bus

    with _global_bus_lock:
        if _global_bus is not None:
            _global_bus.clear()
            _global_bus = None


# =============================================================================
# Integration Helpers
# =============================================================================


def create_learning_store_subscriber(learning_store: "LearningStore") -> LearningCallback:
    """Create a callback that adds learnings to a LearningStore.

    Args:
        learning_store: The store to add learnings to

    Returns:
        Callback function for bus subscription
    """
    def on_learning(learning: Learning) -> None:
        learning_store.add_learning(learning)

    return on_learning


def subscribe_learning_store(learning_store: "LearningStore", bus: LearningBus | None = None) -> LearningCallback:
    """Subscribe a LearningStore to receive learnings from a bus.

    Convenience function that creates the callback and subscribes it.

    Args:
        learning_store: The store to receive learnings
        bus: Optional specific bus (uses global if None)

    Returns:
        The callback (for later unsubscription)
    """
    if bus is None:
        bus = get_learning_bus()

    callback = create_learning_store_subscriber(learning_store)
    bus.subscribe(callback)
    return callback


# Import for type hints in create_learning_store_subscriber
if TYPE_CHECKING:
    from sunwell.agent.learning.store import LearningStore
