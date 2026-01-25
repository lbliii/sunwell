"""Agent — Unified Execution Engine (RFC-110, RFC-MEMORY).

The Agent is THE execution engine for Sunwell. All entry points
(CLI, chat, Studio) call Agent.run() with SessionContext and PersistentMemory.

Key components:
- Agent: The brain — analyzes, plans, executes, validates, learns
- SessionContext: Session state (goal, workspace, options)
- PersistentMemory: Unified memory facade (decisions, failures, patterns)
- Events: Streaming progress updates
- Signals: Goal analysis for routing decisions
- Gates: Validation checkpoints in task graphs

Example:
    >>> from sunwell.agent import Agent
    >>> from sunwell.context.session import SessionContext
    >>> from sunwell.memory.persistent import PersistentMemory
    >>> agent = Agent(model=my_model, tool_executor=tools)
    >>> session = SessionContext.build(workspace, "Build a Flask forum app", options)
    >>> memory = PersistentMemory.load(workspace)
    >>> async for event in agent.run(session, memory):
    ...     print(event)
"""

from sunwell.agent.budget import AdaptiveBudget, CostEstimate
from sunwell.agent.core import Agent, TaskGraph
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
    validate_error_event,
)
from sunwell.agent.fixer import FixResult, FixStage
from sunwell.agent.gates import (
    GateResult,
    GateStepResult,
    GateType,
    ValidationGate,
    detect_gates,
    is_runnable_milestone,
)
from sunwell.agent.learning import Learning, LearningExtractor, LearningStore
from sunwell.agent.lens import resolve_lens_for_goal
from sunwell.agent.metrics import InferenceMetrics, InferenceSample, ModelPerformanceProfile
from sunwell.agent.renderer import (
    JSONRenderer,
    QuietRenderer,
    Renderer,
    RendererConfig,
    RichRenderer,
    create_renderer,
)
from sunwell.agent.request import RunOptions
from sunwell.agent.signals import (
    AdaptiveSignals,
    ErrorSignals,
    FastSignalChecker,
    TaskSignals,
    classify_error,
    extract_signals,
)
from sunwell.agent.thinking import ThinkingBlock, ThinkingDetector, ThinkingPhase
from sunwell.agent.toolchain import LanguageToolchain, detect_toolchain
from sunwell.agent.validation import Artifact, ValidationRunner, ValidationStage

# RFC-111: Skill composition and planning
from sunwell.agent.composer import (
    CapabilityAnalysis,
    CompositionResult,
    CompositionType,
    SkillComposer,
)
from sunwell.agent.planner import (
    CapabilityGap,
    CapabilityMatch,
    GoalPlanner,
    get_skills_for_shortcut,
    SHORTCUT_SKILL_MAP,
)

__all__ = [
    # Agent
    "Agent",
    "TaskGraph",
    # Options
    "RunOptions",
    # Budget
    "AdaptiveBudget",
    "CostEstimate",
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
    # RFC-MEMORY event factories
    "orient_event",
    "learning_added_event",
    "decision_made_event",
    "failure_recorded_event",
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
