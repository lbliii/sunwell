"""JournalWatcher — Cross-process journal monitoring.

Phase 2.3 of Unified Memory Coordination: Enables multi-instance workers
(separate processes) to detect when other workers have added learnings
to the journal.

Unlike LearningBus (in-process), JournalWatcher works across process
boundaries by monitoring the journal file for changes.

Architecture:
    Worker A appends to journal → file size changes
                                        ↓
    Worker B's JournalWatcher → detects size change → loads new entries
                                        ↓
    Worker B's callback receives learnings → adds to LearningStore

Thread-safe for Python 3.14t free-threading.
"""

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.memory.core.journal import LearningJournal

if TYPE_CHECKING:
    from sunwell.agent.learning.learning import Learning

logger = logging.getLogger(__name__)

# Type alias for watcher callbacks
LearningCallback = Callable[["Learning"], None]


@dataclass(slots=True)
class JournalWatcher:
    """Watch journal for new entries from other processes.

    Uses file size comparison to detect changes efficiently.
    When the journal grows, reads only the new entries.

    Usage:
        journal = LearningJournal(memory_dir)
        watcher = JournalWatcher(journal, on_learning)

        # Periodic polling
        while running:
            new_count = watcher.check_for_updates()
            if new_count > 0:
                print(f"Received {new_count} new learnings")
            time.sleep(1)  # Poll interval
    """

    journal: LearningJournal
    """The journal to watch."""

    callback: LearningCallback
    """Callback to invoke for each new learning."""

    _last_position: int = field(default=0, init=False)
    """Last read position in bytes."""

    _last_entry_count: int = field(default=0, init=False)
    """Last known entry count (for deduplication)."""

    _seen_ids: set[str] = field(default_factory=set, init=False)
    """IDs of learnings we've already processed."""

    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    """Lock for thread-safe state updates."""

    _total_received: int = field(default=0, init=False)
    """Total learnings received via watching."""

    def __post_init__(self) -> None:
        """Initialize position to current journal size."""
        if self.journal.exists():
            self._last_position = self.journal.size_bytes()
            # Load existing IDs to avoid reprocessing
            existing = self.journal.load_deduplicated()
            self._seen_ids = set(existing.keys())
            self._last_entry_count = len(existing)

    def check_for_updates(self) -> int:
        """Check for new entries since last check.

        Compares current journal size to last known position.
        If larger, reads and processes new entries.

        Returns:
            Number of new learnings processed
        """
        if not self.journal.exists():
            return 0

        current_size = self.journal.size_bytes()

        with self._lock:
            if current_size <= self._last_position:
                return 0

            # Journal has grown - read new entries
            new_count = self._process_new_entries()
            self._last_position = current_size
            return new_count

    def _process_new_entries(self) -> int:
        """Read and process new entries from journal.

        Uses ID tracking to avoid duplicate processing.

        Returns:
            Number of new learnings processed
        """
        # Load all entries and filter to new ones
        all_entries = self.journal.load_deduplicated()
        processed = 0

        for entry_id, entry in all_entries.items():
            if entry_id not in self._seen_ids:
                self._seen_ids.add(entry_id)

                # Convert to Learning and invoke callback
                try:
                    learning = entry.to_learning()
                    self.callback(learning)
                    processed += 1
                    self._total_received += 1
                except Exception as e:
                    logger.warning(
                        "JournalWatcher callback error for %s: %s",
                        entry_id,
                        e,
                    )

        self._last_entry_count = len(all_entries)
        return processed

    def force_refresh(self) -> int:
        """Force a full refresh from the journal.

        Resets position to 0 and reprocesses all entries.
        Useful after recovery or when state may be stale.

        Returns:
            Number of learnings processed
        """
        with self._lock:
            self._last_position = 0
            self._seen_ids.clear()
            return self._process_new_entries()

    @property
    def stats(self) -> dict[str, int]:
        """Get watcher statistics."""
        with self._lock:
            return {
                "last_position": self._last_position,
                "seen_ids": len(self._seen_ids),
                "total_received": self._total_received,
            }


# =============================================================================
# Polling Watcher (Background Thread)
# =============================================================================


@dataclass(slots=True)
class PollingJournalWatcher:
    """JournalWatcher with automatic background polling.

    Runs a background thread that periodically checks for updates.

    Usage:
        watcher = PollingJournalWatcher(journal, on_learning, poll_interval=1.0)
        watcher.start()
        # ... later ...
        watcher.stop()
    """

    journal: LearningJournal
    """The journal to watch."""

    callback: LearningCallback
    """Callback to invoke for each new learning."""

    poll_interval: float = 1.0
    """Seconds between polls."""

    _watcher: JournalWatcher | None = field(default=None, init=False)
    """The underlying watcher."""

    _thread: threading.Thread | None = field(default=None, init=False)
    """Background polling thread."""

    _running: bool = field(default=False, init=False)
    """Whether polling is active."""

    _stop_event: threading.Event = field(default_factory=threading.Event, init=False)
    """Event to signal thread shutdown."""

    def start(self) -> None:
        """Start background polling."""
        if self._running:
            return

        self._watcher = JournalWatcher(self.journal, self.callback)
        self._running = True
        self._stop_event.clear()

        self._thread = threading.Thread(
            target=self._poll_loop,
            daemon=True,
            name="JournalWatcher",
        )
        self._thread.start()
        logger.debug("PollingJournalWatcher started (interval: %.1fs)", self.poll_interval)

    def stop(self, timeout: float = 5.0) -> None:
        """Stop background polling.

        Args:
            timeout: Seconds to wait for thread to stop
        """
        if not self._running:
            return

        self._running = False
        self._stop_event.set()

        if self._thread:
            self._thread.join(timeout=timeout)
            self._thread = None

        logger.debug("PollingJournalWatcher stopped")

    def _poll_loop(self) -> None:
        """Background polling loop."""
        while self._running and not self._stop_event.is_set():
            try:
                if self._watcher:
                    self._watcher.check_for_updates()
            except Exception as e:
                logger.warning("JournalWatcher poll error: %s", e)

            # Wait for interval or stop signal
            self._stop_event.wait(timeout=self.poll_interval)

    @property
    def is_running(self) -> bool:
        """Check if polling is active."""
        return self._running

    @property
    def stats(self) -> dict[str, int]:
        """Get watcher statistics."""
        if self._watcher:
            return self._watcher.stats
        return {"last_position": 0, "seen_ids": 0, "total_received": 0}


# =============================================================================
# Factory Functions
# =============================================================================


def create_journal_watcher(
    workspace: Path,
    callback: LearningCallback,
) -> JournalWatcher:
    """Create a JournalWatcher for a workspace.

    Args:
        workspace: Project workspace root
        callback: Function to call for each new learning

    Returns:
        Configured JournalWatcher
    """
    memory_dir = workspace / ".sunwell" / "memory"
    journal = LearningJournal(memory_dir)
    return JournalWatcher(journal, callback)


def create_polling_watcher(
    workspace: Path,
    callback: LearningCallback,
    poll_interval: float = 1.0,
) -> PollingJournalWatcher:
    """Create a PollingJournalWatcher for a workspace.

    Args:
        workspace: Project workspace root
        callback: Function to call for each new learning
        poll_interval: Seconds between polls

    Returns:
        Configured PollingJournalWatcher (not yet started)
    """
    memory_dir = workspace / ".sunwell" / "memory"
    journal = LearningJournal(memory_dir)
    return PollingJournalWatcher(journal, callback, poll_interval)


# =============================================================================
# Integration Helpers
# =============================================================================


def create_learning_store_callback(learning_store: "LearningStore") -> LearningCallback:
    """Create a callback that adds learnings to a LearningStore.

    Args:
        learning_store: The store to add learnings to

    Returns:
        Callback function for watcher
    """
    def on_learning(learning: Learning) -> None:
        learning_store.add_learning(learning)

    return on_learning


if TYPE_CHECKING:
    from sunwell.agent.learning.store import LearningStore
