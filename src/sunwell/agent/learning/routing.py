"""Routing outcome store for adaptive threshold learning.

This module provides:
- RoutingOutcome: Records outcome of a routing decision
- RoutingOutcomeStore: Thread-safe store with threshold suggestion
"""

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class RoutingOutcome:
    """Records outcome of a routing decision.

    Immutable record that captures what routing strategy was selected,
    the confidence score, and whether the task succeeded.
    """

    task_type: str
    """Task category (e.g., 'code_generation', 'question_answering')."""

    confidence: float
    """Input confidence score (0.0-1.0)."""

    strategy: str
    """Selected strategy: 'vortex', 'interference', or 'single_shot'."""

    success: bool
    """Whether the task completed successfully."""

    tool_count: int
    """Number of tool calls made."""

    validation_passed: bool
    """Whether validation gates passed."""

    timestamp: datetime = field(default_factory=datetime.now)
    """When this outcome was recorded."""

    @property
    def id(self) -> str:
        """Content-addressable ID for deduplication."""
        return f"{self.timestamp.isoformat()}:{self.task_type}:{self.strategy}"


# Default routing thresholds (matches loop.py)
DEFAULT_VORTEX_THRESHOLD = 0.6
DEFAULT_INTERFERENCE_THRESHOLD = 0.85


@dataclass(slots=True)
class RoutingOutcomeStore:
    """Thread-safe store for routing outcomes with threshold suggestion.

    Tracks historical routing decisions and their outcomes to suggest
    optimal confidence thresholds for routing strategies.

    RFC-122: Thread-safe operations for Python 3.14t free-threading support.
    """

    outcomes: list[RoutingOutcome] = field(default_factory=list)
    """All recorded outcomes."""

    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    """Lock for thread-safe mutations."""

    _outcome_ids: set[str] = field(default_factory=set, init=False)
    """Set of outcome IDs for O(1) deduplication."""

    def record(self, outcome: RoutingOutcome) -> None:
        """Record a routing outcome (thread-safe, O(1) deduplication).

        Args:
            outcome: The routing outcome to record
        """
        with self._lock:
            if outcome.id not in self._outcome_ids:
                self._outcome_ids.add(outcome.id)
                self.outcomes.append(outcome)

    def get_success_rate(
        self,
        strategy: str,
        confidence_range: tuple[float, float],
    ) -> float:
        """Get success rate for a strategy within a confidence range.

        Args:
            strategy: The routing strategy ('vortex', 'interference', 'single_shot')
            confidence_range: (min, max) confidence bounds

        Returns:
            Success rate (0.0-1.0) or -1.0 if no data
        """
        min_conf, max_conf = confidence_range

        with self._lock:
            matching = [
                o for o in self.outcomes
                if o.strategy == strategy
                and min_conf <= o.confidence < max_conf
            ]

        if not matching:
            return -1.0

        successes = sum(1 for o in matching if o.success)
        return successes / len(matching)

    def get_strategy_stats(self) -> dict[str, dict[str, float]]:
        """Get success statistics for each strategy.

        Returns:
            Dict mapping strategy -> {count, success_rate, avg_confidence}
        """
        with self._lock:
            outcomes_snapshot = list(self.outcomes)

        stats: dict[str, dict[str, float]] = {}

        for strategy in ("vortex", "interference", "single_shot"):
            matching = [o for o in outcomes_snapshot if o.strategy == strategy]
            if matching:
                successes = sum(1 for o in matching if o.success)
                stats[strategy] = {
                    "count": len(matching),
                    "success_rate": successes / len(matching),
                    "avg_confidence": sum(o.confidence for o in matching) / len(matching),
                }

        return stats

    def suggest_thresholds(
        self,
        min_samples: int = 20,
        bucket_size: float = 0.1,
    ) -> tuple[float, float]:
        """Analyze outcomes to suggest optimal thresholds.

        Strategy:
        1. Bucket outcomes by confidence (0.0-0.1, 0.1-0.2, etc.)
        2. For each bucket, find which strategy had highest success rate
        3. Find transition points where optimal strategy changes
        4. Return thresholds at those transition points

        Args:
            min_samples: Minimum total samples before suggesting changes
            bucket_size: Size of confidence buckets for analysis

        Returns:
            (vortex_threshold, interference_threshold)
            Returns defaults if insufficient data
        """
        with self._lock:
            if len(self.outcomes) < min_samples:
                return (DEFAULT_VORTEX_THRESHOLD, DEFAULT_INTERFERENCE_THRESHOLD)
            outcomes_snapshot = list(self.outcomes)

        # Build buckets: confidence range -> strategy -> (success, total)
        buckets: dict[float, dict[str, tuple[int, int]]] = {}

        for outcome in outcomes_snapshot:
            # Round confidence to bucket
            bucket = round(outcome.confidence // bucket_size * bucket_size, 2)

            if bucket not in buckets:
                buckets[bucket] = {}

            if outcome.strategy not in buckets[bucket]:
                buckets[bucket][outcome.strategy] = (0, 0)

            success, total = buckets[bucket][outcome.strategy]
            if outcome.success:
                success += 1
            total += 1
            buckets[bucket][outcome.strategy] = (success, total)

        # Find best strategy per bucket
        best_per_bucket: dict[float, tuple[str, float]] = {}

        for bucket, strategies in sorted(buckets.items()):
            best_strategy = None
            best_rate = -1.0

            for strategy, (success, total) in strategies.items():
                if total >= 3:  # Minimum samples per bucket per strategy
                    rate = success / total
                    if rate > best_rate:
                        best_rate = rate
                        best_strategy = strategy

            if best_strategy:
                best_per_bucket[bucket] = (best_strategy, best_rate)

        if len(best_per_bucket) < 3:
            return (DEFAULT_VORTEX_THRESHOLD, DEFAULT_INTERFERENCE_THRESHOLD)

        # Find transition points
        sorted_buckets = sorted(best_per_bucket.keys())
        vortex_threshold = DEFAULT_VORTEX_THRESHOLD
        interference_threshold = DEFAULT_INTERFERENCE_THRESHOLD

        prev_strategy = None
        for bucket in sorted_buckets:
            strategy, _rate = best_per_bucket[bucket]

            if prev_strategy == "vortex" and strategy in ("interference", "single_shot"):
                # Transition from vortex to something else
                vortex_threshold = bucket

            if prev_strategy == "interference" and strategy == "single_shot":
                # Transition from interference to single_shot
                interference_threshold = bucket

            prev_strategy = strategy

        # Ensure thresholds are in valid range and order
        vortex_threshold = max(0.3, min(0.7, vortex_threshold))
        interference_threshold = max(vortex_threshold + 0.1, min(0.95, interference_threshold))

        return (vortex_threshold, interference_threshold)

    def get_recent_outcomes(self, limit: int = 50) -> list[RoutingOutcome]:
        """Get the most recent outcomes.

        Args:
            limit: Maximum number of outcomes to return

        Returns:
            List of recent outcomes (newest first)
        """
        with self._lock:
            return list(reversed(self.outcomes[-limit:]))

    def save_to_disk(self, base_path: Path | None = None) -> int:
        """Persist outcomes to .sunwell/intelligence/routing_outcomes.jsonl.

        Args:
            base_path: Project root (defaults to cwd)

        Returns:
            Number of outcomes saved
        """
        with self._lock:
            if not self.outcomes:
                return 0
            outcomes_snapshot = list(self.outcomes)

        base = base_path or Path.cwd()
        intel_dir = base / ".sunwell" / "intelligence"
        intel_dir.mkdir(parents=True, exist_ok=True)

        outcomes_path = intel_dir / "routing_outcomes.jsonl"

        # Load existing IDs to avoid duplicates
        existing_ids: set[str] = set()
        if outcomes_path.exists():
            with open(outcomes_path, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            data = json.loads(line)
                            existing_ids.add(data.get("id", ""))
                        except json.JSONDecodeError:
                            pass

        # Append new outcomes
        saved = 0
        with open(outcomes_path, "a", encoding="utf-8") as f:
            for outcome in outcomes_snapshot:
                if outcome.id not in existing_ids:
                    record = {
                        "id": outcome.id,
                        "task_type": outcome.task_type,
                        "confidence": outcome.confidence,
                        "strategy": outcome.strategy,
                        "success": outcome.success,
                        "tool_count": outcome.tool_count,
                        "validation_passed": outcome.validation_passed,
                        "timestamp": outcome.timestamp.isoformat(),
                    }
                    f.write(json.dumps(record) + "\n")
                    saved += 1

        return saved

    def load_from_disk(self, base_path: Path | None = None) -> int:
        """Load outcomes from .sunwell/intelligence/routing_outcomes.jsonl.

        Args:
            base_path: Project root (defaults to cwd)

        Returns:
            Number of outcomes loaded
        """
        base = base_path or Path.cwd()
        outcomes_path = base / ".sunwell" / "intelligence" / "routing_outcomes.jsonl"

        if not outcomes_path.exists():
            return 0

        loaded = 0
        with open(outcomes_path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    outcome = RoutingOutcome(
                        task_type=data["task_type"],
                        confidence=data["confidence"],
                        strategy=data["strategy"],
                        success=data["success"],
                        tool_count=data.get("tool_count", 0),
                        validation_passed=data.get("validation_passed", True),
                        timestamp=datetime.fromisoformat(data["timestamp"]),
                    )
                    self.record(outcome)  # record() is thread-safe and deduplicates
                    loaded += 1
                except (json.JSONDecodeError, KeyError, ValueError):
                    pass

        return loaded

    def clear(self) -> None:
        """Clear all outcomes (thread-safe)."""
        with self._lock:
            self.outcomes.clear()
            self._outcome_ids.clear()
