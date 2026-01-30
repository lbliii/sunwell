"""Planning methods for Agent (extracted from core.py).

Contains task planning logic including:
- Signal-based technique selection
- Harmonic planning (multi-candidate)
- Single-shot planning (simple path)

RFC-112: Debug logging added for Observatory event flow verification.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)

from sunwell.agent.events import (
    AgentEvent,
    EventType,
    GateSummary,
    TaskSummary,
    plan_winner_event,
)
from sunwell.agent.validation.gates import detect_gates

if TYPE_CHECKING:
    from sunwell.agent.core.task_graph import TaskGraph
    from sunwell.agent.learning import LearningStore
    from sunwell.agent.signals import AdaptiveSignals
    from sunwell.agent.utils.budget import AdaptiveBudget
    from sunwell.foundation.core.lens import Lens
    from sunwell.memory.briefing import Briefing
    from sunwell.models import ModelProtocol


async def plan_with_signals(
    goal: str,
    signals: AdaptiveSignals,
    context: dict[str, Any],
    model: ModelProtocol,
    learning_store: LearningStore,
    lens: Lens | None,
    briefing: Briefing | None,
    budget: AdaptiveBudget,
    simulacrum: Any | None = None,
) -> AsyncIterator[AgentEvent]:
    """Plan using signal-appropriate technique.

    Args:
        goal: The goal to plan for
        signals: Extracted signals for routing decisions
        context: Additional planning context
        model: Model for generation
        learning_store: For formatting learnings context
        lens: Active lens (if any)
        briefing: Current briefing (if any)
        budget: Token budget configuration
        simulacrum: SimulacrumStore for knowledge retrieval

    Yields:
        AgentEvent instances. The PLAN_WINNER event contains task_graph and
        planning_context in its data dict for consumers to extract.
    """
    yield AgentEvent(EventType.PLAN_START, {"technique": signals.planning_route})

    # Build context with learnings and lens expertise
    planning_context = dict(context) if context else {}
    learnings_context = learning_store.format_for_prompt()
    if learnings_context:
        planning_context["learnings"] = learnings_context

    if lens:
        planning_context["lens_context"] = lens.to_context()

    if briefing:
        planning_context["briefing"] = briefing.to_prompt()

    # RFC-112: Log planning route decision for Observatory debugging
    logger.debug(f"[Observatory] Planning route selected: {signals.planning_route}")

    if signals.planning_route == "HARMONIC":
        logger.debug("[Observatory] Starting harmonic planning (multi-candidate)")
        async for event in _harmonic_plan(
            goal, planning_context, model, budget, simulacrum
        ):
            yield event
    else:
        logger.debug("[Observatory] Starting single-shot planning (simple path)")
        async for event in _single_shot_plan(goal, planning_context, model):
            yield event


async def _harmonic_plan(
    goal: str,
    context: dict[str, Any],
    model: ModelProtocol,
    budget: AdaptiveBudget,
    simulacrum: Any | None = None,
) -> AsyncIterator[AgentEvent]:
    """Plan using Harmonic planning (multiple candidates).

    Args:
        goal: The goal to plan for
        context: Planning context
        model: Model for generation
        budget: Token budget configuration
        simulacrum: SimulacrumStore for knowledge retrieval

    Yields:
        AgentEvent instances. The PLAN_WINNER event contains task_graph and
        planning_context in its data dict.
    """
    try:
        from sunwell.planning.naaru.planners.harmonic import HarmonicPlanner

        # RFC-123: Stream events live using async queue (fixes regression)
        event_queue: asyncio.Queue[AgentEvent | None] = asyncio.Queue()
        selected_candidate_id = "candidate-0"
        winner_score: float = 0.0
        winner_metrics: dict[str, Any] | None = None
        last_planning_context: Any = None

        def queue_event(event: AgentEvent) -> None:
            # Track the winner info as events come in
            nonlocal selected_candidate_id, winner_score, winner_metrics
            if event.type == EventType.PLAN_WINNER:
                selected_candidate_id = event.data.get(
                    "selected_candidate_id", "candidate-0"
                )
                winner_score = event.data.get("score", 0.0)
                winner_metrics = event.data.get("metrics")
            event_queue.put_nowait(event)

        candidates = 5 if not budget.is_low else 3
        # RFC-112: Explicit refinement_rounds for Observatory ResonanceWave visualization
        refinement_rounds = 2 if not budget.is_low else 1
        logger.debug(
            f"[Observatory] Creating HarmonicPlanner: candidates={candidates}, "
            f"refinement_rounds={refinement_rounds}, event_callback=SET"
        )
        planner = HarmonicPlanner(
            model=model,
            candidates=candidates,
            refinement_rounds=refinement_rounds,
            event_callback=queue_event,
            # RFC-122: Connect to SimulacrumStore for knowledge retrieval
            simulacrum=simulacrum,
        )

        # Run planning in background task so we can stream events
        async def run_planning() -> list[Any]:
            nonlocal last_planning_context
            try:
                result = await planner.plan([goal], context)
                last_planning_context = planner.last_planning_context
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

        gates = detect_gates(tasks)

        from sunwell.agent.core.task_graph import TaskGraph

        task_graph = TaskGraph(tasks=tasks, gates=gates)

        task_list: list[TaskSummary] = [
            {
                "id": t.id,
                "description": t.description,
                "depends_on": list(t.depends_on),
                "produces": list(t.produces)
                if t.produces
                else ([t.target_path] if t.target_path else []),
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
            score=winner_score,
            metrics=winner_metrics,
            # Event-carried data: consumers extract these from event.data
            task_graph=task_graph,
            planning_context=last_planning_context,
        )

    except ImportError:
        async for event in _single_shot_plan(goal, context, model):
            yield event


async def _single_shot_plan(
    goal: str,
    context: dict[str, Any],
    model: ModelProtocol,
) -> AsyncIterator[AgentEvent]:
    """Simple single-shot planning.

    Args:
        goal: The goal to plan for
        context: Planning context
        model: Model for generation

    Yields:
        AgentEvent instances. The PLAN_WINNER event contains task_graph in its data dict.
    """
    try:
        from sunwell.planning.naaru.planners.artifact import ArtifactPlanner

        planner = ArtifactPlanner(model=model)
        graph = await planner.discover_graph(goal, context)

        from sunwell.planning.naaru.artifacts import artifacts_to_tasks

        tasks = artifacts_to_tasks(graph)

        gates = detect_gates(tasks)

        from sunwell.agent.core.task_graph import TaskGraph

        task_graph = TaskGraph(tasks=tasks, gates=gates)

        task_list: list[TaskSummary] = [
            {
                "id": t.id,
                "description": t.description,
                "depends_on": list(t.depends_on),
                "produces": list(t.produces)
                if t.produces
                else ([t.target_path] if t.target_path else []),
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
            # Event-carried data: consumers extract task_graph from event.data
            task_graph=task_graph,
        )

    except ImportError:
        from sunwell.agent.core.task_graph import TaskGraph
        from sunwell.planning.naaru.types import Task, TaskMode

        task = Task(
            id="main",
            description=goal,
            mode=TaskMode.GENERATE,
        )
        task_graph = TaskGraph(tasks=[task], gates=[])

        yield plan_winner_event(
            tasks=1,
            gates=0,
            technique="minimal",
            task_list=[
                {
                    "id": "main",
                    "description": goal,
                    "depends_on": [],
                    "produces": [],
                    "category": None,
                }
            ],
            gate_list=[],
            # Event-carried data: consumers extract task_graph from event.data
            task_graph=task_graph,
        )
