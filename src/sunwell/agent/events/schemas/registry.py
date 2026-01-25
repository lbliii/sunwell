"""Event schema registry - maps EventType to TypedDict classes."""

from typing import TypedDict

from sunwell.agent.events import EventType

from .backlog import (
    BacklogGoalAddedData,
    BacklogGoalCompletedData,
    BacklogGoalFailedData,
    BacklogGoalStartedData,
    BacklogRefreshedData,
)
from .base import (
    CompleteData,
    ErrorData,
    EscalateData,
    MemoryLearningData,
    PlanStartData,
    PlanWinnerData,
    TaskCompleteData,
    TaskFailedData,
    TaskProgressData,
    TaskStartData,
)
from .briefing import BriefingLoadedData, BriefingSavedData
from .convergence import (
    ConvergenceBudgetExceededData,
    ConvergenceFixingData,
    ConvergenceIterationCompleteData,
    ConvergenceIterationStartData,
    ConvergenceMaxIterationsData,
    ConvergenceStableData,
    ConvergenceStartData,
    ConvergenceStuckData,
    ConvergenceTimeoutData,
)
from .fix import (
    FixAttemptData,
    FixCompleteData,
    FixFailedData,
    FixProgressData,
    FixStartData,
)
from .gate import GateFailData, GatePassData, GateStartData, GateStepData
from .harmonic import (
    PlanCandidateGeneratedData,
    PlanCandidateScoredData,
    PlanCandidatesCompleteData,
    PlanCandidateStartData,
    PlanScoringCompleteData,
)
from .integration import (
    IntegrationCheckFailData,
    IntegrationCheckPassData,
    IntegrationCheckStartData,
    OrphanDetectedData,
    StubDetectedData,
    WireTaskGeneratedData,
)
from .lens import LensChangedData, LensSelectedData, LensSuggestedData
from .memory import (
    MemoryCheckpointData,
    MemoryDeadEndData,
    MemoryLoadData,
    MemoryLoadedData,
    MemoryNewData,
    MemorySavedData,
)
from .model import (
    ModelCompleteData,
    ModelHeartbeatData,
    ModelStartData,
    ModelThinkingData,
    ModelTokensData,
)
from .planning import (
    PlanAssessData,
    PlanCandidateData,
    PlanDiscoveryProgressData,
    PlanExpandedData,
)
from .prefetch import (
    PrefetchCompleteData,
    PrefetchStartData,
    PrefetchTimeoutData,
)
from .recovery import (
    RecoveryAbortedData,
    RecoveryLoadedData,
    RecoveryResolvedData,
    RecoverySavedData,
)
from .refinement import (
    PlanRefineAttemptData,
    PlanRefineCompleteData,
    PlanRefineFinalData,
    PlanRefineStartData,
)
from .security import (
    AuditLogEntryData,
    SecurityApprovalReceivedData,
    SecurityApprovalRequestedData,
    SecurityScanCompleteData,
    SecurityViolationData,
)
from .signal import SignalData, SignalRouteData
from .skill import (
    SkillCacheHitData,
    SkillCompileCacheHitData,
    SkillCompileCompleteData,
    SkillCompileStartData,
    SkillExecuteCompleteData,
    SkillExecuteStartData,
    SkillGraphResolvedData,
    SkillSubgraphExtractedData,
    SkillWaveCompleteData,
    SkillWaveStartData,
)
from .validation_schemas import (
    ValidateErrorData,
    ValidateLevelData,
    ValidatePassData,
    ValidateStartData,
)

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
    # Recovery events (RFC-125)
    EventType.RECOVERY_SAVED: RecoverySavedData,
    EventType.RECOVERY_LOADED: RecoveryLoadedData,
    EventType.RECOVERY_RESOLVED: RecoveryResolvedData,
    EventType.RECOVERY_ABORTED: RecoveryAbortedData,
    # Lens events (RFC-064, RFC-071)
    EventType.LENS_SELECTED: LensSelectedData,
    EventType.LENS_CHANGED: LensChangedData,
    EventType.LENS_SUGGESTED: LensSuggestedData,
    # Briefing & Prefetch events
    EventType.BRIEFING_LOADED: BriefingLoadedData,
    EventType.BRIEFING_SAVED: BriefingSavedData,
    EventType.PREFETCH_START: PrefetchStartData,
    EventType.PREFETCH_COMPLETE: PrefetchCompleteData,
    EventType.PREFETCH_TIMEOUT: PrefetchTimeoutData,
    # Model events
    EventType.MODEL_START: ModelStartData,
    EventType.MODEL_TOKENS: ModelTokensData,
    EventType.MODEL_THINKING: ModelThinkingData,
    EventType.MODEL_COMPLETE: ModelCompleteData,
    EventType.MODEL_HEARTBEAT: ModelHeartbeatData,
    # Skill compilation events
    EventType.SKILL_COMPILE_START: SkillCompileStartData,
    EventType.SKILL_COMPILE_COMPLETE: SkillCompileCompleteData,
    EventType.SKILL_COMPILE_CACHE_HIT: SkillCompileCacheHitData,
    EventType.SKILL_SUBGRAPH_EXTRACTED: SkillSubgraphExtractedData,
    # Backlog events
    EventType.BACKLOG_GOAL_ADDED: BacklogGoalAddedData,
    EventType.BACKLOG_GOAL_STARTED: BacklogGoalStartedData,
    EventType.BACKLOG_GOAL_COMPLETED: BacklogGoalCompletedData,
    EventType.BACKLOG_GOAL_FAILED: BacklogGoalFailedData,
    EventType.BACKLOG_REFRESHED: BacklogRefreshedData,
    # Convergence events
    EventType.CONVERGENCE_START: ConvergenceStartData,
    EventType.CONVERGENCE_ITERATION_START: ConvergenceIterationStartData,
    EventType.CONVERGENCE_ITERATION_COMPLETE: ConvergenceIterationCompleteData,
    EventType.CONVERGENCE_FIXING: ConvergenceFixingData,
    EventType.CONVERGENCE_STABLE: ConvergenceStableData,
    EventType.CONVERGENCE_TIMEOUT: ConvergenceTimeoutData,
    EventType.CONVERGENCE_STUCK: ConvergenceStuckData,
    EventType.CONVERGENCE_MAX_ITERATIONS: ConvergenceMaxIterationsData,
    EventType.CONVERGENCE_BUDGET_EXCEEDED: ConvergenceBudgetExceededData,
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
    # Recovery events (RFC-125)
    EventType.RECOVERY_SAVED: {"recovery_id", "artifact_ids"},
    EventType.RECOVERY_LOADED: {"recovery_id", "artifact_ids"},
    EventType.RECOVERY_RESOLVED: {"recovery_id", "artifacts_passed"},
    EventType.RECOVERY_ABORTED: {"recovery_id", "reason"},
    # Lens events (RFC-064, RFC-071)
    EventType.LENS_SELECTED: {"name"},
    EventType.LENS_CHANGED: {"new_lens"},
    EventType.LENS_SUGGESTED: {"suggested", "reason"},
    # Briefing & Prefetch events
    EventType.BRIEFING_LOADED: {"path"},
    EventType.BRIEFING_SAVED: {"path"},
    EventType.PREFETCH_START: {"sources"},
    EventType.PREFETCH_COMPLETE: {"duration_ms", "sources_loaded"},
    EventType.PREFETCH_TIMEOUT: {"timeout_ms"},
    # Model events
    EventType.MODEL_START: {"provider", "model"},
    EventType.MODEL_TOKENS: {"tokens"},
    EventType.MODEL_THINKING: {"content"},
    EventType.MODEL_COMPLETE: {"duration_ms"},
    EventType.MODEL_HEARTBEAT: {"elapsed_ms"},
    # Skill compilation events
    EventType.SKILL_COMPILE_START: {"lens_name"},
    EventType.SKILL_COMPILE_COMPLETE: {"lens_name", "skill_count", "duration_ms"},
    EventType.SKILL_COMPILE_CACHE_HIT: {"lens_name"},
    EventType.SKILL_SUBGRAPH_EXTRACTED: {"skill_name", "subgraph_size"},
    # Backlog events
    EventType.BACKLOG_GOAL_ADDED: {"goal_id", "title"},
    EventType.BACKLOG_GOAL_STARTED: {"goal_id"},
    EventType.BACKLOG_GOAL_COMPLETED: {"goal_id"},
    EventType.BACKLOG_GOAL_FAILED: {"goal_id", "error"},
    EventType.BACKLOG_REFRESHED: {"goal_count"},
    # Convergence events
    EventType.CONVERGENCE_START: {"max_iterations"},
    EventType.CONVERGENCE_ITERATION_START: {"iteration"},
    EventType.CONVERGENCE_ITERATION_COMPLETE: {"iteration", "errors_found"},
    EventType.CONVERGENCE_FIXING: {"iteration", "errors_to_fix"},
    EventType.CONVERGENCE_STABLE: {"iterations"},
    EventType.CONVERGENCE_TIMEOUT: {"elapsed_ms"},
    EventType.CONVERGENCE_STUCK: {"iterations", "persistent_errors"},
    EventType.CONVERGENCE_MAX_ITERATIONS: {"max_iterations"},
    EventType.CONVERGENCE_BUDGET_EXCEEDED: {"budget_ms", "elapsed_ms"},
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
