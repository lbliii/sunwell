"""Tests for confidence scoring (RFC-100 Phase 2).

Tests the confidence aggregation and calibration components.
"""

from pathlib import Path

from sunwell.confidence import (
    CalibrationTracker,
    ConfidenceFeedback,
    ConfidenceLevel,
    Evidence,
    ModelNode,
    aggregate_confidence,
    score_to_band,
)
from sunwell.confidence.aggregation import ConfidenceFactors, calculate_confidence


class TestConfidenceLevel:
    """Tests for ConfidenceLevel enum."""

    def test_high_value(self) -> None:
        """HIGH should have string value 'high'."""
        assert ConfidenceLevel.HIGH.value == "high"

    def test_moderate_value(self) -> None:
        """MODERATE should have string value 'moderate'."""
        assert ConfidenceLevel.MODERATE.value == "moderate"

    def test_low_value(self) -> None:
        """LOW should have string value 'low'."""
        assert ConfidenceLevel.LOW.value == "low"

    def test_uncertain_value(self) -> None:
        """UNCERTAIN should have string value 'uncertain'."""
        assert ConfidenceLevel.UNCERTAIN.value == "uncertain"


class TestScoreToBand:
    """Tests for score_to_band function."""

    def test_high_band(self) -> None:
        """Scores >= 0.9 should be HIGH."""
        assert score_to_band(0.95) == ConfidenceLevel.HIGH
        assert score_to_band(0.90) == ConfidenceLevel.HIGH
        assert score_to_band(1.0) == ConfidenceLevel.HIGH

    def test_moderate_band(self) -> None:
        """Scores 0.7-0.89 should be MODERATE."""
        assert score_to_band(0.89) == ConfidenceLevel.MODERATE
        assert score_to_band(0.75) == ConfidenceLevel.MODERATE
        assert score_to_band(0.70) == ConfidenceLevel.MODERATE

    def test_low_band(self) -> None:
        """Scores 0.5-0.69 should be LOW."""
        assert score_to_band(0.69) == ConfidenceLevel.LOW
        assert score_to_band(0.55) == ConfidenceLevel.LOW
        assert score_to_band(0.50) == ConfidenceLevel.LOW

    def test_uncertain_band(self) -> None:
        """Scores < 0.5 should be UNCERTAIN."""
        assert score_to_band(0.49) == ConfidenceLevel.UNCERTAIN
        assert score_to_band(0.25) == ConfidenceLevel.UNCERTAIN
        assert score_to_band(0.0) == ConfidenceLevel.UNCERTAIN


class TestEvidence:
    """Tests for Evidence dataclass."""

    def test_create_evidence(self) -> None:
        """Should create evidence with all fields."""
        evidence = Evidence(
            source_file="src/module.py",
            line_range=(42, 50),
            reasoning="Function definition matches expected signature",
            evidence_type="code",
            weight=0.95,
        )

        assert evidence.source_file == "src/module.py"
        assert evidence.line_range == (42, 50)
        assert evidence.reasoning == "Function definition matches expected signature"
        assert evidence.evidence_type == "code"
        assert evidence.weight == 0.95

    def test_evidence_defaults(self) -> None:
        """Evidence should have sensible defaults."""
        evidence = Evidence(source_file="test.py")
        assert evidence.line_range is None
        assert evidence.reasoning == ""
        assert evidence.evidence_type == "code"
        assert evidence.weight == 1.0

    def test_evidence_to_dict(self) -> None:
        """Evidence should serialize to dict."""
        evidence = Evidence(
            source_file="test.py",
            line_range=(1, 10),
            reasoning="Test",
        )
        result = evidence.to_dict()
        assert result["source_file"] == "test.py"
        assert result["line_range"] == [1, 10]


class TestModelNode:
    """Tests for ModelNode dataclass."""

    def test_create_model_node(self) -> None:
        """Should create a model node."""
        evidence = Evidence(source_file="test.py", reasoning="Test")
        node = ModelNode(
            name="TestModule",
            confidence=0.85,
            provenance=(evidence,),
        )

        assert node.name == "TestModule"
        assert node.confidence == 0.85
        assert len(node.provenance) == 1

    def test_model_node_level(self) -> None:
        """Should calculate correct confidence level."""
        node_high = ModelNode(name="high", confidence=0.95)
        assert node_high.level == ConfidenceLevel.HIGH

        node_low = ModelNode(name="low", confidence=0.4)
        assert node_low.level == ConfidenceLevel.UNCERTAIN

    def test_model_node_emoji(self) -> None:
        """Should return correct emoji."""
        node = ModelNode(name="test", confidence=0.95)
        assert node.emoji == "🟢"

    def test_aggregate_confidence_no_children(self) -> None:
        """Node without children should return its own confidence."""
        node = ModelNode(name="test", confidence=0.8)
        assert node.aggregate_confidence() == 0.8

    def test_aggregate_confidence_with_children(self) -> None:
        """Node with children should aggregate conservatively."""
        child1 = ModelNode(name="c1", confidence=0.9)
        child2 = ModelNode(name="c2", confidence=0.7)
        parent = ModelNode(name="parent", confidence=0.95, children=(child1, child2))

        # Parent confidence capped by children's average
        # Children avg = (0.9 + 0.7) / 2 = 0.8
        # min(0.95, 0.8) = 0.8
        assert parent.aggregate_confidence() == 0.8


class TestAggregateConfidence:
    """Tests for aggregate_confidence function."""

    def test_aggregate_empty_list(self) -> None:
        """Empty list should return 1.0 (no uncertainty)."""
        assert aggregate_confidence([]) == 1.0

    def test_aggregate_conservative(self) -> None:
        """Conservative strategy should return minimum."""
        nodes = [
            ModelNode(name="a", confidence=0.9),
            ModelNode(name="b", confidence=0.7),
            ModelNode(name="c", confidence=0.8),
        ]
        result = aggregate_confidence(nodes, strategy="conservative")
        assert result == 0.7

    def test_aggregate_average(self) -> None:
        """Average strategy should return mean."""
        nodes = [
            ModelNode(name="a", confidence=0.9),
            ModelNode(name="b", confidence=0.6),
        ]
        result = aggregate_confidence(nodes, strategy="average")
        assert result == 0.75

    def test_aggregate_weighted(self) -> None:
        """Weighted strategy should weight by evidence count."""
        evidence = Evidence(source_file="test.py")
        nodes = [
            ModelNode(name="a", confidence=0.9, provenance=(evidence, evidence)),  # 3 weight
            ModelNode(name="b", confidence=0.6, provenance=()),  # 1 weight
        ]
        result = aggregate_confidence(nodes, strategy="weighted")
        # (0.9 * 3 + 0.6 * 1) / 4 = 3.3 / 4 = 0.825
        assert abs(result - 0.825) < 0.01


class TestCalculateConfidence:
    """Tests for calculate_confidence function."""

    def test_calculate_with_strong_evidence(self) -> None:
        """Strong evidence should yield high evidence score."""
        evidence = [
            Evidence(source_file="a.py", weight=1.0),
            Evidence(source_file="b.py", weight=1.0),
            Evidence(source_file="c.py", weight=1.0),
        ]
        score, factors = calculate_confidence(evidence)
        assert factors.evidence_score == 1.0  # 3/3 = max

    def test_calculate_with_weak_evidence(self) -> None:
        """Weak evidence should yield lower score."""
        evidence = [Evidence(source_file="a.py", weight=0.5)]
        score, factors = calculate_confidence(evidence)
        assert factors.evidence_score < 0.5

    def test_calculate_with_no_evidence(self) -> None:
        """No evidence should yield 0 evidence score."""
        score, factors = calculate_confidence([])
        assert factors.evidence_score == 0.0

    def test_calculate_with_fresh_content(self) -> None:
        """Recent updates should yield high recency score."""
        evidence = [Evidence(source_file="a.py")]
        score, factors = calculate_confidence(evidence, days_since_update=3)
        assert factors.recency_score == 1.0

    def test_calculate_with_stale_content(self) -> None:
        """Old content should yield lower recency score."""
        evidence = [Evidence(source_file="a.py")]
        score, factors = calculate_confidence(evidence, days_since_update=365)
        assert factors.recency_score == 0.3

    def test_calculate_with_passing_tests(self) -> None:
        """Passing tests should yield high test score."""
        evidence = [Evidence(source_file="a.py")]
        score, factors = calculate_confidence(evidence, test_results=[True, True, True])
        assert factors.test_score == 1.0

    def test_calculate_with_failing_tests(self) -> None:
        """Failing tests should yield low test score."""
        evidence = [Evidence(source_file="a.py")]
        score, factors = calculate_confidence(evidence, test_results=[False, False])
        assert factors.test_score == 0.0


class TestConfidenceFactors:
    """Tests for ConfidenceFactors dataclass."""

    def test_total_calculation(self) -> None:
        """Should calculate weighted total correctly."""
        factors = ConfidenceFactors(
            evidence_score=1.0,      # 40%
            consistency_score=1.0,   # 30%
            recency_score=1.0,       # 15%
            test_score=1.0,          # 15%
        )
        assert factors.total == 1.0

    def test_total_partial(self) -> None:
        """Should calculate weighted partial score."""
        factors = ConfidenceFactors(
            evidence_score=0.5,      # 0.5 * 0.4 = 0.2
            consistency_score=0.5,   # 0.5 * 0.3 = 0.15
            recency_score=0.5,       # 0.5 * 0.15 = 0.075
            test_score=0.5,          # 0.5 * 0.15 = 0.075
        )
        assert factors.total == 0.5


class TestConfidenceFeedback:
    """Tests for ConfidenceFeedback dataclass."""

    def test_create_feedback(self) -> None:
        """Should create feedback record."""
        feedback = ConfidenceFeedback(
            claim_id="test-claim-1",
            predicted_confidence=0.9,
            user_judgment="correct",
            claim_text="The function returns a string",
        )

        assert feedback.claim_id == "test-claim-1"
        assert feedback.predicted_confidence == 0.9
        assert feedback.user_judgment == "correct"

    def test_feedback_to_dict(self) -> None:
        """Should serialize to dict."""
        feedback = ConfidenceFeedback(
            claim_id="test",
            predicted_confidence=0.8,
            user_judgment="incorrect",
        )
        result = feedback.to_dict()
        assert result["claim_id"] == "test"
        assert result["predicted_confidence"] == 0.8
        assert result["user_judgment"] == "incorrect"

    def test_feedback_from_dict(self) -> None:
        """Should deserialize from dict."""
        data = {
            "claim_id": "test",
            "predicted_confidence": 0.75,
            "user_judgment": "partially_correct",
            "timestamp": "2026-01-22T12:00:00",
        }
        feedback = ConfidenceFeedback.from_dict(data)
        assert feedback.claim_id == "test"
        assert feedback.predicted_confidence == 0.75


class TestCalibrationTracker:
    """Tests for CalibrationTracker."""

    def test_record_feedback(self, tmp_path: Path) -> None:
        """Should record feedback."""
        tracker = CalibrationTracker(storage_path=tmp_path / "calibration.json")
        feedback = ConfidenceFeedback(
            claim_id="test",
            predicted_confidence=0.9,
            user_judgment="correct",
        )
        tracker.record_feedback(feedback)

        assert len(tracker._feedback) == 1

    def test_metrics_empty(self, tmp_path: Path) -> None:
        """Empty tracker should return empty metrics."""
        tracker = CalibrationTracker(storage_path=tmp_path / "calibration.json")
        metrics = tracker.get_metrics()
        assert metrics.total_samples == 0

    def test_metrics_with_feedback(self, tmp_path: Path) -> None:
        """Should calculate metrics from feedback."""
        tracker = CalibrationTracker(storage_path=tmp_path / "calibration.json")

        # Add some feedback
        tracker.record_feedback(ConfidenceFeedback(
            claim_id="1", predicted_confidence=0.95, user_judgment="correct"
        ))
        tracker.record_feedback(ConfidenceFeedback(
            claim_id="2", predicted_confidence=0.8, user_judgment="correct"
        ))
        tracker.record_feedback(ConfidenceFeedback(
            claim_id="3", predicted_confidence=0.7, user_judgment="incorrect"
        ))

        metrics = tracker.get_metrics()
        assert metrics.total_samples == 3
        assert metrics.correct_count == 2
        assert metrics.incorrect_count == 1

    def test_brier_score_perfect(self, tmp_path: Path) -> None:
        """Perfect predictions should have low Brier score."""
        tracker = CalibrationTracker(storage_path=tmp_path / "calibration.json")

        # High confidence, all correct
        for i in range(5):
            tracker.record_feedback(ConfidenceFeedback(
                claim_id=f"correct-{i}",
                predicted_confidence=0.95,
                user_judgment="correct",
            ))

        metrics = tracker.get_metrics()
        # Brier = mean((0.95 - 1.0)^2) = 0.0025
        assert metrics.brier_score < 0.01

    def test_brier_score_poor(self, tmp_path: Path) -> None:
        """Overconfident wrong predictions should have high Brier score."""
        tracker = CalibrationTracker(storage_path=tmp_path / "calibration.json")

        # High confidence, all wrong
        for i in range(5):
            tracker.record_feedback(ConfidenceFeedback(
                claim_id=f"wrong-{i}",
                predicted_confidence=0.95,
                user_judgment="incorrect",
            ))

        metrics = tracker.get_metrics()
        # Brier = mean((0.95 - 0.0)^2) = 0.9025
        assert metrics.brier_score > 0.8

    def test_persistence(self, tmp_path: Path) -> None:
        """Should persist and reload feedback."""
        storage = tmp_path / "calibration.json"

        # Create tracker and add feedback
        tracker1 = CalibrationTracker(storage_path=storage)
        tracker1.record_feedback(ConfidenceFeedback(
            claim_id="persistent",
            predicted_confidence=0.8,
            user_judgment="correct",
        ))

        # Create new tracker with same storage
        tracker2 = CalibrationTracker(storage_path=storage)
        assert len(tracker2._feedback) == 1
        assert tracker2._feedback[0].claim_id == "persistent"
