"""Agent — THE Execution Engine for Sunwell (RFC-110).

The Agent is the single point of intelligence. All entry points
(CLI, chat, Studio) call Agent.run() with a RunRequest.

The Agent:
1. Analyzes goals (signals)
2. Selects expertise (lens)
3. Plans execution (task graph)
4. Executes with validation (gates)
5. Auto-fixes errors (Compound Eye)
6. Learns from execution (Simulacrum)

Agent uses Naaru internally for parallel task execution,
but Naaru is an implementation detail — not an entry point.

Example:
    >>> from sunwell.agent import Agent, RunRequest
    >>> agent = Agent(model=model, tool_executor=tools)
    >>> request = RunRequest(goal="Build a REST API with auth")
    >>> async for event in agent.run(request):
    ...     print(event)
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from time import time
from typing import TYPE_CHECKING, Any

from sunwell.agent.budget import AdaptiveBudget
from sunwell.agent.events import (
    AgentEvent,
    EventType,
    GateSummary,
    TaskSummary,
    briefing_loaded_event,
    briefing_saved_event,
    complete_event,
    lens_selected_event,
    lens_suggested_event,
    memory_learning_event,
    model_complete_event,
    model_start_event,
    model_thinking_event,
    model_tokens_event,
    plan_winner_event,
    prefetch_complete_event,
    prefetch_start_event,
    prefetch_timeout_event,
    signal_event,
    task_complete_event,
    task_start_event,
)
from sunwell.agent.fixer import FixStage
from sunwell.agent.gates import GateDetector, ValidationGate
from sunwell.agent.learning import LearningExtractor, LearningStore
from sunwell.agent.metrics import InferenceMetrics
from sunwell.agent.request import RunOptions, RunRequest
from sunwell.agent.signals import AdaptiveSignals, extract_signals
from sunwell.agent.thinking import ThinkingDetector
from sunwell.agent.toolchain import detect_toolchain
from sunwell.agent.validation import Artifact, ValidationRunner, ValidationStage

if TYPE_CHECKING:
    from sunwell.core.lens import Lens
    from sunwell.memory.briefing import Briefing, PrefetchedContext
    from sunwell.models.protocol import ModelProtocol
    from sunwell.naaru.types import Task
    from sunwell.simulacrum.core.store import SimulacrumStore


@dataclass
class TaskGraph:
    """A graph of tasks with execution state."""

    tasks: list[Task] = field(default_factory=list)
    """All tasks in the graph."""

    gates: list[ValidationGate] = field(default_factory=list)
    """Validation gates."""

    completed_ids: set[str] = field(default_factory=set)
    """IDs of completed tasks."""

    completed_artifacts: set[str] = field(default_factory=set)
    """Artifacts that have been produced."""

    def has_pending_tasks(self) -> bool:
        """Check if there are pending tasks."""
        return len(self.completed_ids) < len(self.tasks)

    def get_ready_tasks(self) -> list[Task]:
        """Get tasks that are ready to execute."""
        return [
            t
            for t in self.tasks
            if t.id not in self.completed_ids
            and t.is_ready(self.completed_ids, self.completed_artifacts)
        ]

    def mark_complete(self, task: Task) -> None:
        """Mark a task as complete."""
        self.completed_ids.add(task.id)
        self.completed_artifacts.update(task.produces)

    @property
    def completed_summary(self) -> str:
        """Summary of completed work."""
        return f"{len(self.completed_ids)}/{len(self.tasks)} tasks"


@dataclass
class Agent:
    """THE execution engine for Sunwell.

    This is the single point of intelligence. All entry points
    (CLI, chat, Studio) call Agent.run() with a RunRequest.

    Agent uses Naaru internally for parallel task execution,
    but Naaru is an implementation detail — not an entry point.

    Attributes:
        model: LLM for generation
        tool_executor: Executor for tools (file I/O, commands, etc.)
        cwd: Working directory (default: Path.cwd())
        budget: Token budget configuration
    """

    model: ModelProtocol
    """Model for generation."""

    tool_executor: Any = None
    """Tool executor for file I/O, commands, etc."""

    cwd: Path | None = None
    """Working directory."""

    budget: AdaptiveBudget = field(default_factory=AdaptiveBudget)
    """Token budget with auto-economization."""

    # Optional session/memory
    session: str | None = None
    """Simulacrum session name for persistence."""

    simulacrum: SimulacrumStore | None = None
    """Optional pre-configured Simulacrum store."""

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
    _learning_extractor: LearningExtractor = field(default_factory=LearningExtractor, init=False)
    _validation_runner: ValidationRunner | None = field(default=None, init=False)
    _fix_stage: FixStage | None = field(default=None, init=False)
    _naaru: Any = field(default=None, init=False)
    _inference_metrics: InferenceMetrics = field(default_factory=InferenceMetrics, init=False)
    _task_graph: TaskGraph | None = field(default=None, init=False)

    # Briefing state
    _briefing: Briefing | None = field(default=None, init=False)
    _prefetched_context: PrefetchedContext | None = field(default=None, init=False)
    _session_learnings: list[Any] = field(default_factory=list, init=False)
    _current_blockers: list[str] = field(default_factory=list, init=False)
    _current_goal: str = field(default="", init=False)

    # RFC-122: Compound learning state
    _last_planning_context: Any = field(default=None, init=False)
    """Last planning context from HarmonicPlanner for learning loop."""

    _files_changed_this_run: list[str] = field(default_factory=list, init=False)
    """Files modified during this run (for template extraction)."""

    def __post_init__(self) -> None:
        if self.cwd is None:
            self.cwd = Path.cwd()
        self.cwd = Path(self.cwd)

        # Initialize toolchain for validation
        toolchain = detect_toolchain(self.cwd)
        self._validation_runner = ValidationRunner(toolchain, self.cwd)
        self._fix_stage = FixStage(self.model, self.cwd, max_attempts=3)

        # Load inference metrics from disk for model discovery
        self._inference_metrics.load_from_disk(self.cwd)

        # Initialize Naaru for task execution (if tool_executor provided)
        if self.tool_executor:
            self._init_naaru()

    def _init_naaru(self) -> None:
        """Initialize internal Naaru for task execution."""
        from sunwell.naaru import Naaru
        from sunwell.types.config import NaaruConfig

        self._naaru = Naaru(
            workspace=self.cwd,
            synthesis_model=self.model,
            tool_executor=self.tool_executor,
            config=NaaruConfig(
                enable_parallel_execution=True,
                max_parallel_tasks=4,
            ),
        )

    async def run(self, request: RunRequest) -> AsyncIterator[AgentEvent]:
        """Execute a goal through the unified pipeline.

        This is THE execution method. All roads lead here.

        Pipeline:
        1. SIGNAL    → Analyze goal complexity and domain
        2. LENS      → Select or validate expertise injection
        3. PLAN      → Decompose into task graph
        4. EXECUTE   → Run tasks (Naaru handles parallelism)
        5. VALIDATE  → Check gates at checkpoints
        6. FIX       → Auto-fix failures (Compound Eye)
        7. LEARN     → Persist patterns to Simulacrum

        Args:
            request: RunRequest with goal, context, options

        Yields:
            AgentEvent for each step of execution
        """
        start_time = time()

        # Use request's cwd if provided, else use agent's cwd
        cwd = request.cwd or self.cwd
        self._current_goal = request.goal

        # Load memory and briefing
        async for event in self._load_memory(request):
            yield event

        # Resolve lens if not already set
        if request.lens:
            self.lens = request.lens
        elif self.lens is None and self.auto_lens:
            from sunwell.agent.lens import resolve_lens_for_goal

            resolution = await resolve_lens_for_goal(
                goal=request.goal,
                project_path=cwd,
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

        # Extract signals
        yield signal_event("extracting")
        signals = await self._extract_signals_with_memory(request.goal)
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

        # Plan
        async for event in self._plan_with_signals(request.goal, signals, request.context):
            yield event
            if event.type == EventType.ERROR:
                return

        # Execute with gates (RFC-123: optionally with convergence loops)
        execution_success = True
        if request.options.converge:
            async for event in self._execute_with_convergence(request.options):
                yield event
                if event.type in (EventType.ERROR, EventType.ESCALATE):
                    execution_success = False
                    return
        else:
            async for event in self._execute_with_gates(request.options):
                yield event
                if event.type in (EventType.ERROR, EventType.ESCALATE):
                    execution_success = False
                    return

        # RFC-122: Extract learnings from execution
        async for event in self._learn_from_execution(request.goal, execution_success):
            yield event

        # Save session
        if request.options.persist_learnings:
            async for event in self._save_memory(request.options):
                yield event

        # Complete
        duration = time() - start_time
        tasks_done = len(self._task_graph.completed_ids) if self._task_graph else 0
        gates_done = len(self._task_graph.gates) if self._task_graph else 0
        yield complete_event(
            tasks_completed=tasks_done,
            gates_passed=gates_done,
            duration_s=duration,
            learnings=len(self._learning_store.learnings),
        )

    async def resume_from_recovery(
        self,
        recovery_state: Any,
        user_hint: str | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """Resume execution from a recovery state (RFC-125).

        When a previous run failed with partial progress, this method
        resumes with full context of what succeeded and what failed,
        focusing only on fixing the failed artifacts.

        Args:
            recovery_state: RecoveryState from a previous failed run
            user_hint: Optional hint from user to guide fixes

        Yields:
            AgentEvent for each step of recovery execution
        """
        from sunwell.recovery import build_healing_context

        start_time = time()

        yield AgentEvent(
            EventType.MEMORY_LOAD,
            {
                "source": "recovery",
                "recovery_id": recovery_state.run_id,
                "passed_count": len(recovery_state.passed_artifacts),
                "failed_count": len(recovery_state.failed_artifacts),
            },
        )

        # Build healing context with full information about what failed
        healing_context = build_healing_context(recovery_state, user_hint)

        # Create focused goal for fixing failed artifacts
        failed_paths = [str(a.path) for a in recovery_state.failed_artifacts]
        fix_goal = (
            f"Fix these files that failed validation: {', '.join(failed_paths)}\n\n"
            f"CONTEXT:\n{healing_context}"
        )

        self._current_goal = fix_goal

        # Extract signals for the fix task
        yield signal_event("extracting")
        signals = await self._extract_signals_with_memory(fix_goal)
        yield signal_event("extracted", signals=signals.to_dict())

        # Plan the fix
        async for event in self._plan_with_signals(fix_goal, signals, {
            "is_recovery": True,
            "original_goal": recovery_state.goal,
            "failed_files": failed_paths,
            "passed_files": [str(a.path) for a in recovery_state.passed_artifacts],
        }):
            yield event
            if event.type == EventType.ERROR:
                return

        # Execute with convergence to ensure we reach a stable state
        async for event in self._execute_with_convergence_recovery(
            recovery_state, healing_context
        ):
            yield event
            if event.type in (EventType.ERROR, EventType.ESCALATE):
                # Recovery failed again — state preserved for another attempt
                return

        # Success — extract learnings from recovery
        async for event in self._learn_from_execution(recovery_state.goal, True):
            yield event

        duration = time() - start_time
        yield complete_event(
            tasks_completed=len(recovery_state.failed_artifacts),
            gates_passed=1,
            duration_s=duration,
            learnings=len(self._learning_store.learnings),
        )

    async def _execute_with_convergence_recovery(
        self,
        recovery_state: Any,
        healing_context: str,
    ) -> AsyncIterator[AgentEvent]:
        """Execute recovery with convergence loops.

        Focused execution that only regenerates failed artifacts,
        preserving passed ones.
        """
        from sunwell.agent.gates import GateType
        from sunwell.convergence import ConvergenceConfig, ConvergenceLoop

        # Get files to fix
        failed_files = [a.path for a in recovery_state.failed_artifacts]

        # Run convergence loop focused on failed files
        config = ConvergenceConfig(
            max_iterations=5,
            enabled_gates=frozenset({GateType.LINT, GateType.TYPE, GateType.SYNTAX}),
        )

        loop = ConvergenceLoop(
            model=self.model,
            cwd=self.cwd,
            config=config,
            goal=recovery_state.goal,
            run_id=f"recovery-{recovery_state.run_id}",
        )

        async for event in loop.run(failed_files):
            yield event

    async def plan(self, request: RunRequest) -> AsyncIterator[AgentEvent]:
        """Plan without executing (dry run mode).

        Extracts signals, selects technique, and generates plan,
        but does not execute tasks.

        Args:
            request: RunRequest with goal and context

        Yields:
            Planning events only
        """
        yield signal_event("extracting")
        signals = await self._extract_signals_with_memory(request.goal)
        yield signal_event("extracted", signals=signals.to_dict())

        yield AgentEvent(
            EventType.SIGNAL_ROUTE,
            {
                "planning": signals.planning_route,
                "execution": signals.execution_route,
                "confidence": signals.effective_confidence,
            },
        )

        async for event in self._plan_with_signals(request.goal, signals, request.context):
            yield event

    async def _load_memory(self, request: RunRequest) -> AsyncIterator[AgentEvent]:
        """Load Simulacrum session if specified, plus disk-persisted learnings and briefing."""
        # Load briefing FIRST (instant orientation)
        if request.options.enable_briefing:
            async for event in self._load_briefing():
                yield event

        # Always try to load disk-persisted learnings
        disk_loaded = self._learning_store.load_from_disk(self.cwd)
        if disk_loaded > 0:
            yield AgentEvent(
                EventType.MEMORY_LEARNING,
                {"loaded": disk_loaded, "source": "disk"},
            )

        # Use pre-configured simulacrum if provided
        if self.simulacrum:
            yield AgentEvent(
                EventType.MEMORY_LOADED,
                {"session": "pre-configured", "turns": 0},
            )
            loaded = self._learning_store.load_from_simulacrum(self.simulacrum)
            if loaded > 0:
                yield AgentEvent(
                    EventType.MEMORY_LEARNING,
                    {"loaded": loaded, "source": "simulacrum"},
                )
            return

        # Load session if specified
        session = request.session or self.session
        if not session:
            return

        yield AgentEvent(EventType.MEMORY_LOAD, {"session": session})

        try:
            from sunwell.simulacrum.core.store import SimulacrumStore

            memory_path = self.cwd / ".sunwell" / "memory"
            store = SimulacrumStore(memory_path)

            try:
                store.load_session(session)
                self.simulacrum = store
                yield AgentEvent(
                    EventType.MEMORY_LOADED,
                    {
                        "session": session,
                        "turns": len(store.get_dag().turns),
                    },
                )
                loaded = self._learning_store.load_from_simulacrum(store)
                if loaded > 0:
                    yield AgentEvent(
                        EventType.MEMORY_LEARNING,
                        {"loaded": loaded, "source": "session"},
                    )
            except FileNotFoundError:
                store.new_session(session)
                self.simulacrum = store
                yield AgentEvent(EventType.MEMORY_NEW, {"session": session})

        except ImportError:
            yield AgentEvent(
                EventType.MEMORY_NEW,
                {"session": session, "note": "Simulacrum not available"},
            )

    async def _load_briefing(self) -> AsyncIterator[AgentEvent]:
        """Load briefing and optionally run prefetch."""
        from sunwell.memory.briefing import Briefing

        briefing = Briefing.load(self.cwd)
        if not briefing:
            return

        self._briefing = briefing

        yield briefing_loaded_event(
            mission=briefing.mission,
            status=briefing.status.value,
            has_hazards=len(briefing.hazards) > 0,
            has_dispatch_hints=bool(briefing.predicted_skills or briefing.suggested_lens),
        )

        # Run prefetch if enabled
        if self._briefing:
            async for event in self._run_prefetch():
                yield event

    async def _run_prefetch(self) -> AsyncIterator[AgentEvent]:
        """Run briefing-driven prefetch with timeout."""
        if not self._briefing:
            return

        yield prefetch_start_event(self._briefing.mission)

        try:
            from sunwell.prefetch.dispatcher import (
                analyze_briefing_for_prefetch,
                execute_prefetch,
            )

            prefetch_plan = await analyze_briefing_for_prefetch(self._briefing)
            self._prefetched_context = await execute_prefetch(
                prefetch_plan,
                self.cwd,
                timeout=2.0,
            )

            if self._prefetched_context:
                current_lens_name = getattr(self.lens, "name", None)
                if prefetch_plan.suggested_lens and (
                    not self.lens or prefetch_plan.suggested_lens != current_lens_name
                ):
                    yield lens_suggested_event(
                        suggested=prefetch_plan.suggested_lens,
                        reason="briefing_routing",
                    )

                yield prefetch_complete_event(
                    files_loaded=len(self._prefetched_context.files),
                    learnings_loaded=len(self._prefetched_context.learnings),
                    skills_activated=list(self._prefetched_context.active_skills),
                )
            else:
                yield prefetch_timeout_event()

        except Exception as e:
            yield prefetch_timeout_event(error=str(e))

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
        yield AgentEvent(
            EventType.PLAN_START,
            {"technique": signals.planning_route},
        )

        # Build context with learnings and lens expertise
        planning_context = dict(context) if context else {}
        learnings_context = self._learning_store.format_for_prompt()
        if learnings_context:
            planning_context["learnings"] = learnings_context

        if self.lens:
            planning_context["lens_context"] = self.lens.to_context()

        if self._briefing:
            planning_context["briefing"] = self._briefing.to_prompt()

        if self._prefetched_context and self._prefetched_context.files:
            planning_context["prefetched_files"] = self._prefetched_context.files

        if signals.planning_route == "HARMONIC":
            async for event in self._harmonic_plan(goal, planning_context):
                yield event
        else:
            async for event in self._single_shot_plan(goal, planning_context):
                yield event

    async def _harmonic_plan(
        self,
        goal: str,
        context: dict[str, Any],
    ) -> AsyncIterator[AgentEvent]:
        """Plan using Harmonic planning (multiple candidates)."""
        import asyncio

        try:
            from sunwell.naaru.planners.harmonic import HarmonicPlanner

            # RFC-123: Stream events live using async queue (fixes regression)
            event_queue: asyncio.Queue[AgentEvent | None] = asyncio.Queue()
            selected_candidate_id = "candidate-0"

            def queue_event(event: AgentEvent) -> None:
                # Track the winner ID as events come in
                nonlocal selected_candidate_id
                if event.type == EventType.PLAN_WINNER:
                    selected_candidate_id = event.data.get("selected_candidate_id", "candidate-0")
                event_queue.put_nowait(event)

            candidates = 5 if not self.budget.is_low else 3
            planner = HarmonicPlanner(
                model=self.model,
                candidates=candidates,
                event_callback=queue_event,
                # RFC-122: Connect to SimulacrumStore for knowledge retrieval
                simulacrum=self.simulacrum,
            )

            # Run planning in background task so we can stream events
            async def run_planning() -> list[Task]:
                try:
                    result = await planner.plan([goal], context)
                    return result
                finally:
                    # Signal completion
                    event_queue.put_nowait(None)

            planning_task = asyncio.create_task(run_planning())

            # Stream events as they arrive (live progress)
            while True:
                event = await event_queue.get()
                if event is None:
                    break
                # Skip plan_winner from planner - we emit our own with full details
                if event.type != EventType.PLAN_WINNER:
                    yield event

            # Await completion and get tasks
            tasks = await planning_task

            # RFC-122: Store planning context for learning loop
            self._last_planning_context = planner.last_planning_context

            detector = GateDetector()
            gates = detector.detect_gates(tasks)

            self._task_graph = TaskGraph(tasks=tasks, gates=gates)

            task_list: list[TaskSummary] = [
                {
                    "id": t.id,
                    "description": t.description,
                    "depends_on": list(t.depends_on),
                    "produces": list(t.produces) if t.produces else (
                        [t.target_path] if t.target_path else []
                    ),
                    "category": getattr(t, "category", None),
                }
                for t in tasks
            ]
            gate_list: list[GateSummary] = [
                {
                    "id": g.id,
                    "type": g.gate_type.value,
                    "after_tasks": list(g.depends_on),
                }
                for g in gates
            ]

            yield plan_winner_event(
                tasks=len(tasks),
                gates=len(gates),
                technique="harmonic",
                selected_candidate_id=selected_candidate_id,
                task_list=task_list,
                gate_list=gate_list,
            )

        except ImportError:
            async for event in self._single_shot_plan(goal, context):
                yield event

    async def _single_shot_plan(
        self,
        goal: str,
        context: dict[str, Any],
    ) -> AsyncIterator[AgentEvent]:
        """Simple single-shot planning."""
        try:
            from sunwell.naaru.planners.artifact import ArtifactPlanner

            planner = ArtifactPlanner(model=self.model)
            graph = await planner.discover_graph(goal, context)

            from sunwell.naaru.artifacts import artifacts_to_tasks

            tasks = artifacts_to_tasks(graph)

            detector = GateDetector()
            gates = detector.detect_gates(tasks)

            self._task_graph = TaskGraph(tasks=tasks, gates=gates)

            task_list: list[TaskSummary] = [
                {
                    "id": t.id,
                    "description": t.description,
                    "depends_on": list(t.depends_on),
                    "produces": list(t.produces) if t.produces else (
                        [t.target_path] if t.target_path else []
                    ),
                    "category": getattr(t, "category", None),
                }
                for t in tasks
            ]
            gate_list: list[GateSummary] = [
                {
                    "id": g.id,
                    "type": g.gate_type.value,
                    "after_tasks": list(g.depends_on),
                }
                for g in gates
            ]

            yield plan_winner_event(
                tasks=len(tasks),
                gates=len(gates),
                technique="single_shot",
                task_list=task_list,
                gate_list=gate_list,
            )

        except ImportError:
            from sunwell.naaru.types import Task, TaskMode

            task = Task(
                id="main",
                description=goal,
                mode=TaskMode.GENERATE,
            )
            self._task_graph = TaskGraph(tasks=[task], gates=[])

            yield plan_winner_event(
                tasks=1,
                gates=0,
                technique="minimal",
                task_list=[{
                    "id": "main",
                    "description": goal,
                    "depends_on": [],
                    "produces": [],
                    "category": None,
                }],
                gate_list=[],
            )

    async def _execute_with_gates(self, options: RunOptions) -> AsyncIterator[AgentEvent]:
        """Execute tasks with validation gates and inference visibility."""
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
                yield task_start_event(task.id, task.description)

                start = time()

                if self.stream_inference:
                    async for event in self._execute_task_streaming(task):
                        yield event

                    result_text = getattr(self, "_last_task_result", None)
                    if result_text and task.target_path:
                        path = self.cwd / task.target_path
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(result_text)
                        # RFC-122: Track files changed for learning extraction
                        self._files_changed_this_run.append(task.target_path)

                        artifact = Artifact(
                            path=path,
                            content=result_text,
                            task_id=task.id,
                        )
                    else:
                        artifact = None
                else:
                    artifact = await self._execute_task(task)

                duration_ms = int((time() - start) * 1000)

                if artifact:
                    artifacts[task.id] = artifact

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

                    async for event in self._validate_gate(gate, gate_artifacts):
                        yield event

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

        After each task completes, runs validation gates and fixes errors
        until code stabilizes or limits are reached.

        Args:
            options: Execution options including convergence config
        """
        from sunwell.convergence import ConvergenceConfig, ConvergenceLoop

        config = options.convergence_config or ConvergenceConfig()

        # Create convergence loop
        loop = ConvergenceLoop(
            model=self.model,
            cwd=self.cwd,
            config=config,
        )

        # Track files written during execution
        written_files: list[Path] = []
        artifacts: dict[str, Artifact] = {}

        async def on_write(path: Path) -> None:
            """Hook called after each file write."""
            written_files.append(path)
            # Build artifact for convergence
            if path.exists():
                artifacts[str(path)] = Artifact(
                    path=path,
                    content=path.read_text(),
                    task_id="convergence",
                )

        # Set up hook on tool executor
        if self._naaru and self._naaru.tool_executor:
            self._naaru.tool_executor.on_file_write = on_write

        try:
            # Execute tasks normally with gates
            async for event in self._execute_with_gates(options):
                yield event

                # After each task completes, run convergence if files changed
                if event.type == EventType.TASK_COMPLETE and written_files:
                    async for conv_event in loop.run(list(written_files), artifacts):
                        yield conv_event

                    if loop.result and not loop.result.stable:
                        # Escalate if convergence failed
                        yield AgentEvent(
                            EventType.ESCALATE,
                            {"reason": f"Convergence failed: {loop.result.status.value}"},
                        )
                        return

                    written_files.clear()

                if event.type in (EventType.ERROR, EventType.ESCALATE):
                    return
        finally:
            # Clean up hook
            if self._naaru and self._naaru.tool_executor:
                self._naaru.tool_executor.on_file_write = None

    async def _execute_task(self, task: Task) -> Artifact | None:
        """Execute a single task (non-streaming fallback)."""
        async for _event in self._execute_task_streaming(task):
            pass

        result_text = getattr(self, "_last_task_result", None)

        if result_text and task.target_path:
            path = self.cwd / task.target_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(result_text)
            # RFC-122: Track files changed for learning extraction
            self._files_changed_this_run.append(task.target_path)

            return Artifact(
                path=path,
                content=result_text,
                task_id=task.id,
            )

        return None

    async def _execute_task_streaming(self, task: Task) -> AsyncIterator[AgentEvent]:
        """Execute a single task with inference visibility."""
        from sunwell.models.protocol import GenerateOptions

        learnings_context = self._learning_store.format_for_prompt(5)

        prompt = f"""Generate code for this task:

TASK: {task.description}

{f"KNOWN FACTS:{chr(10)}{learnings_context}" if learnings_context else ""}

Output ONLY the code (no explanation, no markdown fences):"""

        prompt_tokens = len(prompt) // 4
        model_id = getattr(self.model, "model_id", "unknown")
        estimated_time = self._inference_metrics.estimate_time(
            model_id, prompt_tokens, expected_output=500
        )

        yield model_start_event(
            task_id=task.id,
            model=model_id,
            prompt_tokens=prompt_tokens,
            estimated_time_s=estimated_time,
        )

        start_time = time()
        first_token_time: float | None = None
        token_buffer: list[str] = []
        token_count = 0
        thinking_detector = ThinkingDetector()

        try:
            async for chunk in self.model.generate_stream(
                prompt,
                options=GenerateOptions(temperature=0.3, max_tokens=4000),
            ):
                if first_token_time is None:
                    first_token_time = time()

                token_buffer.append(chunk)
                token_count += 1

                thinking_blocks = thinking_detector.feed(chunk)
                for block in thinking_blocks:
                    yield model_thinking_event(
                        task_id=task.id,
                        phase=block.phase,
                        content=block.content,
                        is_complete=block.is_complete,
                    )

                elapsed = time() - start_time
                if token_count % self.token_batch_size == 0:
                    tps = token_count / elapsed if elapsed > 0 else None
                    yield model_tokens_event(
                        task_id=task.id,
                        tokens="".join(token_buffer[-self.token_batch_size:]),
                        token_count=token_count,
                        tokens_per_second=tps,
                    )

        except AttributeError:
            result = await self.model.generate(
                prompt,
                options=GenerateOptions(temperature=0.3, max_tokens=4000),
            )
            if result.text:
                token_buffer = [result.text]
                token_count = len(result.text) // 4
                first_token_time = time()

        duration = time() - start_time
        tps = token_count / duration if duration > 0 else 0
        ttft_ms = int((first_token_time - start_time) * 1000) if first_token_time else None

        self._inference_metrics.record(
            model=model_id,
            duration_s=duration,
            tokens=token_count,
            ttft_ms=ttft_ms,
        )

        yield model_complete_event(
            task_id=task.id,
            total_tokens=token_count,
            duration_s=duration,
            tokens_per_second=tps,
            time_to_first_token_ms=ttft_ms,
        )

        self._last_task_result = "".join(token_buffer)

    async def _validate_gate(
        self,
        gate: ValidationGate,
        artifacts: list[Artifact],
    ) -> AsyncIterator[AgentEvent]:
        """Validate at a gate."""
        validation_stage = ValidationStage(self.cwd)
        gate_artifacts = {gate.id: artifacts}

        async for event in validation_stage.validate_all([gate], gate_artifacts):
            yield event

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

    async def _save_memory(self, options: RunOptions) -> AsyncIterator[AgentEvent]:
        """Save learnings to disk, optionally to Simulacrum, and update briefing."""
        disk_saved = self._learning_store.save_to_disk(self.cwd)

        sim_synced = 0
        if self.simulacrum:
            sim_synced = self._learning_store.sync_to_simulacrum(self.simulacrum)
            self.simulacrum.save_session()

        metrics_saved = self._inference_metrics.save_to_disk(self.cwd)

        if disk_saved > 0 or sim_synced > 0:
            yield AgentEvent(
                EventType.MEMORY_SAVED,
                {
                    "learnings": len(self._learning_store.learnings),
                    "disk_saved": disk_saved,
                    "sim_synced": sim_synced,
                    "metrics_models": metrics_saved,
                },
            )

        if options.enable_briefing:
            async for event in self._save_briefing():
                yield event

    async def _save_briefing(self) -> AsyncIterator[AgentEvent]:
        """Generate and save new briefing based on session work."""
        from sunwell.memory.briefing import (
            Briefing,
            BriefingStatus,
            ExecutionSummary,
            briefing_to_learning,
            compress_briefing,
        )
        from sunwell.routing.briefing_router import (
            predict_skills_from_briefing,
            suggest_lens_from_briefing,
        )

        if self._task_graph:
            summary = ExecutionSummary.from_task_graph(
                self._task_graph,
                self._session_learnings,
            )
        else:
            summary = ExecutionSummary(
                last_action="Session completed.",
                next_action=None,
                modified_files=(),
                tasks_completed=0,
                gates_passed=0,
                new_learnings=(),
            )

        new_status = self._determine_briefing_status()

        if self._briefing:
            old_briefing = self._briefing
        elif self._current_goal:
            old_briefing = Briefing.create_initial(
                mission=self._current_goal,
                goal_hash=None,
            )
        else:
            return

        predicted_skills = predict_skills_from_briefing(old_briefing)
        suggested_lens = suggest_lens_from_briefing(old_briefing)

        new_briefing = compress_briefing(
            old_briefing=old_briefing,
            summary=summary,
            new_status=new_status,
            blockers=self._current_blockers,
            predicted_skills=predicted_skills,
            suggested_lens=suggested_lens,
        )
        new_briefing.save(self.cwd)

        yield briefing_saved_event(
            status=new_briefing.status.value,
            next_action=new_briefing.next_action,
            tasks_completed=summary.tasks_completed,
        )

        if new_status == BriefingStatus.COMPLETE:
            completion_learning = briefing_to_learning(new_briefing)
            if completion_learning:
                self._learning_store.add_learning(completion_learning)
                yield memory_learning_event(
                    fact=completion_learning.fact,
                    category="task_completion",
                )

    # =========================================================================
    # RFC-122: Compound Learning Loop
    # =========================================================================

    async def _learn_from_execution(
        self,
        goal: str,
        success: bool,
    ) -> AsyncIterator[AgentEvent]:
        """Extract learnings from completed execution (RFC-122).

        Called after all tasks complete to:
        1. Record usage of learnings that were retrieved for planning
        2. Extract template patterns from successful novel tasks
        3. Extract ordering heuristics from successful executions

        Args:
            goal: The completed goal
            success: Whether execution succeeded

        Yields:
            Learning events for new templates/heuristics
        """
        # Get tasks from task graph
        if not self._task_graph:
            return

        tasks = self._task_graph.tasks

        # Get planning context that was used
        planning_context = self._last_planning_context

        # Record usage of learnings that were retrieved
        if planning_context and success:
            for learning in planning_context.all_learnings:
                self._learning_store.record_usage(learning.id, success=True)

        # Only extract new learnings on success
        if not success:
            return

        # Collect files changed and artifacts created
        files_changed = self._files_changed_this_run
        artifacts_created = [
            artifact
            for task in tasks
            for artifact in (task.produces or [])
        ]

        # Try to extract template from successful novel task
        # Novel = no high-confidence template was used
        template_was_used = (
            planning_context
            and planning_context.best_template
            and planning_context.best_template.confidence >= 0.8
        )

        if not template_was_used and len(artifacts_created) >= 2:
            try:
                template_learning = await self._learning_extractor.extract_template(
                    goal=goal,
                    files_changed=files_changed,
                    artifacts_created=artifacts_created,
                    tasks=tasks,
                )
                if template_learning and self.simulacrum:
                    self.simulacrum.get_dag().add_learning(template_learning)
                    yield memory_learning_event(
                        fact=template_learning.fact,
                        category="template",
                    )
            except Exception:
                pass  # Don't fail run on learning extraction errors

        # Try to extract ordering heuristics
        if len(tasks) >= 3:
            try:
                heuristic_learning = self._learning_extractor.extract_heuristic(
                    goal=goal,
                    tasks=tasks,
                )
                if heuristic_learning and self.simulacrum:
                    self.simulacrum.get_dag().add_learning(heuristic_learning)
                    yield memory_learning_event(
                        fact=heuristic_learning.fact,
                        category="heuristic",
                    )
            except Exception:
                pass  # Don't fail run on learning extraction errors

        # Clear run state
        self._files_changed_this_run = []

    def _determine_briefing_status(self) -> Any:
        """Determine briefing status from task graph state."""
        from sunwell.memory.briefing import BriefingStatus

        if not self._task_graph:
            return BriefingStatus.IN_PROGRESS

        if self._current_blockers:
            return BriefingStatus.BLOCKED

        if not self._task_graph.has_pending_tasks():
            return BriefingStatus.COMPLETE

        return BriefingStatus.IN_PROGRESS
