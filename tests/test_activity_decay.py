"""Tests for activity-based memory decay (MIRA-inspired).

Tests cover:
- ActivityTracker: persistence, activity day counting
- activity_decay_score(): decay formula, newness boost
- Integration: decay impacts retrieval scoring
"""

import json
import tempfile
from datetime import date
from pathlib import Path

import pytest

from sunwell.memory.core.activity import ActivityTracker, ProjectActivity
from sunwell.memory.simulacrum.core.retrieval.similarity import activity_decay_score
from sunwell.memory.simulacrum.core.turn import Learning


# =============================================================================
# ActivityTracker Tests
# =============================================================================


class TestProjectActivity:
    """Tests for ProjectActivity dataclass."""

    def test_default_values(self) -> None:
        """Default state has zero activity days."""
        activity = ProjectActivity()
        assert activity.cumulative_activity_days == 0
        assert activity.last_activity_date is None

    def test_with_values(self) -> None:
        """Can initialize with values."""
        activity = ProjectActivity(
            cumulative_activity_days=10,
            last_activity_date="2025-01-15",
        )
        assert activity.cumulative_activity_days == 10
        assert activity.last_activity_date == "2025-01-15"


class TestActivityTracker:
    """Tests for ActivityTracker persistence and counting."""

    def test_record_activity_increments_on_new_day(self, tmp_path: Path) -> None:
        """Recording activity on a new day increments the count."""
        tracker = ActivityTracker(tmp_path)
        
        # First activity
        day1 = tracker.record_activity("test-project")
        assert day1 == 1
        
        # Same day - should not increment
        day1_again = tracker.record_activity("test-project")
        assert day1_again == 1

    def test_activity_persists_across_instances(self, tmp_path: Path) -> None:
        """Activity state persists to disk and loads correctly."""
        # Create tracker and record activity
        tracker1 = ActivityTracker(tmp_path)
        tracker1.record_activity("test-project")
        
        # Create new tracker instance - should load persisted state
        tracker2 = ActivityTracker(tmp_path)
        days = tracker2.get_activity_days("test-project")
        assert days == 1

    def test_separate_projects_tracked_separately(self, tmp_path: Path) -> None:
        """Different projects have independent activity counts."""
        tracker = ActivityTracker(tmp_path)
        
        tracker.record_activity("project-a")
        tracker.record_activity("project-b")
        
        # Each project should have 1 day
        assert tracker.get_activity_days("project-a") == 1
        assert tracker.get_activity_days("project-b") == 1

    def test_new_project_starts_at_zero(self, tmp_path: Path) -> None:
        """Unknown projects start with zero activity days."""
        tracker = ActivityTracker(tmp_path)
        assert tracker.get_activity_days("nonexistent") == 0

    def test_activity_file_structure(self, tmp_path: Path) -> None:
        """Activity is stored in correct file location."""
        tracker = ActivityTracker(tmp_path)
        tracker.record_activity("my-project")
        
        expected_path = tmp_path / "projects" / "my-project" / "activity.json"
        assert expected_path.exists()
        
        with open(expected_path) as f:
            data = json.load(f)
        
        assert data["cumulative_activity_days"] == 1
        assert data["last_activity_date"] == date.today().isoformat()

    def test_cache_cleared_properly(self, tmp_path: Path) -> None:
        """Clear cache forces reload from disk."""
        tracker = ActivityTracker(tmp_path)
        tracker.record_activity("test-project")
        
        # Manually modify the file
        path = tmp_path / "projects" / "test-project" / "activity.json"
        with open(path, "w") as f:
            json.dump({"cumulative_activity_days": 999, "last_activity_date": "2020-01-01"}, f)
        
        # Without clear, should still have cached value
        assert tracker.get_activity_days("test-project") == 1
        
        # After clear, should reload from disk
        tracker.clear_cache("test-project")
        assert tracker.get_activity_days("test-project") == 999


# =============================================================================
# Decay Function Tests
# =============================================================================


class TestActivityDecayScore:
    """Tests for activity_decay_score() function."""

    def test_new_learning_gets_boost(self) -> None:
        """Brand new learnings (age=0) get newness boost."""
        score = activity_decay_score(
            activity_day_created=10,
            current_activity_days=10,
        )
        # At age=0: base=1.0, newness_boost=0.3 → total ~1.3
        assert 1.25 <= score <= 1.35

    def test_newness_boost_decays_linearly(self) -> None:
        """Newness boost decays to zero over newness_boost_days."""
        # At half the newness period
        score_mid = activity_decay_score(
            activity_day_created=0,
            current_activity_days=7,
            newness_boost_days=15,
            newness_boost=0.3,
        )
        
        # At end of newness period
        score_end = activity_decay_score(
            activity_day_created=0,
            current_activity_days=15,
            newness_boost_days=15,
            newness_boost=0.3,
        )
        
        # Mid should have some boost, end should have none
        assert score_mid > score_end
        # End of newness period has no boost, just base decay
        assert score_end < 1.0

    def test_decay_over_time(self) -> None:
        """Score decreases as activity days pass."""
        score_0 = activity_decay_score(activity_day_created=0, current_activity_days=0)
        score_30 = activity_decay_score(activity_day_created=0, current_activity_days=30)
        score_60 = activity_decay_score(activity_day_created=0, current_activity_days=60)
        score_100 = activity_decay_score(activity_day_created=0, current_activity_days=100)
        
        # Should be monotonically decreasing
        assert score_0 > score_30 > score_60 > score_100
        
        # Score should approach but never reach zero
        assert score_100 > 0

    def test_half_life_approximately_67_days(self) -> None:
        """Default decay_rate=0.015 gives ~67 activity day half-life."""
        # At approximately 67 days, score should be ~0.5 (plus any remaining newness)
        score = activity_decay_score(
            activity_day_created=0,
            current_activity_days=67,
            newness_boost=0.0,  # Disable to test pure decay
        )
        # 1.0 / (1.0 + 67 * 0.015) = 1.0 / 2.005 ≈ 0.499
        assert 0.45 <= score <= 0.55

    def test_custom_decay_rate(self) -> None:
        """Custom decay_rate affects decay speed."""
        slow = activity_decay_score(
            activity_day_created=0,
            current_activity_days=30,
            decay_rate=0.01,  # Slower
            newness_boost=0.0,
        )
        fast = activity_decay_score(
            activity_day_created=0,
            current_activity_days=30,
            decay_rate=0.03,  # Faster
            newness_boost=0.0,
        )
        
        assert slow > fast

    def test_negative_age_clamped_to_zero(self) -> None:
        """If activity_day_created > current (data error), clamp age to 0."""
        # This shouldn't happen, but handle gracefully
        score = activity_decay_score(
            activity_day_created=100,
            current_activity_days=50,  # Less than created
        )
        # Age = max(0, 50 - 100) = max(0, -50) = 0
        # So score should be like age=0 with boost
        assert score > 1.0  # Has newness boost


# =============================================================================
# Learning Integration Tests
# =============================================================================


class TestLearningWithActivityDays:
    """Tests for Learning with activity day fields."""

    def test_learning_created_with_activity_day(self) -> None:
        """Learning can be created with activity_day_created."""
        learning = Learning(
            fact="Test fact",
            source_turns=(),
            confidence=0.9,
            category="fact",
            activity_day_created=42,
        )
        assert learning.activity_day_created == 42

    def test_learning_defaults_to_zero(self) -> None:
        """Learning defaults to 0 for activity fields."""
        learning = Learning(
            fact="Test fact",
            source_turns=(),
            confidence=0.9,
            category="fact",
        )
        assert learning.activity_day_created == 0
        assert learning.activity_day_accessed == 0

    def test_with_access_updates_activity_day(self) -> None:
        """with_access() updates activity_day_accessed."""
        learning = Learning(
            fact="Test fact",
            source_turns=(),
            confidence=0.9,
            category="fact",
            activity_day_created=10,
        )
        
        updated = learning.with_access(activity_day=20)
        
        assert updated.activity_day_created == 10  # Unchanged
        assert updated.activity_day_accessed == 20  # Updated
        assert updated.use_count == learning.use_count + 1

    def test_with_activity_day_created_stamps_learning(self) -> None:
        """with_activity_day_created() stamps a new learning."""
        learning = Learning(
            fact="Test fact",
            source_turns=(),
            confidence=0.9,
            category="fact",
        )
        
        stamped = learning.with_activity_day_created(activity_day=15)
        
        assert stamped.activity_day_created == 15
        # Original should be unchanged (frozen)
        assert learning.activity_day_created == 0


# =============================================================================
# Activity-Based vs Calendar-Based Decay Comparison
# =============================================================================


class TestActivityVsCalendarDecay:
    """Tests demonstrating activity-based decay differs from calendar-based."""

    def test_vacation_does_not_penalize_memories(self) -> None:
        """Memories don't decay during vacation (no activity)."""
        # Scenario: User worked Day 1-5, then vacation Day 6-15, back Day 16
        # Memory created Day 3
        
        # Activity days: Day 1=1, Day 2=2, Day 3=3, Day 4=4, Day 5=5
        # After vacation: Day 16=6 (only 6th activity day)
        
        # Activity-based age: 6 - 3 = 3 activity days
        activity_score = activity_decay_score(
            activity_day_created=3,
            current_activity_days=6,
            newness_boost=0.0,  # Focus on decay only
        )
        
        # Calendar-based would have: 16 - 3 = 13 calendar days
        # Simulated with activity days = 13
        calendar_score = activity_decay_score(
            activity_day_created=0,
            current_activity_days=13,
            newness_boost=0.0,
        )
        
        # Activity-based should preserve relevance better
        assert activity_score > calendar_score
        
        # Activity-based: 1.0 / (1.0 + 3 * 0.015) = ~0.957
        # Calendar-based: 1.0 / (1.0 + 13 * 0.015) = ~0.837
        assert activity_score > 0.9
        assert calendar_score < 0.9

    def test_consistent_user_penalizes_same_as_activity_days(self) -> None:
        """For daily users, activity days = calendar days."""
        # User who works every day
        activity_score = activity_decay_score(
            activity_day_created=0,
            current_activity_days=30,  # 30 activity days
            newness_boost=0.0,
        )
        
        # For consistent daily use, this equals 30 calendar days
        # Score should be: 1.0 / (1.0 + 30 * 0.015) = ~0.69
        assert 0.65 <= activity_score <= 0.72


# =============================================================================
# DAG Persistence Tests
# =============================================================================


class TestDAGPersistenceWithActivityDays:
    """Tests for DAG save/load preserving activity day fields."""

    def test_save_and_load_preserves_activity_days(self, tmp_path: Path) -> None:
        """Activity day fields survive DAG serialization."""
        from sunwell.memory.simulacrum.core.dag import ConversationDAG
        
        dag = ConversationDAG()
        learning = Learning(
            fact="Test fact",
            source_turns=(),
            confidence=0.9,
            category="fact",
            activity_day_created=42,
            activity_day_accessed=50,
        )
        dag.add_learning(learning)
        
        # Save and reload
        path = tmp_path / "dag.json"
        dag.save(path)
        
        loaded_dag = ConversationDAG.load(path)
        
        loaded_learning = loaded_dag.learnings.get(learning.id)
        assert loaded_learning is not None
        assert loaded_learning.activity_day_created == 42
        assert loaded_learning.activity_day_accessed == 50

