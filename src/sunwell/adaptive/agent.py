"""AdaptiveAgent — Signal-Driven Execution (RFC-042).

The main agent class that orchestrates:
1. Signal extraction → Automatic technique selection
2. Adaptive planning → Harmonic vs single-shot
3. Validation gates → Fail-fast with targeted fixes
4. Iterative DAG expansion → Learn and expand
5. Simulacrum integration → Cross-session memory

Example:
    >>> agent = AdaptiveAgent(model=my_model)
    >>> async for event in agent.run("Build a Flask forum app"):
    ...     print(event)
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from time import time
from typing import TYPE_CHECKING, Any

from sunwell.adaptive.budget import AdaptiveBudget
from sunwell.adaptive.events import (
    AgentEvent,
    EventType,
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
    prefetch_complete_event,
    prefetch_start_event,
    prefetch_timeout_event,
    signal_event,
    task_complete_event,
    task_start_event,
)
from sunwell.adaptive.metrics import InferenceMetrics, load_profiles_from_disk, save_profiles_to_disk
from sunwell.adaptive.thinking import ThinkingDetector
from sunwell.adaptive.fixer import FixStage
from sunwell.adaptive.gates import GateDetector, ValidationGate
from sunwell.adaptive.learning import LearningExtractor, LearningStore
from sunwell.adaptive.signals import AdaptiveSignals, extract_signals
from sunwell.adaptive.toolchain import detect_toolchain
from sunwell.adaptive.validation import Artifact, ValidationRunner, ValidationStage

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
class AdaptiveAgent:
    """Unified adaptive agent with signal-driven execution.

    This is the ONE agent for Sunwell. It automatically selects techniques
    based on complexity, confidence, and budget. All advanced features
    (Vortex, Compound Eye, Harmonic, Resonance) are applied automatically
    when beneficial.

    Attributes:
        model: LLM for generation
        tool_executor: Executor for tools (file I/O, commands, etc.)
        cwd: Working directory
        budget: Token budget configuration
        max_fix_attempts: Maximum fix attempts per error
        session: Optional Simulacrum session name
        simulacrum: Optional pre-configured Simulacrum store
    """

    model: ModelProtocol
    """Model for generation."""

    tool_executor: Any = None
    """Tool executor for file I/O, commands, etc."""

    cwd: Path | None = None
    """Working directory."""

    budget: AdaptiveBudget = field(default_factory=AdaptiveBudget)
    """Token budget with auto-economization."""

    max_fix_attempts: int = 3
    """Maximum fix attempts per error."""

    session: str | None = None
    """Simulacrum session name for persistence."""

    simulacrum: SimulacrumStore | None = None
    """Optional pre-configured Simulacrum store."""

    # RFC-064: Lens configuration
    lens: "Lens | None" = None
    """Active lens for expertise injection."""

    auto_lens: bool = True
    """Whether to auto-select lens if none provided."""

    # RFC-071: Briefing configuration
    enable_briefing: bool = True
    """Whether to load/save briefings for session continuity."""

    enable_prefetch: bool = True
    """Whether to pre-load context based on briefing signals."""

    prefetch_timeout: float = 2.0
    """Maximum time to wait for prefetch (seconds)."""

    # RFC-081: Inference visibility configuration
    stream_inference: bool = True
    """Whether to use streaming for inference visibility."""

    token_batch_size: int = 10
    """Batch size for token events (reduce event spam)."""

    # Internal state
    _learning_store: LearningStore = field(default_factory=LearningStore, init=False)
    _learning_extractor: LearningExtractor = field(
        default_factory=LearningExtractor, init=False
    )
    _validation_runner: ValidationRunner | None = field(default=None, init=False)
    _fix_stage: FixStage | None = field(default=None, init=False)
    _naaru: Any = field(default=None, init=False)  # Internal Naaru for task execution
    _inference_metrics: InferenceMetrics = field(default_factory=InferenceMetrics, init=False)

    # RFC-071: Briefing state
    _briefing: "Briefing | None" = field(default=None, init=False)
    _prefetched_context: "PrefetchedContext | None" = field(default=None, init=False)
    _session_learnings: list[Any] = field(default_factory=list, init=False)
    _current_blockers: list[str] = field(default_factory=list, init=False)
    _current_goal: str = field(default="", init=False)

    def __post_init__(self):
        if self.cwd is None:
            self.cwd = Path.cwd()
        self.cwd = Path(self.cwd)

        # Initialize toolchain for validation
        toolchain = detect_toolchain(self.cwd)
        self._validation_runner = ValidationRunner(toolchain, self.cwd)
        self._fix_stage = FixStage(self.model, self.cwd, self.max_fix_attempts)

        # RFC-081: Load inference metrics from disk for model discovery
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

    async def plan(
        self,
        goal: str,
        context: dict[str, Any] | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """Plan without executing (dry run mode).

        Extracts signals, selects technique, and generates plan,
        but does not execute tasks.

        Args:
            goal: The user's goal/request
            context: Optional context

        Yields:
            Planning events only
        """
        # Extract signals
        yield signal_event("extracting")
        signals = await self._extract_signals_with_memory(goal)
        yield signal_event("extracted", signals=signals.to_dict())

        # Show routing decision
        yield AgentEvent(
            EventType.SIGNAL_ROUTE,
            {
                "planning": signals.planning_route,
                "execution": signals.execution_route,
                "confidence": signals.effective_confidence,
            },
        )

        # Plan (but don't execute)
        async for event in self._plan_with_signals(goal, signals, context):
            yield event

    async def run(
        self,
        goal: str,
        context: dict[str, Any] | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """Execute a goal with adaptive technique selection.

        This is the main entry point. It:
        1. Loads Simulacrum session (if specified)
        2. Extracts signals from the goal
        3. Plans with signal-appropriate technique
        4. Executes with validation gates
        5. Auto-fixes errors
        6. Saves learnings

        Args:
            goal: The user's goal/request
            context: Optional context (cwd, files, etc.)

        Yields:
            AgentEvent for each step of execution
        """
        start_time = time()

        # RFC-071: Store current goal for briefing
        self._current_goal = goal

        # Load Simulacrum session and briefing
        async for event in self._load_memory():
            yield event

        # RFC-064: Resolve lens if not already set
        if self.lens is None and self.auto_lens:
            from sunwell.adaptive.lens_resolver import resolve_lens_for_goal

            resolution = await resolve_lens_for_goal(
                goal=goal,
                project_path=self.cwd,
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
        signals = await self._extract_signals_with_memory(goal)
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
        async for event in self._plan_with_signals(goal, signals, context):
            yield event
            if event.type == EventType.ERROR:
                return

        # Execute with gates
        async for event in self._execute_with_gates():
            yield event
            if event.type in (EventType.ERROR, EventType.ESCALATE):
                return

        # Save session
        async for event in self._save_memory():
            yield event

        # Complete
        duration = time() - start_time
        tasks_done = len(self._task_graph.completed_ids) if hasattr(self, "_task_graph") else 0
        gates_done = len(self._task_graph.gates) if hasattr(self, "_task_graph") else 0
        yield complete_event(
            tasks_completed=tasks_done,
            gates_passed=gates_done,
            duration_s=duration,
            learnings=len(self._learning_store.learnings),
        )

    async def _load_memory(self) -> AsyncIterator[AgentEvent]:
        """Load Simulacrum session if specified, plus disk-persisted learnings and briefing."""
        # RFC-071: Load briefing FIRST (instant orientation)
        if self.enable_briefing:
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
            # Load learnings from simulacrum into local store
            loaded = self._learning_store.load_from_simulacrum(self.simulacrum)
            if loaded > 0:
                yield AgentEvent(
                    EventType.MEMORY_LEARNING,
                    {"loaded": loaded, "source": "simulacrum"},
                )
            return

        if not self.session:
            return

        yield AgentEvent(EventType.MEMORY_LOAD, {"session": self.session})

        try:
            from sunwell.simulacrum.core.store import SimulacrumStore

            memory_path = self.cwd / ".sunwell" / "memory"
            store = SimulacrumStore(memory_path)

            try:
                store.load_session(self.session)
                self.simulacrum = store
                yield AgentEvent(
                    EventType.MEMORY_LOADED,
                    {
                        "session": self.session,
                        "turns": len(store.get_dag().turns),
                    },
                )
                # Load learnings
                loaded = self._learning_store.load_from_simulacrum(store)
                if loaded > 0:
                    yield AgentEvent(
                        EventType.MEMORY_LEARNING,
                        {"loaded": loaded, "source": "session"},
                    )
            except FileNotFoundError:
                store.new_session(self.session)
                self.simulacrum = store
                yield AgentEvent(EventType.MEMORY_NEW, {"session": self.session})

        except ImportError:
            # Simulacrum not available
            yield AgentEvent(
                EventType.MEMORY_NEW,
                {"session": self.session, "note": "Simulacrum not available"},
            )

    async def _load_briefing(self) -> AsyncIterator[AgentEvent]:
        """Load briefing and optionally run prefetch (RFC-071)."""
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

        # RFC-071: Run prefetch if enabled
        if self.enable_prefetch and self._briefing:
            async for event in self._run_prefetch():
                yield event

    async def _run_prefetch(self) -> AsyncIterator[AgentEvent]:
        """Run briefing-driven prefetch with timeout (RFC-071)."""
        if not self._briefing:
            return

        yield prefetch_start_event(self._briefing.mission)

        try:
            from sunwell.prefetch.dispatcher import (
                analyze_briefing_for_prefetch,
                execute_prefetch,
            )

            # Analyze briefing for prefetch plan
            prefetch_plan = await analyze_briefing_for_prefetch(self._briefing)

            # Execute prefetch with timeout
            self._prefetched_context = await execute_prefetch(
                prefetch_plan,
                self.cwd,
                timeout=self.prefetch_timeout,
            )

            if self._prefetched_context:
                # Suggest lens if different from current
                if prefetch_plan.suggested_lens and (
                    not self.lens or prefetch_plan.suggested_lens != getattr(self.lens, "name", None)
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
                # Prefetch timed out
                yield prefetch_timeout_event()

        except Exception as e:
            # Prefetch failed, continue without warm context
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
        context: dict[str, Any] | None,
    ) -> AsyncIterator[AgentEvent]:
        """Plan using signal-appropriate technique."""
        yield AgentEvent(
            EventType.PLAN_START,
            {"technique": signals.planning_route},
        )

        # Build context with learnings and lens expertise
        planning_context = context or {}
        learnings_context = self._learning_store.format_for_prompt()
        if learnings_context:
            planning_context["learnings"] = learnings_context

        # RFC-064: Add lens context if available
        if self.lens:
            planning_context["lens_context"] = self.lens.to_context()

        # RFC-071: Add briefing context for orientation
        if self._briefing:
            planning_context["briefing"] = self._briefing.to_prompt()

        # RFC-071: Add prefetched files if available
        if self._prefetched_context and self._prefetched_context.files:
            planning_context["prefetched_files"] = self._prefetched_context.files

        if signals.planning_route == "HARMONIC":
            # Use Harmonic planning with multiple candidates
            async for event in self._harmonic_plan(goal, planning_context):
                yield event
        else:
            # Single-shot planning
            async for event in self._single_shot_plan(goal, planning_context):
                yield event

    async def _harmonic_plan(
        self,
        goal: str,
        context: dict[str, Any],
    ) -> AsyncIterator[AgentEvent]:
        """Plan using Harmonic planning (multiple candidates)."""
        try:
            from sunwell.naaru.planners.harmonic import HarmonicPlanner

            # Determine candidates based on budget
            candidates = 5 if not self.budget.is_low else 3

            planner = HarmonicPlanner(
                model=self.model,
                candidates=candidates,
            )

            # Plan
            tasks = await planner.plan([goal], context)

            # Detect gates
            detector = GateDetector()
            gates = detector.detect_gates(tasks)

            self._task_graph = TaskGraph(tasks=tasks, gates=gates)

            yield AgentEvent(
                EventType.PLAN_WINNER,
                {
                    "tasks": len(tasks),
                    "gates": len(gates),
                    "technique": "harmonic",
                },
            )

        except ImportError:
            # Fall back to simple planning
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

            # Convert to tasks
            from sunwell.naaru.artifacts import artifacts_to_tasks

            tasks = artifacts_to_tasks(graph)

            # Detect gates
            detector = GateDetector()
            gates = detector.detect_gates(tasks)

            self._task_graph = TaskGraph(tasks=tasks, gates=gates)

            yield AgentEvent(
                EventType.PLAN_WINNER,
                {
                    "tasks": len(tasks),
                    "gates": len(gates),
                    "technique": "single_shot",
                },
            )

        except ImportError:
            # Minimal fallback
            from sunwell.naaru.types import Task, TaskMode

            task = Task(
                id="main",
                description=goal,
                mode=TaskMode.GENERATE,
            )
            self._task_graph = TaskGraph(tasks=[task], gates=[])

            yield AgentEvent(
                EventType.PLAN_WINNER,
                {"tasks": 1, "gates": 0, "technique": "minimal"},
            )

    async def _execute_with_gates(self) -> AsyncIterator[AgentEvent]:
        """Execute tasks with validation gates and inference visibility (RFC-081)."""
        artifacts: dict[str, Artifact] = {}
        current_gate_idx = 0

        while self._task_graph.has_pending_tasks():
            # Get ready tasks
            ready = self._task_graph.get_ready_tasks()
            if not ready:
                yield AgentEvent(
                    EventType.ERROR,
                    {"message": "No tasks ready to execute (deadlock?)"},
                )
                return

            # Execute ready tasks
            for task in ready:
                yield task_start_event(task.id, task.description)

                start = time()

                # Stream inference events for visibility (RFC-081)
                if self.stream_inference:
                    async for event in self._execute_task_streaming(task):
                        yield event

                    # Get result from streaming
                    result_text = getattr(self, "_last_task_result", None)
                    if result_text and task.target_path:
                        path = self.cwd / task.target_path
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(result_text)

                        artifact = Artifact(
                            path=path,
                            content=result_text,
                            task_id=task.id,
                        )
                    else:
                        artifact = None
                else:
                    # Non-streaming fallback
                    artifact = await self._execute_task(task)

                duration_ms = int((time() - start) * 1000)

                if artifact:
                    artifacts[task.id] = artifact

                    # Extract learnings
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

            # Check if we've hit a gate
            gates_for_completed = [
                g
                for g in self._task_graph.gates[current_gate_idx:]
                if all(dep in self._task_graph.completed_ids for dep in g.depends_on)
            ]

            for gate in gates_for_completed:
                # Run gate validation
                gate_artifacts = [
                    artifacts[tid]
                    for tid in gate.depends_on
                    if tid in artifacts
                ]

                async for event in self._validate_gate(gate, gate_artifacts):
                    yield event

                    if event.type == EventType.GATE_FAIL:
                        # Attempt fix
                        async for fix_event in self._attempt_fix(
                            gate, gate_artifacts
                        ):
                            yield fix_event

                            if fix_event.type == EventType.ESCALATE:
                                return

                current_gate_idx = self._task_graph.gates.index(gate) + 1

    async def _execute_task(self, task: Task) -> Artifact | None:
        """Execute a single task (non-streaming fallback)."""
        # Collect results from streaming execution
        result_text: str | None = None

        async for event in self._execute_task_streaming(task):
            # The streaming method yields events, but we only care about the result
            # The result is stored internally during streaming
            pass

        # Get the result from internal state (set by streaming method)
        result_text = getattr(self, "_last_task_result", None)

        if result_text and task.target_path:
            path = self.cwd / task.target_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(result_text)

            return Artifact(
                path=path,
                content=result_text,
                task_id=task.id,
            )

        return None

    async def _execute_task_streaming(self, task: Task) -> AsyncIterator[AgentEvent]:
        """Execute a single task with inference visibility (RFC-081).

        Streams tokens and emits MODEL_* events during generation,
        providing real-time feedback to the user.

        Yields:
            AgentEvent for model start, tokens, thinking, and complete
        """
        from sunwell.models.protocol import GenerateOptions

        # Build prompt with learnings
        learnings_context = self._learning_store.format_for_prompt(5)

        prompt = f"""Generate code for this task:

TASK: {task.description}

{f"KNOWN FACTS:{chr(10)}{learnings_context}" if learnings_context else ""}

Output ONLY the code (no explanation, no markdown fences):"""

        # Estimate prompt tokens (rough: 1 token ~= 4 chars)
        prompt_tokens = len(prompt) // 4

        # Get estimated time from historical data
        model_id = getattr(self.model, "model_id", "unknown")
        estimated_time = self._inference_metrics.estimate_time(
            model_id, prompt_tokens, expected_output=500
        )

        # Emit start event
        yield model_start_event(
            task_id=task.id,
            model=model_id,
            prompt_tokens=prompt_tokens,
            estimated_time_s=estimated_time,
        )

        # Stream with visibility
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
                # Track first token
                if first_token_time is None:
                    first_token_time = time()

                token_buffer.append(chunk)
                token_count += 1  # Approximate (1 chunk ~= 1 token)

                # Detect thinking blocks
                thinking_blocks = thinking_detector.feed(chunk)
                for block in thinking_blocks:
                    yield model_thinking_event(
                        task_id=task.id,
                        phase=block.phase,
                        content=block.content,
                        is_complete=block.is_complete,
                    )

                # Emit token batches
                elapsed = time() - start_time
                if token_count % self.token_batch_size == 0:
                    tps = token_count / elapsed if elapsed > 0 else None
                    yield model_tokens_event(
                        task_id=task.id,
                        tokens="".join(token_buffer[-self.token_batch_size :]),
                        token_count=token_count,
                        tokens_per_second=tps,
                    )

        except AttributeError:
            # Model doesn't support streaming, fall back to blocking
            result = await self.model.generate(
                prompt,
                options=GenerateOptions(temperature=0.3, max_tokens=4000),
            )
            if result.text:
                token_buffer = [result.text]
                token_count = len(result.text) // 4  # Rough estimate
                first_token_time = time()

        # Calculate final metrics
        duration = time() - start_time
        tps = token_count / duration if duration > 0 else 0
        ttft_ms = int((first_token_time - start_time) * 1000) if first_token_time else None

        # Record metrics for model discovery
        self._inference_metrics.record(
            model=model_id,
            duration_s=duration,
            tokens=token_count,
            ttft_ms=ttft_ms,
        )

        # Emit complete event
        yield model_complete_event(
            task_id=task.id,
            total_tokens=token_count,
            duration_s=duration,
            tokens_per_second=tps,
            time_to_first_token_ms=ttft_ms,
        )

        # Store result for retrieval
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
    ) -> AsyncIterator[AgentEvent]:
        """Attempt to fix errors at a gate."""
        # Collect errors from artifacts
        from sunwell.adaptive.validation import ValidationError

        errors: list[ValidationError] = []

        # For now, create a generic error
        errors.append(
            ValidationError(
                error_type="gate_failure",
                message=f"Gate {gate.id} failed",
            )
        )

        artifacts_dict = {str(a.path): a for a in artifacts}

        async for event in self._fix_stage.fix_errors(errors, artifacts_dict):
            yield event

    async def _save_memory(self) -> AsyncIterator[AgentEvent]:
        """Save learnings to disk, optionally to Simulacrum, and update briefing."""
        # Always save to disk for cross-session persistence
        disk_saved = self._learning_store.save_to_disk(self.cwd)

        # Also sync to simulacrum if available
        sim_synced = 0
        if self.simulacrum:
            sim_synced = self._learning_store.sync_to_simulacrum(self.simulacrum)
            self.simulacrum.save_session()

        # RFC-081: Save inference metrics for model discovery
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

        # RFC-071: Save briefing
        if self.enable_briefing:
            async for event in self._save_briefing():
                yield event

    async def _save_briefing(self) -> AsyncIterator[AgentEvent]:
        """Generate and save new briefing based on session work (RFC-071)."""
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

        # Build execution summary from task graph
        if hasattr(self, "_task_graph") and self._task_graph:
            summary = ExecutionSummary.from_task_graph(
                self._task_graph,
                self._session_learnings,
            )
        else:
            # No task graph, create minimal summary
            summary = ExecutionSummary(
                last_action="Session completed.",
                next_action=None,
                modified_files=(),
                tasks_completed=0,
                gates_passed=0,
                new_learnings=(),
            )

        # Determine new status
        new_status = self._determine_briefing_status()

        # Create or update briefing
        if self._briefing:
            old_briefing = self._briefing
        elif self._current_goal:
            # First session - create initial briefing
            old_briefing = Briefing.create_initial(
                mission=self._current_goal,
                goal_hash=None,
            )
        else:
            # No goal and no briefing - skip
            return

        # Predict skills for next session
        predicted_skills = predict_skills_from_briefing(old_briefing)
        suggested_lens = suggest_lens_from_briefing(old_briefing)

        # Compress and write new briefing
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

        # If mission complete, generate completion learning
        if new_status == BriefingStatus.COMPLETE:
            completion_learning = briefing_to_learning(new_briefing)
            if completion_learning:
                self._learning_store.add_learning(completion_learning)
                yield memory_learning_event(
                    fact=completion_learning.fact,
                    category="task_completion",
                )

    def _determine_briefing_status(self) -> "BriefingStatus":
        """Determine briefing status from task graph state."""
        from sunwell.memory.briefing import BriefingStatus

        if not hasattr(self, "_task_graph") or not self._task_graph:
            return BriefingStatus.IN_PROGRESS

        if self._current_blockers:
            return BriefingStatus.BLOCKED

        # Check if all tasks completed
        if not self._task_graph.has_pending_tasks():
            return BriefingStatus.COMPLETE

        return BriefingStatus.IN_PROGRESS


# =============================================================================
# Convenience Functions
# =============================================================================


async def run_adaptive(
    goal: str,
    model: ModelProtocol,
    session: str | None = None,
    cwd: Path | None = None,
) -> list[AgentEvent]:
    """Run adaptive agent and collect all events.

    Convenience function for non-streaming use cases.

    Args:
        goal: The user's goal
        model: LLM for generation
        session: Optional session name for persistence
        cwd: Working directory

    Returns:
        List of all events from the run
    """
    agent = AdaptiveAgent(model=model, session=session, cwd=cwd)
    events = []

    async for event in agent.run(goal):
        events.append(event)

    return events
