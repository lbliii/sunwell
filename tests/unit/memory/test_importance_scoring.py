"""Tests for MIRA-inspired importance scoring.

Tests the importance scoring module that combines:
- Semantic similarity
- Graph connectivity (hub score)
- Behavioral signals (access patterns, mentions)
- Temporal relevance (recency, deadlines)

Also tests:
- DAG find_learning/replace_learning methods
- Store activity tracking integration
"""

import math
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from sunwell.memory.simulacrum.core.dag import ConversationDAG
from sunwell.memory.simulacrum.core.retrieval.importance import (
    CATEGORY_CONFIGS,
    ImportanceConfig,
    _compute_deadline_multiplier,
    _compute_expiration_multiplier,
    compute_behavioral_score,
    compute_graph_score,
    compute_importance,
    compute_temporal_score,
    get_config_for_category,
)
from sunwell.memory.simulacrum.core.turn import Learning


# === Fixtures ===


@pytest.fixture
def basic_learning() -> Learning:
    """Create a basic learning for testing."""
    return Learning(
        fact="Uses FastAPI for the web framework",
        source_turns=("turn1",),
        confidence=0.8,
        category="fact",
        use_count=5,
        mention_count=2,
        activity_day_created=10,
        activity_day_accessed=15,
    )


@pytest.fixture
def new_learning() -> Learning:
    """Create a newly created learning (for newness boost testing)."""
    return Learning(
        fact="Prefers pytest over unittest",
        source_turns=("turn2",),
        confidence=0.9,
        category="preference",
        use_count=0,
        mention_count=0,
        activity_day_created=18,  # Very recent
        activity_day_accessed=18,  # Never accessed beyond creation
    )


@pytest.fixture
def dead_end_learning() -> Learning:
    """Create a dead-end learning."""
    return Learning(
        fact="Sync database calls caused timeout issues",
        source_turns=("turn3",),
        confidence=0.7,
        category="dead_end",
        use_count=3,
        mention_count=1,
        activity_day_created=5,
        activity_day_accessed=8,
    )


# === ImportanceConfig Tests ===
# Note: ActivityTracker tests are in tests/test_activity_decay.py


class TestImportanceConfig:
    """Tests for ImportanceConfig."""

    def test_default_weights_sum_to_one(self) -> None:
        """Default weights should sum to 1.0."""
        config = ImportanceConfig()
        total = (
            config.semantic_weight
            + config.graph_weight
            + config.behavioral_weight
            + config.temporal_weight
        )
        assert abs(total - 1.0) < 0.001

    def test_category_configs_exist(self) -> None:
        """Category-specific configs exist."""
        assert "dead_end" in CATEGORY_CONFIGS
        assert "preference" in CATEGORY_CONFIGS
        assert "pattern" in CATEGORY_CONFIGS

    def test_get_config_for_category(self) -> None:
        """get_config_for_category returns appropriate config."""
        dead_end_config = get_config_for_category("dead_end")
        assert dead_end_config.behavioral_weight > ImportanceConfig().behavioral_weight

        default_config = get_config_for_category("unknown_category")
        assert default_config == ImportanceConfig()


# === Graph Score Tests ===


class TestGraphScore:
    """Tests for compute_graph_score."""

    def test_zero_links(self) -> None:
        """Zero inbound links returns 0."""
        config = ImportanceConfig()
        assert compute_graph_score(0, config) == 0.0

    def test_linear_region(self) -> None:
        """Score increases linearly up to threshold."""
        config = ImportanceConfig()

        score_5 = compute_graph_score(5, config)
        score_10 = compute_graph_score(10, config)

        # Should be proportional
        assert abs(score_10 / score_5 - 2.0) < 0.001

    def test_diminishing_returns(self) -> None:
        """Score increases slower after threshold."""
        config = ImportanceConfig()

        score_at_threshold = compute_graph_score(config.hub_linear_threshold, config)
        score_at_double = compute_graph_score(config.hub_linear_threshold * 2, config)

        # Gain from 10->20 should be less than gain from 0->10
        gain_linear = score_at_threshold
        gain_diminishing = score_at_double - score_at_threshold

        assert gain_diminishing < gain_linear


# === Behavioral Score Tests ===


class TestBehavioralScore:
    """Tests for compute_behavioral_score."""

    def test_high_use_count_increases_score(self, basic_learning: Learning) -> None:
        """Higher use_count should increase score."""
        config = ImportanceConfig()

        # Create a version with higher use_count
        high_use = Learning(
            fact=basic_learning.fact,
            source_turns=basic_learning.source_turns,
            confidence=basic_learning.confidence,
            category=basic_learning.category,
            use_count=50,
            mention_count=basic_learning.mention_count,
            activity_day_created=basic_learning.activity_day_created,
            activity_day_accessed=basic_learning.activity_day_accessed,
        )

        score_basic = compute_behavioral_score(basic_learning, 20, config)
        score_high = compute_behavioral_score(high_use, 20, config)

        assert score_high > score_basic

    def test_mention_count_boost(self, basic_learning: Learning) -> None:
        """Mentions should boost score significantly."""
        config = ImportanceConfig()

        # Create a version with no mentions
        no_mentions = Learning(
            fact=basic_learning.fact,
            source_turns=basic_learning.source_turns,
            confidence=basic_learning.confidence,
            category=basic_learning.category,
            use_count=basic_learning.use_count,
            mention_count=0,
            activity_day_created=basic_learning.activity_day_created,
            activity_day_accessed=basic_learning.activity_day_accessed,
        )

        score_with_mentions = compute_behavioral_score(basic_learning, 20, config)
        score_no_mentions = compute_behavioral_score(no_mentions, 20, config)

        assert score_with_mentions > score_no_mentions

    def test_confidence_factor(self, basic_learning: Learning) -> None:
        """Higher confidence should boost score."""
        config = ImportanceConfig()

        # Create a version with lower confidence
        low_confidence = Learning(
            fact=basic_learning.fact,
            source_turns=basic_learning.source_turns,
            confidence=0.3,
            category=basic_learning.category,
            use_count=basic_learning.use_count,
            mention_count=basic_learning.mention_count,
            activity_day_created=basic_learning.activity_day_created,
            activity_day_accessed=basic_learning.activity_day_accessed,
        )

        score_high = compute_behavioral_score(basic_learning, 20, config)
        score_low = compute_behavioral_score(low_confidence, 20, config)

        assert score_high > score_low


# === Temporal Score Tests ===


class TestTemporalScore:
    """Tests for compute_temporal_score."""

    def test_newness_boost(self, new_learning: Learning) -> None:
        """New learnings get a boost."""
        config = ImportanceConfig()

        # Current activity day is 20, learning was created at 18
        # Should get newness boost (within 15 days of creation)
        score = compute_temporal_score(new_learning, 20, config)
        assert score > 1.0  # Should be boosted

    def test_newness_decays(self, new_learning: Learning) -> None:
        """Newness boost decays over time."""
        config = ImportanceConfig()

        score_fresh = compute_temporal_score(new_learning, 20, config)
        score_old = compute_temporal_score(new_learning, 50, config)

        assert score_fresh > score_old

    def test_recency_decay(self, basic_learning: Learning) -> None:
        """More recent accesses score higher."""
        config = ImportanceConfig()

        # basic_learning was accessed at day 15
        score_recent = compute_temporal_score(basic_learning, 16, config)  # 1 day ago
        score_old = compute_temporal_score(basic_learning, 50, config)  # 35 days ago

        assert score_recent > score_old


class TestDeadlineMultiplier:
    """Tests for deadline proximity boost."""

    def test_past_event_no_boost(self) -> None:
        """Past events get no boost."""
        past = (datetime.now() - timedelta(days=1)).isoformat()
        assert _compute_deadline_multiplier(past) == 1.0

    def test_imminent_event_max_boost(self) -> None:
        """Events within 24 hours get maximum boost."""
        imminent = (datetime.now() + timedelta(hours=12)).isoformat()
        assert _compute_deadline_multiplier(imminent) == 3.0

    def test_week_away_moderate_boost(self) -> None:
        """Events a week away get moderate boost."""
        week_away = (datetime.now() + timedelta(days=3)).isoformat()
        multiplier = _compute_deadline_multiplier(week_away)
        assert 1.0 < multiplier < 3.0


class TestExpirationMultiplier:
    """Tests for expiration decay."""

    def test_expired_penalty(self) -> None:
        """Expired content gets penalty."""
        expired = (datetime.now() - timedelta(hours=1)).isoformat()
        assert _compute_expiration_multiplier(expired) == 0.1

    def test_expiring_soon_penalty(self) -> None:
        """Content expiring soon gets slight penalty."""
        expiring = (datetime.now() + timedelta(hours=12)).isoformat()
        assert _compute_expiration_multiplier(expiring) == 0.5

    def test_far_future_no_penalty(self) -> None:
        """Content expiring far away gets no penalty."""
        far = (datetime.now() + timedelta(days=30)).isoformat()
        assert _compute_expiration_multiplier(far) == 1.0


# === Integration Tests ===


class TestComputeImportance:
    """Tests for the unified compute_importance function."""

    def test_semantic_dominates_when_high(self, basic_learning: Learning) -> None:
        """High semantic similarity should produce high importance."""
        score_high_semantic = compute_importance(
            basic_learning,
            query_similarity=0.95,
            activity_days=20,
        )
        score_low_semantic = compute_importance(
            basic_learning,
            query_similarity=0.2,
            activity_days=20,
        )

        assert score_high_semantic > score_low_semantic

    def test_category_configs_affect_scoring(
        self,
        basic_learning: Learning,
        dead_end_learning: Learning,
    ) -> None:
        """Different categories use different configs."""
        # Same semantic similarity, but different categories
        fact_score = compute_importance(
            basic_learning,
            query_similarity=0.7,
            activity_days=20,
        )
        dead_end_score = compute_importance(
            dead_end_learning,
            query_similarity=0.7,
            activity_days=20,
        )

        # Scores should differ due to different category weights
        assert fact_score != dead_end_score

    def test_graph_connectivity_boosts_score(self, basic_learning: Learning) -> None:
        """Higher inbound link count should boost score."""
        score_no_links = compute_importance(
            basic_learning,
            query_similarity=0.7,
            activity_days=20,
            inbound_link_count=0,
        )
        score_many_links = compute_importance(
            basic_learning,
            query_similarity=0.7,
            activity_days=20,
            inbound_link_count=15,
        )

        assert score_many_links > score_no_links

    def test_output_in_valid_range(self, basic_learning: Learning) -> None:
        """Importance score should always be between 0 and 1."""
        for similarity in [0.0, 0.3, 0.5, 0.7, 1.0]:
            for activity_days in [0, 10, 50, 100]:
                for links in [0, 5, 20]:
                    score = compute_importance(
                        basic_learning,
                        query_similarity=similarity,
                        activity_days=activity_days,
                        inbound_link_count=links,
                    )
                    assert 0.0 <= score <= 1.0, f"Score {score} out of range"


# === Learning Methods Tests ===


class TestLearningMethods:
    """Tests for the new Learning methods."""

    def test_with_mention_increments(self, basic_learning: Learning) -> None:
        """with_mention() increments mention_count."""
        updated = basic_learning.with_mention()
        assert updated.mention_count == basic_learning.mention_count + 1
        # Verify immutability - original unchanged
        assert basic_learning.mention_count == 2

    def test_with_access_updates_tracking(self, basic_learning: Learning) -> None:
        """with_access() updates access tracking."""
        updated = basic_learning.with_access(activity_day=25)

        assert updated.use_count == basic_learning.use_count + 1
        assert updated.activity_day_accessed == 25
        assert updated.last_used is not None
        # Verify immutability - original unchanged
        assert basic_learning.use_count == 5
        assert basic_learning.activity_day_accessed == 15

    def test_with_activity_day_created_stamps(self, new_learning: Learning) -> None:
        """with_activity_day_created() stamps creation day."""
        # Create a learning with default activity_day_created
        bare = Learning(
            fact="Test fact",
            source_turns=(),
            confidence=0.8,
            category="fact",
        )
        stamped = bare.with_activity_day_created(42)

        assert stamped.activity_day_created == 42
        assert bare.activity_day_created == 0  # Default, unchanged

    def test_fields_propagate_through_with_methods(self, basic_learning: Learning) -> None:
        """All new fields propagate through with_* methods."""
        # Chain multiple with_* calls
        updated = (
            basic_learning.with_mention()
            .with_access(30)
            .with_embedding((0.1, 0.2, 0.3))
        )

        # Original fields preserved
        assert updated.fact == basic_learning.fact
        assert updated.confidence == basic_learning.confidence

        # New fields preserved through chain
        assert updated.mention_count == basic_learning.mention_count + 1
        assert updated.activity_day_accessed == 30
        assert updated.activity_day_created == basic_learning.activity_day_created
        assert updated.embedding == (0.1, 0.2, 0.3)


# === DAG Methods Tests ===


class TestDAGLearningMethods:
    """Tests for DAG find_learning and replace_learning methods."""

    def test_find_learning_exists(self) -> None:
        """find_learning returns learning when it exists."""
        dag = ConversationDAG()
        learning = Learning(
            fact="Test fact",
            source_turns=(),
            confidence=0.8,
            category="fact",
        )
        learning_id = dag.add_learning(learning)

        found = dag.find_learning(learning_id)
        assert found is not None
        assert found.fact == "Test fact"

    def test_find_learning_not_exists(self) -> None:
        """find_learning returns None when learning doesn't exist."""
        dag = ConversationDAG()
        found = dag.find_learning("nonexistent")
        assert found is None

    def test_replace_learning_success(self) -> None:
        """replace_learning updates learning in DAG."""
        dag = ConversationDAG()
        original = Learning(
            fact="Test fact",
            source_turns=(),
            confidence=0.8,
            category="fact",
            use_count=0,
        )
        learning_id = dag.add_learning(original)

        # Update with new access
        updated = original.with_access(activity_day=10)
        result = dag.replace_learning(original, updated)

        assert result is True
        found = dag.find_learning(learning_id)
        assert found is not None
        assert found.use_count == 1
        assert found.activity_day_accessed == 10

    def test_replace_learning_not_found(self) -> None:
        """replace_learning returns False when old learning not found."""
        dag = ConversationDAG()
        old = Learning(
            fact="Not in DAG",
            source_turns=(),
            confidence=0.8,
            category="fact",
        )
        new = old.with_mention()

        result = dag.replace_learning(old, new)
        assert result is False

    def test_replace_preserves_other_learnings(self) -> None:
        """replace_learning doesn't affect other learnings."""
        dag = ConversationDAG()
        learning1 = Learning(
            fact="First fact",
            source_turns=(),
            confidence=0.8,
            category="fact",
        )
        learning2 = Learning(
            fact="Second fact",
            source_turns=(),
            confidence=0.9,
            category="preference",
        )
        id1 = dag.add_learning(learning1)
        id2 = dag.add_learning(learning2)

        # Replace first learning
        updated1 = learning1.with_mention()
        dag.replace_learning(learning1, updated1)

        # Second learning unchanged
        found2 = dag.find_learning(id2)
        assert found2 is not None
        assert found2.fact == "Second fact"
        assert found2.mention_count == 0


# === DAG Serialization Tests for New Fields ===


class TestDAGSerializationNewFields:
    """Tests for DAG serialization of new graph scoring fields."""

    def test_roundtrip_new_fields(self) -> None:
        """New fields survive save/load roundtrip."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "dag.json"

            # Create DAG with learning that has all new fields
            dag = ConversationDAG()
            learning = Learning(
                fact="Test fact with all fields",
                source_turns=("turn1",),
                confidence=0.85,
                category="pattern",
                use_count=7,
                last_used="2025-01-15T10:30:00",
                mention_count=3,
                activity_day_created=10,
                activity_day_accessed=15,
                happens_at="2025-02-01T00:00:00",
                expires_at="2025-03-01T00:00:00",
            )
            dag.add_learning(learning)

            # Save and reload
            dag.save(path)
            loaded = ConversationDAG.load(path)

            # Verify all fields
            loaded_learning = list(loaded.learnings.values())[0]
            assert loaded_learning.fact == "Test fact with all fields"
            assert loaded_learning.mention_count == 3
            assert loaded_learning.activity_day_created == 10
            assert loaded_learning.activity_day_accessed == 15
            assert loaded_learning.happens_at == "2025-02-01T00:00:00"
            assert loaded_learning.expires_at == "2025-03-01T00:00:00"

    def test_roundtrip_default_fields(self) -> None:
        """New fields with defaults survive roundtrip."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "dag.json"

            # Create DAG with learning using defaults
            dag = ConversationDAG()
            learning = Learning(
                fact="Minimal learning",
                source_turns=(),
                confidence=0.5,
                category="fact",
            )
            dag.add_learning(learning)

            # Save and reload
            dag.save(path)
            loaded = ConversationDAG.load(path)

            # Verify defaults preserved
            loaded_learning = list(loaded.learnings.values())[0]
            assert loaded_learning.mention_count == 0
            assert loaded_learning.activity_day_created == 0
            assert loaded_learning.activity_day_accessed == 0
            assert loaded_learning.happens_at is None
            assert loaded_learning.expires_at is None
