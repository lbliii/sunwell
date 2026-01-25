"""Analysis Knowledge for Self-Knowledge Architecture.

RFC-085: Analyze Sunwell's runtime behavior and performance.

Provides capabilities to:
- Record execution events
- Analyze recent failures with root cause identification
- Detect behavioral patterns
- Track model performance
- Diagnose errors with source-level analysis
"""

import json
import threading
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from sunwell.self.types import (
    Diagnosis,
    ExecutionEvent,
    FailureReport,
    FailureSeverity,
    Hotspot,
    ModelReport,
    PatternReport,
    SourceLocation,
)

# Known failure patterns with root cause mapping
KNOWN_FAILURE_PATTERNS: dict[str, dict[str, str]] = {
    "Permission denied": {
        "category": "security",
        "root_cause": "Operation requires elevated trust level",
        "suggestion": "Check trust level. Use --trust-level workspace or shell flag",
    },
    "Rate limit": {
        "category": "throttling",
        "root_cause": "Too many requests in time window",
        "suggestion": "Wait before retrying. Consider batching operations.",
    },
    "Not found": {
        "category": "file_system",
        "root_cause": "File or directory does not exist at expected path",
        "suggestion": "Verify path exists. Check for typos or wrong workspace.",
    },
    "Timeout": {
        "category": "performance",
        "root_cause": "Operation exceeded time limit",
        "suggestion": "Operation took too long. Consider breaking into smaller steps.",
    },
    "Connection": {
        "category": "network",
        "root_cause": "Network connectivity issue",
        "suggestion": "Check internet connection. Verify API keys for web tools.",
    },
    "PathSecurityError": {
        "category": "security",
        "root_cause": "Path attempted to escape workspace jail",
        "suggestion": "Use paths within the workspace root only.",
    },
    "Invalid JSON": {
        "category": "parsing",
        "root_cause": "Tool arguments were malformed",
        "suggestion": "Check argument types match tool schema.",
    },
}


@dataclass(slots=True)
class AnalysisKnowledge:
    """Analyze Sunwell's runtime behavior.

    Thread-safe for recording events. Uses internal locking for file writes.

    Usage via Self singleton:
        >>> from sunwell.self import Self
        >>> Self.get().analysis.recent_failures()
        >>> Self.get().analysis.patterns("session")
    """

    storage: Path

    # Internal state
    _events: list[ExecutionEvent] = field(default_factory=list, init=False)
    _failures: list[FailureReport] = field(default_factory=list, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def __post_init__(self) -> None:
        """Initialize storage directory and load existing data."""
        self.storage.mkdir(parents=True, exist_ok=True)
        self._load_from_storage()

    def record_execution(self, event: ExecutionEvent) -> None:
        """Record an execution event for analysis.

        Thread-safe — uses internal locking for concurrent writes.

        Args:
            event: ExecutionEvent to record

        Example:
            >>> Self.get().analysis.record_execution(ExecutionEvent(
            ...     tool_name="read_file",
            ...     success=True,
            ...     latency_ms=45,
            ... ))
        """
        with self._lock:
            self._events.append(event)
            self._append_event_to_storage(event)

            # If it's a failure, also record a failure report
            if not event.success and event.error:
                report = self._create_failure_report(event)
                self._failures.append(report)
                self._append_failure_to_storage(report)

    def recent_failures(self, limit: int = 10) -> list[FailureReport]:
        """Get recent failures with root cause analysis.

        Args:
            limit: Maximum number of failures to return

        Returns:
            List of FailureReport objects, newest first

        Example:
            >>> failures = Self.get().analysis.recent_failures()
            >>> failures[0].error
            'PathSecurityError: Path escapes workspace'
            >>> failures[0].root_cause
            'Path attempted to escape workspace jail'
        """
        return list(reversed(self._failures[-limit:]))

    def patterns(self, scope: str = "session") -> PatternReport:
        """Analyze behavioral patterns.

        Args:
            scope: Time scope ('session', 'day', 'week', 'all')

        Returns:
            PatternReport with tool usage, error hotspots, sequences

        Example:
            >>> patterns = Self.get().analysis.patterns("week")
            >>> patterns.most_used_tools
            [('read_file', 1523), ('search_files', 892), ...]
        """
        events = self._filter_by_scope(self._events, scope)

        if not events:
            return PatternReport(
                most_used_tools=[],
                error_hotspots=[],
                common_sequences=[],
                total_executions=0,
                success_rate=0.0,
                avg_latency_ms=0.0,
            )

        # Tool usage counts
        tool_counts = Counter(e.tool_name for e in events)
        most_used = tool_counts.most_common(20)

        # Error hotspots (group errors by source location)
        error_events = [e for e in events if not e.success]
        hotspot_counts: dict[str, int] = {}
        for e in error_events:
            # Use tool name as proxy for hotspot (source location would require tracing)
            key = e.tool_name
            hotspot_counts[key] = hotspot_counts.get(key, 0) + 1

        hotspots = [
            Hotspot(
                module="sunwell.tools.handlers",
                method=tool,
                errors=count,
                last_error=datetime.now(),  # Would need actual timestamps
            )
            for tool, count in sorted(hotspot_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        ]

        # Common sequences (bigrams)
        sequences: list[tuple[str, str, int]] = []
        if len(events) >= 2:
            bigrams = Counter(
                (events[i].tool_name, events[i + 1].tool_name)
                for i in range(len(events) - 1)
            )
            sequences = [(a, b, count) for (a, b), count in bigrams.most_common(10) if count >= 2]

        # Overall stats
        successes = sum(1 for e in events if e.success)
        latencies = [e.latency_ms for e in events]

        return PatternReport(
            most_used_tools=most_used,
            error_hotspots=hotspots,
            common_sequences=sequences,
            total_executions=len(events),
            success_rate=round(successes / len(events), 3) if events else 0.0,
            avg_latency_ms=round(sum(latencies) / len(latencies), 1) if latencies else 0.0,
        )

    def model_performance(self) -> ModelReport:
        """Compare model performance across task types.

        Returns:
            ModelReport with performance comparison by model and category

        Example:
            >>> report = Self.get().analysis.model_performance()
            >>> report.best_per_category
            {'code_generation': 'claude-3-5-sonnet', ...}
        """
        events_with_model = [e for e in self._events if e.model]

        if not events_with_model:
            return ModelReport(
                models_tracked=[],
                categories_tracked=[],
                best_per_category={},
                total_entries=0,
            )

        models = list({e.model for e in events_with_model if e.model})
        # Simplified: use tool_name as category
        categories = list({e.tool_name for e in events_with_model})

        # Find best model per category (highest success rate)
        best_per_category: dict[str, str | None] = {}
        for category in categories:
            category_events = [e for e in events_with_model if e.tool_name == category]
            if len(category_events) >= 5:
                model_scores: dict[str, float] = {}
                for model in models:
                    model_events = [e for e in category_events if e.model == model]
                    if model_events:
                        success_rate = sum(1 for e in model_events if e.success) / len(model_events)
                        edit_rate = sum(1 for e in model_events if e.user_edited) / len(model_events)
                        # Quality = (1 - edit_rate) * success_rate
                        model_scores[model] = (1 - edit_rate) * success_rate

                if model_scores:
                    best_per_category[category] = max(model_scores, key=lambda m: model_scores[m])

        return ModelReport(
            models_tracked=models,
            categories_tracked=categories,
            best_per_category=best_per_category,
            total_entries=len(events_with_model),
        )

    def diagnose(self, error: Exception | str) -> Diagnosis:
        """Diagnose an error with source-level analysis.

        Traces the error to source code, finds similar past errors,
        and suggests fixes.

        Args:
            error: Exception instance or error message string

        Returns:
            Diagnosis with root cause, suggestions, and similar errors

        Example:
            >>> diagnosis = Self.get().analysis.diagnose(e)
            >>> diagnosis.root_cause
            'Path attempted to escape workspace jail'
            >>> diagnosis.suggested_fixes
            ['Use paths within the workspace root only.']
        """
        error_msg = str(error)
        error_type = type(error).__name__ if isinstance(error, Exception) else "Error"

        # Match against known patterns
        root_cause = "Unknown error pattern"
        suggestions: list[str] = []
        confidence = 0.3

        for pattern, info in KNOWN_FAILURE_PATTERNS.items():
            if pattern.lower() in error_msg.lower():
                root_cause = info["root_cause"]
                suggestions.append(info["suggestion"])
                confidence = 0.9
                break

        # Find similar past errors
        similar = [
            f for f in self._failures
            if f.error_type == error_type or any(
                p.lower() in f.error.lower()
                for p in KNOWN_FAILURE_PATTERNS
                if p.lower() in error_msg.lower()
            )
        ][:5]

        # Try to identify source location from traceback
        source_location: SourceLocation | None = None
        if isinstance(error, Exception) and error.__traceback__:
            tb = error.__traceback__
            while tb.tb_next:
                tb = tb.tb_next
            frame = tb.tb_frame
            filename = frame.f_code.co_filename
            if "sunwell" in filename:
                # Extract module from path
                parts = filename.split("sunwell/")
                if len(parts) > 1:
                    module_path = "sunwell." + parts[-1].replace("/", ".").replace(".py", "")
                    source_location = SourceLocation(
                        module=module_path,
                        line=tb.tb_lineno,
                    )

        return Diagnosis(
            error=error_msg,
            root_cause=root_cause,
            source_location=source_location,
            similar_past_errors=similar,
            suggested_fixes=suggestions,
            confidence=confidence,
        )

    def _create_failure_report(self, event: ExecutionEvent) -> FailureReport:
        """Create a failure report from an execution event."""
        error_msg = event.error or "Unknown error"

        # Determine error type
        error_type = "unknown"
        for pattern in KNOWN_FAILURE_PATTERNS:
            if pattern.lower() in error_msg.lower():
                error_type = pattern
                break

        # Determine severity
        if any(p in error_msg.lower() for p in ["security", "permission", "escape"]):
            severity = FailureSeverity.HIGH
        elif "timeout" in error_msg.lower() or "rate limit" in error_msg.lower():
            severity = FailureSeverity.MEDIUM
        else:
            severity = FailureSeverity.LOW

        # Get root cause and suggestion
        root_cause: str | None = None
        suggestion: str | None = None
        for pattern, info in KNOWN_FAILURE_PATTERNS.items():
            if pattern.lower() in error_msg.lower():
                root_cause = info["root_cause"]
                suggestion = info["suggestion"]
                break

        return FailureReport(
            error=error_msg,
            error_type=error_type,
            root_cause=root_cause,
            source_location=None,  # Would need traceback capture
            timestamp=event.timestamp,
            severity=severity,
            suggestion=suggestion,
        )

    def _filter_by_scope(
        self,
        events: list[ExecutionEvent],
        scope: str,
    ) -> list[ExecutionEvent]:
        """Filter events by time scope."""
        if scope == "session" or scope == "all":
            return events

        now = datetime.now()
        if scope == "day":
            cutoff = now - timedelta(days=1)
        elif scope == "week":
            cutoff = now - timedelta(weeks=1)
        else:
            return events

        return [e for e in events if e.timestamp > cutoff]

    def _load_from_storage(self) -> None:
        """Load existing data from storage files."""
        # Load execution events
        events_file = self.storage / "executions.jsonl"
        if events_file.exists():
            with events_file.open() as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            self._events.append(ExecutionEvent(
                                tool_name=data["tool_name"],
                                success=data["success"],
                                latency_ms=data["latency_ms"],
                                error=data.get("error"),
                                timestamp=datetime.fromisoformat(data["timestamp"]),
                                model=data.get("model"),
                                user_edited=data.get("user_edited", False),
                            ))
                        except (json.JSONDecodeError, KeyError):
                            continue

        # Load failure reports
        failures_file = self.storage / "failures.jsonl"
        if failures_file.exists():
            with failures_file.open() as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            self._failures.append(FailureReport(
                                error=data["error"],
                                error_type=data["error_type"],
                                root_cause=data.get("root_cause"),
                                source_location=None,
                                timestamp=datetime.fromisoformat(data["timestamp"]),
                                severity=FailureSeverity(data.get("severity", "low")),
                                suggestion=data.get("suggestion"),
                            ))
                        except (json.JSONDecodeError, KeyError):
                            continue

    def _append_event_to_storage(self, event: ExecutionEvent) -> None:
        """Append an execution event to storage."""
        events_file = self.storage / "executions.jsonl"
        data = {
            "tool_name": event.tool_name,
            "success": event.success,
            "latency_ms": event.latency_ms,
            "error": event.error,
            "timestamp": event.timestamp.isoformat(),
            "model": event.model,
            "user_edited": event.user_edited,
        }
        with events_file.open("a") as f:
            f.write(json.dumps(data) + "\n")

    def _append_failure_to_storage(self, report: FailureReport) -> None:
        """Append a failure report to storage."""
        failures_file = self.storage / "failures.jsonl"
        data = {
            "error": report.error,
            "error_type": report.error_type,
            "root_cause": report.root_cause,
            "timestamp": report.timestamp.isoformat(),
            "severity": report.severity.value,
            "suggestion": report.suggestion,
        }
        with failures_file.open("a") as f:
            f.write(json.dumps(data) + "\n")

    def clear(self) -> None:
        """Clear all data (for testing)."""
        with self._lock:
            self._events.clear()
            self._failures.clear()

            for file in ["executions.jsonl", "failures.jsonl"]:
                path = self.storage / file
                if path.exists():
                    path.unlink()
