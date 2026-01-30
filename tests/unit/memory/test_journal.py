"""Tests for journal-based learning persistence.

Tests durability, recovery, and compaction of the learning journal.
"""

import json
import tempfile
from pathlib import Path

import pytest

from sunwell.agent.learning.learning import Learning
from sunwell.memory.core.compaction import JournalCompactor, compact_if_needed
from sunwell.memory.core.journal import JournalEntry, LearningJournal


class TestLearningJournal:
    """Tests for LearningJournal durability."""

    def test_append_creates_file(self, tmp_path: Path) -> None:
        """Journal file is created on first append."""
        journal = LearningJournal(tmp_path)
        learning = Learning(fact="test fact", category="test")

        journal.append(learning)

        assert journal.exists()
        assert journal.count() == 1

    def test_append_is_durable(self, tmp_path: Path) -> None:
        """Appended learning survives journal reload."""
        journal = LearningJournal(tmp_path)
        learning = Learning(fact="persistent fact", category="pattern")

        journal.append(learning)

        # Create new journal instance (simulates restart)
        journal2 = LearningJournal(tmp_path)
        entries = journal2.load_all()

        assert len(entries) == 1
        assert entries[0].fact == "persistent fact"
        assert entries[0].category == "pattern"

    def test_append_batch_atomicity(self, tmp_path: Path) -> None:
        """Batch append writes all learnings."""
        journal = LearningJournal(tmp_path)
        learnings = [
            Learning(fact=f"fact {i}", category="test")
            for i in range(5)
        ]

        count = journal.append_batch(learnings)

        assert count == 5
        assert journal.count() == 5

    def test_load_deduplicated(self, tmp_path: Path) -> None:
        """Duplicate IDs are deduplicated on load."""
        journal = LearningJournal(tmp_path)

        # Append same learning twice
        learning = Learning(fact="same fact", category="test")
        journal.append(learning)
        journal.append(learning)

        # Raw count includes duplicates
        assert journal.count() == 2

        # Deduplicated has one entry
        deduplicated = journal.load_deduplicated()
        assert len(deduplicated) == 1

    def test_load_as_learnings(self, tmp_path: Path) -> None:
        """Journal entries convert back to Learning objects."""
        journal = LearningJournal(tmp_path)
        original = Learning(
            fact="original fact",
            category="pattern",
            confidence=0.9,
            source_file="test.py",
            source_line=42,
        )

        journal.append(original)
        learnings = journal.load_as_learnings()

        assert len(learnings) == 1
        loaded = learnings[0]
        assert loaded.fact == original.fact
        assert loaded.category == original.category
        assert loaded.confidence == original.confidence
        assert loaded.source_file == original.source_file
        assert loaded.source_line == original.source_line

    def test_load_since_timestamp(self, tmp_path: Path) -> None:
        """load_since filters by timestamp."""
        journal = LearningJournal(tmp_path)

        # Append two learnings
        learning1 = Learning(fact="early", category="test")
        journal.append(learning1)

        # Get the timestamp of the first entry
        entries = journal.load_all()
        cutoff = entries[0].timestamp

        # Append another learning (will have later timestamp)
        learning2 = Learning(fact="later", category="test")
        journal.append(learning2)

        # Filter by timestamp
        recent = journal.load_since(cutoff)
        assert len(recent) == 1
        assert recent[0].fact == "later"

    def test_truncate(self, tmp_path: Path) -> None:
        """Truncate clears journal contents."""
        journal = LearningJournal(tmp_path)
        journal.append(Learning(fact="will be deleted", category="test"))

        assert journal.count() == 1

        journal.truncate()

        assert journal.count() == 0
        assert journal.exists()  # File still exists, just empty

    def test_malformed_entry_skipped(self, tmp_path: Path) -> None:
        """Malformed entries are skipped during load."""
        journal = LearningJournal(tmp_path)

        # Write valid entry
        journal.append(Learning(fact="valid", category="test"))

        # Write malformed entry directly
        with journal._journal_path.open("a", encoding="utf-8") as f:
            f.write("not valid json\n")
            f.write('{"id": "x", "fact": "valid2", "category": "test", "confidence": 0.8, "timestamp": "2025-01-01"}\n')

        entries = journal.load_all()

        # Should load 2 entries (skipping malformed)
        assert len(entries) == 2


class TestJournalCompactor:
    """Tests for journal compaction."""

    def test_should_compact_size_threshold(self, tmp_path: Path) -> None:
        """Compaction triggers when size threshold exceeded."""
        compactor = JournalCompactor(tmp_path, size_threshold=100)
        journal = LearningJournal(tmp_path)

        # Write enough data to exceed threshold
        for i in range(10):
            journal.append(Learning(fact=f"fact {i} with some extra text to make it longer", category="test"))

        assert compactor.should_compact()

    def test_should_compact_entry_threshold(self, tmp_path: Path) -> None:
        """Compaction triggers when entry threshold exceeded."""
        compactor = JournalCompactor(tmp_path, entry_threshold=5)
        journal = LearningJournal(tmp_path)

        for i in range(6):
            journal.append(Learning(fact=f"fact {i}", category="test"))

        assert compactor.should_compact()

    def test_compact_creates_checkpoint(self, tmp_path: Path) -> None:
        """Compaction creates a checkpoint file."""
        journal = LearningJournal(tmp_path)
        for i in range(3):
            journal.append(Learning(fact=f"fact {i}", category="test"))

        compactor = JournalCompactor(tmp_path)
        result = compactor.compact(force=True)

        assert result is not None
        assert result.checkpoint_path.exists()
        assert result.entries_compacted == 3

    def test_compact_truncates_journal(self, tmp_path: Path) -> None:
        """Compaction truncates the journal after checkpoint."""
        journal = LearningJournal(tmp_path)
        journal.append(Learning(fact="will be compacted", category="test"))

        compactor = JournalCompactor(tmp_path)
        compactor.compact(force=True)

        # Journal should be empty after compaction
        assert journal.count() == 0

    def test_recover_from_checkpoint(self, tmp_path: Path) -> None:
        """Entries can be recovered from checkpoint."""
        journal = LearningJournal(tmp_path)
        for i in range(3):
            journal.append(Learning(fact=f"recoverable {i}", category="test"))

        compactor = JournalCompactor(tmp_path)
        compactor.compact(force=True)

        # Recover from checkpoint
        recovered = compactor.recover_from_checkpoint()

        assert len(recovered) == 3
        facts = [e.fact for e in recovered]
        assert "recoverable 0" in facts
        assert "recoverable 1" in facts
        assert "recoverable 2" in facts

    def test_prune_old_checkpoints(self, tmp_path: Path) -> None:
        """Old checkpoints are pruned, keeping only recent ones."""
        journal = LearningJournal(tmp_path)
        compactor = JournalCompactor(tmp_path, keep_checkpoints=2)

        # Create 4 checkpoints
        for i in range(4):
            journal.append(Learning(fact=f"batch {i}", category="test"))
            compactor.compact(force=True)

        checkpoints = compactor.list_checkpoints()

        # Should keep only 2 most recent
        assert len(checkpoints) == 2


class TestJournalEntry:
    """Tests for JournalEntry serialization."""

    def test_round_trip_json(self) -> None:
        """JournalEntry survives JSON round-trip."""
        entry = JournalEntry(
            id="test123",
            fact="test fact",
            category="pattern",
            confidence=0.95,
            timestamp="2025-01-30T10:00:00",
            source_file="test.py",
            source_line=42,
        )

        json_str = entry.to_json()
        loaded = JournalEntry.from_json(json_str)

        assert loaded.id == entry.id
        assert loaded.fact == entry.fact
        assert loaded.category == entry.category
        assert loaded.confidence == entry.confidence
        assert loaded.timestamp == entry.timestamp
        assert loaded.source_file == entry.source_file
        assert loaded.source_line == entry.source_line

    def test_from_learning(self) -> None:
        """JournalEntry can be created from Learning."""
        learning = Learning(
            fact="learned fact",
            category="type",
            confidence=0.8,
            source_file="code.py",
            source_line=10,
        )

        entry = JournalEntry.from_learning(learning)

        assert entry.id == learning.id
        assert entry.fact == learning.fact
        assert entry.category == learning.category
        assert entry.confidence == learning.confidence
        assert entry.source_file == learning.source_file
        assert entry.source_line == learning.source_line

    def test_to_learning(self) -> None:
        """JournalEntry can be converted back to Learning."""
        entry = JournalEntry(
            id="abc123",
            fact="journal fact",
            category="api",
            confidence=0.75,
            timestamp="2025-01-30T10:00:00",
            source_file="api.py",
            source_line=100,
        )

        learning = entry.to_learning()

        assert learning.fact == entry.fact
        assert learning.category == entry.category
        assert learning.confidence == entry.confidence
        assert learning.source_file == entry.source_file
        assert learning.source_line == entry.source_line


class TestCrashRecovery:
    """Integration tests for crash recovery scenarios."""

    def test_recovery_after_simulated_crash(self, tmp_path: Path) -> None:
        """Learnings survive simulated crash (journal reload)."""
        workspace = tmp_path / "workspace"
        memory_dir = workspace / ".sunwell" / "memory"
        memory_dir.mkdir(parents=True)

        # Session 1: Write learnings
        journal1 = LearningJournal(memory_dir)
        learnings = [
            Learning(fact="session 1 fact 1", category="pattern"),
            Learning(fact="session 1 fact 2", category="type"),
        ]
        for l in learnings:
            journal1.append(l)

        # Simulate crash (no clean shutdown, just restart)
        del journal1

        # Session 2: Recover learnings
        journal2 = LearningJournal(memory_dir)
        recovered = journal2.load_as_learnings()

        assert len(recovered) == 2
        facts = [l.fact for l in recovered]
        assert "session 1 fact 1" in facts
        assert "session 1 fact 2" in facts

    def test_recovery_from_checkpoint_plus_journal(self, tmp_path: Path) -> None:
        """Recovery combines checkpoint and journal entries."""
        memory_dir = tmp_path

        # Phase 1: Create checkpoint
        journal = LearningJournal(memory_dir)
        journal.append(Learning(fact="checkpointed", category="test"))

        compactor = JournalCompactor(memory_dir)
        compactor.compact(force=True)

        # Phase 2: Add more to journal after checkpoint
        journal.append(Learning(fact="post-checkpoint", category="test"))

        # Recovery: checkpoint + journal
        checkpoint_entries = compactor.recover_from_checkpoint()
        journal_entries = journal.load_all()

        # Both should be available
        assert len(checkpoint_entries) == 1
        assert checkpoint_entries[0].fact == "checkpointed"
        assert len(journal_entries) == 1
        assert journal_entries[0].fact == "post-checkpoint"

    def test_deduplication_across_checkpoint_and_journal(self, tmp_path: Path) -> None:
        """Same learning in checkpoint and journal is deduplicated."""
        memory_dir = tmp_path
        journal = LearningJournal(memory_dir)

        # Add learning and checkpoint
        learning = Learning(fact="duplicate me", category="test")
        journal.append(learning)

        compactor = JournalCompactor(memory_dir)
        compactor.compact(force=True)

        # Re-add same learning to journal
        journal.append(learning)

        # Load all (checkpoint + journal) - should deduplicate
        checkpoint_entries = {e.id: e for e in compactor.recover_from_checkpoint()}
        journal_entries = journal.load_deduplicated()

        # Combine and deduplicate
        all_entries = {**checkpoint_entries, **journal_entries}
        assert len(all_entries) == 1  # Single unique learning
