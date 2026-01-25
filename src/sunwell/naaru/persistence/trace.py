"""Trace logging for execution events."""

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_PLANS_DIR = Path(".sunwell/plans")


@dataclass(slots=True)
class TraceLogger:
    """Append-only event logging for execution trace.

    Writes JSONL format for easy streaming and analysis.

    Example:
        >>> logger = TraceLogger(goal_hash="abc123")
        >>> logger.log_event("plan_created", artifact_count=5)
        >>> logger.log_event("wave_start", wave=0, artifacts=["A", "B"])
    """

    goal_hash: str
    base_path: Path = field(default_factory=lambda: DEFAULT_PLANS_DIR)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def trace_path(self) -> Path:
        """Get path to trace file."""
        return self.base_path / f"{self.goal_hash}.trace.jsonl"

    def log_event(self, event: str, **kwargs: Any) -> None:
        """Log an event to the trace file.

        Args:
            event: Event type (plan_created, wave_start, artifact_complete, etc.)
            **kwargs: Additional event data
        """
        record = {
            "ts": datetime.now().isoformat(),
            "event": event,
            **kwargs,
        }

        with self._lock:
            self.base_path.mkdir(parents=True, exist_ok=True)
            with open(self.trace_path, "a") as f:
                f.write(json.dumps(record) + "\n")

    def read_events(self) -> list[dict[str, Any]]:
        """Read all events from trace file.

        Returns:
            List of event records
        """
        if not self.trace_path.exists():
            return []

        events = []
        with open(self.trace_path) as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))
        return events

    def clear(self) -> None:
        """Clear the trace file."""
        with self._lock:
            if self.trace_path.exists():
                self.trace_path.unlink()
