"""Tests for AwarenessStore."""

import json
from pathlib import Path

import pytest

from sunwell.awareness.patterns import AwarenessPattern, PatternType
from sunwell.awareness.store import AwarenessStore


@pytest.fixture
def temp_awareness_dir(tmp_path: Path) -> Path:
    """Create a temporary awareness directory."""
    awareness_dir = tmp_path / ".sunwell" / "awareness"
    awareness_dir.mkdir(parents=True)
    return awareness_dir


class TestAwarenessStore:
    """Tests for the AwarenessStore class."""

    def test_add_pattern_creates_entry(self, temp_awareness_dir: Path) -> None:
        """Adding a pattern should create an entry in the store."""
        store = AwarenessStore(temp_awareness_dir)

        pattern = AwarenessPattern(
            pattern_type=PatternType.CONFIDENCE,
            observation="test observation",
            metric=0.20,
            sample_size=10,
            context="test",
        )

        store.add_pattern(pattern)

        assert len(store) == 1
        assert pattern.id in store

    def test_add_duplicate_pattern_merges(self, temp_awareness_dir: Path) -> None:
        """Adding pattern with same ID should merge via reinforcement."""
        store = AwarenessStore(temp_awareness_dir)

        p1 = AwarenessPattern(
            pattern_type=PatternType.CONFIDENCE,
            observation="test",
            metric=0.20,
            sample_size=10,
            context="test",
        )
        p2 = AwarenessPattern(
            pattern_type=PatternType.CONFIDENCE,
            observation="test",
            metric=0.40,
            sample_size=10,
            context="test",  # Same context = same ID
        )

        store.add_pattern(p1)
        store.add_pattern(p2)

        assert len(store) == 1

        # Should have merged samples and averaged metric
        merged = store.get_pattern(p1.id)
        assert merged is not None
        assert merged.sample_size == 20
        assert merged.metric == pytest.approx(0.30)  # Average of 0.20 and 0.40

    def test_get_significant_filters_by_confidence(self, temp_awareness_dir: Path) -> None:
        """get_significant should only return significant patterns."""
        store = AwarenessStore(temp_awareness_dir)

        # Significant: enough samples and high metric
        significant = AwarenessPattern(
            pattern_type=PatternType.CONFIDENCE,
            observation="significant",
            metric=0.20,
            sample_size=10,
            context="sig",
        )

        # Not significant: below metric threshold
        insignificant = AwarenessPattern(
            pattern_type=PatternType.CONFIDENCE,
            observation="insignificant",
            metric=0.05,
            sample_size=10,
            context="insig",
        )

        store.add_pattern(significant)
        store.add_pattern(insignificant)

        result = store.get_significant(limit=10)

        assert len(result) == 1
        assert result[0].context == "sig"

    def test_save_and_load_roundtrip(self, temp_awareness_dir: Path) -> None:
        """Store should survive save/load roundtrip."""
        store = AwarenessStore(temp_awareness_dir)

        patterns = [
            AwarenessPattern(
                pattern_type=PatternType.CONFIDENCE,
                observation="confidence pattern",
                metric=0.20,
                sample_size=10,
                context="confidence",
            ),
            AwarenessPattern(
                pattern_type=PatternType.TOOL_AVOIDANCE,
                observation="tool avoidance pattern",
                metric=0.85,
                sample_size=15,
                context="grep_search",
            ),
        ]

        for p in patterns:
            store.add_pattern(p)

        # Save
        store.save()

        # Load into new store
        loaded_store = AwarenessStore.load(temp_awareness_dir)

        assert len(loaded_store) == 2

        for original in patterns:
            loaded = loaded_store.get_pattern(original.id)
            assert loaded is not None
            assert loaded.observation == original.observation
            assert loaded.metric == original.metric
            assert loaded.sample_size == original.sample_size

    def test_prune_decayed_removes_old_patterns(self, temp_awareness_dir: Path) -> None:
        """prune_decayed should remove patterns below threshold."""
        store = AwarenessStore(temp_awareness_dir)

        # Old pattern - accessed 100 activity days ago
        old_pattern = AwarenessPattern(
            pattern_type=PatternType.CONFIDENCE,
            observation="old",
            metric=0.20,
            sample_size=10,
            context="old",
            activity_day_accessed=0,
        )

        # Recent pattern - accessed today
        recent_pattern = AwarenessPattern(
            pattern_type=PatternType.CONFIDENCE,
            observation="recent",
            metric=0.20,
            sample_size=10,
            context="recent",
            activity_day_accessed=100,
        )

        store.add_pattern(old_pattern)
        store.add_pattern(recent_pattern)

        # Prune at activity day 100 with low threshold
        removed = store.prune_decayed(activity_day=100, threshold=0.30)

        assert removed == 1
        assert len(store) == 1
        assert recent_pattern.id in store
        assert old_pattern.id not in store

    def test_get_by_type_filters_correctly(self, temp_awareness_dir: Path) -> None:
        """get_by_type should return only patterns of that type."""
        store = AwarenessStore(temp_awareness_dir)

        patterns = [
            AwarenessPattern(
                pattern_type=PatternType.CONFIDENCE,
                observation="confidence",
                metric=0.20,
                sample_size=10,
                context="c1",
            ),
            AwarenessPattern(
                pattern_type=PatternType.CONFIDENCE,
                observation="confidence 2",
                metric=0.20,
                sample_size=10,
                context="c2",
            ),
            AwarenessPattern(
                pattern_type=PatternType.TOOL_AVOIDANCE,
                observation="avoidance",
                metric=0.80,
                sample_size=10,
                context="tool",
            ),
        ]

        for p in patterns:
            store.add_pattern(p)

        confidence_patterns = store.get_by_type(PatternType.CONFIDENCE)
        avoidance_patterns = store.get_by_type(PatternType.TOOL_AVOIDANCE)

        assert len(confidence_patterns) == 2
        assert len(avoidance_patterns) == 1

    def test_load_creates_empty_store_if_no_file(self, tmp_path: Path) -> None:
        """Loading from non-existent directory should create empty store."""
        non_existent = tmp_path / "does_not_exist"
        store = AwarenessStore.load(non_existent)

        assert len(store) == 0

    def test_mark_accessed_updates_activity_day(self, temp_awareness_dir: Path) -> None:
        """mark_accessed should update activity_day_accessed."""
        store = AwarenessStore(temp_awareness_dir)

        pattern = AwarenessPattern(
            pattern_type=PatternType.CONFIDENCE,
            observation="test",
            metric=0.20,
            sample_size=10,
            context="test",
            activity_day_accessed=0,
        )
        store.add_pattern(pattern)

        store.mark_accessed([pattern.id], activity_day=50)

        updated = store.get_pattern(pattern.id)
        assert updated is not None
        assert updated.activity_day_accessed == 50


class TestStoreThreadSafety:
    """Tests for thread safety of AwarenessStore."""

    def test_concurrent_adds_dont_lose_patterns(self, temp_awareness_dir: Path) -> None:
        """Concurrent adds should not lose any patterns."""
        import threading

        store = AwarenessStore(temp_awareness_dir)
        num_threads = 10
        patterns_per_thread = 10

        def add_patterns(thread_id: int) -> None:
            for i in range(patterns_per_thread):
                pattern = AwarenessPattern(
                    pattern_type=PatternType.CONFIDENCE,
                    observation=f"thread {thread_id} pattern {i}",
                    metric=0.20,
                    sample_size=5,
                    context=f"t{thread_id}_p{i}",
                )
                store.add_pattern(pattern)

        threads = [
            threading.Thread(target=add_patterns, args=(i,))
            for i in range(num_threads)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have all patterns
        assert len(store) == num_threads * patterns_per_thread
