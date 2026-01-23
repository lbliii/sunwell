"""Demo history persistence (RFC-095 Phase 2).

Saves demo results to .sunwell/demo_history/ for tracking improvements
and sharing results.
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DemoHistoryEntry:
    """A saved demo result.

    Attributes:
        timestamp: ISO timestamp when the demo was run.
        model_name: Name of the model used.
        task_name: Name or "custom" for the task.
        task_prompt: The prompt used.
        single_shot_score: Score from single-shot method.
        sunwell_score: Score from Sunwell method.
        improvement_percent: Percentage improvement.
        single_shot_code: Generated code from single-shot.
        sunwell_code: Generated code from Sunwell.
        single_shot_time_ms: Time taken for single-shot in ms.
        sunwell_time_ms: Time taken for Sunwell in ms.
    """

    timestamp: str
    model_name: str
    task_name: str
    task_prompt: str
    single_shot_score: float
    sunwell_score: float
    improvement_percent: float
    single_shot_code: str
    sunwell_code: str
    single_shot_time_ms: int
    sunwell_time_ms: int

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> DemoHistoryEntry:
        """Create from dictionary."""
        return cls(**data)


def get_history_dir() -> Path:
    """Get the demo history directory, creating if needed.

    Returns:
        Path to .sunwell/demo_history/
    """
    history_dir = Path.cwd() / ".sunwell" / "demo_history"
    history_dir.mkdir(parents=True, exist_ok=True)
    return history_dir


def save_demo_result(
    comparison,  # DemoComparison
    model_name: str,
) -> Path:
    """Save a demo comparison result to history.

    Args:
        comparison: The DemoComparison result.
        model_name: Name of the model used.

    Returns:
        Path to the saved JSON file.
    """
    history_dir = get_history_dir()

    # Create entry
    timestamp = datetime.now().isoformat()
    entry = DemoHistoryEntry(
        timestamp=timestamp,
        model_name=model_name,
        task_name=comparison.task.name,
        task_prompt=comparison.task.prompt,
        single_shot_score=comparison.single_score.score,
        sunwell_score=comparison.sunwell_score.score,
        improvement_percent=comparison.improvement_percent,
        single_shot_code=comparison.single_shot.code,
        sunwell_code=comparison.sunwell.code,
        single_shot_time_ms=comparison.single_shot.time_ms,
        sunwell_time_ms=comparison.sunwell.time_ms,
    )

    # Generate filename from timestamp
    filename = f"{timestamp.replace(':', '-').replace('.', '-')}.json"
    file_path = history_dir / filename

    # Save
    file_path.write_text(json.dumps(entry.to_dict(), indent=2))

    return file_path


def load_history(limit: int = 10) -> list[DemoHistoryEntry]:
    """Load recent demo history entries.

    Args:
        limit: Maximum number of entries to load.

    Returns:
        List of DemoHistoryEntry, most recent first.
    """
    history_dir = get_history_dir()

    if not history_dir.exists():
        return []

    # Get JSON files sorted by name (which is timestamp-based)
    files = sorted(history_dir.glob("*.json"), reverse=True)[:limit]

    entries = []
    for file_path in files:
        try:
            data = json.loads(file_path.read_text())
            entries.append(DemoHistoryEntry.from_dict(data))
        except (json.JSONDecodeError, TypeError, KeyError):
            # Skip corrupted files
            continue

    return entries


def get_history_summary() -> dict:
    """Get a summary of demo history.

    Returns:
        Dictionary with summary statistics.
    """
    entries = load_history(limit=100)

    if not entries:
        return {"total_runs": 0}

    improvements = [e.improvement_percent for e in entries]
    single_scores = [e.single_shot_score for e in entries]
    sunwell_scores = [e.sunwell_score for e in entries]

    return {
        "total_runs": len(entries),
        "avg_improvement": sum(improvements) / len(improvements),
        "max_improvement": max(improvements),
        "avg_single_shot_score": sum(single_scores) / len(single_scores),
        "avg_sunwell_score": sum(sunwell_scores) / len(sunwell_scores),
        "models_used": list({e.model_name for e in entries}),
        "tasks_run": list({e.task_name for e in entries}),
    }
