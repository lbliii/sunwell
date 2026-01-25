"""Naaru - Coordinated Intelligence for Local Models (RFC-016, RFC-019, RFC-032, RFC-034).

The Naaru is Sunwell's answer to maximizing quality and throughput from small
local models. Instead of a simple worker pool, it implements coordinated
intelligence with specialized components that work in harmony.

RFC-032 Additions:
- Task: Universal work unit (generalizes Opportunity)
- TaskMode, TaskStatus: Task execution enums
- TaskPlanner: Protocol for task planning/decomposition
- AgentPlanner: LLM-based planning for arbitrary goals
- AgentResult: Result from agent mode execution
- AgentCheckpoint: Checkpointing for long-running tasks

RFC-034 Additions:
- Contract-aware task fields (produces, requires, modifies)
- PlanningStrategy: Sequential, contract-first, or resource-aware planning
- Parallel task execution with conflict detection
- Task graph analysis and visualization utilities

Architecture:
```
              ┌─────────────────┐
              │      NAARU      │  ← Coordinates everything
              │   (The Light)   │
              └────────┬────────┘
                       │
        ╔══════════════╧══════════════╗
        ║    CONVERGENCE (7 slots)    ║  ← Shared working memory
        ╚══════════════╤══════════════╝
                       │
     ┌─────────────────┼─────────────────┐
     │                 │                 │
     ▼                 ▼                 ▼
 ┌────────┐       ┌────────┐       ┌────────┐
 │ SHARD  │       │ SHARD  │       │ SHARD  │  ← Parallel helpers
 │ Memory │       │Context │       │ Verify │
 └────────┘       └────────┘       └────────┘
```

Thematic Naming (from Naaru lore):
- **Voice**: The model that speaks/creates (synthesis model)
- **Wisdom**: The model that judges/evaluates (judge model)
- **Harmonic**: Multiple voices in alignment (multi-persona generation)
- **Convergence**: Shared purpose/working memory (7±2 slots)
- **Shards**: Fragments working in parallel (CPU helpers)
- **Resonance**: Feedback that amplifies quality (refinement loop)
- **Discernment**: Quick insight before deep judgment (tiered validation)
- **Attunement**: Intent-aware routing (cognitive routing)
- **Purity**: How pure the Light must be (quality threshold)
- **Luminance**: Confidence/quality score

Example:
    >>> from sunwell.naaru import Naaru, NaaruConfig
    >>> from sunwell.models.ollama import OllamaModel
    >>>
    >>> naaru = Naaru(
    ...     workspace=Path("."),
    ...     synthesis_model=OllamaModel("gemma3:1b"),
    ...     judge_model=OllamaModel("gemma3:4b"),
    ...     config=NaaruConfig(
    ...         harmonic_synthesis=True,
    ...         resonance=2,
    ...         convergence=7,
    ...     ),
    ... )
    >>>
    >>> results = await naaru.illuminate(
    ...     goals=["improve error handling"],
    ...     max_time_seconds=120,
    ... )

Lore:
    In World of Warcraft, the Naaru are beings of pure Light that coordinate
    and guide. The Sunwell was restored by a Naaru (M'uru). The metaphor fits:
    - Naaru = The coordinator
    - Convergence = Shared purpose/working memory
    - Shards = Fragments working in parallel
    - Resonance = Feedback that amplifies quality
    - Harmonic = Multiple voices in alignment
    - Illuminate = The Naaru's light reveals the best path
"""

# Core types
# RFC-034: Task Graph Analysis
# RFC-067: Integration-Aware DAG types (canonical: sunwell.integration)
# RFC-067: Integration Verification (canonical: sunwell.integration)
# RFC-074: Incremental Execution v2 (content-addressed cache)
# Re-export v2 types from sunwell.incremental for convenience
from sunwell.incremental import (
    ExecutionCache,
    ExecutionPlan,
    IncrementalResult,
    SkipDecision,
    SkipReason,
)
from sunwell.incremental import IncrementalExecutor as IncrementalExecutorV2
from sunwell.integration import (
    IntegrationCheck,
    IntegrationCheckType,
    IntegrationResult,
    IntegrationType,
    IntegrationVerifier,
    RequiredIntegration,
    StubDetection,
    TaskType,
)
from sunwell.naaru.analysis import (
    ParallelismAnalysis,
    analyze_parallelism,
    format_execution_summary,
    validate_contracts,
    visualize_task_graph,
)

# RFC-036: Artifact-First Planning
from sunwell.naaru.artifacts import (
    ArtifactCreationError,
    # Exceptions
    ArtifactError,
    ArtifactGraph,
    ArtifactLimits,
    ArtifactSpec,
    CyclicDependencyError,
    DiscoveryFailedError,
    GraphExplosionError,
    MissingDependencyError,
    VerificationResult,
    artifact_to_task,
    artifacts_to_tasks,
    get_model_distribution,
    select_model_tier,
)

# RFC-032: Checkpointing
from sunwell.naaru.checkpoint import (
    AgentCheckpoint,
    FailurePolicy,
    ParallelConfig,
    TaskExecutionConfig,
    find_latest_checkpoint,
    get_checkpoint_path,
)

# Convergence - Shared Working Memory
from sunwell.naaru.convergence import (
    Convergence,
    Slot,
    SlotSource,
)

# The Coordinator
from sunwell.naaru.coordinator import (
    AgentResult,  # RFC-032
    Naaru,
)

# Core types
from sunwell.naaru.core import (
    MessageBus,
    MessageType,
    NaaruMessage,
    NaaruRegion,
)

# Discernment - Tiered Validation
from sunwell.naaru.discernment import (
    Discernment,
    DiscernmentResult,
    DiscernmentVerdict,
)
from sunwell.naaru.discovery import OpportunityDiscoverer

# RFC-033: Unified Architecture
from sunwell.naaru.diversity import (
    HARMONIC_PERSONAS,
    Candidate,
    diversity_harmonic,
    diversity_none,
    diversity_rotation,
    diversity_sampling,
)

# RFC-076: Modular Components
from sunwell.naaru.events import EventEmitter, NaaruEventEmitter
from sunwell.naaru.execution import ExecutionCoordinator

# RFC-036: Artifact Execution
from sunwell.naaru.executor import (
    ArtifactExecutor,
    ArtifactResult,
    ExecutionEvent,
    ExecutionResult,
    execute_artifact_graph,
    execute_with_discovery,
)
from sunwell.naaru.learnings import LearningExtractor

# Core runners
from sunwell.naaru.loop import AutonomousRunner
from sunwell.naaru.migration import (
    create_rfc019_equivalent_config,
    create_rfc028_equivalent_config,
    migrate_rfc019_to_rfc033,
)
from sunwell.naaru.parallel import ParallelAutonomousRunner, WorkerStats
from sunwell.naaru.persistence import (
    ArtifactCompletion,
    ExecutionStatus,
    PlanStore,
    SavedExecution,
    TraceLogger,
    get_latest_execution,
    hash_content,
    hash_file,
    hash_goal,
    resume_execution,
    save_execution,
)

# RFC-032: Task Planners
from sunwell.naaru.planners import (
    AgentPlanner,
    # RFC-036: Artifact-First Planner
    ArtifactPlanner,
    PlanningError,
    PlanningStrategy,
    SelfImprovementPlanner,
    TaskPlanner,
)
from sunwell.naaru.refinement import (
    RefinementResult,
    refine_full,
    refine_none,
    refine_tiered,
)

# Resonance - Feedback Loop
from sunwell.naaru.resonance import (
    RefinementAttempt,
    Resonance,
    ResonanceConfig,
    ResonanceResult,
    create_resonance_handler,
)
from sunwell.naaru.selection import (
    select_heuristic,
    select_judge,
    select_passthrough,
    select_voting,
)

# RFC-110: Session management moved to Agent level

# Shards - Parallel Helpers
from sunwell.naaru.shards import (
    Shard,
    ShardPool,
    ShardType,
)
from sunwell.naaru.signals import SignalHandler, StopReason
from sunwell.naaru.types import (
    Opportunity,
    OpportunityCategory,
    RiskLevel,
    SessionConfig,
    SessionState,
    SessionStatus,
    # RFC-032: Agent Mode types
    Task,
    TaskMode,
    TaskStatus,
)
from sunwell.naaru.unified import (
    TaskAnalysis,
    UnifiedResult,
    create_auto_config,
    create_balanced_config,
    create_cheap_diversity_config,
    create_minimal_config,
    create_quality_config,
    select_strategies,
    unified_pipeline,
)

# Workers
from sunwell.naaru.workers import (
    AnalysisWorker,
    CognitiveRoutingWorker,
    ExecutiveWorker,
    HarmonicSynthesisWorker,
    MemoryWorker,
    ToolRegionWorker,  # RFC-032
    ValidationWorker,
)

# NaaruConfig moved to sunwell.types.config
from sunwell.types.config import NaaruConfig

# ModelSize moved to sunwell.types.model_size
from sunwell.types.model_size import ModelSize


__all__ = [
    # Core Types
    "SessionStatus",
    "RiskLevel",
    "Opportunity",
    "OpportunityCategory",
    "SessionConfig",
    "SessionState",

    # RFC-032: Agent Mode Types
    "Task",
    "TaskMode",
    "TaskStatus",

    # RFC-067: Integration-Aware DAG Types
    "TaskType",
    "IntegrationType",
    "IntegrationCheckType",
    "RequiredIntegration",
    "IntegrationCheck",
    "IntegrationResult",

    # Core Runners
    "AutonomousRunner",
    "OpportunityDiscoverer",
    "ParallelAutonomousRunner",
    "WorkerStats",
    "SignalHandler",
    "StopReason",

    # Naaru Coordinator
    "Naaru",
    "NaaruConfig",
    "NaaruRegion",
    "NaaruMessage",
    "MessageBus",
    "MessageType",
    "AgentResult",

    # Naaru Workers
    "HarmonicSynthesisWorker",
    "ValidationWorker",
    "AnalysisWorker",
    "MemoryWorker",
    "ExecutiveWorker",
    "ToolRegionWorker",
    "CognitiveRoutingWorker",

    # RFC-032: Task Planners
    "TaskPlanner",
    "PlanningError",
    "SelfImprovementPlanner",
    "AgentPlanner",

    # RFC-034: Planning Strategy
    "PlanningStrategy",

    # RFC-036: Artifact-First Planner
    "ArtifactPlanner",

    # RFC-036: Artifact Types
    "ArtifactSpec",
    "ArtifactGraph",
    "ArtifactLimits",
    "VerificationResult",
    "artifact_to_task",
    "artifacts_to_tasks",
    "select_model_tier",
    "get_model_distribution",

    # RFC-036: Artifact Exceptions
    "ArtifactError",
    "CyclicDependencyError",
    "GraphExplosionError",
    "MissingDependencyError",
    "DiscoveryFailedError",
    "ArtifactCreationError",

    # RFC-036: Artifact Execution
    "ArtifactExecutor",
    "ArtifactResult",
    "ExecutionResult",
    "ExecutionEvent",
    "execute_artifact_graph",
    "execute_with_discovery",

    # RFC-034: Task Graph Analysis
    "ParallelismAnalysis",
    "visualize_task_graph",
    "analyze_parallelism",
    "validate_contracts",
    "format_execution_summary",

    # RFC-032: Checkpointing
    "AgentCheckpoint",
    "FailurePolicy",
    "TaskExecutionConfig",
    "ParallelConfig",
    "find_latest_checkpoint",
    "get_checkpoint_path",

    # Convergence (Working Memory)
    "Convergence",
    "Slot",
    "SlotSource",

    # Shards (Parallel Helpers)
    "Shard",
    "ShardPool",
    "ShardType",

    # Resonance (Feedback Loop)
    "Resonance",
    "ResonanceConfig",
    "ResonanceResult",
    "RefinementAttempt",
    "create_resonance_handler",

    # Discernment (Tiered Validation)
    "Discernment",
    "DiscernmentVerdict",
    "DiscernmentResult",

    # Model Size (moved from rotation.py to types/)
    "ModelSize",

    # RFC-033: Unified Architecture - Diversity Layer
    "Candidate",
    "diversity_none",
    "diversity_sampling",
    "diversity_rotation",
    "diversity_harmonic",
    "HARMONIC_PERSONAS",

    # RFC-033: Unified Architecture - Selection Layer
    "select_passthrough",
    "select_heuristic",
    "select_voting",
    "select_judge",

    # RFC-033: Unified Architecture - Refinement Layer
    "RefinementResult",
    "refine_none",
    "refine_tiered",
    "refine_full",

    # RFC-033: Unified Architecture - Pipeline
    "TaskAnalysis",
    "UnifiedResult",
    "unified_pipeline",
    "select_strategies",
    "create_minimal_config",
    "create_cheap_diversity_config",
    "create_balanced_config",
    "create_quality_config",
    "create_auto_config",

    # RFC-033: Migration Helpers
    "migrate_rfc019_to_rfc033",
    "create_rfc019_equivalent_config",
    "create_rfc028_equivalent_config",

    # RFC-040: Plan Persistence
    "SavedExecution",
    "ArtifactCompletion",
    "ExecutionStatus",
    "PlanStore",
    "TraceLogger",
    "hash_goal",
    "hash_content",
    "hash_file",
    "save_execution",
    "get_latest_execution",
    "resume_execution",

    # RFC-074: Incremental Execution v2
    "ExecutionCache",
    "ExecutionPlan",
    "IncrementalResult",
    "IncrementalExecutorV2",
    "SkipDecision",
    "SkipReason",

    # RFC-067: Integration Verification
    "IntegrationVerifier",
    "StubDetection",

    # RFC-076: Modular Components
    "EventEmitter",
    "NaaruEventEmitter",
    "ExecutionCoordinator",
    "LearningExtractor",

    # RFC-110: Session management moved to Agent level
]
