"""Confidence calibration for Reasoned Decisions (RFC-073).

Calibrates reasoner confidence based on historical accuracy. If decisions
at 80% confidence are only correct 60% of the time, adjusts future
confidence scores downward.

Good calibration means: predicted confidence ≈ actual accuracy.
- Model says 80% confident → should be right ~80% of time
- If actually right 60% → calibration curve shifts confidence down

Example:
    >>> calibrator = ConfidenceCalibrator()
    >>> calibrator.record_outcome(decision, was_correct=True)
    >>> calibrator.record_outcome(decision2, was_correct=False)
    >>> calibrator.get_calibration_curve()
    {0.8: 0.65, 0.9: 0.82, ...}  # predicted → actual
"""

import json
import sqlite3
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.reasoning.decisions import DecisionType, ReasonedDecision


@dataclass
class CalibrationRecord:
    """A single calibration data point.

    Attributes:
        decision_type: Type of decision.
        predicted_confidence: What the model said (0-1).
        was_correct: Whether the decision was actually correct.
        timestamp: When the decision was made.
        context_hash: Hash of context for deduplication.
    """

    decision_type: str
    predicted_confidence: float
    was_correct: bool
    timestamp: float
    context_hash: str = ""


@dataclass
class CalibrationStats:
    """Calibration statistics for a confidence band.

    Attributes:
        predicted_range: The confidence band (e.g., (0.75, 0.85)).
        count: Number of decisions in this band.
        correct_count: Number of correct decisions.
        actual_accuracy: Actual accuracy (correct_count / count).
        calibration_error: |predicted - actual| (lower is better).
    """

    predicted_range: tuple[float, float]
    count: int
    correct_count: int
    actual_accuracy: float
    calibration_error: float


@dataclass
class ConfidenceCalibrator:
    """Calibrate reasoner confidence based on historical accuracy.

    Maintains a history of (confidence, outcome) pairs and computes
    calibration curves to adjust future confidence scores.

    Calibration target: ±10% accuracy (90% confidence should be
    correct 80-100% of the time).

    Storage: SQLite database at `.sunwell/reasoning/calibration.db`

    Example:
        >>> calibrator = ConfidenceCalibrator()
        >>> calibrator.record_outcome(decision, was_correct=True)
        >>> calibrated = calibrator.calibrate(0.8)
        >>> print(calibrated)  # Might be 0.65 if historically 80% predictions
                               # are only right 65% of the time
    """

    db_path: Path | None = None
    """Path to SQLite database for persistence."""

    band_size: float = 0.1
    """Size of confidence bands for bucketing (default: 10%)."""

    _records: list[CalibrationRecord] = field(default_factory=list, repr=False)
    """In-memory records (flushed to DB periodically)."""

    _conn: sqlite3.Connection | None = field(default=None, repr=False)
    """Database connection."""

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    """Thread safety lock."""

    _calibration_cache: dict[str, dict[float, float]] = field(
        default_factory=dict, repr=False
    )
    """Cached calibration curves by decision type."""

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS calibration_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        decision_type TEXT NOT NULL,
        predicted_confidence REAL NOT NULL,
        was_correct INTEGER NOT NULL,
        timestamp REAL NOT NULL,
        context_hash TEXT,
        created_at REAL DEFAULT (unixepoch('now'))
    );

    CREATE INDEX IF NOT EXISTS idx_calibration_type
        ON calibration_records(decision_type);
    CREATE INDEX IF NOT EXISTS idx_calibration_confidence
        ON calibration_records(predicted_confidence);
    """

    def __post_init__(self) -> None:
        """Initialize database if path provided."""
        if self.db_path:
            self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite database."""
        if not self.db_path:
            return

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(self.SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._flush_records()
            self._conn.close()
            self._conn = None

    def __enter__(self) -> ConfidenceCalibrator:
        """Context manager entry."""
        return self

    def __exit__(self, *args) -> None:
        """Context manager exit."""
        self.close()

    def record_outcome(
        self,
        decision: ReasonedDecision,
        was_correct: bool,
        context_hash: str = "",
    ) -> None:
        """Record the outcome of a decision for calibration.

        Args:
            decision: The decision that was made.
            was_correct: Whether the decision was actually correct.
            context_hash: Optional hash for deduplication.
        """
        record = CalibrationRecord(
            decision_type=decision.decision_type.value,
            predicted_confidence=decision.confidence,
            was_correct=was_correct,
            timestamp=time.time(),
            context_hash=context_hash,
        )

        with self._lock:
            self._records.append(record)

            # Flush to DB if we have enough records
            if len(self._records) >= 100:
                self._flush_records()

            # Invalidate cache for this decision type
            self._calibration_cache.pop(decision.decision_type.value, None)

    def _flush_records(self) -> None:
        """Flush in-memory records to database."""
        if not self._conn or not self._records:
            return

        try:
            self._conn.executemany(
                """
                INSERT INTO calibration_records
                    (decision_type, predicted_confidence, was_correct, timestamp, context_hash)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        r.decision_type, r.predicted_confidence,
                        int(r.was_correct), r.timestamp, r.context_hash,
                    )
                    for r in self._records
                ],
            )
            self._conn.commit()
            self._records.clear()
        except sqlite3.Error:
            pass  # Silent fail, keep records in memory

    def calibrate(
        self,
        confidence: float,
        decision_type: DecisionType | str | None = None,
    ) -> float:
        """Calibrate a confidence score based on historical accuracy.

        If we've seen decisions at this confidence level be wrong more
        often than predicted, adjust downward (and vice versa).

        Args:
            confidence: Raw confidence score (0-1).
            decision_type: Optional decision type for type-specific calibration.

        Returns:
            Calibrated confidence score.
        """
        if decision_type:
            type_str = decision_type if isinstance(decision_type, str) else decision_type.value
        else:
            type_str = None

        curve = self._get_calibration_curve(type_str)

        if not curve:
            return confidence  # No data, return raw

        # Find the nearest band
        band = self._get_band(confidence)
        if band in curve:
            return curve[band]

        # Interpolate if band not found
        return self._interpolate(confidence, curve)

    def _get_calibration_curve(
        self,
        decision_type: str | None = None,
    ) -> dict[float, float]:
        """Get calibration curve (predicted → actual accuracy).

        Args:
            decision_type: Optional type filter.

        Returns:
            Dict mapping predicted confidence (band midpoint) to actual accuracy.
        """
        cache_key = decision_type or "__all__"

        if cache_key in self._calibration_cache:
            return self._calibration_cache[cache_key]

        # Compute curve from data
        records = self._load_records(decision_type)
        curve = self._compute_curve(records)

        self._calibration_cache[cache_key] = curve
        return curve

    def _load_records(
        self,
        decision_type: str | None = None,
    ) -> list[CalibrationRecord]:
        """Load records from database and memory."""
        records = list(self._records)  # In-memory first

        if self._conn:
            try:
                if decision_type:
                    rows = self._conn.execute(
                        "SELECT * FROM calibration_records WHERE decision_type = ?",
                        (decision_type,),
                    ).fetchall()
                else:
                    rows = self._conn.execute(
                        "SELECT * FROM calibration_records"
                    ).fetchall()

                for row in rows:
                    records.append(
                        CalibrationRecord(
                            decision_type=row["decision_type"],
                            predicted_confidence=row["predicted_confidence"],
                            was_correct=bool(row["was_correct"]),
                            timestamp=row["timestamp"],
                            context_hash=row["context_hash"] or "",
                        )
                    )
            except sqlite3.Error:
                pass  # Fall back to in-memory only

        return records

    def _compute_curve(
        self,
        records: list[CalibrationRecord],
    ) -> dict[float, float]:
        """Compute calibration curve from records.

        Groups records into bands and computes actual accuracy per band.
        """
        if not records:
            return {}

        # Group by confidence band
        bands: dict[float, list[bool]] = defaultdict(list)
        for record in records:
            band = self._get_band(record.predicted_confidence)
            bands[band].append(record.was_correct)

        # Compute accuracy per band
        curve = {}
        for band, outcomes in bands.items():
            if len(outcomes) >= 5:  # Require minimum samples
                accuracy = sum(outcomes) / len(outcomes)
                curve[band] = accuracy

        return curve

    def _get_band(self, confidence: float) -> float:
        """Get the band midpoint for a confidence value.

        Args:
            confidence: Raw confidence (0-1).

        Returns:
            Band midpoint (e.g., 0.75 for confidence in [0.7, 0.8)).
        """
        band_index = int(confidence / self.band_size)
        return (band_index + 0.5) * self.band_size

    def _interpolate(
        self,
        confidence: float,
        curve: dict[float, float],
    ) -> float:
        """Interpolate calibrated confidence from curve.

        Args:
            confidence: Raw confidence.
            curve: Calibration curve.

        Returns:
            Interpolated calibrated confidence.
        """
        if not curve:
            return confidence

        sorted_bands = sorted(curve.keys())

        # Clamp to curve bounds
        if confidence <= sorted_bands[0]:
            return curve[sorted_bands[0]]
        if confidence >= sorted_bands[-1]:
            return curve[sorted_bands[-1]]

        # Linear interpolation
        for i, band in enumerate(sorted_bands[:-1]):
            next_band = sorted_bands[i + 1]
            if band <= confidence < next_band:
                t = (confidence - band) / (next_band - band)
                return curve[band] + t * (curve[next_band] - curve[band])

        return confidence

    def get_calibration_stats(
        self,
        decision_type: str | None = None,
    ) -> list[CalibrationStats]:
        """Get calibration statistics by confidence band.

        Args:
            decision_type: Optional type filter.

        Returns:
            List of CalibrationStats per band.
        """
        records = self._load_records(decision_type)

        if not records:
            return []

        # Group by band
        bands: dict[float, list[bool]] = defaultdict(list)
        for record in records:
            band = self._get_band(record.predicted_confidence)
            bands[band].append(record.was_correct)

        # Compute stats
        stats = []
        for band, outcomes in sorted(bands.items()):
            count = len(outcomes)
            correct_count = sum(outcomes)
            actual = correct_count / count if count > 0 else 0

            # Band range
            low = band - self.band_size / 2
            high = band + self.band_size / 2
            predicted = band  # Midpoint

            stats.append(
                CalibrationStats(
                    predicted_range=(low, high),
                    count=count,
                    correct_count=correct_count,
                    actual_accuracy=actual,
                    calibration_error=abs(predicted - actual),
                )
            )

        return stats

    def get_overall_calibration_error(
        self,
        decision_type: str | None = None,
    ) -> float:
        """Get weighted average calibration error.

        Target: ≤10% (predictions should be within 10% of actual accuracy).

        Args:
            decision_type: Optional type filter.

        Returns:
            Weighted average calibration error (0-1).
        """
        stats = self.get_calibration_stats(decision_type)

        if not stats:
            return 0.0

        total_weight = sum(s.count for s in stats)
        if total_weight == 0:
            return 0.0

        weighted_error = sum(s.calibration_error * s.count for s in stats)
        return weighted_error / total_weight

    def is_well_calibrated(
        self,
        decision_type: str | None = None,
        threshold: float = 0.10,
    ) -> bool:
        """Check if calibration meets target threshold.

        Args:
            decision_type: Optional type filter.
            threshold: Maximum acceptable calibration error (default: 10%).

        Returns:
            True if calibration error ≤ threshold.
        """
        return self.get_overall_calibration_error(decision_type) <= threshold

    def to_dict(self) -> dict:
        """Export calibration data as dictionary."""
        return {
            "curves": {
                type_: dict(curve)
                for type_, curve in self._calibration_cache.items()
            },
            "stats": {
                type_: [
                    {
                        "predicted_range": s.predicted_range,
                        "count": s.count,
                        "correct_count": s.correct_count,
                        "actual_accuracy": s.actual_accuracy,
                        "calibration_error": s.calibration_error,
                    }
                    for s in self.get_calibration_stats(type_ if type_ != "__all__" else None)
                ]
                for type_ in list(self._calibration_cache.keys()) or ["__all__"]
            },
        }

    def save_json(self, path: Path) -> None:
        """Save calibration data to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load_json(cls, path: Path) -> ConfidenceCalibrator:
        """Load calibration data from JSON file."""
        calibrator = cls()

        if not path.exists():
            return calibrator

        try:
            with open(path) as f:
                data = json.load(f)

            # Restore cached curves
            for type_, curve in data.get("curves", {}).items():
                calibrator._calibration_cache[type_] = {
                    float(k): v for k, v in curve.items()
                }

        except (json.JSONDecodeError, OSError):
            pass

        return calibrator

    def clear(self) -> None:
        """Clear all calibration data."""
        with self._lock:
            self._records.clear()
            self._calibration_cache.clear()

            if self._conn:
                try:
                    self._conn.execute("DELETE FROM calibration_records")
                    self._conn.commit()
                except sqlite3.Error:
                    pass
