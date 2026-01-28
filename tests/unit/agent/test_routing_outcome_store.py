"""Tests for sunwell.agent.learning.routing module.

Tests cover:
- RoutingOutcome creation and ID computation
- RoutingOutcomeStore thread safety
- Threshold suggestion algorithm
- Persistence (save/load to disk)
- Success rate calculation
"""

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import pytest

from sunwell.agent.learning import (
    DEFAULT_INTERFERENCE_THRESHOLD,
    DEFAULT_VORTEX_THRESHOLD,
    RoutingOutcome,
    RoutingOutcomeStore,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_outcome() -> RoutingOutcome:
    """Create a sample routing outcome."""
    return RoutingOutcome(
        task_type="code_generation",
        confidence=0.75,
        strategy="interference",
        success=True,
        tool_count=5,
        validation_passed=True,
    )


@pytest.fixture
def routing_store() -> RoutingOutcomeStore:
    """Create an empty routing outcome store."""
    return RoutingOutcomeStore()


@pytest.fixture
def populated_store() -> RoutingOutcomeStore:
    """Create a store with sample data representing typical usage patterns."""
    store = RoutingOutcomeStore()

    # Low confidence tasks (< 0.6) - Vortex performs well
    for i in range(10):
        store.record(RoutingOutcome(
            task_type="complex_refactor",
            confidence=0.4 + (i * 0.01),
            strategy="vortex",
            success=True,  # 8/10 success
            tool_count=10,
            validation_passed=True,
        ))
    store.record(RoutingOutcome(
        task_type="complex_refactor",
        confidence=0.45,
        strategy="vortex",
        success=False,
        tool_count=8,
        validation_passed=False,
    ))
    store.record(RoutingOutcome(
        task_type="complex_refactor",
        confidence=0.48,
        strategy="vortex",
        success=False,
        tool_count=6,
        validation_passed=False,
    ))

    # Medium confidence tasks (0.6-0.85) - Interference performs well
    for i in range(10):
        store.record(RoutingOutcome(
            task_type="code_generation",
            confidence=0.65 + (i * 0.01),
            strategy="interference",
            success=True,  # 9/10 success
            tool_count=5,
            validation_passed=True,
        ))
    store.record(RoutingOutcome(
        task_type="code_generation",
        confidence=0.70,
        strategy="interference",
        success=False,
        tool_count=4,
        validation_passed=False,
    ))

    # High confidence tasks (>= 0.85) - Single-shot performs well
    for i in range(10):
        store.record(RoutingOutcome(
            task_type="simple_fix",
            confidence=0.88 + (i * 0.01),
            strategy="single_shot",
            success=True,  # 10/10 success
            tool_count=2,
            validation_passed=True,
        ))

    return store


@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    """Create a temporary project directory."""
    return tmp_path


# =============================================================================
# RoutingOutcome Tests
# =============================================================================


class TestRoutingOutcome:
    """Tests for RoutingOutcome dataclass."""

    def test_creation(self, sample_outcome: RoutingOutcome) -> None:
        """Test RoutingOutcome can be created with valid data."""
        assert sample_outcome.task_type == "code_generation"
        assert sample_outcome.confidence == 0.75
        assert sample_outcome.strategy == "interference"
        assert sample_outcome.success is True
        assert sample_outcome.tool_count == 5
        assert sample_outcome.validation_passed is True
        assert isinstance(sample_outcome.timestamp, datetime)

    def test_id_generation(self, sample_outcome: RoutingOutcome) -> None:
        """Test that outcome ID is generated correctly."""
        outcome_id = sample_outcome.id
        assert outcome_id is not None
        assert "code_generation" in outcome_id
        assert "interference" in outcome_id

    def test_frozen(self, sample_outcome: RoutingOutcome) -> None:
        """Test that RoutingOutcome is immutable."""
        with pytest.raises(AttributeError):
            sample_outcome.success = False  # type: ignore[misc]


# =============================================================================
# RoutingOutcomeStore Tests
# =============================================================================


class TestRoutingOutcomeStore:
    """Tests for RoutingOutcomeStore."""

    def test_record_outcome(self, routing_store: RoutingOutcomeStore) -> None:
        """Test recording an outcome."""
        outcome = RoutingOutcome(
            task_type="test",
            confidence=0.5,
            strategy="vortex",
            success=True,
            tool_count=3,
            validation_passed=True,
        )
        routing_store.record(outcome)
        assert len(routing_store.outcomes) == 1
        assert routing_store.outcomes[0] == outcome

    def test_deduplication(self, routing_store: RoutingOutcomeStore) -> None:
        """Test that duplicate outcomes are not recorded."""
        outcome = RoutingOutcome(
            task_type="test",
            confidence=0.5,
            strategy="vortex",
            success=True,
            tool_count=3,
            validation_passed=True,
        )
        routing_store.record(outcome)
        routing_store.record(outcome)  # Same outcome
        assert len(routing_store.outcomes) == 1

    def test_thread_safety(self, routing_store: RoutingOutcomeStore) -> None:
        """Test concurrent recording is thread-safe."""
        outcomes_recorded = []

        def record_outcomes(thread_id: int) -> None:
            for i in range(100):
                outcome = RoutingOutcome(
                    task_type=f"task_{thread_id}_{i}",
                    confidence=0.5,
                    strategy="vortex",
                    success=True,
                    tool_count=1,
                    validation_passed=True,
                )
                routing_store.record(outcome)
                outcomes_recorded.append(outcome)

        threads = [threading.Thread(target=record_outcomes, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All outcomes should be recorded (no race conditions)
        assert len(routing_store.outcomes) == 500

    def test_get_success_rate(self, populated_store: RoutingOutcomeStore) -> None:
        """Test success rate calculation for strategy and confidence range."""
        # Vortex in low confidence range should have ~80% success
        vortex_rate = populated_store.get_success_rate("vortex", (0.0, 0.6))
        assert vortex_rate > 0.6  # At least 60% success

        # Single-shot in high confidence range should have 100% success
        single_shot_rate = populated_store.get_success_rate("single_shot", (0.85, 1.0))
        assert single_shot_rate == 1.0

        # No data should return -1.0
        empty_rate = populated_store.get_success_rate("vortex", (0.99, 1.0))
        assert empty_rate == -1.0

    def test_get_strategy_stats(self, populated_store: RoutingOutcomeStore) -> None:
        """Test getting statistics for all strategies."""
        stats = populated_store.get_strategy_stats()

        assert "vortex" in stats
        assert "interference" in stats
        assert "single_shot" in stats

        assert stats["vortex"]["count"] > 0
        assert 0.0 <= stats["vortex"]["success_rate"] <= 1.0

    def test_clear(self, populated_store: RoutingOutcomeStore) -> None:
        """Test clearing the store."""
        assert len(populated_store.outcomes) > 0
        populated_store.clear()
        assert len(populated_store.outcomes) == 0


# =============================================================================
# Threshold Suggestion Tests
# =============================================================================


class TestThresholdSuggestion:
    """Tests for the threshold suggestion algorithm."""

    def test_returns_defaults_with_insufficient_data(
        self, routing_store: RoutingOutcomeStore
    ) -> None:
        """Test that defaults are returned when there's not enough data."""
        vortex_th, interference_th = routing_store.suggest_thresholds(min_samples=20)
        assert vortex_th == DEFAULT_VORTEX_THRESHOLD
        assert interference_th == DEFAULT_INTERFERENCE_THRESHOLD

    def test_suggests_thresholds_with_sufficient_data(
        self, populated_store: RoutingOutcomeStore
    ) -> None:
        """Test threshold suggestion with populated data."""
        vortex_th, interference_th = populated_store.suggest_thresholds(min_samples=10)

        # Thresholds should be in valid range
        assert 0.3 <= vortex_th <= 0.7
        assert vortex_th + 0.1 <= interference_th <= 0.95

        # Vortex threshold should be lower than interference threshold
        assert vortex_th < interference_th

    def test_threshold_bounds(self, populated_store: RoutingOutcomeStore) -> None:
        """Test that suggested thresholds stay within valid bounds."""
        vortex_th, interference_th = populated_store.suggest_thresholds()

        # Verify bounds
        assert vortex_th >= 0.3
        assert vortex_th <= 0.7
        assert interference_th >= vortex_th + 0.1
        assert interference_th <= 0.95


# =============================================================================
# Persistence Tests
# =============================================================================


class TestPersistence:
    """Tests for save/load to disk."""

    def test_save_to_disk(
        self, populated_store: RoutingOutcomeStore, temp_project: Path
    ) -> None:
        """Test saving outcomes to disk."""
        saved = populated_store.save_to_disk(temp_project)
        assert saved > 0

        # Verify file was created
        outcomes_path = temp_project / ".sunwell" / "intelligence" / "routing_outcomes.jsonl"
        assert outcomes_path.exists()

    def test_load_from_disk(
        self, populated_store: RoutingOutcomeStore, temp_project: Path
    ) -> None:
        """Test loading outcomes from disk."""
        # Save first
        populated_store.save_to_disk(temp_project)

        # Load into new store
        new_store = RoutingOutcomeStore()
        loaded = new_store.load_from_disk(temp_project)

        assert loaded > 0
        assert len(new_store.outcomes) == len(populated_store.outcomes)

    def test_save_load_roundtrip(
        self, populated_store: RoutingOutcomeStore, temp_project: Path
    ) -> None:
        """Test that save/load preserves all data."""
        original_count = len(populated_store.outcomes)

        # Save
        populated_store.save_to_disk(temp_project)

        # Load into new store
        new_store = RoutingOutcomeStore()
        new_store.load_from_disk(temp_project)

        # Verify counts match
        assert len(new_store.outcomes) == original_count

        # Verify strategy stats are similar
        original_stats = populated_store.get_strategy_stats()
        loaded_stats = new_store.get_strategy_stats()

        for strategy in ["vortex", "interference", "single_shot"]:
            if strategy in original_stats:
                assert strategy in loaded_stats
                assert original_stats[strategy]["count"] == loaded_stats[strategy]["count"]

    def test_deduplication_on_save(
        self, routing_store: RoutingOutcomeStore, temp_project: Path
    ) -> None:
        """Test that duplicate outcomes are not saved twice."""
        outcome = RoutingOutcome(
            task_type="test",
            confidence=0.5,
            strategy="vortex",
            success=True,
            tool_count=3,
            validation_passed=True,
        )
        routing_store.record(outcome)

        # Save twice
        routing_store.save_to_disk(temp_project)
        routing_store.save_to_disk(temp_project)

        # Load and verify no duplicates
        new_store = RoutingOutcomeStore()
        new_store.load_from_disk(temp_project)
        assert len(new_store.outcomes) == 1

    def test_load_from_nonexistent(
        self, routing_store: RoutingOutcomeStore, temp_project: Path
    ) -> None:
        """Test loading from nonexistent file returns 0."""
        loaded = routing_store.load_from_disk(temp_project)
        assert loaded == 0
        assert len(routing_store.outcomes) == 0
