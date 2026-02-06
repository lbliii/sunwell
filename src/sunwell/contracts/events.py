"""Event types for Adaptive Agent streaming.

Extracted from sunwell.agent.events.types per the Contracts Layer plan.
This module imports ONLY from stdlib.

Note: DEFAULT_UI_HINTS remains in sunwell.agent.events.types because it is
a runtime configuration detail, not a shared contract.
"""

from dataclasses import dataclass, field
from enum import Enum
from time import time
from typing import Any, Literal, Protocol, TypedDict, runtime_checkable


# =============================================================================
# UI Hints (RFC-097)
# =============================================================================


@dataclass(frozen=True, slots=True)
class EventUIHints:
    """UI rendering hints for frontend (RFC-097).

    Optional hints that help the frontend render events more richly.
    These are suggestions — the frontend may ignore them.

    Example:
        >>> hints = EventUIHints(icon="*", severity="info", progress=0.5)
        >>> hints.to_dict()
        {'icon': '*', 'severity': 'info', 'progress': 0.5, ...}
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
    """Suggested animation: 'pulse', 'fade-in', 'shake', 'shimmer', 'spiral', 'sparkle'."""

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


# =============================================================================
# Event Type Enum
# =============================================================================


class EventType(Enum):
    """Types of events emitted by the Adaptive Agent."""

    # ═══════════════════════════════════════════════════════════════
    # RFC-131: Session Lifecycle Events
    # ═══════════════════════════════════════════════════════════════
    SESSION_START = "session_start"
    """Session awakening. Emitted at CLI start."""

    SESSION_READY = "session_ready"
    """Session ready for goal input."""

    SESSION_END = "session_end"
    """Session complete. Clean shutdown."""

    SESSION_CRASH = "session_crash"
    """Session interrupted unexpectedly."""

    # ═══════════════════════════════════════════════════════════════
    # RFC-131: Goal Lifecycle Events
    # ═══════════════════════════════════════════════════════════════
    GOAL_RECEIVED = "goal_received"
    """Goal received and acknowledged."""

    GOAL_ANALYZING = "goal_analyzing"
    """Analyzing goal complexity and route."""

    GOAL_READY = "goal_ready"
    """Plan illuminated, ready to execute."""

    GOAL_COMPLETE = "goal_complete"
    """Goal achieved successfully."""

    GOAL_FAILED = "goal_failed"
    """Goal could not be achieved."""

    GOAL_PAUSED = "goal_paused"
    """Goal paused at checkpoint."""

    # ═══════════════════════════════════════════════════════════════
    # Memory events (Simulacrum integration)
    # ═══════════════════════════════════════════════════════════════
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

    # RFC-MEMORY: Unified memory events
    ORIENT = "orient"
    """Memory loaded, constraints identified (RFC-MEMORY)."""

    LEARNING_ADDED = "learning_added"
    """New learning extracted and recorded."""

    DECISION_MADE = "decision_made"
    """Architectural decision recorded."""

    FAILURE_RECORDED = "failure_recorded"
    """Failed approach recorded."""

    BRIEFING_UPDATED = "briefing_updated"
    """Briefing saved for next session."""

    KNOWLEDGE_RETRIEVED = "knowledge_retrieved"
    """Knowledge retrieved from simulacrum for planning."""

    TEMPLATE_MATCHED = "template_matched"
    """Template matched for guided planning."""

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

    TASK_OUTPUT = "task_output"
    """Task produced output that should be displayed (no target file)."""

    TASK_FAILED = "task_failed"
    """Task execution failed."""

    # Parallel execution events
    PARALLEL_GROUP_START = "parallel_group_start"
    """Starting parallel execution of a task group."""

    PARALLEL_GROUP_COMPLETE = "parallel_group_complete"
    """Parallel task group completed."""

    PARALLEL_DISPATCH_START = "parallel_dispatch_start"
    """TaskDispatcher beginning parallel execution phase."""

    PARALLEL_DISPATCH_COMPLETE = "parallel_dispatch_complete"
    """TaskDispatcher finished all execution."""

    ISOLATION_WARNING = "isolation_warning"
    """Workspace isolation warning (e.g., non-git fallback)."""

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

    LOG = "log"
    """General log message for verbose/debug output."""

    # RFC-125: Recovery events
    RECOVERY_SAVED = "recovery_saved"
    """Recovery state saved — user can review."""

    RECOVERY_LOADED = "recovery_loaded"
    """Resuming from recovery state."""

    RECOVERY_RESOLVED = "recovery_resolved"
    """Recovery completed — all artifacts passed."""

    RECOVERY_ABORTED = "recovery_aborted"
    """User chose to abort recovery."""

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

    # Contract verification events
    CONTRACT_VERIFY_START = "contract_verify_start"
    """Starting Protocol contract verification."""

    CONTRACT_VERIFY_PASS = "contract_verify_pass"
    """Contract verification passed."""

    CONTRACT_VERIFY_FAIL = "contract_verify_fail"
    """Contract verification failed."""

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
    """Skill graph resolved for lens."""

    SKILL_WAVE_START = "skill_wave_start"
    """Starting execution of a wave of parallel skills."""

    SKILL_WAVE_COMPLETE = "skill_wave_complete"
    """Wave execution completed."""

    SKILL_CACHE_HIT = "skill_cache_hit"
    """Skill result retrieved from cache."""

    SKILL_EXECUTE_START = "skill_execute_start"
    """Starting execution of a single skill."""

    SKILL_EXECUTE_COMPLETE = "skill_execute_complete"
    """Skill execution completed (success or failure)."""

    # Skill compilation events (RFC-111)
    SKILL_COMPILE_START = "skill_compile_start"
    """Starting skill compilation."""

    SKILL_COMPILE_COMPLETE = "skill_compile_complete"
    """Skill compilation completed."""

    SKILL_COMPILE_CACHE_HIT = "skill_compile_cache_hit"
    """Compiled TaskGraph retrieved from cache."""

    SKILL_SUBGRAPH_EXTRACTED = "skill_subgraph_extracted"
    """Subgraph extracted for targeted skill execution."""

    # Security events (RFC-089)
    SECURITY_APPROVAL_REQUESTED = "security_approval_requested"
    """DAG requires user approval before execution."""

    SECURITY_APPROVAL_RECEIVED = "security_approval_received"
    """User responded to approval request."""

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

    # Tool calling events
    TOOL_START = "tool_start"
    """Tool call initiated."""

    TOOL_COMPLETE = "tool_complete"
    """Tool call completed successfully."""

    TOOL_ERROR = "tool_error"
    """Tool call failed."""

    TOOL_LOOP_START = "tool_loop_start"
    """Agentic tool loop started."""

    TOOL_LOOP_TURN = "tool_loop_turn"
    """Turn in the agentic tool loop."""

    TOOL_LOOP_COMPLETE = "tool_loop_complete"
    """Agentic tool loop finished."""

    # RFC-134: Tool introspection and escalation events
    TOOL_REPAIR = "tool_repair"
    """Tool call arguments were repaired by introspection."""

    TOOL_BLOCKED = "tool_blocked"
    """Tool call blocked due to invalid arguments."""

    TOOL_RETRY = "tool_retry"
    """Retrying tool call with escalated strategy."""

    TOOL_ESCALATE = "tool_escalate"
    """Tool failures exceeded retry limit, escalating to user."""

    # Reliability detection events
    RELIABILITY_WARNING = "reliability_warning"
    """Detected potential reliability issue."""

    RELIABILITY_HALLUCINATION = "reliability_hallucination"
    """Model appears to have hallucinated task completion."""

    TOOL_PATTERN_LEARNED = "tool_pattern_learned"
    """Recorded a successful tool pattern for future use."""

    PROGRESSIVE_UNLOCK = "progressive_unlock"
    """New tool category unlocked by progressive policy."""

    # Convergence events (RFC-123)
    CONVERGENCE_START = "convergence_start"
    """Starting convergence loop."""

    CONVERGENCE_ITERATION_START = "convergence_iteration_start"
    """Starting a convergence iteration."""

    CONVERGENCE_ITERATION_COMPLETE = "convergence_iteration_complete"
    """Completed a convergence iteration."""

    CONVERGENCE_FIXING = "convergence_fixing"
    """Agent is fixing errors found by gates."""

    CONVERGENCE_STABLE = "convergence_stable"
    """All gates pass — code is stable."""

    CONVERGENCE_TIMEOUT = "convergence_timeout"
    """Convergence timed out."""

    CONVERGENCE_STUCK = "convergence_stuck"
    """Same error keeps recurring — escalating."""

    CONVERGENCE_MAX_ITERATIONS = "convergence_max_iterations"
    """Max iterations reached without stability."""

    CONVERGENCE_BUDGET_EXCEEDED = "convergence_budget_exceeded"
    """Token budget exhausted."""

    # Model delegation events (RFC-137)
    DELEGATION_STARTED = "delegation_started"
    """Smart-to-dumb model delegation initiated (RFC-137)."""

    EPHEMERAL_LENS_CREATED = "ephemeral_lens_created"
    """EphemeralLens generated by smart model (RFC-137)."""

    # ═══════════════════════════════════════════════════════════════
    # Conversational DAG Architecture
    # ═══════════════════════════════════════════════════════════════
    INTENT_CLASSIFIED = "intent_classified"
    """User intent classified into DAG path."""

    NODE_TRANSITION = "node_transition"
    """Transitioned between nodes in the intent DAG."""

    # ═══════════════════════════════════════════════════════════════
    # Domain Detection
    # ═══════════════════════════════════════════════════════════════
    DOMAIN_DETECTED = "domain_detected"
    """Domain detected for goal (code, research, writing, etc.)."""

    # Agent Constellation events (RFC-130)
    SPECIALIST_SPAWNED = "specialist_spawned"
    """Specialist agent spawned for a subtask."""

    SPECIALIST_COMPLETED = "specialist_completed"
    """Specialist agent completed its task."""

    CHECKPOINT_FOUND = "checkpoint_found"
    """Found existing checkpoint for goal (RFC-130)."""

    CHECKPOINT_SAVED = "checkpoint_saved"
    """Semantic checkpoint saved (RFC-130)."""

    PHASE_COMPLETE = "phase_complete"
    """Agent completed a semantic phase (RFC-130)."""

    AUTONOMOUS_ACTION_BLOCKED = "autonomous_action_blocked"
    """Autonomous action blocked by guardrails (RFC-130)."""

    GUARD_EVOLUTION_SUGGESTED = "guard_evolution_suggested"
    """Guard evolution suggested based on violations (RFC-130)."""

    # ═══════════════════════════════════════════════════════════════
    # File/Artifact Events
    # ═══════════════════════════════════════════════════════════════
    FILE_CREATED = "file_created"
    """File created by the agent."""

    FILE_MODIFIED = "file_modified"
    """File modified by the agent."""

    FILE_DELETED = "file_deleted"
    """File deleted by the agent."""

    FILE_READ = "file_read"
    """File read by the agent."""

    CODE_GENERATED = "code_generated"
    """Code generated and ready to display."""

    LEARNING_EXTRACTED = "learning_extracted"
    """Learning extracted from generated code or execution."""

    # ═══════════════════════════════════════════════════════════════
    # Reliability Events (Solo Dev Hardening)
    # ═══════════════════════════════════════════════════════════════
    CIRCUIT_BREAKER_OPEN = "circuit_breaker_open"
    """Circuit breaker opened due to consecutive failures."""

    BUDGET_EXHAUSTED = "budget_exhausted"
    """Token budget fully consumed, execution stopped."""

    BUDGET_WARNING = "budget_warning"
    """Token budget running low (below warning threshold)."""

    HEALTH_CHECK_FAILED = "health_check_failed"
    """Pre-flight health check failed, blocking execution."""

    HEALTH_WARNING = "health_warning"
    """Health check found non-critical issues."""

    TIMEOUT = "timeout"
    """Execution timed out."""


# =============================================================================
# Agent Event Dataclass
# =============================================================================


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
        """Convert to JSON-serializable dict.

        Note: DEFAULT_UI_HINTS lookup is handled by the caller or
        the original module (sunwell.agent.events.types), not here.
        This keeps contracts free of runtime configuration.
        """
        result = {
            "type": self.type.value,
            "data": self.data,
            "timestamp": self.timestamp,
        }
        if self.ui_hints:
            result["ui_hints"] = self.ui_hints.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentEvent":
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

    def with_ui_hints(self, hints: EventUIHints) -> "AgentEvent":
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
# Event Emitter Protocol
# =============================================================================


@runtime_checkable
class EventEmitter(Protocol):
    """Protocol for event emitters.

    All event-emitting code should implement this protocol.
    """

    def emit(self, event: AgentEvent) -> None:
        """Emit an event.

        Args:
            event: The event to emit
        """
        ...
