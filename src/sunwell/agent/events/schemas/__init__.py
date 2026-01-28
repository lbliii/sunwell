"""Event schemas - modular TypedDict definitions for type-safe events.

This package provides TypedDict schemas for each event type, organized by domain.
All schemas are re-exported here for convenient access.

Structure:
- base.py: Common events (PlanStartData, TaskStartData, etc.)
- planning.py: Planning events
- harmonic.py: Harmonic planning events (RFC-058)
- refinement.py: Plan refinement events
- memory.py: Memory events
- signal.py: Signal events
- gate.py: Gate events
- validation.py: Validation events
- fix.py: Fix events
- lens.py: Lens events
- briefing.py: Briefing events
- prefetch.py: Prefetch events
- model.py: Model events
- skill.py: Skill events
- backlog.py: Backlog events
- convergence.py: Convergence events
- recovery.py: Recovery events
- integration.py: Integration verification events
- contract.py: Contract verification events
- security.py: Security events
- session.py: Session and goal lifecycle events (RFC-131)
- tool.py: Tool calling events (RFC-134)
- delegation.py: Delegation events (RFC-137)
- constellation.py: Agent constellation events (RFC-130)
- reliability.py: Reliability events (Solo Dev Hardening)
- registry.py: EVENT_SCHEMAS and REQUIRED_FIELDS dictionaries
- validation.py: Validation functions
- factories.py: Factory functions
- protocols.py: EventEmitter protocols
"""

# Re-export all schemas
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
    MethodMismatchData,
    TierResultData,
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
from .factories import (
    validated_plan_winner_event,
    validated_task_complete_event,
    validated_task_failed_event,
    validated_task_start_event,
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
from .protocols import EventEmitter, ValidatedEventEmitter
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
from .registry import EVENT_SCHEMAS, REQUIRED_FIELDS
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
from .validation import (
    create_validated_event,
    get_validation_mode,
    validate_event_data,
)
from .validation_schemas import (
    ValidateErrorData,
    ValidateLevelData,
    ValidatePassData,
    ValidateStartData,
)

__all__ = [
    # Registry
    "EVENT_SCHEMAS",
    "REQUIRED_FIELDS",
    # Protocols
    "EventEmitter",
    "ValidatedEventEmitter",
    # Validation functions
    "validate_event_data",
    "create_validated_event",
    "get_validation_mode",
    # Factory functions
    "validated_task_start_event",
    "validated_task_complete_event",
    "validated_task_failed_event",
    "validated_plan_winner_event",
    # Base schemas
    "PlanStartData",
    "PlanWinnerData",
    "TaskStartData",
    "TaskProgressData",
    "TaskCompleteData",
    "TaskFailedData",
    "TaskOutputData",
    "MemoryLearningData",
    "CompleteData",
    "ErrorData",
    "EscalateData",
    # Session/Goal schemas (RFC-131)
    "SessionStartData",
    "SessionReadyData",
    "SessionEndData",
    "SessionCrashData",
    "GoalReceivedData",
    "GoalAnalyzingData",
    "GoalReadyData",
    "GoalCompleteData",
    "GoalFailedData",
    "GoalPausedData",
    # Planning schemas
    "PlanCandidateData",
    "PlanExpandedData",
    "PlanAssessData",
    "PlanDiscoveryProgressData",
    # Harmonic schemas
    "PlanCandidateStartData",
    "PlanCandidateGeneratedData",
    "PlanCandidatesCompleteData",
    "PlanCandidateScoredData",
    "PlanScoringCompleteData",
    # Refinement schemas
    "PlanRefineStartData",
    "PlanRefineAttemptData",
    "PlanRefineCompleteData",
    "PlanRefineFinalData",
    # Memory schemas
    "MemoryLoadData",
    "MemoryLoadedData",
    "MemoryNewData",
    "MemoryDeadEndData",
    "MemoryCheckpointData",
    "MemorySavedData",
    # RFC-MEMORY unified memory schemas
    "OrientData",
    "LearningAddedData",
    "DecisionMadeData",
    "FailureRecordedData",
    "BriefingUpdatedData",
    "KnowledgeRetrievedData",
    "TemplateMatchedData",
    # Signal schemas
    "SignalData",
    "SignalRouteData",
    # Gate schemas
    "GateStartData",
    "GateStepData",
    "GatePassData",
    "GateFailData",
    # Validation schemas
    "ValidateStartData",
    "ValidateLevelData",
    "ValidateErrorData",
    "ValidatePassData",
    # Fix schemas
    "FixStartData",
    "FixProgressData",
    "FixAttemptData",
    "FixCompleteData",
    "FixFailedData",
    # Lens schemas
    "LensSelectedData",
    "LensChangedData",
    "LensSuggestedData",
    # Briefing schemas
    "BriefingLoadedData",
    "BriefingSavedData",
    # Prefetch schemas
    "PrefetchStartData",
    "PrefetchCompleteData",
    "PrefetchTimeoutData",
    # Model schemas
    "ModelStartData",
    "ModelTokensData",
    "ModelThinkingData",
    "ModelCompleteData",
    "ModelHeartbeatData",
    # Skill schemas
    "SkillCompileStartData",
    "SkillCompileCompleteData",
    "SkillCompileCacheHitData",
    "SkillSubgraphExtractedData",
    "SkillGraphResolvedData",
    "SkillWaveStartData",
    "SkillWaveCompleteData",
    "SkillCacheHitData",
    "SkillExecuteStartData",
    "SkillExecuteCompleteData",
    # Backlog schemas
    "BacklogGoalAddedData",
    "BacklogGoalStartedData",
    "BacklogGoalCompletedData",
    "BacklogGoalFailedData",
    "BacklogRefreshedData",
    # Convergence schemas
    "ConvergenceStartData",
    "ConvergenceIterationStartData",
    "ConvergenceIterationCompleteData",
    "ConvergenceFixingData",
    "ConvergenceStableData",
    "ConvergenceTimeoutData",
    "ConvergenceStuckData",
    "ConvergenceMaxIterationsData",
    "ConvergenceBudgetExceededData",
    # Recovery schemas
    "RecoverySavedData",
    "RecoveryLoadedData",
    "RecoveryResolvedData",
    "RecoveryAbortedData",
    # Integration schemas
    "IntegrationCheckStartData",
    "IntegrationCheckPassData",
    "IntegrationCheckFailData",
    "StubDetectedData",
    "OrphanDetectedData",
    "WireTaskGeneratedData",
    # Contract verification schemas
    "ContractVerifyStartData",
    "ContractVerifyPassData",
    "ContractVerifyFailData",
    "MethodMismatchData",
    "TierResultData",
    # Security schemas
    "SecurityApprovalRequestedData",
    "SecurityApprovalReceivedData",
    "SecurityViolationData",
    "SecurityScanCompleteData",
    "AuditLogEntryData",
    # Tool schemas (RFC-134)
    "ToolStartData",
    "ToolCompleteData",
    "ToolErrorData",
    "ToolLoopStartData",
    "ToolLoopTurnData",
    "ToolLoopCompleteData",
    "ToolRepairData",
    "ToolBlockedData",
    "ToolRetryData",
    "ToolEscalateData",
    "ToolPatternLearnedData",
    "ProgressiveUnlockData",
    # Delegation schemas (RFC-137)
    "DelegationStartedData",
    "EphemeralLensCreatedData",
    # Constellation schemas (RFC-130)
    "SpecialistSpawnedData",
    "SpecialistCompletedData",
    "CheckpointFoundData",
    "CheckpointSavedData",
    "PhaseCompleteData",
    "AutonomousActionBlockedData",
    "GuardEvolutionSuggestedData",
    # Reliability schemas (Solo Dev Hardening)
    "ReliabilityWarningData",
    "ReliabilityHallucinationData",
    "CircuitBreakerOpenData",
    "BudgetExhaustedData",
    "BudgetWarningData",
    "HealthCheckFailedData",
    "HealthWarningData",
    "TimeoutData",
]
