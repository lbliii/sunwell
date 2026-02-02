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
    TaskOutputData,
    TaskProgressData,
    TaskStartData,
)
from .briefing import BriefingLoadedData, BriefingSavedData
from .contract import (
    ContractVerifyFailData,
    ContractVerifyPassData,
    ContractVerifyStartData,
)
from .constellation import (
    AutonomousActionBlockedData,
    CheckpointFoundData,
    CheckpointSavedData,
    GuardEvolutionSuggestedData,
    PhaseCompleteData,
    SpecialistCompletedData,
    SpecialistSpawnedData,
)
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
from .delegation import DelegationStartedData, EphemeralLensCreatedData
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
    PlanCandidatesCompleteData,
    PlanCandidateScoredData,
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
from .intent import DomainDetectedData, IntentClassifiedData, NodeTransitionData
from .lens import LensChangedData, LensSelectedData, LensSuggestedData
from .memory import (
    BriefingUpdatedData,
    DecisionMadeData,
    FailureRecordedData,
    KnowledgeRetrievedData,
    LearningAddedData,
    MemoryCheckpointData,
    MemoryDeadEndData,
    MemoryLoadData,
    MemoryLoadedData,
    MemoryNewData,
    MemorySavedData,
    OrientData,
    TemplateMatchedData,
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
from .reliability import (
    BudgetExhaustedData,
    BudgetWarningData,
    CircuitBreakerOpenData,
    HealthCheckFailedData,
    HealthWarningData,
    ReliabilityHallucinationData,
    ReliabilityWarningData,
    TimeoutData,
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
from .session import (
    GoalAnalyzingData,
    GoalCompleteData,
    GoalFailedData,
    GoalPausedData,
    GoalReadyData,
    GoalReceivedData,
    SessionCrashData,
    SessionEndData,
    SessionReadyData,
    SessionStartData,
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
from .tool import (
    ProgressiveUnlockData,
    ToolBlockedData,
    ToolCompleteData,
    ToolErrorData,
    ToolEscalateData,
    ToolLoopCompleteData,
    ToolLoopStartData,
    ToolLoopTurnData,
    ToolPatternLearnedData,
    ToolRepairData,
    ToolRetryData,
    ToolStartData,
)
from .validation_schemas import (
    ValidateErrorData,
    ValidateLevelData,
    ValidatePassData,
    ValidateStartData,
)

EVENT_SCHEMAS: dict[EventType, type[TypedDict]] = {
    # =============================================================================
    # Session Lifecycle Events (RFC-131)
    # =============================================================================
    EventType.SESSION_START: SessionStartData,
    EventType.SESSION_READY: SessionReadyData,
    EventType.SESSION_END: SessionEndData,
    EventType.SESSION_CRASH: SessionCrashData,
    # =============================================================================
    # Goal Lifecycle Events (RFC-131)
    # =============================================================================
    EventType.GOAL_RECEIVED: GoalReceivedData,
    EventType.GOAL_ANALYZING: GoalAnalyzingData,
    EventType.GOAL_READY: GoalReadyData,
    EventType.GOAL_COMPLETE: GoalCompleteData,
    EventType.GOAL_FAILED: GoalFailedData,
    EventType.GOAL_PAUSED: GoalPausedData,
    # =============================================================================
    # Planning events
    # =============================================================================
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
    # Discovery progress (RFC-059)
    EventType.PLAN_DISCOVERY_PROGRESS: PlanDiscoveryProgressData,
    # =============================================================================
    # Memory events
    # =============================================================================
    EventType.MEMORY_LOAD: MemoryLoadData,
    EventType.MEMORY_LOADED: MemoryLoadedData,
    EventType.MEMORY_NEW: MemoryNewData,
    EventType.MEMORY_LEARNING: MemoryLearningData,
    EventType.MEMORY_DEAD_END: MemoryDeadEndData,
    EventType.MEMORY_CHECKPOINT: MemoryCheckpointData,
    EventType.MEMORY_SAVED: MemorySavedData,
    # RFC-MEMORY: Unified memory events
    EventType.ORIENT: OrientData,
    EventType.LEARNING_ADDED: LearningAddedData,
    EventType.DECISION_MADE: DecisionMadeData,
    EventType.FAILURE_RECORDED: FailureRecordedData,
    EventType.BRIEFING_UPDATED: BriefingUpdatedData,
    EventType.KNOWLEDGE_RETRIEVED: KnowledgeRetrievedData,
    EventType.TEMPLATE_MATCHED: TemplateMatchedData,
    # =============================================================================
    # Signal events
    # =============================================================================
    EventType.SIGNAL: SignalData,
    EventType.SIGNAL_ROUTE: SignalRouteData,
    # =============================================================================
    # Intent and Domain events (Conversational DAG, RFC-DOMAINS)
    # =============================================================================
    EventType.INTENT_CLASSIFIED: IntentClassifiedData,
    EventType.NODE_TRANSITION: NodeTransitionData,
    EventType.DOMAIN_DETECTED: DomainDetectedData,
    # =============================================================================
    # Gate events
    # =============================================================================
    EventType.GATE_START: GateStartData,
    EventType.GATE_STEP: GateStepData,
    EventType.GATE_PASS: GatePassData,
    EventType.GATE_FAIL: GateFailData,
    # =============================================================================
    # Execution events
    # =============================================================================
    EventType.TASK_START: TaskStartData,
    EventType.TASK_PROGRESS: TaskProgressData,
    EventType.TASK_COMPLETE: TaskCompleteData,
    EventType.TASK_FAILED: TaskFailedData,
    EventType.TASK_OUTPUT: TaskOutputData,
    # =============================================================================
    # Validation events
    # =============================================================================
    EventType.VALIDATE_START: ValidateStartData,
    EventType.VALIDATE_LEVEL: ValidateLevelData,
    EventType.VALIDATE_ERROR: ValidateErrorData,
    EventType.VALIDATE_PASS: ValidatePassData,
    # =============================================================================
    # Fix events
    # =============================================================================
    EventType.FIX_START: FixStartData,
    EventType.FIX_PROGRESS: FixProgressData,
    EventType.FIX_ATTEMPT: FixAttemptData,
    EventType.FIX_COMPLETE: FixCompleteData,
    EventType.FIX_FAILED: FixFailedData,
    # =============================================================================
    # Completion events
    # =============================================================================
    EventType.COMPLETE: CompleteData,
    EventType.ERROR: ErrorData,
    EventType.ESCALATE: EscalateData,
    # =============================================================================
    # Recovery events (RFC-125)
    # =============================================================================
    EventType.RECOVERY_SAVED: RecoverySavedData,
    EventType.RECOVERY_LOADED: RecoveryLoadedData,
    EventType.RECOVERY_RESOLVED: RecoveryResolvedData,
    EventType.RECOVERY_ABORTED: RecoveryAbortedData,
    # =============================================================================
    # Lens events (RFC-064, RFC-071)
    # =============================================================================
    EventType.LENS_SELECTED: LensSelectedData,
    EventType.LENS_CHANGED: LensChangedData,
    EventType.LENS_SUGGESTED: LensSuggestedData,
    # =============================================================================
    # Briefing & Prefetch events (RFC-071)
    # =============================================================================
    EventType.BRIEFING_LOADED: BriefingLoadedData,
    EventType.BRIEFING_SAVED: BriefingSavedData,
    EventType.PREFETCH_START: PrefetchStartData,
    EventType.PREFETCH_COMPLETE: PrefetchCompleteData,
    EventType.PREFETCH_TIMEOUT: PrefetchTimeoutData,
    # =============================================================================
    # Model events (RFC-081)
    # =============================================================================
    EventType.MODEL_START: ModelStartData,
    EventType.MODEL_TOKENS: ModelTokensData,
    EventType.MODEL_THINKING: ModelThinkingData,
    EventType.MODEL_COMPLETE: ModelCompleteData,
    EventType.MODEL_HEARTBEAT: ModelHeartbeatData,
    # =============================================================================
    # Skill events (RFC-087, RFC-111)
    # =============================================================================
    EventType.SKILL_GRAPH_RESOLVED: SkillGraphResolvedData,
    EventType.SKILL_WAVE_START: SkillWaveStartData,
    EventType.SKILL_WAVE_COMPLETE: SkillWaveCompleteData,
    EventType.SKILL_CACHE_HIT: SkillCacheHitData,
    EventType.SKILL_EXECUTE_START: SkillExecuteStartData,
    EventType.SKILL_EXECUTE_COMPLETE: SkillExecuteCompleteData,
    EventType.SKILL_COMPILE_START: SkillCompileStartData,
    EventType.SKILL_COMPILE_COMPLETE: SkillCompileCompleteData,
    EventType.SKILL_COMPILE_CACHE_HIT: SkillCompileCacheHitData,
    EventType.SKILL_SUBGRAPH_EXTRACTED: SkillSubgraphExtractedData,
    # =============================================================================
    # Backlog events (RFC-094)
    # =============================================================================
    EventType.BACKLOG_GOAL_ADDED: BacklogGoalAddedData,
    EventType.BACKLOG_GOAL_STARTED: BacklogGoalStartedData,
    EventType.BACKLOG_GOAL_COMPLETED: BacklogGoalCompletedData,
    EventType.BACKLOG_GOAL_FAILED: BacklogGoalFailedData,
    EventType.BACKLOG_REFRESHED: BacklogRefreshedData,
    # =============================================================================
    # Security events (RFC-089)
    # =============================================================================
    EventType.SECURITY_APPROVAL_REQUESTED: SecurityApprovalRequestedData,
    EventType.SECURITY_APPROVAL_RECEIVED: SecurityApprovalReceivedData,
    EventType.SECURITY_VIOLATION: SecurityViolationData,
    EventType.SECURITY_SCAN_COMPLETE: SecurityScanCompleteData,
    EventType.AUDIT_LOG_ENTRY: AuditLogEntryData,
    # =============================================================================
    # Convergence events (RFC-123)
    # =============================================================================
    EventType.CONVERGENCE_START: ConvergenceStartData,
    EventType.CONVERGENCE_ITERATION_START: ConvergenceIterationStartData,
    EventType.CONVERGENCE_ITERATION_COMPLETE: ConvergenceIterationCompleteData,
    EventType.CONVERGENCE_FIXING: ConvergenceFixingData,
    EventType.CONVERGENCE_STABLE: ConvergenceStableData,
    EventType.CONVERGENCE_TIMEOUT: ConvergenceTimeoutData,
    EventType.CONVERGENCE_STUCK: ConvergenceStuckData,
    EventType.CONVERGENCE_MAX_ITERATIONS: ConvergenceMaxIterationsData,
    EventType.CONVERGENCE_BUDGET_EXCEEDED: ConvergenceBudgetExceededData,
    # =============================================================================
    # Agent Constellation events (RFC-130)
    # =============================================================================
    EventType.SPECIALIST_SPAWNED: SpecialistSpawnedData,
    EventType.SPECIALIST_COMPLETED: SpecialistCompletedData,
    EventType.CHECKPOINT_FOUND: CheckpointFoundData,
    EventType.CHECKPOINT_SAVED: CheckpointSavedData,
    EventType.PHASE_COMPLETE: PhaseCompleteData,
    EventType.AUTONOMOUS_ACTION_BLOCKED: AutonomousActionBlockedData,
    EventType.GUARD_EVOLUTION_SUGGESTED: GuardEvolutionSuggestedData,
    # =============================================================================
    # Tool calling events (RFC-134)
    # =============================================================================
    EventType.TOOL_START: ToolStartData,
    EventType.TOOL_COMPLETE: ToolCompleteData,
    EventType.TOOL_ERROR: ToolErrorData,
    EventType.TOOL_LOOP_START: ToolLoopStartData,
    EventType.TOOL_LOOP_TURN: ToolLoopTurnData,
    EventType.TOOL_LOOP_COMPLETE: ToolLoopCompleteData,
    EventType.TOOL_REPAIR: ToolRepairData,
    EventType.TOOL_BLOCKED: ToolBlockedData,
    EventType.TOOL_RETRY: ToolRetryData,
    EventType.TOOL_ESCALATE: ToolEscalateData,
    EventType.TOOL_PATTERN_LEARNED: ToolPatternLearnedData,
    EventType.PROGRESSIVE_UNLOCK: ProgressiveUnlockData,
    # =============================================================================
    # Delegation events (RFC-137)
    # =============================================================================
    EventType.DELEGATION_STARTED: DelegationStartedData,
    EventType.EPHEMERAL_LENS_CREATED: EphemeralLensCreatedData,
    # =============================================================================
    # Integration verification events (RFC-067)
    # =============================================================================
    EventType.INTEGRATION_CHECK_START: IntegrationCheckStartData,
    EventType.INTEGRATION_CHECK_PASS: IntegrationCheckPassData,
    EventType.INTEGRATION_CHECK_FAIL: IntegrationCheckFailData,
    EventType.STUB_DETECTED: StubDetectedData,
    EventType.ORPHAN_DETECTED: OrphanDetectedData,
    EventType.WIRE_TASK_GENERATED: WireTaskGeneratedData,
    # =============================================================================
    # Contract verification events
    # =============================================================================
    EventType.CONTRACT_VERIFY_START: ContractVerifyStartData,
    EventType.CONTRACT_VERIFY_PASS: ContractVerifyPassData,
    EventType.CONTRACT_VERIFY_FAIL: ContractVerifyFailData,
    # =============================================================================
    # Reliability Events (Solo Dev Hardening)
    # =============================================================================
    EventType.RELIABILITY_WARNING: ReliabilityWarningData,
    EventType.RELIABILITY_HALLUCINATION: ReliabilityHallucinationData,
    EventType.CIRCUIT_BREAKER_OPEN: CircuitBreakerOpenData,
    EventType.BUDGET_EXHAUSTED: BudgetExhaustedData,
    EventType.BUDGET_WARNING: BudgetWarningData,
    EventType.HEALTH_CHECK_FAILED: HealthCheckFailedData,
    EventType.HEALTH_WARNING: HealthWarningData,
    EventType.TIMEOUT: TimeoutData,
}

# =============================================================================
# Required fields per event type
# These MUST match what the factory functions actually produce.
# =============================================================================
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
    EventType.TASK_OUTPUT: {"task_id", "content"},
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
    # Briefing & Prefetch events - updated to match factories
    EventType.BRIEFING_LOADED: {"mission", "status", "has_hazards"},
    EventType.BRIEFING_SAVED: {"status"},
    EventType.PREFETCH_START: {"briefing"},
    EventType.PREFETCH_COMPLETE: {"files_loaded", "learnings_loaded", "skills_activated"},
    # Model events - updated to match factories
    EventType.MODEL_START: {"task_id", "model"},
    EventType.MODEL_TOKENS: {"task_id", "tokens", "token_count"},
    EventType.MODEL_THINKING: {"task_id", "phase", "content"},
    EventType.MODEL_COMPLETE: {"task_id", "total_tokens", "duration_s", "tokens_per_second"},
    EventType.MODEL_HEARTBEAT: {"task_id", "elapsed_s", "token_count"},
    # Skill compilation events
    EventType.SKILL_COMPILE_START: {"lens_name"},
    EventType.SKILL_COMPILE_COMPLETE: {"lens_name", "task_count", "wave_count", "duration_ms"},
    EventType.SKILL_COMPILE_CACHE_HIT: {"cache_key", "task_count", "wave_count"},
    EventType.SKILL_SUBGRAPH_EXTRACTED: {"target_skills", "total_skills", "extracted_skills"},
    # Backlog events
    EventType.BACKLOG_GOAL_ADDED: {"goal_id", "title"},
    EventType.BACKLOG_GOAL_STARTED: {"goal_id"},
    EventType.BACKLOG_GOAL_COMPLETED: {"goal_id"},
    EventType.BACKLOG_GOAL_FAILED: {"goal_id", "error"},
    EventType.BACKLOG_REFRESHED: {"goal_count"},
    # Convergence events - updated to match factories
    EventType.CONVERGENCE_START: {"files", "gates", "max_iterations"},
    EventType.CONVERGENCE_ITERATION_START: {"iteration", "files"},
    EventType.CONVERGENCE_ITERATION_COMPLETE: {"iteration", "all_passed", "total_errors", "gate_results"},
    EventType.CONVERGENCE_FIXING: {"iteration", "error_count"},
    EventType.CONVERGENCE_STABLE: {"iterations", "duration_ms"},
    EventType.CONVERGENCE_TIMEOUT: {"iterations"},
    EventType.CONVERGENCE_STUCK: {"iterations", "repeated_errors"},
    EventType.CONVERGENCE_MAX_ITERATIONS: {"iterations"},
    EventType.CONVERGENCE_BUDGET_EXCEEDED: {"tokens_used", "max_tokens"},
    # Discovery progress (RFC-059)
    EventType.PLAN_DISCOVERY_PROGRESS: {"artifacts_discovered", "phase"},
    # Integration verification events (RFC-067)
    EventType.INTEGRATION_CHECK_START: {
        "edge_id", "check_type", "source_artifact", "target_artifact"
    },
    EventType.INTEGRATION_CHECK_PASS: {"edge_id", "check_type", "verification_method"},
    EventType.INTEGRATION_CHECK_FAIL: {"edge_id", "check_type", "expected", "actual"},
    EventType.STUB_DETECTED: {"artifact_id", "file_path", "stub_type", "location"},
    EventType.ORPHAN_DETECTED: {"artifact_id", "file_path"},
    EventType.WIRE_TASK_GENERATED: {
        "task_id", "source_artifact", "target_artifact", "integration_type"
    },
    # Contract verification events
    EventType.CONTRACT_VERIFY_START: {
        "task_id", "protocol_name", "implementation_file", "contract_file"
    },
    EventType.CONTRACT_VERIFY_PASS: {
        "task_id", "protocol_name", "final_tier"
    },
    EventType.CONTRACT_VERIFY_FAIL: {
        "task_id", "protocol_name", "final_tier", "error_message"
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
    # Tool calling events (RFC-134)
    EventType.TOOL_START: {"tool_name", "tool_call_id"},
    EventType.TOOL_COMPLETE: {"tool_name", "tool_call_id", "success", "output"},
    EventType.TOOL_ERROR: {"tool_name", "tool_call_id", "error"},
    EventType.TOOL_LOOP_START: {"task_description", "max_turns", "tool_count"},
    EventType.TOOL_LOOP_TURN: {"turn", "tool_calls_count"},
    EventType.TOOL_LOOP_COMPLETE: {"turns_used", "tool_calls_total"},
    EventType.TOOL_REPAIR: {"tool_name", "tool_call_id", "repairs"},
    EventType.TOOL_BLOCKED: {"tool_name", "tool_call_id", "reason"},
    EventType.TOOL_RETRY: {"tool_name", "tool_call_id", "attempt", "strategy", "error"},
    EventType.TOOL_ESCALATE: {"tool_name", "error", "reason"},
    EventType.TOOL_PATTERN_LEARNED: {"task_type", "tool_sequence", "success_rate"},
    EventType.PROGRESSIVE_UNLOCK: {"category", "tools_unlocked", "turn", "validation_passes"},
    # Delegation events (RFC-137)
    EventType.DELEGATION_STARTED: {"task_description", "smart_model", "delegation_model", "reason"},
    EventType.EPHEMERAL_LENS_CREATED: {
        "task_scope", "heuristics_count", "patterns_count", "generated_by"
    },
    # Constellation events (RFC-130)
    EventType.SPECIALIST_SPAWNED: {"specialist_id", "task_id", "parent_id", "role", "focus"},
    EventType.SPECIALIST_COMPLETED: {"specialist_id", "success", "summary", "tokens_used"},
    EventType.CHECKPOINT_FOUND: {"phase", "checkpoint_at", "goal"},
    EventType.CHECKPOINT_SAVED: {"phase", "summary"},
    EventType.PHASE_COMPLETE: {"phase", "duration_seconds"},
    EventType.AUTONOMOUS_ACTION_BLOCKED: {
        "action_type", "reason", "blocking_rule", "risk_level"
    },
    EventType.GUARD_EVOLUTION_SUGGESTED: {"guard_id", "evolution_type", "reason", "confidence"},
    # RFC-MEMORY: Unified memory events
    EventType.ORIENT: {"learnings", "constraints", "dead_ends"},
    EventType.LEARNING_ADDED: {"fact", "category"},
    EventType.DECISION_MADE: {"category", "question", "choice"},
    EventType.FAILURE_RECORDED: {"description", "error_type", "context"},
    EventType.BRIEFING_UPDATED: {"status"},
    # Reliability events (Solo Dev Hardening)
    EventType.RELIABILITY_WARNING: {"warning"},
    EventType.RELIABILITY_HALLUCINATION: {"detected_pattern"},
    EventType.CIRCUIT_BREAKER_OPEN: {"state", "consecutive_failures", "failure_threshold"},
    EventType.BUDGET_EXHAUSTED: {"spent", "budget"},
    EventType.BUDGET_WARNING: {"remaining"},
    EventType.HEALTH_CHECK_FAILED: {"errors"},
    EventType.HEALTH_WARNING: {"warnings"},
    EventType.TIMEOUT: {"operation"},
}
