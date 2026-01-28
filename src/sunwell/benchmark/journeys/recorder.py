"""EventRecorder for capturing agent events during journey execution.

Subscribes to the agent event bus and collects all events for assertion.
Provides structured access to intent classifications, signals, tool calls,
and other observable outcomes.
"""

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sunwell.agent.events import AgentEvent, EventType, on_event


@dataclass(slots=True)
class ToolCallRecord:
    """Record of a single tool call."""

    name: str
    """Tool name (e.g., "write_file", "shell")."""

    arguments: dict[str, Any]
    """Arguments passed to the tool."""

    result: str | None = None
    """Tool result (if captured)."""

    success: bool = True
    """Whether the tool call succeeded."""

    error: str | None = None
    """Error message if failed."""

    timestamp: float = 0.0
    """When the tool was called."""


@dataclass(slots=True)
class IntentRecord:
    """Record of an intent classification."""

    intent: str
    """Classified intent (TASK, CONVERSATION, COMMAND, etc.)."""

    confidence: float
    """Classification confidence (0.0-1.0)."""

    reasoning: str | None = None
    """Why this classification was made."""


@dataclass(slots=True)
class SignalRecord:
    """Record of extracted signals."""

    complexity: str | None = None
    needs_tools: str | None = None
    is_ambiguous: str | None = None
    is_dangerous: str | None = None
    is_epic: str | None = None
    confidence: float = 0.5
    domain: str = "general"
    planning_route: str | None = None
    execution_route: str | None = None


@dataclass(slots=True)
class FileChange:
    """Record of a file change."""

    path: str
    """File path (relative or absolute)."""

    operation: str
    """Operation: "create", "modify", "delete", "rename", "copy"."""

    content: str | None = None
    """File content after operation (if available)."""


@dataclass(slots=True)
class RoutingRecord:
    """Record of a routing decision."""

    confidence: float
    """Confidence score (0.0-1.0)."""

    strategy: str
    """Strategy used: "vortex", "interference", "single_shot"."""

    turn: int = 0
    """Turn when routing occurred."""

    threshold_vortex: float = 0.6
    """Threshold below which Vortex is used."""

    threshold_interference: float = 0.85
    """Threshold below which Interference is used."""


@dataclass(slots=True)
class ModelMetricsRecord:
    """Record of model generation metrics."""

    model: str | None = None
    """Model identifier used for generation."""

    prompt_tokens: int | None = None
    """Tokens in the prompt."""

    completion_tokens: int | None = None
    """Tokens in the completion."""

    total_tokens: int = 0
    """Total tokens consumed."""

    tokens_per_second: float | None = None
    """Generation speed."""

    duration_s: float | None = None
    """Generation duration in seconds."""

    finish_reason: str | None = None
    """Why generation stopped."""


@dataclass(slots=True)
class ValidationRecord:
    """Record of a validation gate result."""

    gate_id: str
    """Unique identifier for the gate."""

    gate_type: str
    """Gate type: "syntax", "lint", "type", "runtime"."""

    passed: bool
    """Whether the gate passed."""

    errors: list[str] = field(default_factory=list)
    """Error messages if gate failed."""

    duration_ms: int = 0
    """Validation duration in milliseconds."""


@dataclass(slots=True)
class ReliabilityRecord:
    """Record of a reliability issue."""

    failure_type: str
    """Type of failure: "hallucinated_completion", "no_tools_when_needed", etc."""

    confidence: float
    """Confidence in the detection (0.0-1.0)."""

    message: str
    """Human-readable description."""

    suggested_action: str | None = None
    """Recommended remediation."""


@dataclass(slots=True)
class PlanRecord:
    """Record of a plan selection."""

    plan_id: str | None = None
    """Plan identifier."""

    technique: str | None = None
    """Planning technique used."""

    tasks: int = 0
    """Number of tasks in the plan."""

    confidence: float = 0.0
    """Confidence in the plan."""


@dataclass
class TurnSnapshot:
    """Snapshot of recorder state for a single turn."""

    turn_index: int
    """Which turn this snapshot is from (0-indexed)."""

    events: list[AgentEvent]
    """Events captured during this turn."""

    tool_calls: list[ToolCallRecord]
    """Tool calls during this turn."""

    intents: list[IntentRecord]
    """Intent classifications during this turn."""

    signals: list[SignalRecord]
    """Signals extracted during this turn."""

    file_changes: list[FileChange]
    """File changes during this turn."""

    outputs: list[str]
    """Outputs during this turn."""

    errors: list[str]
    """Errors during this turn."""

    routings: list[RoutingRecord] = field(default_factory=list)
    """Routing decisions during this turn."""

    model_metrics: list[ModelMetricsRecord] = field(default_factory=list)
    """Model generation metrics during this turn."""

    validations: list[ValidationRecord] = field(default_factory=list)
    """Validation gate results during this turn."""

    reliability_issues: list[ReliabilityRecord] = field(default_factory=list)
    """Reliability issues detected during this turn."""

    plans: list[PlanRecord] = field(default_factory=list)
    """Plan selections during this turn."""


@dataclass
class EventRecorder:
    """Captures all agent events during execution for behavioral assertions.

    Usage:
        >>> recorder = EventRecorder()
        >>> recorder.start()
        >>> # ... run agent ...
        >>> recorder.stop()
        >>> assert recorder.has_tool_call("write_file")
        >>> assert recorder.intent == "TASK"

    Multi-turn support:
        >>> recorder.new_turn()  # Archive current turn, start fresh
        >>> recorder.turn_history  # Access previous turns
        >>> recorder.all_events  # All events across all turns
    """

    events: list[AgentEvent] = field(default_factory=list)
    """Events for current turn."""

    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    """Extracted tool call records for current turn."""

    intents: list[IntentRecord] = field(default_factory=list)
    """Extracted intent classifications for current turn."""

    signals: list[SignalRecord] = field(default_factory=list)
    """Extracted signal records for current turn."""

    file_changes: list[FileChange] = field(default_factory=list)
    """Extracted file changes for current turn."""

    outputs: list[str] = field(default_factory=list)
    """Model outputs/completions for current turn."""

    errors: list[str] = field(default_factory=list)
    """Captured errors for current turn."""

    routings: list[RoutingRecord] = field(default_factory=list)
    """Routing decisions for current turn."""

    model_metrics: list[ModelMetricsRecord] = field(default_factory=list)
    """Model generation metrics for current turn."""

    validations: list[ValidationRecord] = field(default_factory=list)
    """Validation gate results for current turn."""

    reliability_issues: list[ReliabilityRecord] = field(default_factory=list)
    """Reliability issues detected for current turn."""

    plans: list[PlanRecord] = field(default_factory=list)
    """Plan selections for current turn."""

    turn_history: list[TurnSnapshot] = field(default_factory=list)
    """Archived snapshots from previous turns."""

    current_turn: int = 0
    """Current turn index (0-indexed)."""

    _unsubscribe: Callable[[], None] | None = field(default=None, repr=False)
    """Unsubscribe function from event bus."""

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    """Thread-safe access to collections."""

    def start(self) -> None:
        """Start recording events from the event bus."""
        if self._unsubscribe is not None:
            return  # Already recording

        self._unsubscribe = on_event(self._handle_event)

    def stop(self) -> None:
        """Stop recording events."""
        if self._unsubscribe:
            self._unsubscribe()
            self._unsubscribe = None

    def new_turn(self) -> None:
        """Archive current turn and start a new one.

        Preserves all data from current turn in turn_history,
        then clears current-turn collections for fresh recording.
        """
        with self._lock:
            # Archive current turn if there's data
            if self.events or self.tool_calls or self.intents:
                snapshot = TurnSnapshot(
                    turn_index=self.current_turn,
                    events=list(self.events),
                    tool_calls=list(self.tool_calls),
                    intents=list(self.intents),
                    signals=list(self.signals),
                    file_changes=list(self.file_changes),
                    outputs=list(self.outputs),
                    errors=list(self.errors),
                    routings=list(self.routings),
                    model_metrics=list(self.model_metrics),
                    validations=list(self.validations),
                    reliability_issues=list(self.reliability_issues),
                    plans=list(self.plans),
                )
                self.turn_history.append(snapshot)

            # Clear current turn
            self.events.clear()
            self.tool_calls.clear()
            self.intents.clear()
            self.signals.clear()
            self.file_changes.clear()
            self.outputs.clear()
            self.errors.clear()
            self.routings.clear()
            self.model_metrics.clear()
            self.validations.clear()
            self.reliability_issues.clear()
            self.plans.clear()

            # Increment turn counter
            self.current_turn += 1

    def reset(self) -> None:
        """Clear all recorded data including history.

        For multi-turn journeys, prefer new_turn() to preserve history.
        """
        with self._lock:
            self.events.clear()
            self.tool_calls.clear()
            self.intents.clear()
            self.signals.clear()
            self.file_changes.clear()
            self.outputs.clear()
            self.errors.clear()
            self.routings.clear()
            self.model_metrics.clear()
            self.validations.clear()
            self.reliability_issues.clear()
            self.plans.clear()
            self.turn_history.clear()
            self.current_turn = 0

    @property
    def all_events(self) -> list[AgentEvent]:
        """Get all events across all turns (including current)."""
        with self._lock:
            all_evts: list[AgentEvent] = []
            for snapshot in self.turn_history:
                all_evts.extend(snapshot.events)
            all_evts.extend(self.events)
            return all_evts

    @property
    def all_tool_calls(self) -> list[ToolCallRecord]:
        """Get all tool calls across all turns."""
        with self._lock:
            all_calls: list[ToolCallRecord] = []
            for snapshot in self.turn_history:
                all_calls.extend(snapshot.tool_calls)
            all_calls.extend(self.tool_calls)
            return all_calls

    def get_turn(self, turn_index: int) -> TurnSnapshot | None:
        """Get snapshot for a specific turn."""
        with self._lock:
            for snapshot in self.turn_history:
                if snapshot.turn_index == turn_index:
                    return snapshot
            # Current turn not archived yet
            if turn_index == self.current_turn:
                return TurnSnapshot(
                    turn_index=self.current_turn,
                    events=list(self.events),
                    tool_calls=list(self.tool_calls),
                    intents=list(self.intents),
                    signals=list(self.signals),
                    file_changes=list(self.file_changes),
                    outputs=list(self.outputs),
                    errors=list(self.errors),
                    routings=list(self.routings),
                    model_metrics=list(self.model_metrics),
                    validations=list(self.validations),
                    reliability_issues=list(self.reliability_issues),
                    plans=list(self.plans),
                )
            return None

    def _handle_event(self, event: AgentEvent) -> None:
        """Process an event from the bus."""
        with self._lock:
            self.events.append(event)
            self._extract_from_event(event)

    def _extract_from_event(self, event: AgentEvent) -> None:
        """Extract structured data from an event."""
        data = event.data or {}

        # Tool events
        if event.type == EventType.TOOL_START:
            self.tool_calls.append(ToolCallRecord(
                name=data.get("tool", data.get("name", "")),
                arguments=data.get("arguments", data.get("args", {})),
                timestamp=event.timestamp,
            ))
        elif event.type == EventType.TOOL_COMPLETE:
            # Update last tool call with result
            if self.tool_calls:
                tool_name = data.get("tool", data.get("name", ""))
                # Find matching tool call (last one with same name)
                for tc in reversed(self.tool_calls):
                    if tc.name == tool_name and tc.result is None:
                        tc.result = data.get("result", "")
                        tc.success = True
                        break
        elif event.type == EventType.TOOL_ERROR:
            # Update last tool call with error
            if self.tool_calls:
                tool_name = data.get("tool", data.get("name", ""))
                for tc in reversed(self.tool_calls):
                    if tc.name == tool_name and tc.result is None:
                        tc.error = data.get("error", str(data))
                        tc.success = False
                        break

        # Intent events (from routing)
        elif event.type == EventType.SIGNAL:
            signal_type = data.get("signal_type", data.get("type", ""))
            if signal_type == "intent" or "intent" in data:
                self.intents.append(IntentRecord(
                    intent=data.get("intent", data.get("value", "UNKNOWN")),
                    confidence=data.get("confidence", 0.5),
                    reasoning=data.get("reasoning"),
                ))
            # Also extract signals if present
            if any(k in data for k in ("complexity", "needs_tools", "is_ambiguous")):
                self.signals.append(SignalRecord(
                    complexity=data.get("complexity"),
                    needs_tools=data.get("needs_tools"),
                    is_ambiguous=data.get("is_ambiguous"),
                    is_dangerous=data.get("is_dangerous"),
                    is_epic=data.get("is_epic"),
                    confidence=data.get("confidence", 0.5),
                    domain=data.get("domain", "general"),
                    planning_route=data.get("planning_route"),
                    execution_route=data.get("execution_route"),
                ))

        # Model output events
        elif event.type == EventType.MODEL_COMPLETE:
            content = data.get("content", data.get("text", ""))
            if content:
                self.outputs.append(content)
            # Also extract model metrics
            self.model_metrics.append(ModelMetricsRecord(
                model=data.get("model"),
                prompt_tokens=data.get("prompt_tokens"),
                completion_tokens=data.get("completion_tokens"),
                total_tokens=data.get("total_tokens", 0),
                tokens_per_second=data.get("tokens_per_second"),
                duration_s=data.get("duration_s"),
                finish_reason=data.get("finish_reason"),
            ))
        elif event.type == EventType.TASK_COMPLETE:
            output = data.get("output", data.get("result", ""))
            if output and isinstance(output, str):
                self.outputs.append(output)

        # Routing events
        elif event.type == EventType.SIGNAL_ROUTE:
            self.routings.append(RoutingRecord(
                confidence=data.get("confidence", 0.0),
                strategy=data.get("strategy", "unknown"),
                turn=self.current_turn,
                threshold_vortex=data.get("threshold_vortex", 0.6),
                threshold_interference=data.get("threshold_interference", 0.85),
            ))

        # Validation gate events
        elif event.type == EventType.GATE_PASS:
            self.validations.append(ValidationRecord(
                gate_id=data.get("gate_id", "unknown"),
                gate_type=data.get("gate_type", "unknown"),
                passed=True,
                duration_ms=data.get("duration_ms", 0),
            ))
        elif event.type == EventType.GATE_FAIL:
            self.validations.append(ValidationRecord(
                gate_id=data.get("gate_id", "unknown"),
                gate_type=data.get("gate_type", "unknown"),
                passed=False,
                errors=[data.get("error_message", "")] if data.get("error_message") else [],
                duration_ms=data.get("duration_ms", 0),
            ))

        # Reliability events
        elif event.type in (EventType.RELIABILITY_WARNING, EventType.RELIABILITY_HALLUCINATION):
            self.reliability_issues.append(ReliabilityRecord(
                failure_type=data.get("failure_type", "unknown"),
                confidence=data.get("confidence", 0.0),
                message=data.get("message", ""),
                suggested_action=data.get("suggested_action"),
            ))

        # Plan winner event
        elif event.type == EventType.PLAN_WINNER:
            self.plans.append(PlanRecord(
                plan_id=data.get("selected_candidate_id"),
                technique=data.get("technique"),
                tasks=len(data.get("tasks", data.get("task_list", []))),
                confidence=data.get("score", 0.0),
            ))

        # File change events - expanded to include more tools
        elif event.type == EventType.TOOL_COMPLETE:
            tool_name = data.get("tool_name", data.get("tool", data.get("name", "")))
            args = data.get("arguments", {})
            
            if tool_name == "write_file":
                path = args.get("path", "")
                if path:
                    self.file_changes.append(FileChange(
                        path=path,
                        operation="create",
                        content=args.get("content"),
                    ))
            elif tool_name == "edit_file":
                path = args.get("path", "")
                if path:
                    self.file_changes.append(FileChange(
                        path=path,
                        operation="modify",
                        content=None,  # Edit doesn't provide full content
                    ))
            elif tool_name == "delete_file":
                path = args.get("path", "")
                if path:
                    self.file_changes.append(FileChange(
                        path=path,
                        operation="delete",
                        content=None,
                    ))
            elif tool_name == "rename_file":
                src = args.get("source", args.get("src", ""))
                dst = args.get("destination", args.get("dst", args.get("target", "")))
                if src:
                    self.file_changes.append(FileChange(
                        path=src,
                        operation="rename",
                        content=dst,  # Store destination in content field
                    ))
            elif tool_name == "copy_file":
                src = args.get("source", args.get("src", ""))
                dst = args.get("destination", args.get("dst", args.get("target", "")))
                if src:
                    self.file_changes.append(FileChange(
                        path=dst or src,
                        operation="copy",
                        content=None,
                    ))

        # Error events
        elif event.type == EventType.ERROR:
            error_msg = data.get("error", data.get("message", str(data)))
            self.errors.append(error_msg)

    # =========================================================================
    # Query Methods for Assertions
    # =========================================================================

    @property
    def intent(self) -> str | None:
        """Get the primary intent classification (first one)."""
        return self.intents[0].intent if self.intents else None

    @property
    def all_output(self) -> str:
        """Get all outputs concatenated."""
        return "\n".join(self.outputs)

    def has_tool_call(self, tool_name: str) -> bool:
        """Check if a tool was called."""
        return any(tc.name == tool_name for tc in self.tool_calls)

    def get_tool_calls(self, tool_name: str) -> list[ToolCallRecord]:
        """Get all calls to a specific tool."""
        return [tc for tc in self.tool_calls if tc.name == tool_name]

    def tool_call_args_match(
        self,
        tool_name: str,
        expected_args: dict[str, Any],
    ) -> bool:
        """Check if a tool was called with args containing expected values.

        Supports glob patterns for string values (e.g., "*.py").
        """
        import fnmatch

        for tc in self.tool_calls:
            if tc.name != tool_name:
                continue

            match = True
            for key, expected in expected_args.items():
                actual = tc.arguments.get(key)
                if actual is None:
                    match = False
                    break

                # Handle glob patterns for strings
                if isinstance(expected, str) and isinstance(actual, str):
                    if "*" in expected or "?" in expected:
                        if not fnmatch.fnmatch(actual, expected):
                            match = False
                            break
                    elif expected not in actual:
                        match = False
                        break
                # Handle list of alternatives
                elif isinstance(expected, list):
                    if isinstance(actual, str):
                        if not any(e in actual for e in expected):
                            match = False
                            break
                # Direct comparison
                elif actual != expected:
                    match = False
                    break

            if match:
                return True

        return False

    def has_file_change(self, pattern: str | None = None, path: str | None = None) -> bool:
        """Check if a file was changed.

        Args:
            pattern: Glob pattern to match (e.g., "*.py")
            path: Exact path to match
        """
        import fnmatch

        for fc in self.file_changes:
            if path and fc.path == path:
                return True
            if pattern and fnmatch.fnmatch(fc.path, pattern):
                return True
            if pattern and fnmatch.fnmatch(Path(fc.path).name, pattern):
                return True

        return False

    def file_contains(self, path: str, *patterns: str) -> bool:
        """Check if a file contains all the given patterns."""
        for fc in self.file_changes:
            if fc.path == path or Path(fc.path).name == path:
                if fc.content:
                    return all(p.lower() in fc.content.lower() for p in patterns)
        return False

    def output_contains(self, *patterns: str, case_sensitive: bool = False) -> bool:
        """Check if output contains all patterns."""
        output = self.all_output
        if not case_sensitive:
            output = output.lower()
            patterns = tuple(p.lower() for p in patterns)
        return all(p in output for p in patterns)

    def output_not_contains(self, *patterns: str, case_sensitive: bool = False) -> bool:
        """Check if output does NOT contain any of the patterns."""
        output = self.all_output
        if not case_sensitive:
            output = output.lower()
            patterns = tuple(p.lower() for p in patterns)
        return all(p not in output for p in patterns)

    def get_signal(self, key: str) -> Any:
        """Get the first signal value for a key."""
        if not self.signals:
            return None
        return getattr(self.signals[0], key, None)

    def has_error(self) -> bool:
        """Check if any errors were recorded."""
        return len(self.errors) > 0

    # =========================================================================
    # New Query Methods for Observability
    # =========================================================================

    @property
    def routing_strategy(self) -> str | None:
        """Get the routing strategy used (first one)."""
        if self.routings:
            return self.routings[0].strategy
        # Check turn history
        for snapshot in self.turn_history:
            if snapshot.routings:
                return snapshot.routings[0].strategy
        return None

    @property
    def routing_confidence(self) -> float | None:
        """Get the routing confidence (first one)."""
        if self.routings:
            return self.routings[0].confidence
        for snapshot in self.turn_history:
            if snapshot.routings:
                return snapshot.routings[0].confidence
        return None

    @property
    def total_tokens(self) -> int:
        """Get total tokens consumed across all generations."""
        total = 0
        # Current turn
        for m in self.model_metrics:
            total += m.total_tokens or (
                (m.prompt_tokens or 0) + (m.completion_tokens or 0)
            )
        # Turn history
        for snapshot in self.turn_history:
            for m in snapshot.model_metrics:
                total += m.total_tokens or (
                    (m.prompt_tokens or 0) + (m.completion_tokens or 0)
                )
        return total

    @property
    def all_model_metrics(self) -> list[ModelMetricsRecord]:
        """Get all model metrics across all turns."""
        result: list[ModelMetricsRecord] = []
        for snapshot in self.turn_history:
            result.extend(snapshot.model_metrics)
        result.extend(self.model_metrics)
        return result

    @property
    def all_validations(self) -> list[ValidationRecord]:
        """Get all validation records across all turns."""
        result: list[ValidationRecord] = []
        for snapshot in self.turn_history:
            result.extend(snapshot.validations)
        result.extend(self.validations)
        return result

    @property
    def all_reliability_issues(self) -> list[ReliabilityRecord]:
        """Get all reliability issues across all turns."""
        result: list[ReliabilityRecord] = []
        for snapshot in self.turn_history:
            result.extend(snapshot.reliability_issues)
        result.extend(self.reliability_issues)
        return result

    def has_reliability_issue(self, failure_type: str | None = None) -> bool:
        """Check if a reliability issue was detected.

        Args:
            failure_type: Optional specific failure type to check for.
                         If None, checks for any reliability issue.
        """
        all_issues = self.all_reliability_issues
        if not all_issues:
            return False
        if failure_type is None:
            return True
        return any(r.failure_type == failure_type for r in all_issues)

    def validation_passed(self, gate_type: str | None = None) -> bool:
        """Check if validations passed.

        Args:
            gate_type: Optional specific gate type to check.
                      If None, checks all validations passed.

        Returns:
            True if all relevant validations passed (or no validations ran).
        """
        all_validations = self.all_validations
        if not all_validations:
            return True  # No validations = vacuously true

        if gate_type is None:
            return all(v.passed for v in all_validations)
        else:
            relevant = [v for v in all_validations if v.gate_type == gate_type]
            if not relevant:
                return True
            return all(v.passed for v in relevant)

    def validation_failed(self, gate_type: str | None = None) -> bool:
        """Check if any validation failed.

        Args:
            gate_type: Optional specific gate type to check.

        Returns:
            True if any relevant validation failed.
        """
        all_validations = self.all_validations
        if not all_validations:
            return False

        if gate_type is None:
            return any(not v.passed for v in all_validations)
        else:
            relevant = [v for v in all_validations if v.gate_type == gate_type]
            return any(not v.passed for v in relevant)

    # =========================================================================
    # Context Manager
    # =========================================================================

    def __enter__(self) -> "EventRecorder":
        self.start()
        return self

    def __exit__(self, *args: object) -> None:
        self.stop()
