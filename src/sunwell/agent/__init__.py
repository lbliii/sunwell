"""Agent — Unified Execution Engine (RFC-110, RFC-MEMORY, RFC-134, RFC-137).

The Agent is THE execution engine for Sunwell. All entry points
(CLI, chat, Studio) call Agent.run() with SessionContext and PersistentMemory.

RFC-138: Module Architecture Consolidation - Consolidates context, convergence,
recovery, prefetch, chat, incremental, execution, runtime, and parallel modules.

Key components:
- Agent: The brain — analyzes, plans, executes, validates, learns
- AgentLoop: S-Tier Tool Calling with introspection and learning (RFC-134)
- SessionContext: Session state (goal, workspace, options)
- PersistentMemory: Unified memory facade (decisions, failures, patterns)
- Events: Streaming progress updates (see events.schemas for TypedDict schemas)
- Signals: Goal analysis for routing decisions
- Gates: Validation checkpoints in task graphs
- Ephemeral Lens: Smart-to-dumb model delegation (RFC-137)

S-Tier Tool Calling (RFC-134):
- Tool call introspection and repair via `introspect_tool_call()`
- Progressive tool enablement
- Automatic retry with strategy escalation
- Tool usage pattern learning

Smart-to-Dumb Model Delegation (RFC-137):
- Use `should_use_delegation()` to decide when to delegate
- Use `create_ephemeral_lens()` to generate lens with smart model
- Execute with cheap model using the ephemeral lens

Example:
    >>> from sunwell.agent import Agent, AgentLoop, LoopConfig
    >>> from sunwell.agent import create_ephemeral_lens, should_use_delegation
    >>> from sunwell.agent import create_validated_event, EventType
    >>>
    >>> # Basic agent usage
    >>> agent = Agent(model=my_model, tool_executor=tools)
    >>> async for event in agent.run(session, memory):
    ...     print(event)
    >>>
    >>> # S-Tier tool loop
    >>> loop = AgentLoop(model=model, executor=executor, config=LoopConfig())
    >>> async for event in loop.run("Implement user auth"):
    ...     print(event)
    >>>
    >>> # With delegation
    >>> loop = AgentLoop(
    ...     model=haiku,
    ...     executor=executor,
    ...     config=LoopConfig(enable_delegation=True),
    ...     smart_model=opus,
    ...     delegation_model=haiku,
    ... )
"""

from sunwell.agent.core import Agent, AgentLoop, TaskGraph, run_tool_loop, sanitize_code_content
from sunwell.agent.events import (
    AgentEvent,
    EventType,
    EventUIHints,
    GateSummary,
    TaskSummary,
    briefing_loaded_event,
    briefing_saved_event,
    complete_event,
    decision_made_event,
    delegation_started_event,
    ephemeral_lens_created_event,
    failure_recorded_event,
    gate_start_event,
    gate_step_event,
    learning_added_event,
    lens_selected_event,
    lens_suggested_event,
    memory_learning_event,
    model_complete_event,
    model_start_event,
    model_thinking_event,
    model_tokens_event,
    orient_event,
    plan_winner_event,
    prefetch_complete_event,
    prefetch_start_event,
    prefetch_timeout_event,
    signal_event,
    task_complete_event,
    task_start_event,
    tool_complete_event,
    tool_error_event,
    tool_loop_complete_event,
    tool_loop_start_event,
    tool_loop_turn_event,
    tool_start_event,
    validate_error_event,
)
from sunwell.agent.events.schemas import (
    EVENT_SCHEMAS,
    REQUIRED_FIELDS,
    EventEmitter,
    ValidatedEventEmitter,
    create_validated_event,
    validate_event_data,
)
from sunwell.agent.execution import (
    determine_specialist_role,
    execute_task_streaming_fallback,
    execute_task_with_tools,
    execute_via_specialist,
    execute_with_convergence,
    get_context_snapshot,
    select_lens_for_task,
    should_spawn_specialist,
    validate_gate,
)
from sunwell.agent.execution.fixer import FixResult, FixStage
from sunwell.agent.learning.execution import learn_from_execution
from sunwell.agent.learning.extractor import LearningExtractor
from sunwell.agent.learning.learning import Learning
from sunwell.agent.learning.store import LearningStore
from sunwell.agent.loop import LoopConfig, LoopState
from sunwell.agent.planning import plan_with_signals

# RFC-111: Skill composition and planning
from sunwell.agent.planning.composer import (
    CapabilityAnalysis,
    CompositionResult,
    CompositionType,
    SkillComposer,
)
from sunwell.agent.planning.planner import (
    SHORTCUT_SKILL_MAP,
    CapabilityGap,
    CapabilityMatch,
    GoalPlanner,
    get_skills_for_shortcut,
)
from sunwell.agent.recovery.recovery_helpers import (
    execute_with_convergence_recovery,
    resume_from_recovery,
)
from sunwell.agent.signals import (
    AdaptiveSignals,
    ErrorSignals,
    FastSignalChecker,
    TaskSignals,
    classify_error,
    extract_signals,
)
from sunwell.agent.utils.budget import AdaptiveBudget, CostEstimate
from sunwell.agent.utils.checkpoint_manager import CheckpointManager
from sunwell.agent.utils.ephemeral_lens import create_ephemeral_lens, should_use_delegation
from sunwell.agent.utils.lens import resolve_lens_for_goal
from sunwell.agent.utils.metrics import InferenceMetrics, InferenceSample, ModelPerformanceProfile
from sunwell.agent.utils.renderer import (
    JSONRenderer,
    QuietRenderer,
    Renderer,
    RendererConfig,
    RichRenderer,
    create_renderer,
)
from sunwell.agent.utils.request import RunOptions
from sunwell.agent.utils.spawn import (
    SpawnDepthExceeded,
    SpawnRequest,
    SpecialistResult,
    SpecialistState,
)
from sunwell.agent.utils.thinking import ThinkingBlock, ThinkingDetector, ThinkingPhase
from sunwell.agent.utils.toolchain import LanguageToolchain, detect_toolchain
from sunwell.agent.validation import (
    Artifact,
    GateResult,
    GateStepResult,
    GateType,
    IntrospectionResult,
    ValidationError,
    ValidationGate,
    ValidationRunner,
    ValidationStage,
    detect_gates,
    introspect_tool_call,
    is_runnable_milestone,
)

__all__ = [
    # Agent
    "Agent",
    "TaskGraph",
    "CheckpointManager",
    # Execution helpers
    "determine_specialist_role",
    "execute_task_streaming_fallback",
    "execute_task_with_tools",
    "execute_with_convergence",
    "sanitize_code_content",
    "select_lens_for_task",
    "should_spawn_specialist",
    "validate_gate",
    # Planning helpers
    "plan_with_signals",
    # Recovery helpers
    "execute_with_convergence_recovery",
    "resume_from_recovery",
    # Specialist helpers
    "execute_via_specialist",
    "get_context_snapshot",
    # Learning helpers
    "learn_from_execution",
    # AgentLoop (S-Tier Tool Calling)
    "AgentLoop",
    "LoopConfig",
    "LoopState",
    "run_tool_loop",
    # Options
    "RunOptions",
    # Budget
    "AdaptiveBudget",
    "CostEstimate",
    # Event Schema (type-safe event handling)
    "EVENT_SCHEMAS",
    "REQUIRED_FIELDS",
    "EventEmitter",
    "ValidatedEventEmitter",
    "create_validated_event",
    "validate_event_data",
    # Events
    "AgentEvent",
    "EventType",
    "EventUIHints",
    "TaskSummary",
    "GateSummary",
    # Event factories
    "signal_event",
    "task_start_event",
    "task_complete_event",
    "gate_start_event",
    "gate_step_event",
    "validate_error_event",
    "memory_learning_event",
    "complete_event",
    "lens_selected_event",
    "lens_suggested_event",
    "briefing_loaded_event",
    "briefing_saved_event",
    "prefetch_start_event",
    "prefetch_complete_event",
    "prefetch_timeout_event",
    "model_start_event",
    "model_tokens_event",
    "model_thinking_event",
    "model_complete_event",
    "plan_winner_event",
    # Tool event factories (S-Tier Tool Calling)
    "tool_start_event",
    "tool_complete_event",
    "tool_error_event",
    "tool_loop_start_event",
    "tool_loop_turn_event",
    "tool_loop_complete_event",
    # RFC-MEMORY event factories
    "orient_event",
    "learning_added_event",
    "decision_made_event",
    "failure_recorded_event",
    # RFC-137: Delegation event factories
    "delegation_started_event",
    "ephemeral_lens_created_event",
    # RFC-137: Ephemeral Lens (smart-to-dumb delegation)
    "create_ephemeral_lens",
    "should_use_delegation",
    # RFC-134: Tool introspection
    "IntrospectionResult",
    "introspect_tool_call",
    # RFC-130: Agent Constellation (specialist spawning)
    "SpawnDepthExceeded",
    "SpawnRequest",
    "SpecialistResult",
    "SpecialistState",
    # Thinking
    "ThinkingBlock",
    "ThinkingDetector",
    "ThinkingPhase",
    # Fixer
    "FixStage",
    "FixResult",
    # Gates
    "GateType",
    "ValidationGate",
    "GateResult",
    "GateStepResult",
    "detect_gates",
    "is_runnable_milestone",
    # Metrics
    "InferenceMetrics",
    "InferenceSample",
    "ModelPerformanceProfile",
    # Learning
    "Learning",
    "LearningExtractor",
    "LearningStore",
    # Lens
    "resolve_lens_for_goal",
    # Renderer
    "Renderer",
    "RichRenderer",
    "QuietRenderer",
    "JSONRenderer",
    "RendererConfig",
    "create_renderer",
    # Signals
    "AdaptiveSignals",
    "ErrorSignals",
    "classify_error",
    "extract_signals",
    "FastSignalChecker",
    "TaskSignals",
    # Toolchains
    "LanguageToolchain",
    "detect_toolchain",
    # Validation
    "Artifact",
    "ValidationError",
    "ValidationRunner",
    "ValidationStage",
    # RFC-111: Skill Composition
    "SkillComposer",
    "CompositionType",
    "CompositionResult",
    "CapabilityAnalysis",
    # RFC-111: Goal Planning
    "GoalPlanner",
    "CapabilityMatch",
    "CapabilityGap",
    "get_skills_for_shortcut",
    "SHORTCUT_SKILL_MAP",
]
