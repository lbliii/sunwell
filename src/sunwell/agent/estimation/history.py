"""Execution history for duration calibration (RFC: Plan-Based Duration Estimation).

Tracks actual execution durations by plan profile to improve future estimates.
Uses similarity matching to find relevant historical executions.

Storage: .sunwell/metrics/execution_history.json
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from statistics import mean, stdev, quantiles
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sunwell.agent.core.task_graph import TaskGraph
    from sunwell.planning.naaru.planners.metrics import PlanMetrics
    from sunwell.planning.naaru.types import TaskMode

logger = logging.getLogger(__name__)

# Minimum samples needed for meaningful statistics
MIN_SAMPLES_FOR_CALIBRATION = 3
MIN_SAMPLES_FOR_CONFIDENCE = 5


@dataclass(frozen=True, slots=True)
class PlanProfile:
    """Fingerprint of a plan for matching similar past executions.

    Used to find historical executions with similar characteristics
    for calibration purposes.
    """

    task_count: int
    """Total number of tasks."""

    mode_distribution: tuple[tuple[str, int], ...]
    """Distribution of task modes, e.g., (("generate", 5), ("modify", 3))."""

    effort_distribution: tuple[tuple[str, int], ...]
    """Distribution of effort levels, e.g., (("medium", 4), ("large", 2))."""

    tool_count: int
    """Total unique tools across all tasks."""

    depth: int
    """Plan depth (critical path length)."""

    estimated_waves: int
    """Number of execution waves."""

    @classmethod
    def from_task_graph(
        cls,
        task_graph: TaskGraph,
        metrics: PlanMetrics,
    ) -> PlanProfile:
        """Create profile from task graph and metrics."""
        tasks = task_graph.tasks

        # Count modes
        mode_counts: dict[str, int] = {}
        for task in tasks:
            mode_name = task.mode.value if hasattr(task.mode, "value") else str(task.mode)
            mode_counts[mode_name] = mode_counts.get(mode_name, 0) + 1

        # Count effort levels
        effort_counts: dict[str, int] = {}
        for task in tasks:
            effort = task.estimated_effort.lower() if task.estimated_effort else "medium"
            effort_counts[effort] = effort_counts.get(effort, 0) + 1

        # Count unique tools
        all_tools: set[str] = set()
        for task in tasks:
            if task.tools:
                all_tools.update(task.tools)

        return cls(
            task_count=len(tasks),
            mode_distribution=tuple(sorted(mode_counts.items())),
            effort_distribution=tuple(sorted(effort_counts.items())),
            tool_count=len(all_tools),
            depth=metrics.depth,
            estimated_waves=metrics.estimated_waves,
        )

    def similarity_score(self, other: PlanProfile) -> float:
        """Calculate similarity to another profile (0.0 to 1.0).

        Higher score means more similar plans.
        """
        scores: list[float] = []

        # Task count similarity (within 2x is similar)
        if self.task_count > 0 and other.task_count > 0:
            ratio = min(self.task_count, other.task_count) / max(self.task_count, other.task_count)
            scores.append(ratio)
        else:
            scores.append(0.0)

        # Depth similarity
        if self.depth > 0 and other.depth > 0:
            ratio = min(self.depth, other.depth) / max(self.depth, other.depth)
            scores.append(ratio)
        else:
            scores.append(0.5)

        # Waves similarity
        if self.estimated_waves > 0 and other.estimated_waves > 0:
            ratio = min(self.estimated_waves, other.estimated_waves) / max(
                self.estimated_waves, other.estimated_waves
            )
            scores.append(ratio)
        else:
            scores.append(0.5)

        # Mode distribution overlap
        self_modes = dict(self.mode_distribution)
        other_modes = dict(other.mode_distribution)
        all_modes = set(self_modes.keys()) | set(other_modes.keys())
        if all_modes:
            overlap = sum(
                min(self_modes.get(m, 0), other_modes.get(m, 0)) for m in all_modes
            )
            total = max(sum(self_modes.values()), sum(other_modes.values()))
            scores.append(overlap / total if total > 0 else 0)
        else:
            scores.append(0.5)

        return mean(scores)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "task_count": self.task_count,
            "mode_distribution": list(self.mode_distribution),
            "effort_distribution": list(self.effort_distribution),
            "tool_count": self.tool_count,
            "depth": self.depth,
            "estimated_waves": self.estimated_waves,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlanProfile:
        """Deserialize from dictionary."""
        return cls(
            task_count=data["task_count"],
            mode_distribution=tuple(tuple(x) for x in data["mode_distribution"]),
            effort_distribution=tuple(tuple(x) for x in data["effort_distribution"]),
            tool_count=data["tool_count"],
            depth=data["depth"],
            estimated_waves=data["estimated_waves"],
        )


@dataclass(frozen=True, slots=True)
class HistorySample:
    """A single execution sample for calibration."""

    profile: PlanProfile
    """Plan profile at execution time."""

    estimated_seconds: int
    """What we estimated before execution."""

    actual_seconds: int
    """What actually happened."""

    timestamp: str
    """ISO timestamp when this was recorded."""

    @property
    def accuracy_ratio(self) -> float:
        """Ratio of actual/estimated (1.0 = perfect)."""
        if self.estimated_seconds <= 0:
            return 1.0
        return self.actual_seconds / self.estimated_seconds

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "profile": self.profile.to_dict(),
            "estimated_seconds": self.estimated_seconds,
            "actual_seconds": self.actual_seconds,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HistorySample:
        """Deserialize from dictionary."""
        return cls(
            profile=PlanProfile.from_dict(data["profile"]),
            estimated_seconds=data["estimated_seconds"],
            actual_seconds=data["actual_seconds"],
            timestamp=data["timestamp"],
        )


@dataclass(slots=True)
class ExecutionHistory:
    """Tracks actual execution durations by plan profile.

    Thread-safe with a lock for concurrent access.
    Persists to disk at .sunwell/metrics/execution_history.json.
    """

    samples: list[HistorySample] = field(default_factory=list)
    """All recorded samples."""

    _lock: threading.Lock = field(default_factory=threading.Lock)
    """Lock for thread-safe access."""

    _project_path: Path | None = field(default=None)
    """Project path for saving."""

    # Limit samples to prevent unbounded growth
    MAX_SAMPLES = 500

    def record(
        self,
        profile: PlanProfile,
        estimated_seconds: int,
        actual_seconds: int,
    ) -> None:
        """Record an execution sample.

        Args:
            profile: Plan profile at execution time
            estimated_seconds: What we estimated
            actual_seconds: What actually happened
        """
        sample = HistorySample(
            profile=profile,
            estimated_seconds=estimated_seconds,
            actual_seconds=actual_seconds,
            timestamp=datetime.now().isoformat(),
        )

        with self._lock:
            self.samples.append(sample)

            # Trim old samples if needed
            if len(self.samples) > self.MAX_SAMPLES:
                # Keep most recent samples
                self.samples = self.samples[-self.MAX_SAMPLES :]

    def calibration_factor(self, profile: PlanProfile) -> float | None:
        """Get calibration factor for similar profiles.

        Returns ratio of actual/estimated from similar past executions,
        or None if insufficient data.
        """
        similar = self._find_similar_samples(profile, min_similarity=0.6)

        if len(similar) < MIN_SAMPLES_FOR_CALIBRATION:
            return None

        ratios = [s.accuracy_ratio for s in similar]
        return mean(ratios)

    def confidence_interval(self, profile: PlanProfile) -> tuple[float, float] | None:
        """Get confidence interval (P25, P75) for similar profiles.

        Returns (low_ratio, high_ratio) from similar past executions,
        or None if insufficient data.
        """
        similar = self._find_similar_samples(profile, min_similarity=0.6)

        if len(similar) < MIN_SAMPLES_FOR_CONFIDENCE:
            return None

        ratios = sorted(s.accuracy_ratio for s in similar)

        # Use quantiles if enough samples, otherwise simple min/max with padding
        if len(ratios) >= 4:
            q = quantiles(ratios, n=4)  # Returns 3 quartiles
            return (q[0], q[2])  # P25, P75
        else:
            return (min(ratios) * 0.9, max(ratios) * 1.1)

    def _find_similar_samples(
        self,
        profile: PlanProfile,
        min_similarity: float = 0.5,
    ) -> list[HistorySample]:
        """Find samples with similar profiles."""
        with self._lock:
            return [
                s
                for s in self.samples
                if s.profile.similarity_score(profile) >= min_similarity
            ]

    def save(self, project_path: Path | None = None) -> int:
        """Save history to disk.

        Args:
            project_path: Project root directory (uses cached path if None)

        Returns:
            Number of samples saved
        """
        path = project_path or self._project_path
        if path is None:
            logger.warning("No project path for saving execution history")
            return 0

        metrics_dir = path / ".sunwell" / "metrics"
        metrics_dir.mkdir(parents=True, exist_ok=True)
        history_file = metrics_dir / "execution_history.json"

        with self._lock:
            data = {
                "version": 1,
                "samples": [s.to_dict() for s in self.samples],
            }

        try:
            with history_file.open("w") as f:
                json.dump(data, f, indent=2)
            return len(self.samples)
        except OSError as e:
            logger.warning("Failed to save execution history: %s", e)
            return 0

    @classmethod
    def load(cls, project_path: Path) -> ExecutionHistory:
        """Load history from disk.

        Args:
            project_path: Project root directory

        Returns:
            ExecutionHistory (empty if file doesn't exist)
        """
        history_file = project_path / ".sunwell" / "metrics" / "execution_history.json"

        history = cls(_project_path=project_path)

        if not history_file.exists():
            return history

        try:
            with history_file.open() as f:
                data = json.load(f)

            if data.get("version") != 1:
                logger.warning("Unknown execution history version: %s", data.get("version"))
                return history

            history.samples = [
                HistorySample.from_dict(s) for s in data.get("samples", [])
            ]

        except (OSError, json.JSONDecodeError, KeyError) as e:
            logger.warning("Failed to load execution history: %s", e)

        return history

    def get_stats(self) -> dict[str, Any]:
        """Get overall statistics."""
        with self._lock:
            if not self.samples:
                return {"sample_count": 0}

            ratios = [s.accuracy_ratio for s in self.samples]

            return {
                "sample_count": len(self.samples),
                "avg_accuracy_ratio": mean(ratios),
                "std_accuracy_ratio": stdev(ratios) if len(ratios) > 1 else 0,
                "min_accuracy_ratio": min(ratios),
                "max_accuracy_ratio": max(ratios),
            }
