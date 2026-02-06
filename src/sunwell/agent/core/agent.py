"""Agent — THE Execution Engine for Sunwell (RFC-110, RFC-MEMORY).

The Agent is the single point of intelligence. All entry points
(CLI, chat, Studio) call Agent.run() with SessionContext and PersistentMemory.

The Agent:
1. Orients — loads memory context, identifies constraints
2. Analyzes goals (signals)
3. Selects expertise (lens)
4. Plans execution (task graph) — memory-informed
5. Executes with validation (gates)
6. Auto-fixes errors (Compound Eye)
7. Learns from execution — syncs to PersistentMemory

Agent uses Naaru internally for parallel task execution,
but Naaru is an implementation detail — not an entry point.

Example:
    >>> from sunwell.agent import Agent
    >>> from sunwell.agent.context.session import SessionContext
    >>> from sunwell.memory import PersistentMemory
    >>> agent = Agent(model=model, tool_executor=tools)
    >>> session = SessionContext.build(workspace, "Build a REST API", options)
    >>> memory = PersistentMemory.load(workspace)
    >>> async for event in agent.run(session, memory):
    ...     print(event)
"""

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from time import time
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)

from sunwell.agent.core.task_graph import TaskGraph, sanitize_code_content
from sunwell.agent.events import (
    AgentEvent,
    EventType,
    briefing_loaded_event,
    complete_event,
    domain_detected_event,
    failure_recorded_event,
    intent_classified_event,
    lens_selected_event,
    memory_learning_event,
    orient_event,
    signal_event,
    task_complete_event,
    task_output_event,
    task_start_event,
)
from sunwell.agent.execution import (
    TaskDispatcher,
    determine_specialist_role,
    execute_task_streaming_fallback,
    execute_task_with_tools,
    execute_via_specialist,
    execute_with_convergence,
    get_context_snapshot,
    select_lens_for_task,
    should_spawn_specialist,
    should_use_parallel_dispatch,
    validate_gate,
)
from sunwell.agent.execution.fixer import FixStage
from sunwell.agent.learning import (
    LearningExtractor,
    LearningStore,
    RoutingOutcomeStore,
    learn_from_execution,
)
from sunwell.agent.signals import AdaptiveSignals, extract_signals
from sunwell.agent.utils.budget import AdaptiveBudget
from sunwell.agent.utils.metrics import InferenceMetrics
from sunwell.agent.utils.request import RunOptions
from sunwell.agent.utils.toolchain import detect_toolchain
from sunwell.agent.validation import Artifact, ValidationRunner
from sunwell.agent.validation.gates import ValidationGate
from sunwell.tools.selection.graph import ToolDAGError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator as TypeAsyncIterator, Callable

    from sunwell.agent.coordination.parallel_executor import ParallelExecutor, TaskResult
    from sunwell.agent.loop.config import LoopConfig
    from sunwell.agent.recovery.types import RecoveryState
    from sunwell.foundation.core.lens import Lens
    from sunwell.memory.briefing import Briefing, PrefetchedContext
    from sunwell.memory.simulacrum.core.planning_context import PlanningContext
    from sunwell.memory.simulacrum.core.store import SimulacrumStore
    from sunwell.models import ModelProtocol
    from sunwell.planning.naaru import Naaru
    from sunwell.planning.naaru.types import Task
    from sunwell.tools.execution import ToolExecutor
    from sunwell.tools.tracking import InvocationTracker

from sunwell.agent.context.session import SessionContext
from sunwell.memory import PersistentMemory
from sunwell.planning.naaru.checkpoint import AgentCheckpoint, CheckpointPhase


@dataclass(frozen=True, slots=True)
class PlanResult:
    """Result from plan_only() for duration estimation.

    Contains the task graph and metrics needed for accurate
    duration estimation before execution.
    """

    task_graph: TaskGraph
    """The planned task graph."""

    metrics: Any  # PlanMetrics | PlanMetricsV2
    """Plan quality metrics (depth, parallelism, etc.)."""

    signals: Any = None  # AdaptiveSignals
    """Extracted signals from goal analysis."""

    estimated_seconds: int | None = None
    """Duration estimate in seconds (set after estimation for calibration)."""


@dataclass(slots=True)
class Agent:
    """THE execution engine for Sunwell (RFC-MEMORY, RFC-137).

    This is the single point of intelligence. All entry points
    (CLI, chat, Studio) call Agent.run() with SessionContext and PersistentMemory.

    Agent uses Naaru internally for parallel task execution,
    but Naaru is an implementation detail — not an entry point.

    RFC-137 adds smart-to-dumb model delegation for cost optimization:
    - Configure smart_model + delegation_model at construction
    - Enable via RunOptions.enable_delegation
    - Large tasks auto-delegate to cheaper model with ephemeral lens

    Attributes:
        model: Primary LLM for generation
        smart_model: Optional smart model for lens creation (RFC-137)
        delegation_model: Optional cheap model for delegated execution (RFC-137)
        tool_executor: Executor for tools (file I/O, commands, etc.)
        cwd: Working directory (default: Path.cwd())
        budget: Token budget configuration
    """

    model: ModelProtocol
    """Primary model for generation."""

    tool_executor: ToolExecutor | None = None
    """Tool executor for file I/O, commands, etc."""

    cwd: Path | None = None
    """Working directory."""

    budget: AdaptiveBudget = field(default_factory=AdaptiveBudget)
    """Token budget with auto-economization."""

    # RFC-137: Model delegation
    smart_model: ModelProtocol | None = None
    """Smart model for ephemeral lens creation (RFC-137).

    Used during delegation to analyze the task and create guidance.
    If None, uses the primary model for lens creation.
    """

    delegation_model: ModelProtocol | None = None
    """Cheap model for delegated task execution (RFC-137).

    Used for actual code generation/execution after lens creation.
    If None, delegation is disabled even with enable_delegation=True.
    """

    # Lens configuration
    lens: Lens | None = None
    """Active lens for expertise injection."""

    auto_lens: bool = True
    """Whether to auto-select lens if none provided."""

    # Inference visibility configuration
    stream_inference: bool = True
    """Whether to use streaming for inference visibility."""

    token_batch_size: int = 10
    """Batch size for token events (reduce event spam)."""

    # Internal state (not user-configurable)
    _learning_store: LearningStore = field(default_factory=LearningStore, init=False)
    _routing_outcome_store: RoutingOutcomeStore = field(
        default_factory=RoutingOutcomeStore, init=False
    )
    _learning_extractor: LearningExtractor = field(default_factory=LearningExtractor, init=False)
    _validation_runner: ValidationRunner | None = field(default=None, init=False)
    _fix_stage: FixStage | None = field(default=None, init=False)
    _naaru: Naaru | None = field(default=None, init=False)
    _inference_metrics: InferenceMetrics = field(default_factory=InferenceMetrics, init=False)
    _task_graph: TaskGraph | None = field(default=None, init=False)

    # Run state (set by run() method)
    _current_goal: str = field(default="", init=False)
    _current_options: RunOptions | None = field(default=None, init=False)
    """Current RunOptions for this execution (RFC-137 delegation config)."""
    _briefing: Briefing | None = field(default=None, init=False)
    _workspace_context: str | None = field(default=None, init=False)
    _files_changed_this_run: list[str] = field(default_factory=list, init=False)
    _last_planning_context: PlanningContext | None = field(default=None, init=False)
    _prefetched_context: PrefetchedContext | None = field(default=None, init=False)
    """Prefetched context from briefing (files, hints)."""

    # RFC-MEMORY: Reference to memory stores for planning and execution
    _simulacrum: SimulacrumStore | None = field(default=None, init=False)
    """SimulacrumStore from PersistentMemory (set during run())."""

    _memory: PersistentMemory | None = field(default=None, init=False)
    """Full PersistentMemory reference for task-level context (set during run())."""

    # RFC-130: Agent Constellation — Specialist spawning
    _spawned_specialist_ids: list[str] = field(default_factory=list, init=False)
    """IDs of specialists spawned during this run."""

    # Tool invocation tracking for verification and self-correction
    _invocation_tracker: InvocationTracker | None = field(default=None, init=False)
    """Tracks tool invocations for verification and self-correction."""

    _specialist_count: int = field(default=0, init=False)
    """Count of specialists spawned in this run."""

    # RFC-DOMAINS: Domain detection
    _detected_domain: Any = field(default=None, init=False)
    """Detected domain for current goal (from DomainRegistry)."""

    # RFC-130: Semantic checkpointing
    _user_decisions: list[str] = field(default_factory=list, init=False)
    """User decisions recorded during this run."""

    _checkpoint_count: int = field(default=0, init=False)
    """Number of checkpoints saved in this run."""

    _last_task_result: str | None = field(default=None, init=False)
    """Last task result text (for file writing)."""

    _gates_passed: int = field(default=0, init=False)
    """Count of validation gates that passed during this run."""

    _current_phase: CheckpointPhase = field(
        default=CheckpointPhase.ORIENT_COMPLETE, init=False
    )
    """Current semantic phase of execution."""

    # Recovery manager for persisting execution state on failures
    _recovery_manager: Any = field(default=None, init=False)
    """RecoveryManager for saving state on interruption/failure."""

    def __post_init__(self) -> None:
        if self.cwd is None:
            self.cwd = Path.cwd()
        self.cwd = Path(self.cwd)

        # Initialize toolchain for validation
        toolchain = detect_toolchain(self.cwd)
        self._validation_runner = ValidationRunner(toolchain, self.cwd)
        self._fix_stage = FixStage(self.model, self.cwd, max_attempts=3)

        # Initialize recovery manager for persisting execution state on failures
        from sunwell.agent.recovery.manager import RecoveryManager
        recovery_dir = self.cwd / ".sunwell" / "recovery"
        self._recovery_manager = RecoveryManager(recovery_dir)

        # Load inference metrics from disk for model discovery
        self._inference_metrics.load_from_disk(self.cwd)

        # Load routing outcomes from disk for adaptive routing
        self._routing_outcome_store.load_from_disk(self.cwd)

        # Initialize Naaru for task execution (if tool_executor provided)
        if self.tool_executor:
            self._init_naaru()

    @property
    def simulacrum(self) -> SimulacrumStore | None:
        """Get SimulacrumStore from current run context (RFC-MEMORY)."""
        return self._simulacrum

    def _populate_learning_store_from_memory(
        self,
        workspace: Path,
        memory: PersistentMemory,
    ) -> int:
        """Populate LearningStore from persistent memory sources.

        Phase 1.1 of Unified Memory Coordination: Ensures the agent starts
        with existing learnings from prior sessions and other workers.

        Loads from (in priority order):
        1. Journal (primary durable source)
        2. SimulacrumStore DAG (legacy learnings)

        Args:
            workspace: Project workspace path
            memory: PersistentMemory instance

        Returns:
            Number of learnings loaded
        """
        loaded = 0

        # 1. Load from journal (primary source - durable, cross-worker visible)
        try:
            journal_loaded = self._learning_store.load_from_journal(workspace)
            loaded += journal_loaded
            if journal_loaded > 0:
                logger.debug("Loaded %d learnings from journal", journal_loaded)
        except Exception as e:
            logger.debug("Failed to load from journal: %s", e)

        # 2. Load from SimulacrumStore (may have learnings not yet in journal)
        if memory.simulacrum:
            try:
                sim_loaded = self._learning_store.load_from_simulacrum(memory.simulacrum)
                loaded += sim_loaded
                if sim_loaded > 0:
                    logger.debug("Loaded %d learnings from simulacrum", sim_loaded)
            except Exception as e:
                logger.debug("Failed to load from simulacrum: %s", e)

        if loaded > 0:
            logger.info("Populated LearningStore with %d learnings from memory", loaded)

        return loaded

    def _subscribe_to_learning_bus(self) -> None:
        """Subscribe LearningStore to the global LearningBus.

        Phase 2.2 of Unified Memory Coordination: Enables real-time learning
        sharing between in-process agents (subagents, Naaru workers).

        When another agent publishes a learning to the bus, this agent's
        LearningStore will automatically receive it.
        """
        try:
            from sunwell.memory.core.learning_bus import subscribe_learning_store

            subscribe_learning_store(self._learning_store)
            logger.debug("Subscribed LearningStore to LearningBus")
        except Exception as e:
            logger.debug("Failed to subscribe to LearningBus: %s", e)

    def _init_naaru(self) -> None:
        """Initialize internal Naaru for task execution."""
        from sunwell.foundation.types.config import NaaruConfig
        from sunwell.planning.naaru import Naaru

        self._naaru = Naaru(
            workspace=self.cwd,
            synthesis_model=self.model,
            tool_executor=self.tool_executor,
            simulacrum=self._simulacrum,  # RFC-MEMORY: Pass simulacrum for learnings
            memory=self._memory,           # RFC-MEMORY: Pass PersistentMemory
            config=NaaruConfig(
                enable_parallel_execution=True,
                max_parallel_tasks=4,
            ),
        )

    async def run(
        self,
        session: SessionContext,
        memory: PersistentMemory,
        *,
        precomputed_plan: PlanResult | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """Execute goal with explicit context and memory (RFC-MEMORY).

        This is THE execution method. All entry points (CLI, chat, Studio)
        build SessionContext and PersistentMemory, then call Agent.run().

        Pipeline:
        1. ORIENT   → Load memory context, identify constraints
        2. SIGNAL   → Analyze goal complexity and domain
        3. LENS     → Select or validate expertise injection
        4. PLAN     → Decompose into task graph (memory-informed)
        5. EXECUTE  → Run tasks (Naaru handles parallelism)
        6. VALIDATE → Check gates at checkpoints
        7. FIX      → Auto-fix failures (Compound Eye)
        8. LEARN    → Persist patterns to PersistentMemory

        Args:
            session: SessionContext with goal, workspace, options
            memory: PersistentMemory with decisions, failures, patterns
            precomputed_plan: Optional PlanResult from plan_only() to skip planning

        Yields:
            AgentEvent for each step of execution
        """
        start_time = time()
        self._current_goal = session.goal
        self.cwd = session.cwd
        self._gates_passed = 0  # Reset counter for this run

        # RFC-MEMORY: Store memory references for planning and task execution
        self._simulacrum = memory.simulacrum
        self._memory = memory

        # Populate LearningStore from persistent memory (Phase 1.1: Unified Memory Coordination)
        # This ensures the agent starts with existing learnings from prior sessions
        self._populate_learning_store_from_memory(session.cwd, memory)

        # Phase 2.2: Subscribe LearningStore to LearningBus for real-time sharing
        # This enables in-process agents (subagents, Naaru workers) to share learnings
        self._subscribe_to_learning_bus()

        # Update Naaru's memory references (they were None at __post_init__ time)
        if self._naaru:
            self._naaru.simulacrum = self._simulacrum
            self._naaru.memory = self._memory

        # RFC-126: Store workspace context for task execution
        # RFC-135: Enrich with goal-aware context from SmartContext
        base_context = session.to_planning_prompt()
        from sunwell.knowledge import enrich_context_for_goal

        self._workspace_context = await enrich_context_for_goal(
            goal=session.goal,
            workspace=session.cwd,
            model=self.model,
            base_context=base_context,
        )

        # ─── PHASE 0.1: INTENT CLASSIFICATION (Conversational DAG Architecture) ───
        # Classify intent and emit event for UI display
        from sunwell.agent.intent import (
            classify_intent,
            format_path,
            get_tool_scope,
            requires_approval,
        )

        classification = await classify_intent(session.goal, model=self.model)
        tool_scope = get_tool_scope(classification.path)
        yield intent_classified_event(
            path=tuple(n.value for n in classification.path),
            confidence=classification.confidence,
            reasoning=classification.reasoning,
            requires_approval=requires_approval(classification.path),
            tool_scope=tool_scope.value if tool_scope else None,
        )

        # ─── PHASE 0.2: DOMAIN DETECTION (RFC-DOMAINS) ───
        # Detect domain for goal-appropriate tools and validators
        from sunwell.domains import DomainRegistry

        detected_domain, domain_confidence = DomainRegistry.detect(session.goal)
        self._detected_domain = detected_domain
        yield domain_detected_event(
            domain_type=detected_domain.domain_type.value,
            confidence=domain_confidence,
            tools_package=detected_domain.tools_package,
            validators=[v.name for v in detected_domain.validators],
        )

        # ─── PHASE 0: PREFETCH (RFC-130) ───
        # Memory-informed prefetch to warm context before main execution
        if session.briefing:
            prefetched = await self._run_memory_informed_prefetch(
                session.briefing, memory
            )
            if prefetched:
                self._prefetched_context = prefetched
                # If prefetch suggests a lens, use it (unless explicitly set)
                if prefetched.lens and not session.lens:
                    from sunwell.planning.lens.manager import LensManager
                    try:
                        manager = LensManager()
                        suggested_lens = manager.load(prefetched.lens)
                        if suggested_lens:
                            self.lens = suggested_lens
                            yield lens_selected_event(
                                name=suggested_lens.metadata.name,
                                source="memory_prefetch",
                                confidence=0.75,
                                reason="Lens from similar past goal",
                            )
                    except Exception as e:
                        logger.debug("Failed to load prefetched lens %r: %s", prefetched.lens, e)

        # ─── PHASE 1: ORIENT ───
        # What do we know? What should we avoid?
        memory_ctx = await memory.get_relevant(session.goal)

        yield orient_event(
            learnings=len(memory_ctx.learnings),
            constraints=len(memory_ctx.constraints),
            dead_ends=len(memory_ctx.dead_ends),
        )

        # Use session's briefing if available
        if session.briefing:
            self._briefing = session.briefing
            yield briefing_loaded_event(
                mission=session.briefing.mission,
                status=session.briefing.status.value,
                has_hazards=len(session.briefing.hazards) > 0,
                has_dispatch_hints=bool(
                    session.briefing.predicted_skills or session.briefing.suggested_lens
                ),
            )

        # Resolve lens
        if session.lens:
            self.lens = session.lens
        elif self.lens is None and self.auto_lens:
            from sunwell.agent.utils.lens import resolve_lens_for_goal

            resolution = await resolve_lens_for_goal(
                goal=session.goal,
                project_path=session.cwd,
                auto_select=True,
            )
            if resolution.lens:
                self.lens = resolution.lens
                yield lens_selected_event(
                    name=resolution.lens.metadata.name,
                    source=resolution.source,
                    confidence=resolution.confidence,
                    reason=resolution.reason,
                )

        # ─── PHASE 2: SIGNAL ───
        yield signal_event("extracting")
        signals = await self._extract_signals_with_memory(session.goal)
        yield signal_event("extracted", signals=signals.to_dict())

        # Check for dangerous or ambiguous goals
        if signals.is_dangerous == "YES":
            yield AgentEvent(
                EventType.ESCALATE,
                {
                    "reason": "dangerous_operation",
                    "message": "This goal may be dangerous. Please confirm.",
                },
            )
            return

        if signals.effective_confidence < 0.3:
            yield AgentEvent(
                EventType.ESCALATE,
                {
                    "reason": "low_confidence",
                    "message": "I'm not confident I understand this goal. Please clarify.",
                },
            )
            return

        # ─── PHASE 3: PLAN ───
        if precomputed_plan is not None:
            # Use precomputed plan from plan_only() (skip re-planning)
            self._task_graph = precomputed_plan.task_graph
            # Emit PLAN_WINNER event for consistency with UI
            from sunwell.agent.events import plan_winner_event
            yield plan_winner_event(
                tasks=len(precomputed_plan.task_graph.tasks),
                gates=len(precomputed_plan.task_graph.gates),
                technique="precomputed",
                task_graph=precomputed_plan.task_graph,
            )
        else:
            # Build context with memory constraints
            planning_context: dict[str, Any] = {}
            learnings_context = self._learning_store.format_for_prompt()
            if learnings_context:
                planning_context["learnings"] = learnings_context

            if self.lens:
                planning_context["lens_context"] = self.lens.to_context()

            if self._briefing:
                planning_context["briefing"] = self._briefing.to_prompt()

            # RFC-MEMORY: Inject memory constraints into planning
            memory_prompt = memory_ctx.to_prompt()
            if memory_prompt:
                planning_context["memory_constraints"] = memory_prompt

            async for event in self._plan_with_signals(session.goal, signals, planning_context):
                yield event
                if event.type == EventType.ERROR:
                    return

        # Update session with tasks
        if self._task_graph:
            session.tasks = self._task_graph.tasks

        # ─── PHASE 4: EXECUTE ───
        # Use session options if available, otherwise build defaults
        from sunwell.agent.utils.request import RunOptions
        if session.options is not None:
            options = session.options
        else:
            options = RunOptions(
                trust=session.trust,
                timeout_seconds=session.timeout,
                validate=True,
                persist_learnings=True,
                auto_fix=True,
            )

        # Store current options for task execution (RFC-137 delegation)
        self._current_options = options

        # Decide execution strategy: parallel dispatch or sequential
        execution_fn = self._select_execution_strategy(session, options)

        execution_success = True
        async for event in execution_fn(options):
            yield event
            if event.type in (EventType.ERROR, EventType.ESCALATE):
                execution_success = False
                # Record failure to memory
                if self._task_graph and self._task_graph.tasks:
                    current = session.current_task
                    if current:
                        from sunwell.knowledge import FailedApproach
                        failure = FailedApproach(
                            id="",  # Will be generated
                            description=current.description,
                            error_type="execution_error",
                            error_message=event.data.get("message", "Unknown error"),
                            context=session.goal,
                            session_id=session.session_id,
                        )
                        await memory.add_failure(failure)
                        yield failure_recorded_event(
                            description=failure.description,
                            error_type=failure.error_type,
                            context=failure.context,
                        )
                # Don't return early - continue to session end phases
                break

        # Track modified files
        if self._task_graph:
            for task in self._task_graph.tasks:
                if task.id in self._task_graph.completed_ids and task.target_path:
                    session.files_modified.append(task.target_path)

        # ─── PHASE 5: SAVE SESSION (GUARANTEED) ───
        # Save conversation DAG even on failure - this preserves context for debugging
        memory.sync()

        # ─── PHASE 6: LEARN ───
        # Always extract learnings, even from failures (learn what NOT to do)
        async for event in self._learn_from_execution(
            session.goal, execution_success, memory, force=True
        ):
            yield event

        # ─── PHASE 7: REFLECT ───
        # Analyze session and update briefing
        await self._reflect_on_session(session, execution_success, memory)

        # Save routing outcomes for adaptive routing
        self._routing_outcome_store.save_to_disk(session.cwd)

        # Save briefing for next session
        session.save_briefing()

        # ─── PHASE 8: LOG EXECUTION HISTORY (RFC: Plan-Based Duration Estimation) ───
        # Record actual duration for historical calibration
        duration = time() - start_time
        if (
            precomputed_plan is not None
            and precomputed_plan.estimated_seconds is not None
            and self._task_graph is not None
        ):
            try:
                from sunwell.agent.estimation import ExecutionHistory, PlanProfile

                history = ExecutionHistory.load(session.cwd)
                profile = PlanProfile.from_task_graph(
                    self._task_graph, precomputed_plan.metrics
                )
                history.record(
                    profile=profile,
                    estimated_seconds=precomputed_plan.estimated_seconds,
                    actual_seconds=int(duration),
                )
                history.save(session.cwd)
                logger.debug(
                    "Logged execution history: estimated=%ds, actual=%ds",
                    precomputed_plan.estimated_seconds,
                    int(duration),
                )
            except Exception as e:
                logger.debug("Failed to log execution history: %s", e)

        # ─── COMPLETE ───
        tasks_done = len(self._task_graph.completed_ids) if self._task_graph else 0
        yield complete_event(
            tasks_completed=tasks_done,
            gates_passed=self._gates_passed,
            duration_s=duration,
            learnings=len(self._learning_store.learnings),
        )

    async def resume_from_recovery(
        self,
        recovery_state: RecoveryState,
        user_hint: str | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """Resume execution from a recovery state (RFC-125).

        Delegates to recovery.resume_from_recovery for the actual implementation.
        """
        from sunwell.agent.recovery.recovery_helpers import resume_from_recovery as _resume

        self._current_goal = f"Recovery for: {recovery_state.goal}"

        async for event in _resume(
            recovery_state=recovery_state,
            model=self.model,
            cwd=self.cwd,
            learning_store=self._learning_store,
            extract_signals_fn=self._extract_signals_with_memory,
            plan_with_signals_fn=self._plan_with_signals,
            user_hint=user_hint,
        ):
            yield event

    async def plan(
        self,
        session: SessionContext,
        memory: PersistentMemory | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """Plan without executing (dry run mode).

        Extracts signals, selects technique, and generates plan,
        but does not execute tasks.

        Args:
            session: SessionContext with goal
            memory: Optional PersistentMemory for simulacrum access

        Yields:
            Planning events only
        """
        # RFC-MEMORY: Store memory references for planning
        if memory:
            self._simulacrum = memory.simulacrum
            self._memory = memory

        yield signal_event("extracting")
        signals = await self._extract_signals_with_memory(session.goal)
        yield signal_event("extracted", signals=signals.to_dict())

        yield AgentEvent(
            EventType.SIGNAL_ROUTE,
            {
                "planning": signals.planning_route,
                "execution": signals.execution_route,
                "confidence": signals.effective_confidence,
            },
        )

        async for event in self._plan_with_signals(session.goal, signals, {}):
            yield event

    async def plan_only(
        self,
        goal: str,
        memory: PersistentMemory | None = None,
    ) -> PlanResult:
        """Run planning and return result directly (for duration estimation).

        Unlike plan(), this method returns the TaskGraph and metrics directly
        rather than yielding events. Used by routing to get plan data before
        offering background execution.

        Args:
            goal: The goal to plan for
            memory: Optional PersistentMemory for simulacrum access

        Returns:
            PlanResult with task_graph and metrics
        """
        from sunwell.planning.naaru.planners.metrics import PlanMetrics

        # RFC-MEMORY: Store memory references for planning
        if memory:
            self._simulacrum = memory.simulacrum
            self._memory = memory

        # Extract signals
        signals = await self._extract_signals_with_memory(goal)

        # Build minimal planning context
        planning_context: dict[str, Any] = {}
        learnings_context = self._learning_store.format_for_prompt()
        if learnings_context:
            planning_context["learnings"] = learnings_context

        if self.lens:
            planning_context["lens_context"] = self.lens.to_context()

        if self._briefing:
            planning_context["briefing"] = self._briefing.to_prompt()

        # Run planning and capture task_graph and metrics from PLAN_WINNER event
        task_graph: TaskGraph | None = None
        metrics: PlanMetrics | None = None

        async for event in self._plan_with_signals(goal, signals, planning_context):
            if event.type == EventType.PLAN_WINNER:
                task_graph = event.data.get("task_graph")
                # Metrics from harmonic planning
                metrics_dict = event.data.get("metrics")
                if metrics_dict and isinstance(metrics_dict, dict):
                    # Reconstruct PlanMetrics from dict if available
                    try:
                        metrics = PlanMetrics(
                            depth=metrics_dict.get("depth", 1),
                            width=metrics_dict.get("width", 1),
                            leaf_count=metrics_dict.get("leaf_count", 1),
                            artifact_count=metrics_dict.get("artifact_count", 1),
                            parallelism_factor=metrics_dict.get("parallelism_factor", 1.0),
                            balance_factor=metrics_dict.get("balance_factor", 1.0),
                            file_conflicts=metrics_dict.get("file_conflicts", 0),
                            estimated_waves=metrics_dict.get("estimated_waves", 1),
                        )
                    except (TypeError, KeyError):
                        pass

        # If no task_graph from planning, create empty one
        if task_graph is None:
            task_graph = TaskGraph()

        # If no metrics, create default metrics based on task_graph
        if metrics is None:
            task_count = len(task_graph.tasks)
            metrics = PlanMetrics(
                depth=1,
                width=task_count,
                leaf_count=task_count,
                artifact_count=task_count,
                parallelism_factor=1.0,
                balance_factor=float(task_count),
                file_conflicts=0,
                estimated_waves=1,
            )

        return PlanResult(task_graph=task_graph, metrics=metrics, signals=signals)

    async def _extract_signals_with_memory(self, goal: str) -> AdaptiveSignals:
        """Extract signals with memory context."""
        signals = await extract_signals(goal, self.model)

        # Boost confidence if we have relevant learnings
        relevant = self._learning_store.get_relevant(goal)
        if relevant:
            signals = signals.with_memory_boost(len(relevant))

        return signals

    async def _plan_with_signals(
        self,
        goal: str,
        signals: AdaptiveSignals,
        context: dict[str, Any],
    ) -> AsyncIterator[AgentEvent]:
        """Plan using signal-appropriate technique."""
        # Deferred import to avoid circular dependency
        from sunwell.agent.planning.planning_helpers import plan_with_signals

        async for event in plan_with_signals(
            goal=goal,
            signals=signals,
            context=context,
            model=self.model,
            learning_store=self._learning_store,
            lens=self.lens,
            briefing=self._briefing,
            budget=self.budget,
            simulacrum=self.simulacrum,
        ):
            yield event
            # Extract task_graph and planning_context from PLAN_WINNER event data
            if event.type == EventType.PLAN_WINNER:
                task_graph = event.data.get("task_graph")
                if task_graph is not None:
                    self._task_graph = task_graph
                planning_context = event.data.get("planning_context")
                if planning_context is not None:
                    self._last_planning_context = planning_context

    def _select_execution_strategy(
        self,
        session: SessionContext,
        options: RunOptions,
    ) -> "Callable[[RunOptions], AsyncIterator[AgentEvent]]":
        """Select execution strategy: parallel dispatch or sequential.

        Checks if TaskDispatcher would provide benefit (parallel groups exist
        and parallel execution is enabled), otherwise falls back to sequential.

        Args:
            session: Current session context
            options: Run options

        Returns:
            Execution function to use (parallel or sequential)
        """
        from sunwell.agent.loop.config import LoopConfig

        if not self._task_graph:
            return self._execute_with_gates

        # Create LoopConfig with parallel settings
        config = LoopConfig(
            enable_parallel_tasks=True,
            enable_worktree_isolation=True,
            enable_content_validation=True,
        )

        # Check if parallel dispatch would be beneficial
        if should_use_parallel_dispatch(self._task_graph, config):
            logger.info(
                "Using TaskDispatcher for parallel execution (%d parallelizable groups)",
                len(self._task_graph.get_parallelizable_groups()),
            )
            # Return a wrapper that uses TaskDispatcher
            return lambda opts: self._execute_with_dispatcher(session, opts, config)

        # Fall back to sequential execution
        return self._execute_with_gates

    async def _execute_with_dispatcher(
        self,
        session: SessionContext,
        options: RunOptions,
        config: "LoopConfig",
    ) -> AsyncIterator[AgentEvent]:
        """Execute tasks using TaskDispatcher for parallel execution.

        Uses TaskDispatcher to route parallelizable groups to concurrent
        execution while still handling artifacts and validation gates.

        Args:
            session: Current session context
            options: Run options
            config: Loop configuration with parallel settings

        Yields:
            AgentEvent for each step of execution
        """
        if not self._task_graph:
            return

        # Runtime import to avoid circular dependency
        from sunwell.agent.coordination.parallel_executor import ParallelExecutor, TaskResult

        # Create task executor callback for parallel execution
        # This wraps the agent's task execution to return TaskResult
        async def parallel_task_executor(
            child_session: SessionContext,
            task: "Task",
        ) -> TaskResult:
            """Execute a task in parallel context, returning TaskResult."""
            start = time()
            artifacts: list[str] = []
            output: str | None = None

            try:
                # Execute task using streaming (handles tool calls properly)
                async for _event in self._execute_task_streaming(task):
                    pass  # Consume events; parallel tasks don't stream to UI

                # Get result and write to file if needed
                result_text = getattr(self, "_last_task_result", None)
                if result_text and task.target_path:
                    # Use child session's cwd (may be worktree)
                    path = child_session.cwd / task.target_path
                    path.parent.mkdir(parents=True, exist_ok=True)
                    sanitized = sanitize_code_content(result_text)
                    path.write_text(sanitized)
                    artifacts.append(task.target_path)
                    output = f"Created {task.target_path}"

                # Mark task complete in graph
                if self._task_graph:
                    self._task_graph.mark_complete(task)

                return TaskResult(
                    task_id=task.id,
                    success=True,
                    output=output or "Task completed",
                    artifacts=artifacts,
                    duration_ms=int((time() - start) * 1000),
                )

            except Exception as e:
                logger.exception("Parallel task %s failed", task.id)
                return TaskResult(
                    task_id=task.id,
                    success=False,
                    error=str(e),
                    duration_ms=int((time() - start) * 1000),
                )

        # Create parallel executor with the task executor callback
        parallel_executor = ParallelExecutor(task_executor=parallel_task_executor)

        # Create dispatcher with the configured parallel executor
        dispatcher = TaskDispatcher(
            workspace=self.cwd,
            session=session,
            config=config,
            parallel_executor=parallel_executor,
        )

        # Create sequential execution callback for individual tasks
        async def execute_single_task(task: "Task") -> AsyncIterator[AgentEvent]:
            """Execute a single task and yield events."""
            yield task_start_event(task.id, task.description)

            start = time()

            if self.stream_inference:
                async for event in self._execute_task_streaming(task):
                    yield event

                result_text = getattr(self, "_last_task_result", None)
                if result_text and task.target_path:
                    path = self.cwd / task.target_path
                    path.parent.mkdir(parents=True, exist_ok=True)
                    sanitized = sanitize_code_content(result_text)
                    path.write_text(sanitized)
                    self._files_changed_this_run.append(task.target_path)
            else:
                await self._execute_task(task)

            duration_ms = int((time() - start) * 1000)
            self._task_graph.mark_complete(task)
            yield task_complete_event(task.id, duration_ms)

        # Execute via dispatcher
        artifacts: dict[str, Artifact] = {}
        async for event in dispatcher.execute_graph(self._task_graph, execute_single_task):
            yield event

            # Track artifacts from task completion events
            if event.type == EventType.TASK_COMPLETE:
                task_id = event.data.get("task_id")
                if task_id:
                    # Find the task and check if it has a target path
                    for task in self._task_graph.tasks:
                        if task.id == task_id and task.target_path:
                            path = self.cwd / task.target_path
                            if path.exists():
                                artifacts[task_id] = Artifact(
                                    path=path,
                                    content=path.read_text(),
                                    task_id=task_id,
                                )
                            break

        # Run validation gates after all tasks complete
        if options.validate:
            for gate in self._task_graph.gates:
                if all(dep in self._task_graph.completed_ids for dep in gate.depends_on):
                    gate_artifacts = [
                        artifacts[tid]
                        for tid in gate.depends_on
                        if tid in artifacts
                    ]

                    async for event in validate_gate(gate, gate_artifacts, self.cwd):
                        yield event

                        if event.type == EventType.GATE_PASS:
                            self._gates_passed += 1

                        if event.type == EventType.GATE_FAIL and options.auto_fix:
                            error_msg = event.data.get("error_message", "Unknown error")
                            failed_step = event.data.get("failed_step", "unknown")
                            async for fix_event in self._attempt_fix(
                                gate, gate_artifacts, error_msg, failed_step
                            ):
                                yield fix_event
                                if fix_event.type == EventType.ESCALATE:
                                    return

    async def _execute_with_gates(self, options: RunOptions) -> AsyncIterator[AgentEvent]:
        """Execute tasks with validation gates and inference visibility.

        RFC-130: Now supports specialist spawning for complex tasks.
        """
        if not self._task_graph:
            return

        artifacts: dict[str, Artifact] = {}
        current_gate_idx = 0

        while self._task_graph.has_pending_tasks():
            ready = self._task_graph.get_ready_tasks()
            if not ready:
                yield AgentEvent(
                    EventType.ERROR,
                    {"message": "No tasks ready to execute (deadlock?)"},
                )
                return

            for task in ready:
                # RFC-130: Check if task should be delegated to specialist
                if self._should_spawn_specialist(task):
                    async for event in self._execute_via_specialist(task):
                        yield event
                    self._task_graph.mark_complete(task)
                    continue

                yield task_start_event(task.id, task.description)

                start = time()

                if self.stream_inference:
                    async for event in self._execute_task_streaming(task):
                        yield event

                    result_text = getattr(self, "_last_task_result", None)
                    if result_text and task.target_path:
                        path = self.cwd / task.target_path
                        path.parent.mkdir(parents=True, exist_ok=True)
                        # Sanitize before writing (defense-in-depth)
                        sanitized = sanitize_code_content(result_text)
                        path.write_text(sanitized)
                        result_text = sanitized  # Update for artifact
                        # RFC-122: Track files changed for learning extraction
                        self._files_changed_this_run.append(task.target_path)

                        artifact = Artifact(
                            path=path,
                            content=result_text,
                            task_id=task.id,
                        )
                    elif result_text:
                        # No target path - emit output for display (conversational task)
                        yield task_output_event(task.id, result_text)
                        artifact = None
                    else:
                        artifact = None
                else:
                    artifact = await self._execute_task(task)

                duration_ms = int((time() - start) * 1000)

                if artifact:
                    artifacts[task.id] = artifact

                    # RFC-DOMAINS: Use domain-specific learning extraction if available
                    if self._detected_domain:
                        learnings = self._detected_domain.extract_learnings(
                            artifact.content,
                            str(artifact.path),
                        )
                    else:
                        learnings = self._learning_extractor.extract_from_code(
                            artifact.content,
                            str(artifact.path),
                        )
                    for learning in learnings:
                        self._learning_store.add_learning(learning)
                        yield memory_learning_event(
                            fact=learning.fact,
                            category=learning.category,
                        )

                self._task_graph.mark_complete(task)
                yield task_complete_event(task.id, duration_ms)

            # Check validation gates
            if options.validate:
                gates_for_completed = [
                    g
                    for g in self._task_graph.gates[current_gate_idx:]
                    if all(dep in self._task_graph.completed_ids for dep in g.depends_on)
                ]

                for gate in gates_for_completed:
                    gate_artifacts = [
                        artifacts[tid]
                        for tid in gate.depends_on
                        if tid in artifacts
                    ]

                    # Inline validate_gate (was _validate_gate wrapper)
                    async for event in validate_gate(gate, gate_artifacts, self.cwd):
                        yield event

                        # Track passed gates for completion metrics
                        if event.type == EventType.GATE_PASS:
                            self._gates_passed += 1

                        if event.type == EventType.GATE_FAIL and options.auto_fix:
                            error_msg = event.data.get("error_message", "Unknown error")
                            failed_step = event.data.get("failed_step", "unknown")
                            async for fix_event in self._attempt_fix(
                                gate, gate_artifacts, error_msg, failed_step
                            ):
                                yield fix_event

                                if fix_event.type == EventType.ESCALATE:
                                    return

                    current_gate_idx = self._task_graph.gates.index(gate) + 1

    async def _execute_with_convergence(
        self,
        options: RunOptions,
    ) -> AsyncIterator[AgentEvent]:
        """Execute with convergence loops enabled (RFC-123).

        Delegates to execution.execute_with_convergence for the actual implementation.
        """
        async for event in execute_with_convergence(
            task_graph=self._task_graph,
            model=self.model,
            cwd=self.cwd,
            naaru=self._naaru,
            options=options,
            execute_with_gates_fn=self._execute_with_gates,
        ):
            yield event

    async def _execute_task(self, task: Task) -> Artifact | None:
        """Execute a single task (non-streaming fallback)."""
        async for _event in self._execute_task_streaming(task):
            pass

        result_text = getattr(self, "_last_task_result", None)

        if result_text and task.target_path:
            path = self.cwd / task.target_path
            path.parent.mkdir(parents=True, exist_ok=True)
            # Sanitize before writing (defense-in-depth)
            sanitized = sanitize_code_content(result_text)
            path.write_text(sanitized)
            # RFC-122: Track files changed for learning extraction
            self._files_changed_this_run.append(task.target_path)

            return Artifact(
                path=path,
                content=sanitized,
                task_id=task.id,
            )

        return None

    async def _execute_task_streaming(self, task: Task) -> AsyncIterator[AgentEvent]:
        """Execute a single task with inference visibility.

        For code generation tasks (task.target_path is set), uses AgentLoop
        with native tool calling when tool_executor is available. This ensures
        code is written via write_file tool calls, avoiding markdown fence issues.

        Falls back to text streaming for conversational tasks or when tools unavailable.
        """
        # Use AgentLoop for code generation if tool executor available
        if task.target_path and self.tool_executor:
            try:
                async for event in self._execute_task_with_tools(task):
                    yield event
                return
            except (RuntimeError, ValueError, ToolDAGError) as e:
                # Recoverable tool errors - fallback to streaming is appropriate
                logger.warning(
                    "Tool execution failed (recoverable), falling back to streaming: %s", e
                )
            except (PermissionError, OSError) as e:
                # Security/system errors should not silently fallback
                logger.error("Tool execution failed (non-recoverable): %s", e)
                raise
            # Let TypeError, AttributeError, etc. propagate to surface programming bugs

        # Use streaming for conversational tasks or as fallback
        async for event in self._execute_task_streaming_fallback(task):
            yield event

    async def _execute_task_with_tools(self, task: Task) -> AsyncIterator[AgentEvent]:
        """Execute task via AgentLoop with native tool calling (preferred path).

        Delegates to execution.execute_task_with_tools for the actual implementation.
        """
        async for event in execute_task_with_tools(
            task=task,
            model=self.model,
            tool_executor=self.tool_executor,
            cwd=self.cwd,
            learning_store=self._learning_store,
            routing_outcome_store=self._routing_outcome_store,
            inference_metrics=self._inference_metrics,
            workspace_context=self._workspace_context,
            lens=self.lens,
            memory=self._memory,
            simulacrum=self._simulacrum,
            briefing=self._briefing,  # For trinket composition
            current_options=self._current_options,
            smart_model=self.smart_model,
            delegation_model=self.delegation_model,
            auto_lens=self.auto_lens,
            recovery_manager=self._recovery_manager,
        ):
            yield event
            # Extract result_text and tracker from event data (event-carried pattern)
            result_text = event.data.get("result_text")
            if result_text is not None:
                self._last_task_result = result_text
                if task.target_path:
                    self._files_changed_this_run.append(task.target_path)
            tracker = event.data.get("tracker")
            if tracker is not None:
                self._invocation_tracker = tracker

    async def _select_lens_for_task(self, task: Task) -> Lens | None:
        """Select the best-fit lens for a specific task (lens rotation)."""
        return await select_lens_for_task(task, self.cwd, self.auto_lens)

    async def _execute_task_streaming_fallback(self, task: Task) -> AsyncIterator[AgentEvent]:
        """Fallback: Execute task via text streaming (original implementation)."""
        async for event in execute_task_streaming_fallback(
            task=task,
            model=self.model,
            cwd=self.cwd,
            learning_store=self._learning_store,
            inference_metrics=self._inference_metrics,
            workspace_context=self._workspace_context,
            token_batch_size=self.token_batch_size,
        ):
            yield event
            # Extract result_text from event data (event-carried pattern)
            result_text = event.data.get("result_text")
            if result_text is not None:
                self._last_task_result = result_text

    async def _attempt_fix(
        self,
        gate: ValidationGate,
        artifacts: list[Artifact],
        error_message: str = "Unknown error",
        failed_step: str = "unknown",
    ) -> AsyncIterator[AgentEvent]:
        """Attempt to fix errors at a gate."""
        from sunwell.agent.validation import ValidationError

        errors: list[ValidationError] = []
        errors.append(
            ValidationError(
                error_type=failed_step,
                message=f"Gate {gate.id} failed at {failed_step}: {error_message}",
            )
        )

        artifacts_dict = {str(a.path): a for a in artifacts}

        async for event in self._fix_stage.fix_errors(errors, artifacts_dict):
            yield event

    # =========================================================================
    # RFC-130: Agent Constellation — Specialist Spawning
    # =========================================================================

    def _should_spawn_specialist(self, task: Task) -> bool:
        """Decide if task should be delegated to a specialist."""
        return should_spawn_specialist(
            task=task,
            lens=self.lens,
            specialist_count=self._specialist_count,
            has_naaru=self._naaru is not None,
        )

    async def _execute_via_specialist(self, task: Task) -> AsyncIterator[AgentEvent]:
        """Execute task by delegating to a spawned specialist.

        Delegates to specialist.execute_via_specialist for the actual implementation.
        """
        context = self._get_context_snapshot()

        async for event in execute_via_specialist(
            task=task,
            naaru=self._naaru,
            lens=self.lens,
            cwd=self.cwd,
            context_snapshot=context,
            specialist_count=self._specialist_count,
            files_changed_tracker=self._files_changed_this_run,
        ):
            yield event
            # Extract specialist_id from event data (event-carried pattern)
            specialist_id = event.data.get("specialist_id")
            if specialist_id is not None and event.type == EventType.SPECIALIST_SPAWNED:
                self._spawned_specialist_ids.append(specialist_id)
                self._specialist_count += 1

    def _determine_specialist_role(self, task: Task) -> str:
        """Determine the appropriate specialist role for a task."""
        return determine_specialist_role(task)

    def _get_context_snapshot(self) -> dict[str, Any]:
        """Get current context snapshot to pass to specialist."""
        return get_context_snapshot(
            goal=self._current_goal,
            learning_store=self._learning_store,
            workspace_context=self._workspace_context,
            lens=self.lens,
            briefing=self._briefing,
        )

    # =========================================================================
    # RFC-130: Memory-Informed Prefetch
    # =========================================================================

    async def _run_memory_informed_prefetch(
        self,
        briefing: Briefing,
        memory: PersistentMemory,
    ) -> PrefetchedContext | None:
        """Run memory-informed prefetch before main execution.

        RFC-130: Uses PersistentMemory to find similar past goals and
        pre-load context that was useful in those executions.

        Args:
            briefing: Current briefing with hints
            memory: PersistentMemory to query for similar goals

        Returns:
            PrefetchedContext if successful, None if timeout or error
        """
        from sunwell.agent.prefetch.dispatcher import (
            analyze_briefing_for_prefetch,
            execute_prefetch,
        )

        try:
            # Analyze briefing with memory integration
            plan = await analyze_briefing_for_prefetch(
                briefing=briefing,
                memory=memory,
            )

            # Execute prefetch with timeout
            return await execute_prefetch(
                plan=plan,
                project_path=self.cwd,
                timeout=2.0,  # Don't block for too long
            )
        except Exception as e:
            # Prefetch failure shouldn't block execution
            logger.debug("Memory-informed prefetch failed: %s", e)
            return None

    # =========================================================================
    # RFC-130: Semantic Checkpointing
    # =========================================================================

    async def _save_phase_checkpoint(
        self,
        phase: CheckpointPhase,
        phase_summary: str,
    ) -> AgentEvent:
        """Save checkpoint at semantic phase boundary.

        Delegates to CheckpointManager for the actual implementation.
        """
        from sunwell.agent.utils.checkpoint_manager import CheckpointManager

        manager = CheckpointManager(self.cwd)
        manager.user_decisions = self._user_decisions

        event = manager.save_phase_checkpoint(
            phase=phase,
            phase_summary=phase_summary,
            goal=self._current_goal,
            task_graph=self._task_graph,
            files_changed=self._files_changed_this_run,
            context=self._get_context_snapshot(),
            spawned_specialist_ids=self._spawned_specialist_ids,
        )

        self._checkpoint_count = manager.checkpoint_count
        self._current_phase = manager.current_phase

        return event

    async def _check_for_resumable_checkpoint(
        self,
        goal: str,
    ) -> AgentCheckpoint | None:
        """Check for existing checkpoint for this goal.

        Delegates to CheckpointManager for the actual implementation.
        """
        from sunwell.agent.utils.checkpoint_manager import CheckpointManager

        manager = CheckpointManager(self.cwd)
        return manager.check_for_resumable_checkpoint(goal)

    def record_user_decision(self, decision: str) -> None:
        """Record a user decision for checkpoint tracking."""
        self._user_decisions.append(decision)

    # =========================================================================
    # RFC-122: Compound Learning Loop
    # =========================================================================

    async def _learn_from_execution(
        self,
        goal: str,
        success: bool,
        memory: PersistentMemory | None = None,
        *,
        force: bool = False,
    ) -> AsyncIterator[AgentEvent]:
        """Extract learnings from completed execution (RFC-122).

        Args:
            goal: The goal that was executed
            success: Whether execution succeeded
            memory: Persistent memory for cross-session learnings
            force: If True, extract learnings even without code changes

        Delegates to learning.learn_from_execution for the actual implementation.
        """
        async for fact, category in learn_from_execution(
            goal=goal,
            success=success,
            task_graph=self._task_graph,
            learning_store=self._learning_store,
            learning_extractor=self._learning_extractor,
            files_changed=self._files_changed_this_run,
            last_planning_context=self._last_planning_context,
            memory=memory,
            force=force,
        ):
            yield memory_learning_event(fact=fact, category=category)

        # Clear run state
        self._files_changed_this_run = []

    async def _reflect_on_session(
        self,
        session: SessionContext,
        success: bool,
        memory: PersistentMemory,
    ) -> None:
        """End-of-session reflection to extract higher-level insights.

        Runs AFTER learning extraction. Analyzes the session to:
        1. Identify what worked vs what didn't
        2. Update briefing hazards based on failures
        3. Extract meta-patterns from tool usage

        Args:
            session: The session context
            success: Whether execution succeeded
            memory: Persistent memory for storing insights
        """
        import logging

        logger = logging.getLogger(__name__)

        # Track hazards for briefing
        hazards: list[str] = []

        # 1. Analyze task completion patterns
        if self._task_graph:
            completed = len(self._task_graph.completed_ids)
            total = len(self._task_graph.tasks)

            if not success and completed < total:
                # Find what failed
                failed_tasks = [
                    t for t in self._task_graph.tasks
                    if t.id not in self._task_graph.completed_ids
                ]
                if failed_tasks:
                    failed = failed_tasks[0]
                    hazards.append(f"Failed at: {failed.description[:60]}")

        # 2. Analyze dead ends from learning store
        if self._learning_store.dead_ends:
            recent_dead_ends = self._learning_store.dead_ends[-3:]
            for de in recent_dead_ends:
                hazards.append(f"Avoid: {de.approach[:50]}")

        # 3. Record tool usage patterns for future reference
        tool_patterns = self._learning_store.get_tool_patterns(min_samples=1)
        if tool_patterns:
            # Record the most successful pattern
            best_pattern = max(tool_patterns, key=lambda p: p.confidence)
            if best_pattern.success_rate > 0.7:
                logger.debug(
                    "Successful tool pattern: %s (%.0f%% success)",
                    " → ".join(best_pattern.tool_sequence[:3]),
                    best_pattern.success_rate * 100,
                )

        # 4. Update session with hazards for briefing
        # These will be incorporated when save_briefing() is called
        if hazards:
            # Add to session's internal state for briefing generation
            if not hasattr(session, "_reflection_hazards"):
                session._reflection_hazards = []
            session._reflection_hazards.extend(hazards[:3])  # Limit to top 3

        logger.debug(
            "Session reflection complete: success=%s, hazards=%d",
            success,
            len(hazards),
        )
