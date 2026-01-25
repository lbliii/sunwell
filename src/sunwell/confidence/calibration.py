"""Confidence calibration and feedback tracking (RFC-100).

Tracks user feedback on confidence predictions to:
1. Measure accuracy (Brier score)
2. Adjust thresholds based on actual performance
3. Learn from user corrections

Target: 90% correlation between predicted confidence and actual correctness.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ConfidenceFeedback:
    """User feedback on a confidence prediction.

    Collected when users verify or dispute confidence claims.
    Used to calibrate the confidence scoring system.
    """

    claim_id: str
    """Unique identifier for the claim being evaluated."""

    predicted_confidence: float
    """The confidence score we predicted (0.0-1.0)."""

    user_judgment: Literal["correct", "incorrect", "partially_correct"]
    """User's assessment of the claim's accuracy."""

    timestamp: datetime = field(default_factory=datetime.now)
    """When the feedback was provided."""

    claim_text: str = ""
    """The text of the claim being evaluated."""

    evidence_files: tuple[str, ...] = ()
    """Files referenced as evidence for the claim."""

    user_notes: str = ""
    """Optional user notes explaining their judgment."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "claim_id": self.claim_id,
            "predicted_confidence": self.predicted_confidence,
            "user_judgment": self.user_judgment,
            "timestamp": self.timestamp.isoformat(),
            "claim_text": self.claim_text,
            "evidence_files": list(self.evidence_files),
            "user_notes": self.user_notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConfidenceFeedback:
        """Deserialize from dictionary."""
        return cls(
            claim_id=data["claim_id"],
            predicted_confidence=data["predicted_confidence"],
            user_judgment=data["user_judgment"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            claim_text=data.get("claim_text", ""),
            evidence_files=tuple(data.get("evidence_files", [])),
            user_notes=data.get("user_notes", ""),
        )


@dataclass(frozen=True, slots=True)
class CalibrationMetrics:
    """Metrics for evaluating confidence calibration."""

    total_samples: int = 0
    """Total number of feedback samples."""

    correct_count: int = 0
    """Number of claims judged correct."""

    incorrect_count: int = 0
    """Number of claims judged incorrect."""

    partial_count: int = 0
    """Number of claims judged partially correct."""

    brier_score: float = 0.0
    """Brier score (lower is better, 0.0 is perfect)."""

    accuracy_by_band: tuple[tuple[str, float], ...] = ()
    """Accuracy breakdown by confidence band as (band, accuracy) pairs."""

    override_rate: float = 0.0
    """Rate at which users override/dispute claims."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "total_samples": self.total_samples,
            "correct_count": self.correct_count,
            "incorrect_count": self.incorrect_count,
            "partial_count": self.partial_count,
            "brier_score": self.brier_score,
            "accuracy_by_band": dict(self.accuracy_by_band),
            "override_rate": self.override_rate,
        }


class CalibrationTracker:
    """Tracks and analyzes confidence calibration over time.

    Stores feedback in `.sunwell/confidence_calibration.json` and
    provides metrics for system improvement.
    """

    def __init__(self, storage_path: Path | None = None):
        """Initialize the calibration tracker.

        Args:
            storage_path: Path to store calibration data.
                         Defaults to ~/.sunwell/confidence_calibration.json
        """
        if storage_path is None:
            storage_path = Path.home() / ".sunwell" / "confidence_calibration.json"

        self.storage_path = storage_path
        self._feedback: list[ConfidenceFeedback] = []
        self._load()

    def record_feedback(self, feedback: ConfidenceFeedback) -> None:
        """Record user feedback on a confidence prediction.

        Args:
            feedback: The feedback to record
        """
        self._feedback.append(feedback)
        self._save()

        logger.debug(
            f"Recorded feedback: {feedback.claim_id} - "
            f"{feedback.predicted_confidence:.0%} -> {feedback.user_judgment}"
        )

    def get_metrics(self, since: datetime | None = None) -> CalibrationMetrics:
        """Calculate calibration metrics.

        Args:
            since: Only include feedback since this time (optional)

        Returns:
            CalibrationMetrics with accuracy statistics
        """
        feedback = self._feedback
        if since:
            feedback = [f for f in feedback if f.timestamp >= since]

        if not feedback:
            return CalibrationMetrics()

        # Count judgments
        correct = sum(1 for f in feedback if f.user_judgment == "correct")
        incorrect = sum(1 for f in feedback if f.user_judgment == "incorrect")
        partial = sum(1 for f in feedback if f.user_judgment == "partially_correct")

        # Calculate Brier score
        # Brier = mean((prediction - actual)^2)
        # where actual is 1 for correct, 0.5 for partial, 0 for incorrect
        brier_sum = 0.0
        for f in feedback:
            actual = {"correct": 1.0, "partially_correct": 0.5, "incorrect": 0.0}[
                f.user_judgment
            ]
            brier_sum += (f.predicted_confidence - actual) ** 2

        brier_score = brier_sum / len(feedback)

        # Calculate accuracy by confidence band
        bands = {
            "high": [],      # 90-100%
            "moderate": [],  # 70-89%
            "low": [],       # 50-69%
            "uncertain": [], # <50%
        }

        for f in feedback:
            pct = f.predicted_confidence * 100
            if pct >= 90:
                band = "high"
            elif pct >= 70:
                band = "moderate"
            elif pct >= 50:
                band = "low"
            else:
                band = "uncertain"

            # Score: 1 for correct, 0.5 for partial, 0 for incorrect
            score = {"correct": 1.0, "partially_correct": 0.5, "incorrect": 0.0}[
                f.user_judgment
            ]
            bands[band].append(score)

        accuracy_by_band = tuple(
            (band, sum(scores) / len(scores) if scores else 0.0)
            for band, scores in bands.items()
        )

        # Override rate (incorrect + partial) / total
        override_rate = (incorrect + partial) / len(feedback) if feedback else 0.0

        return CalibrationMetrics(
            total_samples=len(feedback),
            correct_count=correct,
            incorrect_count=incorrect,
            partial_count=partial,
            brier_score=brier_score,
            accuracy_by_band=accuracy_by_band,
            override_rate=override_rate,
        )

    def should_request_feedback(
        self, predicted_confidence: float, claim_id: str
    ) -> bool:
        """Determine if we should request user feedback on a claim.

        Prioritizes requesting feedback on:
        1. 🟡 Moderate confidence (70-89%) - most informative
        2. 🟠 Low confidence (50-69%) - need calibration
        3. Claims not yet verified

        Args:
            predicted_confidence: The confidence score
            claim_id: Unique identifier for the claim

        Returns:
            True if we should request feedback
        """
        # Skip if already have feedback for this claim
        if any(f.claim_id == claim_id for f in self._feedback):
            return False

        pct = predicted_confidence * 100

        # Focus on moderate and low confidence bands
        if 50 <= pct < 90:
            # Sample rate based on confidence (lower = more likely to ask)
            import random
            sample_rate = 0.3 if pct < 70 else 0.2
            return random.random() < sample_rate

        return False

    def get_recent_feedback(self, limit: int = 10) -> list[ConfidenceFeedback]:
        """Get most recent feedback items.

        Args:
            limit: Maximum number of items to return

        Returns:
            List of recent feedback items
        """
        return sorted(
            self._feedback, key=lambda f: f.timestamp, reverse=True
        )[:limit]

    def _load(self) -> None:
        """Load feedback from storage."""
        if not self.storage_path.exists():
            self._feedback = []
            return

        try:
            data = json.loads(self.storage_path.read_text())
            self._feedback = [ConfidenceFeedback.from_dict(f) for f in data.get("feedback", [])]
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to load calibration data: {e}")
            self._feedback = []

    def _save(self) -> None:
        """Save feedback to storage."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": 1,
            "updated_at": datetime.now().isoformat(),
            "feedback": [f.to_dict() for f in self._feedback],
        }

        self.storage_path.write_text(json.dumps(data, indent=2))


def create_feedback_prompt(
    claim_text: str,
    predicted_confidence: float,
) -> str:
    """Create a user-facing prompt for confidence feedback.

    Args:
        claim_text: The claim being evaluated
        predicted_confidence: Our predicted confidence

    Returns:
        Formatted prompt string
    """
    pct = predicted_confidence * 100
    return f"""We said: "{claim_text}" ({pct:.0f}% confident).

Was this accurate?
  [Yes]       - Claim was correct
  [Partially] - Partially correct or needs nuance
  [No]        - Claim was incorrect"""
