"""Track model performance per task category for RFC-015.

Enables data-driven model selection by recording which models
perform best for different types of tasks.
"""


from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sunwell.foundation.utils import safe_jsonl_append, safe_jsonl_load


@dataclass(frozen=True, slots=True)
class ModelPerformanceEntry:
    """Single performance data point for a model execution."""

    model: str
    task_category: str
    success: bool
    latency_ms: int
    timestamp: datetime
    user_edited: bool = False  # Did user modify the output?

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "model": self.model,
            "task_category": self.task_category,
            "success": self.success,
            "latency_ms": self.latency_ms,
            "user_edited": self.user_edited,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModelPerformanceEntry:
        """Create from dict."""
        return cls(
            model=data["model"],
            task_category=data["task_category"],
            success=data["success"],
            latency_ms=data["latency_ms"],
            user_edited=data.get("user_edited", False),
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )


@dataclass(slots=True)
class ModelPerformanceTracker:
    """Track and analyze model performance across task categories.

    Records execution data and computes statistics to inform
    model selection decisions.

    Example:
        >>> tracker = ModelPerformanceTracker()
        >>> tracker.record("claude-3-5-sonnet", "introspection", True, 1200)
        >>> stats = tracker.get_stats("claude-3-5-sonnet", "introspection")
        >>> best = tracker.get_best_model("introspection")
    """

    storage_path: Path | None = None
    entries: list[ModelPerformanceEntry] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Load existing data if storage path provided."""
        if self.storage_path:
            self.storage_path.mkdir(parents=True, exist_ok=True)
            self._load_from_storage()

    def record(
        self,
        model: str,
        task_category: str,
        success: bool,
        latency_ms: int,
        user_edited: bool = False,
    ) -> None:
        """Record a performance data point.

        Args:
            model: Model identifier (e.g., 'claude-3-5-sonnet')
            task_category: Task category (e.g., 'introspection', 'code_generation')
            success: Whether the execution succeeded
            latency_ms: Execution time in milliseconds
            user_edited: Whether user modified the output (indicates lower quality)
        """
        entry = ModelPerformanceEntry(
            model=model,
            task_category=task_category,
            success=success,
            latency_ms=latency_ms,
            user_edited=user_edited,
        )
        self.entries.append(entry)

        if self.storage_path:
            self._append_to_storage(entry)

    def get_stats(self, model: str, task_category: str) -> dict[str, Any]:
        """Get performance stats for a model on a task category.

        Args:
            model: Model identifier
            task_category: Task category

        Returns:
            Dict with count, success_rate, edit_rate, avg_latency_ms, p95_latency_ms
        """
        relevant = [
            e for e in self.entries
            if e.model == model and e.task_category == task_category
        ]

        if not relevant:
            return {"count": 0}

        successes = sum(1 for e in relevant if e.success)
        edits = sum(1 for e in relevant if e.user_edited)
        latencies = [e.latency_ms for e in relevant]

        # Calculate p95 latency
        sorted_latencies = sorted(latencies)
        p95_idx = int(len(sorted_latencies) * 0.95)
        p95_latency = sorted_latencies[p95_idx] if len(latencies) > 20 else max(latencies)

        return {
            "count": len(relevant),
            "success_rate": round(successes / len(relevant), 3),
            "edit_rate": round(edits / len(relevant), 3),
            "avg_latency_ms": round(sum(latencies) / len(latencies), 1),
            "p95_latency_ms": p95_latency,
        }

    def get_best_model(
        self,
        task_category: str,
        min_samples: int = 5,
    ) -> str | None:
        """Get the best performing model for a task category.

        Ranks by: (1 - edit_rate) * success_rate
        Higher is better.

        Args:
            task_category: Task category to optimize for
            min_samples: Minimum number of samples required

        Returns:
            Model identifier or None if insufficient data
        """
        # Single pass: aggregate by model O(n)
        model_data: dict[str, tuple[int, int, int]] = {}  # (count, successes, edits)
        for e in self.entries:
            if e.task_category != task_category:
                continue
            count, successes, edits = model_data.get(e.model, (0, 0, 0))
            model_data[e.model] = (
                count + 1,
                successes + (1 if e.success else 0),
                edits + (1 if e.user_edited else 0),
            )

        # Calculate scores O(m) where m = unique models
        scores: dict[str, float] = {}
        for model, (count, successes, edits) in model_data.items():
            if count >= min_samples:
                success_rate = successes / count
                edit_rate = edits / count
                scores[model] = (1 - edit_rate) * success_rate

        if not scores:
            return None

        return max(scores, key=scores.get)

    def compare_models(
        self,
        task_category: str,
        scope: str = "all",
    ) -> list[dict[str, Any]]:
        """Compare all models on a task category.

        Args:
            task_category: Task category to compare
            scope: Time scope ('session', 'day', 'week', 'all')

        Returns:
            List of model stats sorted by quality score (best first)
        """
        entries = self._filter_by_scope(self.entries, scope)
        models = {
            e.model for e in entries
            if e.task_category == task_category
        }

        comparisons = []
        for model in models:
            # Calculate stats for this model in the filtered scope
            relevant = [
                e for e in entries
                if e.model == model and e.task_category == task_category
            ]

            if not relevant:
                continue

            successes = sum(1 for e in relevant if e.success)
            edits = sum(1 for e in relevant if e.user_edited)
            latencies = [e.latency_ms for e in relevant]

            stats = {
                "model": model,
                "count": len(relevant),
                "success_rate": round(successes / len(relevant), 3),
                "edit_rate": round(edits / len(relevant), 3),
                "avg_latency_ms": round(sum(latencies) / len(latencies), 1),
            }

            # Quality score for sorting
            stats["quality_score"] = round(
                (1 - stats["edit_rate"]) * stats["success_rate"],
                3,
            )
            comparisons.append(stats)

        return sorted(
            comparisons,
            key=lambda x: x["quality_score"],
            reverse=True,
        )

    def get_summary(self, scope: str = "all") -> dict[str, Any]:
        """Get overall performance summary.

        Args:
            scope: Time scope ('session', 'day', 'week', 'all')

        Returns:
            Summary dict with models, categories, and recommendations
        """
        entries = self._filter_by_scope(self.entries, scope)

        if not entries:
            return {"message": "No performance data available"}

        models = {e.model for e in entries}
        categories = {e.task_category for e in entries}

        # Find best model per category
        best_per_category: dict[str, str | None] = {}
        for category in categories:
            category_entries = [e for e in entries if e.task_category == category]
            if len(category_entries) >= 5:
                best = self.get_best_model(category)
                best_per_category[category] = best

        return {
            "total_entries": len(entries),
            "models_tracked": list(models),
            "categories_tracked": list(categories),
            "best_per_category": best_per_category,
            "scope": scope,
        }

    def _filter_by_scope(
        self,
        entries: list[ModelPerformanceEntry],
        scope: str,
    ) -> list[ModelPerformanceEntry]:
        """Filter entries by time scope."""
        if scope == "session" or scope == "all":
            return entries

        now = datetime.now()
        if scope == "day":
            cutoff = now - timedelta(days=1)
        elif scope == "week":
            cutoff = now - timedelta(weeks=1)
        else:
            return entries

        return [e for e in entries if e.timestamp > cutoff]

    def _load_from_storage(self) -> None:
        """Load entries from storage file."""
        if not self.storage_path:
            return

        data_file = self.storage_path / "model_performance.jsonl"
        for data in safe_jsonl_load(data_file):
            try:
                self.entries.append(ModelPerformanceEntry.from_dict(data))
            except KeyError:
                continue

    def _append_to_storage(self, entry: ModelPerformanceEntry) -> None:
        """Append an entry to storage file."""
        if not self.storage_path:
            return

        data_file = self.storage_path / "model_performance.jsonl"
        safe_jsonl_append(entry.to_dict(), data_file)

    def clear(self) -> None:
        """Clear all entries (useful for testing)."""
        self.entries.clear()

        if self.storage_path:
            data_file = self.storage_path / "model_performance.jsonl"
            if data_file.exists():
                data_file.unlink()
