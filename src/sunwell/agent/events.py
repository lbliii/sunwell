"""Event types for Adaptive Agent streaming (RFC-042).

Events enable live progress streaming so users see what's happening,
reducing perceived wait time. Events are yielded as the agent works.

Event categories:
- Memory: Simulacrum load/save, learning extraction
- Signal: Goal analysis, routing decisions
- Planning: Plan candidates, selection, expansion
- Execution: Task progress, completion
- Validation: Gate checks, errors
- Fix: Auto-repair progress

RFC-097: Events now support optional UI hints for richer frontend rendering.
"""


from dataclasses import dataclass, field
from enum import Enum
from time import time
from typing import Any, Literal, TypedDict

# =============================================================================
# RFC-097: Event UI Hints
# =============================================================================


@dataclass(frozen=True, slots=True)
class EventUIHints:
    """UI rendering hints for frontend (RFC-097).

    Optional hints that help the frontend render events more richly.
    These are suggestions — the frontend may ignore them.

    Example:
        >>> hints = EventUIHints(icon="⚡", severity="info", progress=0.5)
        >>> hints.to_dict()
        {'icon': '⚡', 'severity': 'info', 'progress': 0.5, ...}
    """

    icon: str | None = None
    """Suggested icon (emoji or icon name)."""

    severity: Literal["info", "warning", "error", "success"] = "info"
    """Visual severity for styling."""

    progress: float | None = None
    """Progress indicator (0.0-1.0) if known."""

    dismissible: bool = True
    """Whether user can dismiss this notification."""

    highlight_code: bool = False
    """Whether code in data should be syntax highlighted."""

    animation: str | None = None
    """Suggested animation: 'pulse', 'fade-in', 'shake', 'shimmer'."""

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict, omitting None values."""
        result: dict[str, Any] = {"severity": self.severity, "dismissible": self.dismissible}
        if self.icon is not None:
            result["icon"] = self.icon
        if self.progress is not None:
            result["progress"] = self.progress
        if self.highlight_code:
            result["highlight_code"] = True
        if self.animation is not None:
            result["animation"] = self.animation
        return result


# Default UI hints for common event types
_DEFAULT_UI_HINTS: dict[str, EventUIHints] = {
    "task_start": EventUIHints(icon="⚡", severity="info", animation="pulse"),
    "task_complete": EventUIHints(icon="✓", severity="success", animation="fade-in"),
    "task_failed": EventUIHints(icon="✗", severity="error", animation="shake"),
    "error": EventUIHints(icon="✗", severity="error", dismissible=False, animation="shake"),
    "complete": EventUIHints(icon="✨", severity="success", animation="fade-in"),
    "model_start": EventUIHints(icon="🧠", severity="info", animation="pulse"),
    "model_tokens": EventUIHints(icon="🧠", severity="info"),
    "model_thinking": EventUIHints(icon="💭", severity="info", animation="pulse"),
    "model_complete": EventUIHints(icon="✓", severity="success"),
    "gate_pass": EventUIHints(icon="✓", severity="success"),
    "gate_fail": EventUIHints(icon="✗", severity="error"),
    "fix_start": EventUIHints(icon="🔧", severity="warning", animation="pulse"),
    "fix_complete": EventUIHints(icon="✓", severity="success"),
    "security_violation": EventUIHints(
        icon="🛡️", severity="error", dismissible=False, animation="shake"
    ),
    "security_approval_requested": EventUIHints(
        icon="🔐", severity="warning", dismissible=False
    ),
    # RFC-111: Skill compilation events
    "skill_compile_start": EventUIHints(icon="🔨", severity="info", animation="pulse"),
    "skill_compile_complete": EventUIHints(icon="✓", severity="success", animation="fade-in"),
    "skill_compile_cache_hit": EventUIHints(icon="💨", severity="success"),
    "skill_subgraph_extracted": EventUIHints(icon="📊", severity="info"),
}

# =============================================================================
# RFC-090: Plan Transparency Types
# =============================================================================


class TaskSummary(TypedDict):
    """Minimal task info for plan display (RFC-090)."""

    id: str
    description: str
    depends_on: list[str]
    produces: list[str]  # Artifact paths
    category: str | None


class GateSummary(TypedDict):
    """Minimal gate info for plan display (RFC-090)."""

    id: str
    type: str  # "syntax", "lint", "type", "runtime"
    after_tasks: list[str]


class EventType(Enum):
    """Types of events emitted by the Adaptive Agent."""

    # Memory events (Simulacrum integration)
    MEMORY_LOAD = "memory_load"
    """Starting to load session memory."""

    MEMORY_LOADED = "memory_loaded"
    """Session memory loaded successfully."""

    MEMORY_NEW = "memory_new"
    """Created new session (no existing memory)."""

    MEMORY_LEARNING = "memory_learning"
    """Extracted a new learning from generated code."""

    MEMORY_DEAD_END = "memory_dead_end"
    """Recorded a dead end (approach that didn't work)."""

    MEMORY_CHECKPOINT = "memory_checkpoint"
    """Checkpointed memory to disk (survives crashes)."""

    MEMORY_SAVED = "memory_saved"
    """Session memory saved at end of run."""

    # Signal events (adaptive routing)
    SIGNAL = "signal"
    """Signal extraction status or results."""

    SIGNAL_ROUTE = "signal_route"
    """Routing decision based on signals."""

    # Planning events
    PLAN_START = "plan_start"
    """Starting plan generation."""

    PLAN_CANDIDATE = "plan_candidate"
    """Generated a plan candidate (harmonic planning)."""

    PLAN_WINNER = "plan_winner"
    """Selected winning plan."""

    PLAN_EXPANDED = "plan_expanded"
    """Expanded plan with additional tasks (iterative DAG)."""

    PLAN_ASSESS = "plan_assess"
    """Assessing if goal is complete or needs expansion."""

    # RFC-058: Planning visibility events
    PLAN_CANDIDATE_START = "plan_candidate_start"
    """Starting harmonic candidate generation."""

    PLAN_CANDIDATE_GENERATED = "plan_candidate_generated"
    """Generated a single candidate plan."""

    PLAN_CANDIDATES_COMPLETE = "plan_candidates_complete"
    """All candidates generated, starting scoring."""

    PLAN_CANDIDATE_SCORED = "plan_candidate_scored"
    """Scored a candidate with metrics."""

    PLAN_SCORING_COMPLETE = "plan_scoring_complete"
    """All candidates scored, selecting winner."""

    PLAN_REFINE_START = "plan_refine_start"
    """Starting refinement round."""

    PLAN_REFINE_ATTEMPT = "plan_refine_attempt"
    """Attempting refinement improvements."""

    PLAN_REFINE_COMPLETE = "plan_refine_complete"
    """Refinement round completed."""

    PLAN_REFINE_FINAL = "plan_refine_final"
    """All refinement rounds complete."""

    PLAN_DISCOVERY_PROGRESS = "plan_discovery_progress"
    """Progress update during artifact discovery (RFC-059)."""

    # Gate events
    GATE_START = "gate_start"
    """Starting validation at a gate."""

    GATE_STEP = "gate_step"
    """Completed a step within gate validation (syntax, lint, type, etc.)."""

    GATE_PASS = "gate_pass"
    """Gate validation passed."""

    GATE_FAIL = "gate_fail"
    """Gate validation failed."""

    # Execution events
    TASK_START = "task_start"
    """Starting to execute a task."""

    TASK_PROGRESS = "task_progress"
    """Progress update during task execution."""

    TASK_COMPLETE = "task_complete"
    """Task completed successfully."""

    TASK_FAILED = "task_failed"
    """Task execution failed."""

    # Validation events
    VALIDATE_START = "validate_start"
    """Starting validation cascade."""

    VALIDATE_LEVEL = "validate_level"
    """Validation at a specific level (syntax, import, runtime)."""

    VALIDATE_ERROR = "validate_error"
    """Validation found an error."""

    VALIDATE_PASS = "validate_pass"
    """Validation passed at current level."""

    # Fix events
    FIX_START = "fix_start"
    """Starting auto-fix process."""

    FIX_PROGRESS = "fix_progress"
    """Progress during fix (e.g., Compound Eye scanning)."""

    FIX_ATTEMPT = "fix_attempt"
    """Attempting a specific fix."""

    FIX_COMPLETE = "fix_complete"
    """Fix completed successfully."""

    FIX_FAILED = "fix_failed"
    """Fix attempt failed."""

    # Completion events
    COMPLETE = "complete"
    """Agent run completed successfully."""

    ERROR = "error"
    """Agent encountered unrecoverable error."""

    ESCALATE = "escalate"
    """Escalating to user (dangerous operation or low confidence)."""

    # Lens events (RFC-064)
    LENS_SELECTED = "lens_selected"
    """A lens has been selected for the current goal."""

    LENS_CHANGED = "lens_changed"
    """The active lens has been changed during execution."""

    # Integration verification events (RFC-067)
    INTEGRATION_CHECK_START = "integration_check_start"
    """Starting verification of an integration."""

    INTEGRATION_CHECK_PASS = "integration_check_pass"
    """Integration verification passed."""

    INTEGRATION_CHECK_FAIL = "integration_check_fail"
    """Integration verification failed."""

    STUB_DETECTED = "stub_detected"
    """Stub/placeholder implementation detected."""

    ORPHAN_DETECTED = "orphan_detected"
    """Orphan artifact detected (not integrated)."""

    WIRE_TASK_GENERATED = "wire_task_generated"
    """Wire task generated during planning."""

    # Briefing events (RFC-071)
    BRIEFING_LOADED = "briefing_loaded"
    """Briefing loaded at session start."""

    BRIEFING_SAVED = "briefing_saved"
    """Briefing saved at session end."""

    # Prefetch events (RFC-071)
    PREFETCH_START = "prefetch_start"
    """Starting briefing-driven prefetch."""

    PREFETCH_COMPLETE = "prefetch_complete"
    """Prefetch completed, context warm."""

    PREFETCH_TIMEOUT = "prefetch_timeout"
    """Prefetch timed out, proceeding without warm context."""

    LENS_SUGGESTED = "lens_suggested"
    """Lens suggested based on briefing analysis."""

    # Inference visibility events (RFC-081)
    MODEL_START = "model_start"
    """Model generation started. Show spinner."""

    MODEL_TOKENS = "model_tokens"
    """Batch of tokens received. Update counter/preview."""

    MODEL_THINKING = "model_thinking"
    """Detected reasoning content (<think>, Thinking..., etc.)."""

    MODEL_COMPLETE = "model_complete"
    """Generation finished. Show metrics."""

    MODEL_HEARTBEAT = "model_heartbeat"
    """Periodic heartbeat during long generation."""

    # Skill graph execution events (RFC-087)
    SKILL_GRAPH_RESOLVED = "skill_graph_resolved"
    """Skill graph resolved for lens. Shows skill count and wave count."""

    SKILL_WAVE_START = "skill_wave_start"
    """Starting execution of a wave of parallel skills."""

    SKILL_WAVE_COMPLETE = "skill_wave_complete"
    """Wave execution completed. Shows succeeded/failed counts."""

    SKILL_CACHE_HIT = "skill_cache_hit"
    """Skill result retrieved from cache. Shows time saved."""

    SKILL_EXECUTE_START = "skill_execute_start"
    """Starting execution of a single skill."""

    SKILL_EXECUTE_COMPLETE = "skill_execute_complete"
    """Skill execution completed (success or failure)."""

    # Skill compilation events (RFC-111)
    SKILL_COMPILE_START = "skill_compile_start"
    """Starting skill compilation (SkillGraph → TaskGraph)."""

    SKILL_COMPILE_COMPLETE = "skill_compile_complete"
    """Skill compilation completed. Shows task count and wave count."""

    SKILL_COMPILE_CACHE_HIT = "skill_compile_cache_hit"
    """Compiled TaskGraph retrieved from cache."""

    SKILL_SUBGRAPH_EXTRACTED = "skill_subgraph_extracted"
    """Subgraph extracted for targeted skill execution."""

    # Security events (RFC-089)
    SECURITY_APPROVAL_REQUESTED = "security_approval_requested"
    """DAG requires user approval before execution. Shows permissions and risk."""

    SECURITY_APPROVAL_RECEIVED = "security_approval_received"
    """User responded to approval request (approved/rejected)."""

    SECURITY_VIOLATION = "security_violation"
    """Security violation detected during execution."""

    SECURITY_SCAN_COMPLETE = "security_scan_complete"
    """Output security scan completed."""

    AUDIT_LOG_ENTRY = "audit_log_entry"
    """Audit log entry recorded."""

    # Backlog lifecycle events (RFC-094)
    BACKLOG_GOAL_ADDED = "backlog_goal_added"
    """Goal added to backlog."""

    BACKLOG_GOAL_STARTED = "backlog_goal_started"
    """Goal execution started (claimed)."""

    BACKLOG_GOAL_COMPLETED = "backlog_goal_completed"
    """Goal completed successfully."""

    BACKLOG_GOAL_FAILED = "backlog_goal_failed"
    """Goal execution failed."""

    BACKLOG_REFRESHED = "backlog_refreshed"
    """Backlog refreshed from signals."""


@dataclass(frozen=True, slots=True)
class AgentEvent:
    """A single event in the agent stream.

    Events are yielded as the agent works, enabling real-time progress
    display. Each event has a type, associated data, and timestamp.

    RFC-097: Events now support optional UI hints for richer frontend rendering.

    Example:
        >>> event = AgentEvent(EventType.TASK_START, {"task_id": "UserModel"})
        >>> print(f"{event.type.value}: {event.data}")
        task_start: {'task_id': 'UserModel'}
    """

    type: EventType
    """The type of event."""

    data: dict[str, Any] = field(default_factory=dict)
    """Event-specific data."""

    timestamp: float = field(default_factory=time)
    """Unix timestamp when event was created."""

    ui_hints: EventUIHints | None = None
    """Optional UI rendering hints (RFC-097)."""

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        result = {
            "type": self.type.value,
            "data": self.data,
            "timestamp": self.timestamp,
        }
        # RFC-097: Include UI hints if present, or use defaults
        hints = self.ui_hints or _DEFAULT_UI_HINTS.get(self.type.value)
        if hints:
            result["ui_hints"] = hints.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentEvent:
        """Create from dict."""
        ui_hints = None
        if "ui_hints" in data:
            hints_data = data["ui_hints"]
            ui_hints = EventUIHints(
                icon=hints_data.get("icon"),
                severity=hints_data.get("severity", "info"),
                progress=hints_data.get("progress"),
                dismissible=hints_data.get("dismissible", True),
                highlight_code=hints_data.get("highlight_code", False),
                animation=hints_data.get("animation"),
            )
        return cls(
            type=EventType(data["type"]),
            data=data.get("data", {}),
            timestamp=data.get("timestamp", time()),
            ui_hints=ui_hints,
        )

    def with_ui_hints(self, hints: EventUIHints) -> AgentEvent:
        """Return a new event with the given UI hints."""
        return AgentEvent(
            type=self.type,
            data=self.data,
            timestamp=self.timestamp,
            ui_hints=hints,
        )

    def __str__(self) -> str:
        """Human-readable representation."""
        return f"[{self.type.value}] {self.data}"


# =============================================================================
# Event Factory Helpers
# =============================================================================


def signal_event(status: str, **kwargs: Any) -> AgentEvent:
    """Create a signal extraction event."""
    return AgentEvent(EventType.SIGNAL, {"status": status, **kwargs})


def task_start_event(task_id: str, description: str, **kwargs: Any) -> AgentEvent:
    """Create a task start event.

    For type-safe version with validation, use:
    from sunwell.agent.event_schema import validated_task_start_event
    """
    return AgentEvent(
        EventType.TASK_START,
        {"task_id": task_id, "description": description, **kwargs},
    )


def task_complete_event(task_id: str, duration_ms: int, **kwargs: Any) -> AgentEvent:
    """Create a task completion event."""
    return AgentEvent(
        EventType.TASK_COMPLETE,
        {"task_id": task_id, "duration_ms": duration_ms, **kwargs},
    )


def gate_start_event(gate_id: str, gate_type: str, **kwargs: Any) -> AgentEvent:
    """Create a gate start event."""
    return AgentEvent(
        EventType.GATE_START,
        {"gate_id": gate_id, "gate_type": gate_type, **kwargs},
    )


def gate_step_event(
    gate_id: str,
    step: str,
    passed: bool,
    message: str = "",
    **kwargs: Any,
) -> AgentEvent:
    """Create a gate step event."""
    return AgentEvent(
        EventType.GATE_STEP,
        {"gate_id": gate_id, "step": step, "passed": passed, "message": message, **kwargs},
    )


def validate_error_event(
    error_type: str,
    message: str,
    file: str | None = None,
    line: int | None = None,
    **kwargs: Any,
) -> AgentEvent:
    """Create a validation error event."""
    return AgentEvent(
        EventType.VALIDATE_ERROR,
        {
            "error_type": error_type,
            "message": message,
            "file": file,
            "line": line,
            **kwargs,
        },
    )


def fix_progress_event(
    stage: str,
    progress: float,
    detail: str = "",
    **kwargs: Any,
) -> AgentEvent:
    """Create a fix progress event."""
    return AgentEvent(
        EventType.FIX_PROGRESS,
        {"stage": stage, "progress": progress, "detail": detail, **kwargs},
    )


def memory_learning_event(fact: str, category: str, **kwargs: Any) -> AgentEvent:
    """Create a memory learning event."""
    return AgentEvent(
        EventType.MEMORY_LEARNING,
        {"fact": fact, "category": category, **kwargs},
    )


def complete_event(
    tasks_completed: int,
    gates_passed: int,
    duration_s: float,
    **kwargs: Any,
) -> AgentEvent:
    """Create a completion event."""
    return AgentEvent(
        EventType.COMPLETE,
        {
            "tasks_completed": tasks_completed,
            "gates_passed": gates_passed,
            "duration_s": duration_s,
            **kwargs,
        },
    )


def lens_selected_event(
    name: str,
    source: str,
    confidence: float,
    reason: str,
    **kwargs: Any,
) -> AgentEvent:
    """Create a lens selected event (RFC-064)."""
    return AgentEvent(
        EventType.LENS_SELECTED,
        {
            "name": name,
            "source": source,
            "confidence": confidence,
            "reason": reason,
            **kwargs,
        },
    )


# =============================================================================
# RFC-067: Integration Verification Events
# =============================================================================


def integration_check_start_event(
    edge_id: str,
    check_type: str,
    source_artifact: str,
    target_artifact: str,
    **kwargs: Any,
) -> AgentEvent:
    """Create an integration check start event (RFC-067)."""
    return AgentEvent(
        EventType.INTEGRATION_CHECK_START,
        {
            "edge_id": edge_id,
            "check_type": check_type,
            "source_artifact": source_artifact,
            "target_artifact": target_artifact,
            **kwargs,
        },
    )


def integration_check_pass_event(
    edge_id: str,
    check_type: str,
    verification_method: str,
    **kwargs: Any,
) -> AgentEvent:
    """Create an integration check pass event (RFC-067)."""
    return AgentEvent(
        EventType.INTEGRATION_CHECK_PASS,
        {
            "edge_id": edge_id,
            "check_type": check_type,
            "verification_method": verification_method,
            **kwargs,
        },
    )


def integration_check_fail_event(
    edge_id: str,
    check_type: str,
    expected: str,
    actual: str,
    suggested_fix: str | None = None,
    **kwargs: Any,
) -> AgentEvent:
    """Create an integration check fail event (RFC-067)."""
    return AgentEvent(
        EventType.INTEGRATION_CHECK_FAIL,
        {
            "edge_id": edge_id,
            "check_type": check_type,
            "expected": expected,
            "actual": actual,
            "suggested_fix": suggested_fix,
            **kwargs,
        },
    )


def stub_detected_event(
    artifact_id: str,
    file_path: str,
    stub_type: str,
    location: str,
    **kwargs: Any,
) -> AgentEvent:
    """Create a stub detected event (RFC-067)."""
    return AgentEvent(
        EventType.STUB_DETECTED,
        {
            "artifact_id": artifact_id,
            "file_path": file_path,
            "stub_type": stub_type,
            "location": location,
            **kwargs,
        },
    )


def orphan_detected_event(
    artifact_id: str,
    file_path: str,
    **kwargs: Any,
) -> AgentEvent:
    """Create an orphan detected event (RFC-067)."""
    return AgentEvent(
        EventType.ORPHAN_DETECTED,
        {
            "artifact_id": artifact_id,
            "file_path": file_path,
            **kwargs,
        },
    )


def wire_task_generated_event(
    task_id: str,
    source_artifact: str,
    target_artifact: str,
    integration_type: str,
    **kwargs: Any,
) -> AgentEvent:
    """Create a wire task generated event (RFC-067)."""
    return AgentEvent(
        EventType.WIRE_TASK_GENERATED,
        {
            "task_id": task_id,
            "source_artifact": source_artifact,
            "target_artifact": target_artifact,
            "integration_type": integration_type,
            **kwargs,
        },
    )


# =============================================================================
# RFC-071: Briefing Events
# =============================================================================


def briefing_loaded_event(
    mission: str,
    status: str,
    has_hazards: bool,
    has_dispatch_hints: bool = False,
    **kwargs: Any,
) -> AgentEvent:
    """Create a briefing loaded event (RFC-071)."""
    return AgentEvent(
        EventType.BRIEFING_LOADED,
        {
            "mission": mission,
            "status": status,
            "has_hazards": has_hazards,
            "has_dispatch_hints": has_dispatch_hints,
            **kwargs,
        },
    )


def briefing_saved_event(
    status: str,
    next_action: str | None,
    tasks_completed: int,
    **kwargs: Any,
) -> AgentEvent:
    """Create a briefing saved event (RFC-071)."""
    return AgentEvent(
        EventType.BRIEFING_SAVED,
        {
            "status": status,
            "next_action": next_action,
            "tasks_completed": tasks_completed,
            **kwargs,
        },
    )


def prefetch_start_event(briefing_mission: str, **kwargs: Any) -> AgentEvent:
    """Create a prefetch start event (RFC-071)."""
    return AgentEvent(
        EventType.PREFETCH_START,
        {"briefing": briefing_mission, **kwargs},
    )


def prefetch_complete_event(
    files_loaded: int,
    learnings_loaded: int,
    skills_activated: list[str],
    **kwargs: Any,
) -> AgentEvent:
    """Create a prefetch complete event (RFC-071)."""
    return AgentEvent(
        EventType.PREFETCH_COMPLETE,
        {
            "files_loaded": files_loaded,
            "learnings_loaded": learnings_loaded,
            "skills_activated": skills_activated,
            **kwargs,
        },
    )


def prefetch_timeout_event(error: str | None = None, **kwargs: Any) -> AgentEvent:
    """Create a prefetch timeout event (RFC-071)."""
    data: dict[str, Any] = kwargs
    if error:
        data["error"] = error
    return AgentEvent(EventType.PREFETCH_TIMEOUT, data)


def lens_suggested_event(
    suggested: str,
    reason: str,
    **kwargs: Any,
) -> AgentEvent:
    """Create a lens suggested event (RFC-071)."""
    return AgentEvent(
        EventType.LENS_SUGGESTED,
        {"suggested": suggested, "reason": reason, **kwargs},
    )


# =============================================================================
# RFC-081: Inference Visibility Events
# =============================================================================


def model_start_event(
    task_id: str,
    model: str,
    prompt_tokens: int | None = None,
    estimated_time_s: float | None = None,
    **kwargs: Any,
) -> AgentEvent:
    """Create a model start event (RFC-081).

    Emitted when model generation begins. Shows spinner in CLI.

    Args:
        task_id: ID of the task triggering generation
        model: Model identifier (e.g., "gpt-oss:20b")
        prompt_tokens: Estimated prompt tokens (optional)
        estimated_time_s: Estimated generation time based on history (optional)
    """
    return AgentEvent(
        EventType.MODEL_START,
        {
            "task_id": task_id,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "estimated_time_s": estimated_time_s,
            **kwargs,
        },
    )


def model_tokens_event(
    task_id: str,
    tokens: str,
    token_count: int,
    tokens_per_second: float | None = None,
    **kwargs: Any,
) -> AgentEvent:
    """Create a model tokens event (RFC-081).

    Emitted in batches (every ~10 tokens) during streaming generation.
    Updates token counter and preview in CLI/Studio.

    Args:
        task_id: ID of the task generating
        tokens: The actual token text in this batch
        token_count: Cumulative token count so far
        tokens_per_second: Current generation speed (optional)
    """
    return AgentEvent(
        EventType.MODEL_TOKENS,
        {
            "task_id": task_id,
            "tokens": tokens,
            "token_count": token_count,
            "tokens_per_second": tokens_per_second,
            **kwargs,
        },
    )


def model_thinking_event(
    task_id: str,
    phase: str,
    content: str,
    is_complete: bool = False,
    **kwargs: Any,
) -> AgentEvent:
    """Create a model thinking event (RFC-081).

    Emitted when reasoning content is detected (<think>, Thinking..., etc.).
    Shows thinking preview panel in CLI/Studio.

    Args:
        task_id: ID of the task generating
        phase: Thinking phase ("think", "critic", "synthesize", "reasoning")
        content: The thinking content
        is_complete: True when thinking block closes
    """
    return AgentEvent(
        EventType.MODEL_THINKING,
        {
            "task_id": task_id,
            "phase": phase,
            "content": content,
            "is_complete": is_complete,
            **kwargs,
        },
    )


def model_complete_event(
    task_id: str,
    total_tokens: int,
    duration_s: float,
    tokens_per_second: float,
    time_to_first_token_ms: int | None = None,
    **kwargs: Any,
) -> AgentEvent:
    """Create a model complete event (RFC-081).

    Emitted when generation finishes. Shows final metrics.

    Args:
        task_id: ID of the task that generated
        total_tokens: Total tokens generated
        duration_s: Total generation time
        tokens_per_second: Average generation speed
        time_to_first_token_ms: Time to first token in milliseconds (optional)
    """
    return AgentEvent(
        EventType.MODEL_COMPLETE,
        {
            "task_id": task_id,
            "total_tokens": total_tokens,
            "duration_s": duration_s,
            "tokens_per_second": tokens_per_second,
            "time_to_first_token_ms": time_to_first_token_ms,
            **kwargs,
        },
    )


def model_heartbeat_event(
    task_id: str,
    elapsed_s: float,
    token_count: int,
    **kwargs: Any,
) -> AgentEvent:
    """Create a model heartbeat event (RFC-081).

    Emitted periodically during long generations to show activity.

    Args:
        task_id: ID of the task generating
        elapsed_s: Time elapsed since generation started
        token_count: Current token count
    """
    return AgentEvent(
        EventType.MODEL_HEARTBEAT,
        {
            "task_id": task_id,
            "elapsed_s": elapsed_s,
            "token_count": token_count,
            **kwargs,
        },
    )


# =============================================================================
# RFC-087: Skill Graph Event Factories
# =============================================================================


def skill_graph_resolved_event(
    lens_name: str,
    skill_count: int,
    wave_count: int,
    content_hash: str,
    **kwargs: Any,
) -> AgentEvent:
    """Create a skill graph resolved event (RFC-087).

    Emitted when the skill graph for a lens has been resolved.

    Args:
        lens_name: Name of the lens
        skill_count: Number of skills in graph
        wave_count: Number of execution waves
        content_hash: Hash for cache invalidation
    """
    return AgentEvent(
        EventType.SKILL_GRAPH_RESOLVED,
        {
            "lens_name": lens_name,
            "skill_count": skill_count,
            "wave_count": wave_count,
            "content_hash": content_hash,
            **kwargs,
        },
    )


def skill_wave_start_event(
    wave_index: int,
    total_waves: int,
    skills: list[str],
    parallel: bool = True,
    **kwargs: Any,
) -> AgentEvent:
    """Create a skill wave start event (RFC-087).

    Emitted when a wave of parallel skills starts executing.

    Args:
        wave_index: Index of this wave (0-based)
        total_waves: Total number of waves
        skills: Skill names in this wave
        parallel: Whether skills execute in parallel
    """
    return AgentEvent(
        EventType.SKILL_WAVE_START,
        {
            "wave_index": wave_index,
            "total_waves": total_waves,
            "skills": skills,
            "parallel": parallel,
            **kwargs,
        },
    )


def skill_wave_complete_event(
    wave_index: int,
    duration_ms: int,
    succeeded: list[str],
    failed: list[str],
    **kwargs: Any,
) -> AgentEvent:
    """Create a skill wave complete event (RFC-087).

    Emitted when a wave finishes execution.

    Args:
        wave_index: Index of the completed wave
        duration_ms: Wave execution time in milliseconds
        succeeded: Skills that succeeded
        failed: Skills that failed
    """
    return AgentEvent(
        EventType.SKILL_WAVE_COMPLETE,
        {
            "wave_index": wave_index,
            "duration_ms": duration_ms,
            "succeeded": succeeded,
            "failed": failed,
            **kwargs,
        },
    )


def skill_cache_hit_event(
    skill_name: str,
    cache_key: str,
    saved_ms: int,
    **kwargs: Any,
) -> AgentEvent:
    """Create a skill cache hit event (RFC-087).

    Emitted when a skill result is retrieved from cache.

    Args:
        skill_name: Name of the cached skill
        cache_key: Cache key that matched
        saved_ms: Estimated time saved in milliseconds
    """
    return AgentEvent(
        EventType.SKILL_CACHE_HIT,
        {
            "skill_name": skill_name,
            "cache_key": cache_key,
            "saved_ms": saved_ms,
            **kwargs,
        },
    )


def skill_execute_start_event(
    skill_name: str,
    wave_index: int,
    requires: list[str],
    context_keys_available: list[str],
    *,
    risk_level: str | None = None,
    has_permissions: bool = False,
    **kwargs: Any,
) -> AgentEvent:
    """Create a skill execute start event (RFC-087).

    Emitted when a single skill starts executing.

    Args:
        skill_name: Name of the skill
        wave_index: Which wave this skill is in
        requires: Context keys this skill requires
        context_keys_available: Context keys currently available
        risk_level: Security risk level (low/medium/high/critical)
        has_permissions: Whether skill declares explicit permissions
    """
    return AgentEvent(
        EventType.SKILL_EXECUTE_START,
        {
            "skill_name": skill_name,
            "wave_index": wave_index,
            "requires": requires,
            "context_keys_available": context_keys_available,
            "risk_level": risk_level,
            "has_permissions": has_permissions,
            **kwargs,
        },
    )


def skill_execute_complete_event(
    skill_name: str,
    duration_ms: int,
    produces: list[str],
    cached: bool,
    success: bool,
    error: str | None = None,
    *,
    risk_level: str | None = None,
    violations_detected: int = 0,
    **kwargs: Any,
) -> AgentEvent:
    """Create a skill execute complete event (RFC-087).

    Emitted when a skill finishes execution (success or failure).

    Args:
        skill_name: Name of the skill
        duration_ms: Execution time in milliseconds
        produces: Context keys this skill produces
        cached: Whether result was from cache
        success: Whether execution succeeded
        error: Error message if failed
        risk_level: Evaluated security risk level
        violations_detected: Number of security violations during execution
    """
    return AgentEvent(
        EventType.SKILL_EXECUTE_COMPLETE,
        {
            "skill_name": skill_name,
            "duration_ms": duration_ms,
            "produces": produces,
            "cached": cached,
            "success": success,
            "error": error,
            "risk_level": risk_level,
            "violations_detected": violations_detected,
            **kwargs,
        },
    )


# =============================================================================
# RFC-111: Skill Compilation Event Factories
# =============================================================================


def skill_compile_start_event(
    lens_name: str,
    skill_count: int,
    target_skills: list[str] | None = None,
    **kwargs: Any,
) -> AgentEvent:
    """Create a skill compile start event (RFC-111).

    Emitted when starting to compile skills into tasks.

    Args:
        lens_name: Name of the lens being compiled
        skill_count: Number of skills to compile
        target_skills: Optional subset of skills being compiled
    """
    return AgentEvent(
        EventType.SKILL_COMPILE_START,
        {
            "lens_name": lens_name,
            "skill_count": skill_count,
            "target_skills": target_skills,
            **kwargs,
        },
    )


def skill_compile_complete_event(
    lens_name: str,
    task_count: int,
    wave_count: int,
    duration_ms: int,
    cached: bool = False,
    **kwargs: Any,
) -> AgentEvent:
    """Create a skill compile complete event (RFC-111).

    Emitted when skill compilation finishes.

    Args:
        lens_name: Name of the compiled lens
        task_count: Number of tasks in compiled graph
        wave_count: Number of execution waves
        duration_ms: Compilation time in milliseconds
        cached: Whether result was from compilation cache
    """
    return AgentEvent(
        EventType.SKILL_COMPILE_COMPLETE,
        {
            "lens_name": lens_name,
            "task_count": task_count,
            "wave_count": wave_count,
            "duration_ms": duration_ms,
            "cached": cached,
            **kwargs,
        },
    )


def skill_compile_cache_hit_event(
    cache_key: str,
    task_count: int,
    wave_count: int,
    **kwargs: Any,
) -> AgentEvent:
    """Create a skill compile cache hit event (RFC-111).

    Emitted when a compiled TaskGraph is retrieved from cache.

    Args:
        cache_key: Cache key that matched
        task_count: Number of tasks in cached graph
        wave_count: Number of execution waves
    """
    return AgentEvent(
        EventType.SKILL_COMPILE_CACHE_HIT,
        {
            "cache_key": cache_key,
            "task_count": task_count,
            "wave_count": wave_count,
            **kwargs,
        },
    )


def skill_subgraph_extracted_event(
    target_skills: list[str],
    total_skills: int,
    extracted_skills: int,
    **kwargs: Any,
) -> AgentEvent:
    """Create a skill subgraph extracted event (RFC-111).

    Emitted when a subgraph is extracted for targeted execution.

    Args:
        target_skills: Skills that were targeted
        total_skills: Total skills in original graph
        extracted_skills: Skills in extracted subgraph (including dependencies)
    """
    return AgentEvent(
        EventType.SKILL_SUBGRAPH_EXTRACTED,
        {
            "target_skills": target_skills,
            "total_skills": total_skills,
            "extracted_skills": extracted_skills,
            **kwargs,
        },
    )


# =============================================================================
# RFC-089: Security Event Factories
# =============================================================================


def security_approval_requested_event(
    dag_id: str,
    dag_name: str,
    skill_count: int,
    risk_level: str,
    risk_score: float,
    flags: list[str],
    permissions: dict[str, Any] | None = None,
    **kwargs: Any,
) -> AgentEvent:
    """Create a security approval requested event (RFC-089).

    Emitted when a DAG requires user approval before execution.

    Args:
        dag_id: Unique DAG identifier
        dag_name: Human-readable DAG name
        skill_count: Number of skills in the DAG
        risk_level: Risk classification (low/medium/high/critical)
        risk_score: Numeric risk score (0.0-1.0)
        flags: Risk flags detected
        permissions: Permission scope requested (filesystem, network, shell, env)
    """
    return AgentEvent(
        EventType.SECURITY_APPROVAL_REQUESTED,
        {
            "dag_id": dag_id,
            "dag_name": dag_name,
            "skill_count": skill_count,
            "risk_level": risk_level,
            "risk_score": risk_score,
            "flags": flags,
            "permissions": permissions or {},
            **kwargs,
        },
    )


def security_approval_received_event(
    dag_id: str,
    approved: bool,
    modified: bool = False,
    remembered: bool = False,
    **kwargs: Any,
) -> AgentEvent:
    """Create a security approval received event (RFC-089).

    Emitted when user responds to an approval request.

    Args:
        dag_id: DAG that was approved/rejected
        approved: Whether user approved execution
        modified: Whether permissions were modified
        remembered: Whether approval was remembered for session
    """
    return AgentEvent(
        EventType.SECURITY_APPROVAL_RECEIVED,
        {
            "dag_id": dag_id,
            "approved": approved,
            "modified": modified,
            "remembered": remembered,
            **kwargs,
        },
    )


def security_violation_event(
    skill_name: str,
    violation_type: str,
    evidence: str,
    detection_method: str,
    action_taken: str,
    position: int | None = None,
    **kwargs: Any,
) -> AgentEvent:
    """Create a security violation event (RFC-089).

    Emitted when a security violation is detected during execution.

    Args:
        skill_name: Skill that caused the violation
        violation_type: Type of violation (credential_leak, path_traversal, etc.)
        evidence: Evidence supporting detection
        detection_method: How detected (deterministic/llm)
        action_taken: Response action (logged/paused/aborted)
        position: Position in output where detected
    """
    return AgentEvent(
        EventType.SECURITY_VIOLATION,
        {
            "skill_name": skill_name,
            "violation_type": violation_type,
            "evidence": evidence,
            "detection_method": detection_method,
            "action_taken": action_taken,
            "position": position,
            **kwargs,
        },
    )


def security_scan_complete_event(
    output_length: int,
    violations_found: int,
    scan_duration_ms: int,
    method: str,
    **kwargs: Any,
) -> AgentEvent:
    """Create a security scan complete event (RFC-089).

    Emitted when output security scan completes.

    Args:
        output_length: Length of scanned output
        violations_found: Number of violations detected
        scan_duration_ms: Scan duration in milliseconds
        method: Scan method (deterministic/llm/both)
    """
    return AgentEvent(
        EventType.SECURITY_SCAN_COMPLETE,
        {
            "output_length": output_length,
            "violations_found": violations_found,
            "scan_duration_ms": scan_duration_ms,
            "method": method,
            **kwargs,
        },
    )


def audit_log_entry_event(
    skill_name: str,
    action: str,
    risk_level: str,
    details: str | None = None,
    dag_id: str | None = None,
    **kwargs: Any,
) -> AgentEvent:
    """Create an audit log entry event (RFC-089).

    Emitted when an audit log entry is recorded.

    Args:
        skill_name: Skill involved
        action: Action type (execute/violation/denied/error)
        risk_level: Risk level at time of action
        details: Human-readable details
        dag_id: Associated DAG ID
    """
    return AgentEvent(
        EventType.AUDIT_LOG_ENTRY,
        {
            "skill_name": skill_name,
            "action": action,
            "risk_level": risk_level,
            "details": details,
            "dag_id": dag_id,
            **kwargs,
        },
    )


# =============================================================================
# RFC-090: Plan Transparency Event Factory
# =============================================================================


def plan_winner_event(
    tasks: int,
    gates: int,
    technique: str,
    selected_candidate_id: str = "candidate-0",
    task_list: list[TaskSummary] | None = None,
    gate_list: list[GateSummary] | None = None,
    **kwargs: Any,
) -> AgentEvent:
    """Create a plan winner event with optional task details (RFC-090).

    Emitted when plan selection is complete. Includes task/gate counts
    for backward compatibility, plus optional detailed lists.

    Args:
        tasks: Number of tasks in the plan
        gates: Number of validation gates
        technique: Planning technique used ("single_shot", "harmonic", "minimal")
        selected_candidate_id: ID of the selected plan candidate (required by frontend)
        task_list: Optional list of task summaries for display
        gate_list: Optional list of gate summaries for display
    """
    from sunwell.agent.event_schema import create_validated_event

    data: dict[str, Any] = {
        "tasks": tasks,
        "gates": gates,
        "technique": technique,
        "selected_candidate_id": selected_candidate_id,
        **kwargs,
    }

    # RFC-090: Include task details if available
    if task_list is not None:
        data["task_list"] = task_list
    if gate_list is not None:
        data["gate_list"] = gate_list

    return create_validated_event(EventType.PLAN_WINNER, data)
