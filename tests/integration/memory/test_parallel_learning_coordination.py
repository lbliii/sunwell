"""Integration tests for Parallel Learning Coordination (Unified Memory Coordination).

Tests the complete flow of learning sharing between parallel workers:
1. LearningBus for in-process coordination
2. JournalWatcher for cross-process coordination
3. LearningCache for fast queries
4. Agent startup population from memory

Scenario being tested (black-box reproduction):
    Worker A creates Python files → extracts "Project uses python"
    Worker B receives learning (via bus or journal)
    Worker B creates Python files (not Go)
"""

import asyncio
import tempfile
import threading
import time
from pathlib import Path

import pytest

from sunwell.agent.learning.learning import Learning
from sunwell.agent.learning.store import LearningStore
from sunwell.memory.core.journal import LearningJournal
from sunwell.memory.core.journal_watcher import JournalWatcher, PollingJournalWatcher
from sunwell.memory.core.learning_bus import (
    LearningBus,
    get_learning_bus,
    reset_learning_bus,
    subscribe_learning_store,
)
from sunwell.memory.core.learning_cache import LearningCache


class TestLearningBus:
    """Test in-process learning sharing via LearningBus."""

    def test_publish_notify_subscribers(self) -> None:
        """Test that publishing notifies all subscribers."""
        bus = LearningBus()
        received: list[Learning] = []

        def callback(learning: Learning) -> None:
            received.append(learning)

        bus.subscribe(callback)

        learning = Learning(fact="Project uses python", category="project")
        notified = bus.publish(learning)

        assert notified == 1
        assert len(received) == 1
        assert received[0].fact == "Project uses python"

    def test_multiple_subscribers(self) -> None:
        """Test that all subscribers receive the learning."""
        bus = LearningBus()
        received1: list[Learning] = []
        received2: list[Learning] = []

        bus.subscribe(lambda l: received1.append(l))
        bus.subscribe(lambda l: received2.append(l))

        learning = Learning(fact="Uses Flask framework", category="project")
        bus.publish(learning)

        assert len(received1) == 1
        assert len(received2) == 1

    def test_unsubscribe(self) -> None:
        """Test that unsubscribed callbacks don't receive."""
        bus = LearningBus()
        received: list[Learning] = []

        def callback(learning: Learning) -> None:
            received.append(learning)

        bus.subscribe(callback)
        bus.unsubscribe(callback)

        learning = Learning(fact="Test", category="test")
        bus.publish(learning)

        assert len(received) == 0

    def test_error_isolation(self) -> None:
        """Test that one callback error doesn't stop others."""
        bus = LearningBus()
        received: list[Learning] = []

        def bad_callback(learning: Learning) -> None:
            raise ValueError("Intentional error")

        def good_callback(learning: Learning) -> None:
            received.append(learning)

        bus.subscribe(bad_callback)
        bus.subscribe(good_callback)

        learning = Learning(fact="Test", category="test")
        notified = bus.publish(learning)

        # Good callback should still receive
        assert len(received) == 1
        assert bus.stats["errors"] == 1

    def test_subscribe_learning_store(self) -> None:
        """Test integration with LearningStore."""
        bus = LearningBus()
        store = LearningStore()

        callback = subscribe_learning_store(store, bus)

        learning = Learning(fact="Database uses PostgreSQL", category="project")
        bus.publish(learning)

        assert len(store.learnings) == 1
        assert store.learnings[0].fact == "Database uses PostgreSQL"

    def test_global_bus_singleton(self) -> None:
        """Test that get_learning_bus returns same instance."""
        reset_learning_bus()

        bus1 = get_learning_bus()
        bus2 = get_learning_bus()

        assert bus1 is bus2

        reset_learning_bus()


class TestJournalWatcher:
    """Test cross-process learning sharing via JournalWatcher."""

    def test_detect_new_entries(self, tmp_path: Path) -> None:
        """Test that watcher detects new journal entries."""
        journal = LearningJournal(tmp_path)
        received: list[Learning] = []

        def callback(learning: Learning) -> None:
            received.append(learning)

        watcher = JournalWatcher(journal, callback)

        # Simulate Worker A writing a learning
        learning = Learning(fact="Project uses Python", category="project")
        journal.append(learning)

        # Worker B's watcher checks for updates
        new_count = watcher.check_for_updates()

        assert new_count == 1
        assert len(received) == 1
        assert received[0].fact == "Project uses Python"

    def test_no_duplicates(self, tmp_path: Path) -> None:
        """Test that watcher doesn't reprocess entries."""
        journal = LearningJournal(tmp_path)
        received: list[Learning] = []

        watcher = JournalWatcher(journal, lambda l: received.append(l))

        # Write and check
        journal.append(Learning(fact="Test 1", category="test"))
        watcher.check_for_updates()

        # Check again without new data
        count = watcher.check_for_updates()

        assert count == 0
        assert len(received) == 1

    def test_multiple_updates(self, tmp_path: Path) -> None:
        """Test incremental updates work correctly."""
        journal = LearningJournal(tmp_path)
        received: list[Learning] = []

        watcher = JournalWatcher(journal, lambda l: received.append(l))

        # First batch
        journal.append(Learning(fact="Fact 1", category="test"))
        watcher.check_for_updates()

        # Second batch
        journal.append(Learning(fact="Fact 2", category="test"))
        journal.append(Learning(fact="Fact 3", category="test"))
        watcher.check_for_updates()

        assert len(received) == 3


class TestPollingJournalWatcher:
    """Test automatic polling watcher."""

    def test_polling_detects_changes(self, tmp_path: Path) -> None:
        """Test that polling watcher picks up changes."""
        journal = LearningJournal(tmp_path)
        received: list[Learning] = []

        watcher = PollingJournalWatcher(
            journal,
            lambda l: received.append(l),
            poll_interval=0.1,
        )

        watcher.start()
        try:
            # Write while polling
            journal.append(Learning(fact="Polling test", category="test"))

            # Wait for poll
            time.sleep(0.3)

            assert len(received) >= 1
            assert received[0].fact == "Polling test"
        finally:
            watcher.stop()

    def test_stop_polling(self, tmp_path: Path) -> None:
        """Test that stop() cleanly terminates polling."""
        journal = LearningJournal(tmp_path)

        watcher = PollingJournalWatcher(journal, lambda l: None, poll_interval=0.1)

        watcher.start()
        assert watcher.is_running

        watcher.stop()
        assert not watcher.is_running


class TestLearningCache:
    """Test SQLite-backed learning cache."""

    def test_add_and_query(self, tmp_path: Path) -> None:
        """Test basic add and query operations."""
        cache = LearningCache(tmp_path)

        learning = Learning(fact="Cache test", category="test", confidence=0.9)
        cache.add(learning)

        # Query by category
        results = cache.get_by_category("test")
        assert len(results) == 1
        assert results[0].fact == "Cache test"

    def test_sync_from_journal(self, tmp_path: Path) -> None:
        """Test syncing cache from journal."""
        # Write to journal
        journal = LearningJournal(tmp_path)
        journal.append(Learning(fact="Sync test 1", category="test"))
        journal.append(Learning(fact="Sync test 2", category="test"))

        # Sync to cache
        cache = LearningCache(tmp_path)
        synced = cache.sync_from_journal(journal)

        assert synced == 2
        assert cache.count() == 2

    def test_search_facts(self, tmp_path: Path) -> None:
        """Test fact search functionality."""
        cache = LearningCache(tmp_path)

        cache.add(Learning(fact="Project uses Python", category="project"))
        cache.add(Learning(fact="Project uses Flask", category="project"))
        cache.add(Learning(fact="Uses PostgreSQL database", category="project"))

        # Search for Python
        results = cache.search_facts("Python")
        assert len(results) == 1
        assert "Python" in results[0].fact

    def test_concurrent_access(self, tmp_path: Path) -> None:
        """Test that WAL mode allows concurrent access."""
        cache = LearningCache(tmp_path)

        errors: list[Exception] = []

        def writer() -> None:
            try:
                for i in range(10):
                    cache.add(Learning(fact=f"Writer {i}", category="test"))
            except Exception as e:
                errors.append(e)

        def reader() -> None:
            try:
                for _ in range(10):
                    cache.get_recent(limit=5)
            except Exception as e:
                errors.append(e)

        # Run concurrently
        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=reader),
            threading.Thread(target=reader),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


class TestParallelLearningVisibility:
    """Integration test for the black-box scenario.

    Scenario:
        Worker A creates Python files → extracts "Project uses python"
        Worker B receives learning → uses Python (not Go)
    """

    def test_in_process_sharing_via_bus(self, tmp_path: Path) -> None:
        """Test that in-process workers share learnings via bus."""
        reset_learning_bus()
        bus = get_learning_bus()

        # Worker A's LearningStore
        store_a = LearningStore()
        subscribe_learning_store(store_a, bus)

        # Worker B's LearningStore
        store_b = LearningStore()
        subscribe_learning_store(store_b, bus)

        # Worker A extracts a project learning
        project_learning = Learning(
            fact="Project uses Python",
            category="project",
            confidence=1.0,
        )

        # Worker A publishes (simulating execution.py flow)
        bus.publish(project_learning)

        # Both workers should have the learning
        assert len(store_a.learnings) == 1
        assert len(store_b.learnings) == 1
        assert store_b.learnings[0].fact == "Project uses Python"

        reset_learning_bus()

    def test_cross_process_sharing_via_journal(self, tmp_path: Path) -> None:
        """Test that separate processes share learnings via journal."""
        journal = LearningJournal(tmp_path)

        # Worker A writes to journal (simulating execution.py)
        worker_a_learning = Learning(
            fact="Project uses JavaScript",
            category="project",
            confidence=1.0,
        )
        journal.append(worker_a_learning)

        # Worker B watches journal (simulating parallel worker)
        store_b = LearningStore()

        def on_learning(l: Learning) -> None:
            store_b.add_learning(l)

        watcher = JournalWatcher(journal, on_learning)
        watcher.check_for_updates()

        # Worker B should have the learning
        assert len(store_b.learnings) == 1
        assert store_b.learnings[0].fact == "Project uses JavaScript"

    def test_cache_provides_fast_access(self, tmp_path: Path) -> None:
        """Test that cache provides fast access to project learnings."""
        # Simulate learnings accumulated over time
        journal = LearningJournal(tmp_path)
        journal.append(Learning(fact="Project uses Python", category="project"))
        journal.append(Learning(fact="Project uses FastAPI", category="project"))
        journal.append(Learning(fact="Uses PostgreSQL", category="project"))
        journal.append(Learning(fact="Pattern: async/await", category="pattern"))

        # Sync to cache
        cache = LearningCache(tmp_path)
        cache.sync_from_journal(journal)

        # New worker queries project context
        project_learnings = cache.get_by_category("project")

        assert len(project_learnings) == 3
        # Should know about Python, FastAPI, PostgreSQL
        facts = {l.fact for l in project_learnings}
        assert "Project uses Python" in facts
        assert "Project uses FastAPI" in facts

    def test_full_coordination_flow(self, tmp_path: Path) -> None:
        """Test the complete coordination flow from plan.

        Flow:
        1. Worker A creates Python file, extracts learning
        2. Learning goes to journal (durable)
        3. Learning goes to bus (in-process)
        4. Worker B checks journal at task start
        5. Worker B has project context
        """
        reset_learning_bus()
        bus = get_learning_bus()
        journal = LearningJournal(tmp_path)

        # --- Worker A flow ---
        store_a = LearningStore()
        subscribe_learning_store(store_a, bus)

        # A creates a Python file and extracts learning
        python_learning = Learning(
            fact="Project uses Python",
            category="project",
            confidence=1.0,
            source_file="todo.py",
        )

        # A adds to store (in-memory)
        store_a.add_learning(python_learning)

        # A writes to journal (durable)
        journal.append(python_learning)

        # A publishes to bus (in-process sharing)
        bus.publish(python_learning)

        # --- Worker B flow ---
        store_b = LearningStore()
        subscribe_learning_store(store_b, bus)

        # B was just spawned, doesn't have the in-process event
        # B reloads from journal at task start (Phase 1.2)
        loaded = store_b.reload_from_journal(tmp_path)

        # B should now have the learning
        assert loaded == 1 or len(store_b.learnings) > 0  # From bus or journal
        assert any(l.fact == "Project uses Python" for l in store_b.learnings)

        reset_learning_bus()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
