"""Inference Metrics for Model Discovery (RFC-081).

Tracks inference performance per model on user's hardware:
- Tokens per second
- Time to first token (TTFT)
- Quality metrics (gate pass rates)

Helps users discover which models work best for their hardware and tasks.
Supports disk persistence for cross-session model discovery.
"""

import json
import platform
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean, stdev
from typing import Any, Literal


@dataclass
class InferenceSample:
    """A single inference sample."""

    duration_s: float
    tokens: int
    tokens_per_second: float
    ttft_ms: int | None = None


@dataclass
class InferenceMetrics:
    """Track inference performance metrics.

    Collects samples per model to calculate statistics and
    estimate generation times.

    Example:
        >>> metrics = InferenceMetrics()
        >>> metrics.record("gpt-oss:20b", duration_s=15.2, tokens=450, ttft_ms=1800)
        >>> stats = metrics.get_model_stats("gpt-oss:20b")
        >>> print(f"Average: {stats['avg_tokens_per_second']:.1f} tok/s")
    """

    _samples: dict[str, list[InferenceSample]] = field(
        default_factory=lambda: defaultdict(list)
    )

    def record(
        self,
        model: str,
        duration_s: float,
        tokens: int,
        ttft_ms: int | None = None,
    ) -> None:
        """Record an inference sample.

        Args:
            model: Model identifier (e.g., "gpt-oss:20b")
            duration_s: Total generation time in seconds
            tokens: Total tokens generated
            ttft_ms: Time to first token in milliseconds (optional)
        """
        tps = tokens / duration_s if duration_s > 0 else 0
        sample = InferenceSample(
            duration_s=duration_s,
            tokens=tokens,
            tokens_per_second=tps,
            ttft_ms=ttft_ms,
        )
        self._samples[model].append(sample)

    def get_model_stats(self, model: str) -> dict[str, Any]:
        """Get statistics for a model.

        Args:
            model: Model identifier

        Returns:
            Dict with statistics (empty if no samples)
        """
        samples = self._samples.get(model, [])
        if not samples:
            return {}

        tps_values = [s.tokens_per_second for s in samples]
        ttft_values = [s.ttft_ms for s in samples if s.ttft_ms is not None]

        return {
            "sample_count": len(samples),
            "avg_tokens_per_second": mean(tps_values),
            "std_tokens_per_second": stdev(tps_values) if len(tps_values) > 1 else 0,
            "avg_ttft_ms": mean(ttft_values) if ttft_values else None,
            "total_tokens": sum(s.tokens for s in samples),
            "total_time_s": sum(s.duration_s for s in samples),
        }

    def estimate_time(
        self,
        model: str,
        prompt_tokens: int,
        expected_output: int = 500,
    ) -> float | None:
        """Estimate generation time based on historical data.

        Args:
            model: Model identifier
            prompt_tokens: Number of prompt tokens (unused currently)
            expected_output: Expected output tokens

        Returns:
            Estimated time in seconds, or None if no data
        """
        stats = self.get_model_stats(model)
        if not stats or stats["avg_tokens_per_second"] == 0:
            return None

        # Estimate: TTFT + output_tokens / tok_per_sec
        ttft_s = (stats.get("avg_ttft_ms") or 1000) / 1000
        generation_s = expected_output / stats["avg_tokens_per_second"]
        return ttft_s + generation_s

    def get_all_models(self) -> list[str]:
        """Get all models with recorded samples."""
        return list(self._samples.keys())

    def save_to_disk(self, project_path: Path) -> int:
        """Save metrics to disk for cross-session persistence.

        Args:
            project_path: Project root directory

        Returns:
            Number of models saved
        """
        metrics_dir = project_path / ".sunwell" / "metrics"
        metrics_dir.mkdir(parents=True, exist_ok=True)

        metrics_file = metrics_dir / "inference_metrics.json"

        # Convert samples to serializable format
        data = {
            "version": 1,
            "hardware": _get_hardware_id(),
            "models": {},
        }

        for model, samples in self._samples.items():
            data["models"][model] = [
                {
                    "duration_s": s.duration_s,
                    "tokens": s.tokens,
                    "tokens_per_second": s.tokens_per_second,
                    "ttft_ms": s.ttft_ms,
                }
                for s in samples
            ]

        metrics_file.write_text(json.dumps(data, indent=2))
        return len(self._samples)

    def load_from_disk(self, project_path: Path) -> int:
        """Load metrics from disk.

        Args:
            project_path: Project root directory

        Returns:
            Number of models loaded
        """
        metrics_file = project_path / ".sunwell" / "metrics" / "inference_metrics.json"

        if not metrics_file.exists():
            return 0

        try:
            data = json.loads(metrics_file.read_text())

            # Check version compatibility
            if data.get("version", 0) != 1:
                return 0

            # Load samples
            for model, samples_data in data.get("models", {}).items():
                for s in samples_data:
                    sample = InferenceSample(
                        duration_s=s["duration_s"],
                        tokens=s["tokens"],
                        tokens_per_second=s["tokens_per_second"],
                        ttft_ms=s.get("ttft_ms"),
                    )
                    self._samples[model].append(sample)

            return len(data.get("models", {}))

        except (json.JSONDecodeError, KeyError):
            return 0

    def merge_from(self, other: "InferenceMetrics") -> int:
        """Merge samples from another metrics instance.

        Args:
            other: Another InferenceMetrics instance

        Returns:
            Number of samples merged
        """
        count = 0
        for model, samples in other._samples.items():
            self._samples[model].extend(samples)
            count += len(samples)
        return count


@dataclass
class ModelPerformanceProfile:
    """Accumulated performance profile for a model on this hardware.

    Tracks both speed and quality metrics to help users find
    their optimal model.
    """

    model: str
    hardware: str = field(default_factory=lambda: _get_hardware_id())

    # Speed metrics
    samples: int = 0
    total_tokens: int = 0
    total_time_s: float = 0
    avg_tokens_per_second: float = 0
    avg_ttft_ms: float = 0

    # Quality metrics (from validation gates)
    tasks_completed: int = 0
    gates_passed: int = 0
    gates_failed: int = 0

    @property
    def gate_pass_rate(self) -> float | None:
        """Quality proxy: how often does generated code pass gates?"""
        total = self.gates_passed + self.gates_failed
        return self.gates_passed / total if total > 0 else None

    @property
    def quality_speed_score(self) -> float | None:
        """Combined score: quality * speed (higher = better).

        Normalizes speed to 0-1 range (assuming 100 tok/s is "fast").
        """
        if self.gate_pass_rate is None:
            return None
        # Normalize speed to 0-1 range
        speed_normalized = min(1.0, self.avg_tokens_per_second / 100)
        return self.gate_pass_rate * speed_normalized

    def update_from_sample(
        self,
        duration_s: float,
        tokens: int,
        ttft_ms: int | None = None,
    ) -> None:
        """Update profile with a new sample."""
        self.samples += 1
        self.total_tokens += tokens
        self.total_time_s += duration_s

        # Recalculate averages
        if self.total_time_s > 0:
            self.avg_tokens_per_second = self.total_tokens / self.total_time_s

        if ttft_ms is not None:
            # Running average for TTFT
            if self.avg_ttft_ms == 0:
                self.avg_ttft_ms = float(ttft_ms)
            else:
                self.avg_ttft_ms = (self.avg_ttft_ms * (self.samples - 1) + ttft_ms) / self.samples

    def record_gate_result(self, passed: bool) -> None:
        """Record a validation gate result."""
        if passed:
            self.gates_passed += 1
        else:
            self.gates_failed += 1

    def record_task_complete(self) -> None:
        """Record a completed task."""
        self.tasks_completed += 1


def _get_hardware_id() -> str:
    """Get a hardware identifier string."""
    machine = platform.machine()
    system = platform.system()

    if system == "Darwin":
        # Try to get Apple Silicon info
        processor = platform.processor()
        if "arm" in machine.lower():
            return f"Apple Silicon ({machine})"
        return f"macOS ({processor})"
    elif system == "Linux":
        return f"Linux ({machine})"
    elif system == "Windows":
        return f"Windows ({machine})"

    return f"{system} ({machine})"


def recommend_model(
    profiles: dict[str, ModelPerformanceProfile],
    task_type: str,
    user_preference: Literal["speed", "quality", "balanced"] = "balanced",
) -> str | None:
    """Recommend a model based on user's hardware and preferences.

    Args:
        profiles: Dict of model name to performance profile
        task_type: Type of task (currently unused)
        user_preference: Optimization preference

    Returns:
        Recommended model name, or None if no data
    """
    candidates = [p for p in profiles.values() if p.samples >= 5]
    if not candidates:
        return None

    if user_preference == "speed":
        return max(candidates, key=lambda p: p.avg_tokens_per_second).model
    elif user_preference == "quality":
        return max(candidates, key=lambda p: p.gate_pass_rate or 0).model
    else:  # balanced
        return max(candidates, key=lambda p: p.quality_speed_score or 0).model


def save_profiles_to_disk(
    profiles: dict[str, ModelPerformanceProfile],
    project_path: Path,
) -> int:
    """Save model performance profiles to disk.

    Args:
        profiles: Dict of model name to performance profile
        project_path: Project root directory

    Returns:
        Number of profiles saved
    """
    metrics_dir = project_path / ".sunwell" / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)

    profiles_file = metrics_dir / "model_profiles.json"

    data = {
        "version": 1,
        "profiles": {
            name: {
                "model": p.model,
                "hardware": p.hardware,
                "samples": p.samples,
                "total_tokens": p.total_tokens,
                "total_time_s": p.total_time_s,
                "avg_tokens_per_second": p.avg_tokens_per_second,
                "avg_ttft_ms": p.avg_ttft_ms,
                "tasks_completed": p.tasks_completed,
                "gates_passed": p.gates_passed,
                "gates_failed": p.gates_failed,
            }
            for name, p in profiles.items()
        },
    }

    profiles_file.write_text(json.dumps(data, indent=2))
    return len(profiles)


def load_profiles_from_disk(project_path: Path) -> dict[str, ModelPerformanceProfile]:
    """Load model performance profiles from disk.

    Args:
        project_path: Project root directory

    Returns:
        Dict of model name to performance profile
    """
    profiles_file = project_path / ".sunwell" / "metrics" / "model_profiles.json"

    if not profiles_file.exists():
        return {}

    try:
        data = json.loads(profiles_file.read_text())

        if data.get("version", 0) != 1:
            return {}

        profiles = {}
        for name, p in data.get("profiles", {}).items():
            profile = ModelPerformanceProfile(
                model=p["model"],
                hardware=p.get("hardware", _get_hardware_id()),
                samples=p.get("samples", 0),
                total_tokens=p.get("total_tokens", 0),
                total_time_s=p.get("total_time_s", 0),
                avg_tokens_per_second=p.get("avg_tokens_per_second", 0),
                avg_ttft_ms=p.get("avg_ttft_ms", 0),
                tasks_completed=p.get("tasks_completed", 0),
                gates_passed=p.get("gates_passed", 0),
                gates_failed=p.get("gates_failed", 0),
            )
            profiles[name] = profile

        return profiles

    except (json.JSONDecodeError, KeyError):
        return {}
