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
    complete_event,
    memory_learning_event,
    signal_event,
    task_complete_event,
    task_start_event,
)
from sunwell.adaptive.fixer import FixStage
from sunwell.adaptive.gates import GateDetector, ValidationGate
from sunwell.adaptive.learning import LearningExtractor, LearningStore
from sunwell.adaptive.signals import AdaptiveSignals, extract_signals
from sunwell.adaptive.toolchain import detect_toolchain
from sunwell.adaptive.validation import Artifact, ValidationRunner, ValidationStage

if TYPE_CHECKING:
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
    """Adaptive agent with signal-driven execution.

    Makes all advanced features (Vortex, Compound Eye, Harmonic, Resonance)
    automatic by default. Uses cheap signals to decide when to apply
    expensive techniques.

    Attributes:
        model: LLM for generation
        cwd: Working directory
        budget: Token budget configuration
        max_fix_attempts: Maximum fix attempts per error
        session: Optional Simulacrum session name
    """

    model: ModelProtocol
    """Model for generation."""

    cwd: Path | None = None
    """Working directory."""

    budget: AdaptiveBudget = field(default_factory=AdaptiveBudget)
    """Token budget with auto-economization."""

    max_fix_attempts: int = 3
    """Maximum fix attempts per error."""

    session: str | None = None
    """Simulacrum session name for persistence."""

    # Internal state
    _simulacrum: SimulacrumStore | None = field(default=None, init=False)
    _learning_store: LearningStore = field(default_factory=LearningStore, init=False)
    _learning_extractor: LearningExtractor = field(
        default_factory=LearningExtractor, init=False
    )
    _validation_runner: ValidationRunner | None = field(default=None, init=False)
    _fix_stage: FixStage | None = field(default=None, init=False)

    def __post_init__(self):
        if self.cwd is None:
            self.cwd = Path.cwd()
        self.cwd = Path(self.cwd)

        # Initialize toolchain
        toolchain = detect_toolchain(self.cwd)
        self._validation_runner = ValidationRunner(toolchain, self.cwd)
        self._fix_stage = FixStage(self.model, self.cwd, self.max_fix_attempts)

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

        # Load Simulacrum session
        async for event in self._load_memory():
            yield event

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
        """Load Simulacrum session if specified."""
        if not self.session:
            return

        yield AgentEvent(EventType.MEMORY_LOAD, {"session": self.session})

        try:
            from sunwell.simulacrum.core.store import SimulacrumStore

            memory_path = self.cwd / ".sunwell" / "memory"
            self._simulacrum = SimulacrumStore(memory_path)

            try:
                self._simulacrum.load_session(self.session)
                yield AgentEvent(
                    EventType.MEMORY_LOADED,
                    {
                        "session": self.session,
                        "turns": len(self._simulacrum.get_dag().turns),
                    },
                )
            except FileNotFoundError:
                self._simulacrum.new_session(self.session)
                yield AgentEvent(EventType.MEMORY_NEW, {"session": self.session})

        except ImportError:
            # Simulacrum not available
            yield AgentEvent(
                EventType.MEMORY_NEW,
                {"session": self.session, "note": "Simulacrum not available"},
            )

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

        # Build context with learnings
        planning_context = context or {}
        learnings_context = self._learning_store.format_for_prompt()
        if learnings_context:
            planning_context["learnings"] = learnings_context

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
        """Execute tasks with validation gates."""
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
        """Execute a single task."""
        from sunwell.models.protocol import GenerateOptions

        # Build prompt with learnings
        learnings_context = self._learning_store.format_for_prompt(5)

        prompt = f"""Generate code for this task:

TASK: {task.description}

{f"KNOWN FACTS:{chr(10)}{learnings_context}" if learnings_context else ""}

Output ONLY the code (no explanation, no markdown fences):"""

        result = await self.model.generate(
            prompt,
            options=GenerateOptions(temperature=0.3, max_tokens=4000),
        )

        if result.text and task.target_path:
            path = self.cwd / task.target_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(result.text)

            return Artifact(
                path=path,
                content=result.text,
                task_id=task.id,
            )

        return None

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
        """Save Simulacrum session."""
        if not self._simulacrum:
            return

        self._simulacrum.save_session()
        yield AgentEvent(
            EventType.MEMORY_SAVED,
            {"learnings": len(self._learning_store.learnings)},
        )


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
