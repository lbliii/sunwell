"""Type-safe event schemas using Python's type system.

This module provides TypedDict schemas for each event type, ensuring
type safety and validation at both Python and TypeScript boundaries.

Uses:
- TypedDict for event data contracts
- Protocol for event emitter contracts
- Runtime validation for required fields
- Type generation for TypeScript
- ty for type checking (not mypy)
"""


import logging
import os
from dataclasses import dataclass
from typing import Any, Protocol, TypedDict, runtime_checkable

from sunwell.adaptive.events import AgentEvent, EventType

# =============================================================================
# Event Data Schemas (TypedDict for type safety)
# =============================================================================


class PlanStartData(TypedDict, total=False):
    """Data for plan_start event."""
    goal: str


class PlanWinnerData(TypedDict, total=False):
    """Data for plan_winner event.

    Required: tasks
    Optional: All other fields (backward-compatible with non-Harmonic planners)

    RFC-060: This schema is the single source of truth for plan_winner events.
    """
    # Core fields (legacy)
    tasks: int  # REQUIRED - enforced via REQUIRED_FIELDS
    artifact_count: int
    gates: int
    technique: str

    # RFC-058: Harmonic planning fields
    selected_candidate_id: str  # REQUIRED - ID of selected candidate (e.g., 'candidate-0')
    total_candidates: int  # How many candidates were generated
    metrics: dict[str, Any]  # PlanMetrics as dict (score, depth, width, etc.)
    selection_reason: str  # Human-readable selection reason
    variance_strategy: str  # "prompting" | "temperature" | "constraints" | "mixed"
    variance_config: dict[str, Any]  # Variance config used for selected candidate
    refinement_rounds: int  # How many refinement rounds were run
    final_score_improvement: float  # Total score improvement from refinement
    score: float  # CANONICAL - top-level score (same as metrics.score)

    # RFC-090: Plan transparency - detailed task/gate lists
    task_list: list[dict[str, Any]]  # List of TaskSummary dicts
    gate_list: list[dict[str, Any]]  # List of GateSummary dicts


class TaskStartData(TypedDict, total=False):
    """Data for task_start event."""
    task_id: str  # Required
    artifact_id: str  # Alias for compatibility
    description: str  # Required


class TaskProgressData(TypedDict, total=False):
    """Data for task_progress event."""
    task_id: str  # Required
    artifact_id: str  # Alias for compatibility
    progress: int  # 0-100
    message: str


class TaskCompleteData(TypedDict, total=False):
    """Data for task_complete event."""
    task_id: str  # Required
    artifact_id: str  # Alias for compatibility
    duration_ms: int  # Required
    file: str | None


class TaskFailedData(TypedDict, total=False):
    """Data for task_failed event."""
    task_id: str  # Required
    artifact_id: str  # Alias for compatibility
    error: str  # Required


class MemoryLearningData(TypedDict, total=False):
    """Data for memory_learning event."""
    fact: str  # Required
    category: str  # Required


class CompleteData(TypedDict, total=False):
    """Data for complete event."""
    tasks_completed: int  # Required
    tasks_failed: int
    gates_passed: int
    duration_s: float
    learnings_count: int
    completed: int  # Alias for tasks_completed
    failed: int  # Alias for tasks_failed


class ErrorData(TypedDict, total=False):
    """Data for error event."""
    message: str  # Required
    phase: str | None  # "planning" | "discovery" | "execution" | "validation"
    context: dict[str, Any] | None  # Additional context (artifact_id, task_id, etc.)
    error_type: str | None  # Exception class name
    traceback: str | None  # Optional: full traceback for verbose mode


# =============================================================================
# Planning Events
# =============================================================================


class PlanCandidateData(TypedDict, total=False):
    """Data for plan_candidate event (legacy)."""
    candidate_id: str  # Use candidate_id for matching
    artifact_count: int
    description: str


class PlanExpandedData(TypedDict, total=False):
    """Data for plan_expanded event."""
    new_tasks: int
    total_tasks: int
    reason: str


class PlanAssessData(TypedDict, total=False):
    """Data for plan_assess event."""
    complete: bool
    remaining_tasks: int
    assessment: str


# =============================================================================
# Harmonic Planning Events (RFC-058)
# =============================================================================


class PlanCandidateStartData(TypedDict, total=False):
    """Data for plan_candidate_start event."""
    total_candidates: int  # Required
    variance_strategy: str  # e.g., "prompting", "temperature"


class PlanCandidateGeneratedData(TypedDict, total=False):
    """Data for plan_candidate_generated event."""
    candidate_id: str  # REQUIRED - stable identifier (e.g., 'candidate-0')
    artifact_count: int  # Required
    progress: int  # Current count (1-based)
    total_candidates: int  # Required
    variance_config: dict[str, Any]  # Variance configuration used


class PlanCandidatesCompleteData(TypedDict, total=False):
    """Data for plan_candidates_complete event.

    RFC-060: Aligned with actual HarmonicPlanner emission.
    """
    total_candidates: int  # Kept for backward compat
    total_artifacts: int  # Kept for backward compat
    successful_candidates: int  # How many candidates succeeded
    failed_candidates: int  # How many candidates failed


class PlanCandidateScoredData(TypedDict, total=False):
    """Data for plan_candidate_scored event."""
    candidate_id: str  # REQUIRED - stable identifier (e.g., 'candidate-0')
    score: float  # Required
    progress: int  # Current count (1-based)
    total_candidates: int  # Required
    metrics: dict[str, Any]  # PlanMetrics as dict


class PlanScoringCompleteData(TypedDict, total=False):
    """Data for plan_scoring_complete event."""
    total_scored: int  # Required


# =============================================================================
# Refinement Events
# =============================================================================


class PlanRefineStartData(TypedDict, total=False):
    """Data for plan_refine_start event."""
    round: int  # Required
    total_rounds: int  # Required
    current_score: float
    improvements_identified: list[str]


class PlanRefineAttemptData(TypedDict, total=False):
    """Data for plan_refine_attempt event."""
    round: int  # Required
    improvements_applied: list[str]
    new_score: float


class PlanRefineCompleteData(TypedDict, total=False):
    """Data for plan_refine_complete event.

    Required: round
    Optional: All other fields

    RFC-060: Field names aligned with frontend expectations.
    """
    round: int  # REQUIRED - which refinement round (1-indexed)
    improved: bool  # Did this round improve the plan?
    old_score: float | None  # Score before refinement
    new_score: float | None  # Score after refinement
    improvement: float | None  # Delta (new_score - old_score)
    reason: str | None  # Why refinement stopped or continued
    improvements_applied: list[str]  # List of improvements made


class PlanRefineFinalData(TypedDict, total=False):
    """Data for plan_refine_final event."""
    total_rounds: int  # Required
    final_score: float
    total_improvements: int


# =============================================================================
# Memory Events
# =============================================================================


class MemoryLoadData(TypedDict, total=False):
    """Data for memory_load event."""
    session_id: str | None


class MemoryLoadedData(TypedDict, total=False):
    """Data for memory_loaded event."""
    session_id: str | None
    fact_count: int
    dead_end_count: int


class MemoryNewData(TypedDict, total=False):
    """Data for memory_new event."""
    session_id: str | None


class MemoryDeadEndData(TypedDict, total=False):
    """Data for memory_dead_end event."""
    approach: str  # Required
    reason: str


class MemoryCheckpointData(TypedDict, total=False):
    """Data for memory_checkpoint event."""
    session_id: str | None
    fact_count: int


class MemorySavedData(TypedDict, total=False):
    """Data for memory_saved event."""
    session_id: str | None
    fact_count: int
    dead_end_count: int


# =============================================================================
# Signal Events
# =============================================================================


class SignalData(TypedDict, total=False):
    """Data for signal event."""
    status: str  # Required: "extracting" | "extracted"
    signals: dict[str, Any] | None  # Signal extraction results


class SignalRouteData(TypedDict, total=False):
    """Data for signal_route event."""
    route: str  # Required
    complexity: str
    reasoning: str


# =============================================================================
# Gate Events
# =============================================================================


class GateStartData(TypedDict, total=False):
    """Data for gate_start event."""
    gate_id: str  # Required
    gate_type: str  # Required


class GateStepData(TypedDict, total=False):
    """Data for gate_step event."""
    gate_id: str  # Required
    step: str  # Required
    passed: bool  # Required
    message: str


class GatePassData(TypedDict, total=False):
    """Data for gate_pass event."""
    gate_id: str  # Required
    gate_type: str


class GateFailData(TypedDict, total=False):
    """Data for gate_fail event."""
    gate_id: str  # Required
    gate_type: str
    failed_step: str
    errors: list[str]


# =============================================================================
# Validation Events
# =============================================================================


class ValidateStartData(TypedDict, total=False):
    """Data for validate_start event."""
    artifact_id: str | None
    validation_levels: list[str]


class ValidateLevelData(TypedDict, total=False):
    """Data for validate_level event."""
    level: str  # Required: "syntax" | "import" | "runtime"
    artifact_id: str | None
    passed: bool


class ValidateErrorData(TypedDict, total=False):
    """Data for validate_error event."""
    error_type: str  # Required
    message: str  # Required
    file: str | None
    line: int | None


class ValidatePassData(TypedDict, total=False):
    """Data for validate_pass event."""
    level: str  # Required
    artifact_id: str | None


# =============================================================================
# Fix Events
# =============================================================================


class FixStartData(TypedDict, total=False):
    """Data for fix_start event."""
    error_count: int
    artifact_id: str | None


class FixProgressData(TypedDict, total=False):
    """Data for fix_progress event."""
    stage: str  # Required
    progress: float  # Required: 0.0-1.0
    detail: str


class FixAttemptData(TypedDict, total=False):
    """Data for fix_attempt event."""
    attempt: int  # Required
    fix_type: str
    error_id: str | None


class FixCompleteData(TypedDict, total=False):
    """Data for fix_complete event."""
    fixes_applied: int
    errors_remaining: int


class FixFailedData(TypedDict, total=False):
    """Data for fix_failed event."""
    attempt: int  # Required
    reason: str
    error_id: str | None


# =============================================================================
# Discovery Progress Event (RFC-059)
# =============================================================================


class PlanDiscoveryProgressData(TypedDict, total=False):
    """Data for plan_discovery_progress event."""
    artifacts_discovered: int  # Required
    phase: str  # Required: "discovering" | "parsing" | "validating" | "building_graph" | "complete"
    total_estimated: int | None  # Optional: if known
    current_artifact: str | None  # Optional: current artifact being processed


# =============================================================================
# Other Events
# =============================================================================


class EscalateData(TypedDict, total=False):
    """Data for escalate event."""
    reason: str  # Required
    action: str
    context: dict[str, Any] | None


# =============================================================================
# Integration Verification Events (RFC-067)
# =============================================================================


class IntegrationCheckStartData(TypedDict, total=False):
    """Data for integration_check_start event."""
    edge_id: str  # Required
    check_type: str  # Required
    source_artifact: str  # Required
    target_artifact: str  # Required


class IntegrationCheckPassData(TypedDict, total=False):
    """Data for integration_check_pass event."""
    edge_id: str  # Required
    check_type: str  # Required
    verification_method: str  # "ast", "regex", "exists"


class IntegrationCheckFailData(TypedDict, total=False):
    """Data for integration_check_fail event."""
    edge_id: str  # Required
    check_type: str  # Required
    expected: str  # Required
    actual: str  # Required
    suggested_fix: str | None


class StubDetectedData(TypedDict, total=False):
    """Data for stub_detected event."""
    artifact_id: str  # Required
    file_path: str  # Required
    stub_type: str  # Required: "pass", "todo", "not_implemented", "ellipsis"
    location: str  # Required: line:col or function name


class OrphanDetectedData(TypedDict, total=False):
    """Data for orphan_detected event."""
    artifact_id: str  # Required
    file_path: str  # Required


class WireTaskGeneratedData(TypedDict, total=False):
    """Data for wire_task_generated event."""
    task_id: str  # Required
    source_artifact: str  # Required
    target_artifact: str  # Required
    integration_type: str  # Required: "import", "call", "route", etc.


# =============================================================================
# RFC-087: Skill Graph Event Schemas
# =============================================================================


class SkillGraphResolvedData(TypedDict, total=False):
    """Data for skill_graph_resolved event."""
    lens_name: str  # Required
    skill_count: int  # Required
    wave_count: int  # Required
    content_hash: str  # Required


class SkillWaveStartData(TypedDict, total=False):
    """Data for skill_wave_start event."""
    wave_index: int  # Required
    total_waves: int  # Required
    skills: list[str]  # Required - skill names in this wave
    parallel: bool  # Whether skills execute in parallel


class SkillWaveCompleteData(TypedDict, total=False):
    """Data for skill_wave_complete event."""
    wave_index: int  # Required
    duration_ms: int  # Required
    succeeded: list[str]  # Required - skills that succeeded
    failed: list[str]  # Required - skills that failed


class SkillCacheHitData(TypedDict, total=False):
    """Data for skill_cache_hit event."""
    skill_name: str  # Required
    cache_key: str  # Required
    saved_ms: int  # Required - estimated time saved


class SkillExecuteStartData(TypedDict, total=False):
    """Data for skill_execute_start event."""
    skill_name: str  # Required
    wave_index: int  # Required
    requires: list[str]  # Required - context keys this skill needs
    context_keys_available: list[str]  # Required - context keys currently available
    # RFC-089: Security metadata
    risk_level: str | None  # low/medium/high/critical (None = not assessed)
    has_permissions: bool  # Whether skill declares explicit permissions


class SkillExecuteCompleteData(TypedDict, total=False):
    """Data for skill_execute_complete event."""
    skill_name: str  # Required
    duration_ms: int  # Required
    produces: list[str]  # Required - context keys produced
    cached: bool  # Required - whether result was from cache
    success: bool  # Required - whether execution succeeded
    error: str | None  # Error message if failed
    # RFC-089: Security metadata
    risk_level: str | None  # Evaluated risk level after execution
    violations_detected: int  # Number of security violations during execution


# =============================================================================
# RFC-089: Security Event Schemas
# =============================================================================


class SecurityApprovalRequestedData(TypedDict, total=False):
    """Data for security_approval_requested event."""
    dag_id: str  # Required
    dag_name: str  # Required
    skill_count: int  # Required
    risk_level: str  # Required: low/medium/high/critical
    risk_score: float  # Required: 0.0-1.0
    flags: list[str]  # Required - risk flags detected
    permissions: dict[str, Any]  # Permission scope (filesystem, network, etc.)


class SecurityApprovalReceivedData(TypedDict, total=False):
    """Data for security_approval_received event."""
    dag_id: str  # Required
    approved: bool  # Required
    modified: bool  # Whether permissions were modified
    remembered: bool  # Whether remembered for session


class SecurityViolationData(TypedDict, total=False):
    """Data for security_violation event."""
    skill_name: str  # Required
    violation_type: str  # Required: credential_leak, path_traversal, etc.
    evidence: str  # Required
    detection_method: str  # Required: deterministic/llm
    action_taken: str  # Required: logged/paused/aborted
    position: int | None  # Position in output


class SecurityScanCompleteData(TypedDict, total=False):
    """Data for security_scan_complete event."""
    output_length: int  # Required
    violations_found: int  # Required
    scan_duration_ms: int  # Required
    method: str  # Required: deterministic/llm/both


class AuditLogEntryData(TypedDict, total=False):
    """Data for audit_log_entry event."""
    skill_name: str  # Required
    action: str  # Required: execute/violation/denied/error
    risk_level: str  # Required: low/medium/high/critical
    details: str | None  # Human-readable details
    dag_id: str | None  # Associated DAG


# =============================================================================
# Event Schema Registry
# =============================================================================

EVENT_SCHEMAS: dict[EventType, type[TypedDict]] = {
    # Planning events
    EventType.PLAN_START: PlanStartData,
    EventType.PLAN_CANDIDATE: PlanCandidateData,
    EventType.PLAN_WINNER: PlanWinnerData,
    EventType.PLAN_EXPANDED: PlanExpandedData,
    EventType.PLAN_ASSESS: PlanAssessData,
    # Harmonic planning events (RFC-058)
    EventType.PLAN_CANDIDATE_START: PlanCandidateStartData,
    EventType.PLAN_CANDIDATE_GENERATED: PlanCandidateGeneratedData,
    EventType.PLAN_CANDIDATES_COMPLETE: PlanCandidatesCompleteData,
    EventType.PLAN_CANDIDATE_SCORED: PlanCandidateScoredData,
    EventType.PLAN_SCORING_COMPLETE: PlanScoringCompleteData,
    # Refinement events
    EventType.PLAN_REFINE_START: PlanRefineStartData,
    EventType.PLAN_REFINE_ATTEMPT: PlanRefineAttemptData,
    EventType.PLAN_REFINE_COMPLETE: PlanRefineCompleteData,
    EventType.PLAN_REFINE_FINAL: PlanRefineFinalData,
    # Memory events
    EventType.MEMORY_LOAD: MemoryLoadData,
    EventType.MEMORY_LOADED: MemoryLoadedData,
    EventType.MEMORY_NEW: MemoryNewData,
    EventType.MEMORY_LEARNING: MemoryLearningData,
    EventType.MEMORY_DEAD_END: MemoryDeadEndData,
    EventType.MEMORY_CHECKPOINT: MemoryCheckpointData,
    EventType.MEMORY_SAVED: MemorySavedData,
    # Signal events
    EventType.SIGNAL: SignalData,
    EventType.SIGNAL_ROUTE: SignalRouteData,
    # Gate events
    EventType.GATE_START: GateStartData,
    EventType.GATE_STEP: GateStepData,
    EventType.GATE_PASS: GatePassData,
    EventType.GATE_FAIL: GateFailData,
    # Execution events
    EventType.TASK_START: TaskStartData,
    EventType.TASK_PROGRESS: TaskProgressData,
    EventType.TASK_COMPLETE: TaskCompleteData,
    EventType.TASK_FAILED: TaskFailedData,
    # Validation events
    EventType.VALIDATE_START: ValidateStartData,
    EventType.VALIDATE_LEVEL: ValidateLevelData,
    EventType.VALIDATE_ERROR: ValidateErrorData,
    EventType.VALIDATE_PASS: ValidatePassData,
    # Fix events
    EventType.FIX_START: FixStartData,
    EventType.FIX_PROGRESS: FixProgressData,
    EventType.FIX_ATTEMPT: FixAttemptData,
    EventType.FIX_COMPLETE: FixCompleteData,
    EventType.FIX_FAILED: FixFailedData,
    # Completion events
    EventType.COMPLETE: CompleteData,
    EventType.ERROR: ErrorData,
    EventType.ESCALATE: EscalateData,
    # Discovery progress (RFC-059)
    EventType.PLAN_DISCOVERY_PROGRESS: PlanDiscoveryProgressData,
    # Integration verification events (RFC-067)
    EventType.INTEGRATION_CHECK_START: IntegrationCheckStartData,
    EventType.INTEGRATION_CHECK_PASS: IntegrationCheckPassData,
    EventType.INTEGRATION_CHECK_FAIL: IntegrationCheckFailData,
    EventType.STUB_DETECTED: StubDetectedData,
    EventType.ORPHAN_DETECTED: OrphanDetectedData,
    EventType.WIRE_TASK_GENERATED: WireTaskGeneratedData,
    # Skill graph events (RFC-087)
    EventType.SKILL_GRAPH_RESOLVED: SkillGraphResolvedData,
    EventType.SKILL_WAVE_START: SkillWaveStartData,
    EventType.SKILL_WAVE_COMPLETE: SkillWaveCompleteData,
    EventType.SKILL_CACHE_HIT: SkillCacheHitData,
    EventType.SKILL_EXECUTE_START: SkillExecuteStartData,
    EventType.SKILL_EXECUTE_COMPLETE: SkillExecuteCompleteData,
    # Security events (RFC-089)
    EventType.SECURITY_APPROVAL_REQUESTED: SecurityApprovalRequestedData,
    EventType.SECURITY_APPROVAL_RECEIVED: SecurityApprovalReceivedData,
    EventType.SECURITY_VIOLATION: SecurityViolationData,
    EventType.SECURITY_SCAN_COMPLETE: SecurityScanCompleteData,
    EventType.AUDIT_LOG_ENTRY: AuditLogEntryData,
}

# Required fields per event type
REQUIRED_FIELDS: dict[EventType, set[str]] = {
    # Planning events
    EventType.PLAN_WINNER: {"tasks", "selected_candidate_id"},
    # Harmonic planning events
    EventType.PLAN_CANDIDATE_START: {"total_candidates"},
    EventType.PLAN_CANDIDATE_GENERATED: {"candidate_id", "artifact_count", "total_candidates"},
    EventType.PLAN_CANDIDATES_COMPLETE: {"total_candidates"},
    EventType.PLAN_CANDIDATE_SCORED: {"candidate_id", "score", "total_candidates"},
    EventType.PLAN_SCORING_COMPLETE: {"total_scored"},
    # Refinement events
    EventType.PLAN_REFINE_START: {"round", "total_rounds"},
    EventType.PLAN_REFINE_ATTEMPT: {"round"},
    EventType.PLAN_REFINE_COMPLETE: {"round"},
    EventType.PLAN_REFINE_FINAL: {"total_rounds"},
    # Memory events
    EventType.MEMORY_LEARNING: {"fact", "category"},
    EventType.MEMORY_DEAD_END: {"approach"},
    # Signal events
    EventType.SIGNAL: {"status"},
    EventType.SIGNAL_ROUTE: {"route"},
    # Gate events
    EventType.GATE_START: {"gate_id", "gate_type"},
    EventType.GATE_STEP: {"gate_id", "step", "passed"},
    EventType.GATE_PASS: {"gate_id"},
    EventType.GATE_FAIL: {"gate_id"},
    # Execution events
    EventType.TASK_START: {"task_id", "description"},
    EventType.TASK_PROGRESS: {"task_id"},
    EventType.TASK_COMPLETE: {"task_id", "duration_ms"},
    EventType.TASK_FAILED: {"task_id", "error"},
    # Validation events
    EventType.VALIDATE_LEVEL: {"level"},
    EventType.VALIDATE_ERROR: {"error_type", "message"},
    EventType.VALIDATE_PASS: {"level"},
    # Fix events
    EventType.FIX_PROGRESS: {"stage", "progress"},
    EventType.FIX_ATTEMPT: {"attempt"},
    EventType.FIX_FAILED: {"attempt"},
    # Completion events
    EventType.COMPLETE: {"tasks_completed"},
    EventType.ERROR: {"message"},
    EventType.ESCALATE: {"reason"},
    # Discovery progress (RFC-059)
    EventType.PLAN_DISCOVERY_PROGRESS: {"artifacts_discovered", "phase"},
    # Integration verification events (RFC-067)
    EventType.INTEGRATION_CHECK_START: {
        "edge_id", "check_type", "source_artifact", "target_artifact"
    },
    EventType.INTEGRATION_CHECK_PASS: {"edge_id", "check_type"},
    EventType.INTEGRATION_CHECK_FAIL: {"edge_id", "check_type", "expected", "actual"},
    EventType.STUB_DETECTED: {"artifact_id", "file_path", "stub_type", "location"},
    EventType.ORPHAN_DETECTED: {"artifact_id", "file_path"},
    EventType.WIRE_TASK_GENERATED: {
        "task_id", "source_artifact", "target_artifact", "integration_type"
    },
    # Skill graph events (RFC-087)
    EventType.SKILL_GRAPH_RESOLVED: {
        "lens_name", "skill_count", "wave_count", "content_hash"
    },
    EventType.SKILL_WAVE_START: {"wave_index", "total_waves", "skills"},
    EventType.SKILL_WAVE_COMPLETE: {"wave_index", "duration_ms", "succeeded", "failed"},
    EventType.SKILL_CACHE_HIT: {"skill_name", "cache_key", "saved_ms"},
    EventType.SKILL_EXECUTE_START: {
        "skill_name", "wave_index", "requires", "context_keys_available"
    },
    EventType.SKILL_EXECUTE_COMPLETE: {
        "skill_name", "duration_ms", "produces", "cached", "success"
    },
    # Security events (RFC-089)
    EventType.SECURITY_APPROVAL_REQUESTED: {
        "dag_id", "dag_name", "skill_count", "risk_level", "risk_score", "flags"
    },
    EventType.SECURITY_APPROVAL_RECEIVED: {"dag_id", "approved"},
    EventType.SECURITY_VIOLATION: {
        "skill_name", "violation_type", "evidence", "detection_method", "action_taken"
    },
    EventType.SECURITY_SCAN_COMPLETE: {
        "output_length", "violations_found", "scan_duration_ms", "method"
    },
    EventType.AUDIT_LOG_ENTRY: {"skill_name", "action", "risk_level"},
}


# =============================================================================
# Event Validation (RFC-060)
# =============================================================================

# RFC-060: Validation mode control via environment variable
# Values: "strict" (raise on error), "lenient" (log warning), "off" (no validation)
# Default: "lenient" in production, can be set to "strict" for dev/CI
_VALIDATION_MODE_VAR = "SUNWELL_EVENT_VALIDATION"


def get_validation_mode() -> str:
    """Get the current event validation mode.

    RFC-060: Controlled via SUNWELL_EVENT_VALIDATION environment variable.

    Returns:
        "strict" - Raise ValueError on validation failure
        "lenient" - Log warning but emit event anyway (default)
        "off" - No validation
    """
    return os.environ.get(_VALIDATION_MODE_VAR, "lenient").lower()


def validate_event_data(event_type: EventType, data: dict[str, Any]) -> dict[str, Any]:
    """Validate event data against schema.

    Args:
        event_type: The event type
        data: Event data to validate

    Returns:
        Validated and normalized data

    Raises:
        ValueError: If required fields are missing (only in strict mode)
    """
    # Normalize field names (artifact_id → task_id)
    normalized = dict(data)

    # Map artifact_id to task_id for compatibility
    if "artifact_id" in normalized and "task_id" not in normalized:
        normalized["task_id"] = normalized["artifact_id"]

    # Check required fields
    required = REQUIRED_FIELDS.get(event_type, set())
    missing = required - set(normalized.keys())

    if missing:
        error_msg = (
            f"Event {event_type.value} missing required fields: {missing}. "
            f"Got: {list(normalized.keys())}"
        )
        mode = get_validation_mode()
        if mode == "strict":
            raise ValueError(error_msg)
        elif mode == "lenient":
            logging.warning(f"[RFC-060] Event validation warning: {error_msg}")
        # mode == "off": silently continue

    return normalized


def create_validated_event(
    event_type: EventType,
    data: dict[str, Any],
    **kwargs: Any,
) -> AgentEvent:
    """Create an AgentEvent with validated data.

    RFC-060: Validation behavior controlled by SUNWELL_EVENT_VALIDATION env var.
    - "strict": Raise ValueError on validation failure
    - "lenient": Log warning but create event anyway (default)
    - "off": No validation

    Args:
        event_type: The event type
        data: Event data (will be validated)
        **kwargs: Additional data fields

    Returns:
        Validated AgentEvent

    Raises:
        ValueError: If validation fails and mode is "strict"
    """
    merged_data = {**data, **kwargs}

    mode = get_validation_mode()
    if mode != "off":
        try:
            validated_data = validate_event_data(event_type, merged_data)
        except ValueError:
            if mode == "strict":
                raise
            # lenient mode: use unvalidated data
            validated_data = merged_data
    else:
        validated_data = merged_data

    return AgentEvent(event_type, validated_data)


# =============================================================================
# Type-Safe Event Factories
# =============================================================================


def validated_task_start_event(
    task_id: str,
    description: str,
    artifact_id: str | None = None,
    **kwargs: Any,
) -> AgentEvent:
    """Create a validated task_start event."""
    data: TaskStartData = {
        "task_id": task_id,
        "description": description,
        **kwargs,
    }
    if artifact_id:
        data["artifact_id"] = artifact_id
    return create_validated_event(EventType.TASK_START, data)


def validated_task_complete_event(
    task_id: str,
    duration_ms: int,
    artifact_id: str | None = None,
    file: str | None = None,
    **kwargs: Any,
) -> AgentEvent:
    """Create a validated task_complete event."""
    data: TaskCompleteData = {
        "task_id": task_id,
        "duration_ms": duration_ms,
        **kwargs,
    }
    if artifact_id:
        data["artifact_id"] = artifact_id
    if file:
        data["file"] = file
    return create_validated_event(EventType.TASK_COMPLETE, data)


def validated_task_failed_event(
    task_id: str,
    error: str,
    artifact_id: str | None = None,
    **kwargs: Any,
) -> AgentEvent:
    """Create a validated task_failed event."""
    data: TaskFailedData = {
        "task_id": task_id,
        "error": error,
        **kwargs,
    }
    if artifact_id:
        data["artifact_id"] = artifact_id
    return create_validated_event(EventType.TASK_FAILED, data)


def validated_plan_winner_event(
    tasks: int,
    artifact_count: int | None = None,
    gates: int | None = None,
    technique: str | None = None,
    **kwargs: Any,
) -> AgentEvent:
    """Create a validated plan_winner event."""
    data: PlanWinnerData = {
        "tasks": tasks,
        **kwargs,
    }
    if artifact_count is not None:
        data["artifact_count"] = artifact_count
    if gates is not None:
        data["gates"] = gates
    if technique:
        data["technique"] = technique
    return create_validated_event(EventType.PLAN_WINNER, data)


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


@dataclass(frozen=True, slots=True)
class ValidatedEventEmitter:
    """Event emitter with validation.

    Wraps an event emitter and validates events before emitting.
    """

    inner: EventEmitter
    validate: bool = True

    def emit(self, event: AgentEvent) -> None:
        """Emit a validated event."""
        if self.validate:
            validate_event_data(event.type, event.data)
        self.inner.emit(event)


# =============================================================================
# TypeScript Type Generation
# =============================================================================


def generate_typescript_types() -> str:
    """Generate TypeScript type definitions from Python schemas.

    Returns:
        TypeScript type definitions as a string
    """
    lines = [
        "// Auto-generated from Python event schemas",
        "// Do not edit manually - regenerate from event_schema.py",
        "",
        "export interface AgentEvent {",
        "  type: string;",
        "  data: Record<string, any>;",
        "  timestamp: number;",
        "}",
        "",
        "export interface PlanStartData {",
        "  goal?: string;",
        "}",
        "",
        "export interface PlanWinnerData {",
        "  tasks: number;",
        "  artifact_count?: number;",
        "  gates?: number;",
        "  technique?: string;",
        "}",
        "",
        "export interface TaskStartData {",
        "  task_id: string;",
        "  artifact_id?: string;",
        "  description: string;",
        "}",
        "",
        "export interface TaskProgressData {",
        "  task_id: string;",
        "  artifact_id?: string;",
        "  progress?: number;",
        "  message?: string;",
        "}",
        "",
        "export interface TaskCompleteData {",
        "  task_id: string;",
        "  artifact_id?: string;",
        "  duration_ms: number;",
        "  file?: string | null;",
        "}",
        "",
        "export interface TaskFailedData {",
        "  task_id: string;",
        "  artifact_id?: string;",
        "  error: string;",
        "}",
        "",
        "export interface MemoryLearningData {",
        "  fact: string;",
        "  category: string;",
        "}",
        "",
        "export interface CompleteData {",
        "  tasks_completed: number;",
        "  tasks_failed?: number;",
        "  gates_passed?: number;",
        "  duration_s?: number;",
        "  learnings_count?: number;",
        "  completed?: number;",
        "  failed?: number;",
        "}",
        "",
        "export interface ErrorData {",
        "  message: string;",
        "}",
        "",
        "// Event type union",
        "export type EventData =",
        "  | PlanStartData",
        "  | PlanWinnerData",
        "  | TaskStartData",
        "  | TaskProgressData",
        "  | TaskCompleteData",
        "  | TaskFailedData",
        "  | MemoryLearningData",
        "  | CompleteData",
        "  | ErrorData",
        "  | Record<string, any>;  // Fallback for unknown events",
    ]

    return "\n".join(lines)
