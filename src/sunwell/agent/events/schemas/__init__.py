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
- security.py: Security events
- registry.py: EVENT_SCHEMAS and REQUIRED_FIELDS dictionaries
- validation.py: Validation functions
- factories.py: Factory functions
- protocols.py: EventEmitter protocols
"""

# Re-export all schemas
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
from .backlog import (
    BacklogGoalAddedData,
    BacklogGoalCompletedData,
    BacklogGoalFailedData,
    BacklogGoalStartedData,
    BacklogRefreshedData,
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
from .protocols import EventEmitter, ValidatedEventEmitter
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
from .registry import EVENT_SCHEMAS, REQUIRED_FIELDS
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
    "MemoryLearningData",
    "CompleteData",
    "ErrorData",
    "EscalateData",
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
    # Security schemas
    "SecurityApprovalRequestedData",
    "SecurityApprovalReceivedData",
    "SecurityViolationData",
    "SecurityScanCompleteData",
    "AuditLogEntryData",
]
