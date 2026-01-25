"""Autonomous Goal Workflow (RFC-130).

Unified entry point for fully autonomous multi-agent workflows.
Combines all four pillars: dynamic spawning, semantic checkpoints,
adaptive guards, and memory-informed prefetch.

Example:
    >>> async for event in autonomous_goal(
    ...     goal="Implement user authentication",
    ...     project_path=Path.cwd(),
    ...     max_duration_hours=4,
    ... ):
    ...     handle_event(event)
"""

import asyncio
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from pathlib import Path

from sunwell.agent.events import (
    AgentEvent,
    EventType,
    checkpoint_found_event,
)


@dataclass(frozen=True, slots=True)
class AutonomousConfig:
    """Configuration for autonomous workflow.

    RFC-130: Controls behavior of autonomous execution including
    specialist spawning, checkpoint intervals, and guard policies.
    """

    # Timing
    max_duration_hours: float = 4.0
    """Maximum duration for autonomous session."""

    checkpoint_interval_minutes: float = 15.0
    """Save checkpoint every N minutes."""

    # Specialist spawning
    enable_spawning: bool = True
    """Whether to allow specialist spawning."""

    max_spawn_depth: int = 2
    """Maximum depth for specialist spawning."""

    specialist_budget_tokens: int = 10_000
    """Token budget for all specialists combined."""

    # Guards
    trust_level: str = "supervised"
    """Trust level: conservative, guarded, supervised, full."""

    enable_guard_learning: bool = True
    """Enable adaptive guard learning from violations."""

    # Memory
    enable_memory_prefetch: bool = True
    """Enable memory-informed prefetch."""

    # Resume
    auto_resume: bool = True
    """Automatically resume from checkpoint if found."""


@dataclass(slots=True)
class AutonomousState:
    """Runtime state for autonomous execution."""

    goal: str
    """The goal being executed."""

    started_at: float = 0.0
    """Unix timestamp when execution started."""

    checkpoint_count: int = 0
    """Number of checkpoints saved."""

    specialists_spawned: int = 0
    """Number of specialists spawned."""

    guards_triggered: int = 0
    """Number of times guards were triggered."""

    memory_hits: int = 0
    """Number of similar past goals found."""

    current_phase: str = "orient"
    """Current semantic phase."""

    resumed_from_checkpoint: bool = False
    """Whether execution resumed from checkpoint."""

    user_decisions: list[str] = field(default_factory=list)
    """User decisions made during execution."""


async def autonomous_goal(
    goal: str,
    project_path: Path,
    config: AutonomousConfig | None = None,
    on_checkpoint: Callable[[AgentEvent], None] | None = None,
) -> AsyncIterator[AgentEvent]:
    """Execute goal autonomously with all RFC-130 features.

    This is the unified entry point for fully autonomous multi-agent workflows.
    It combines:
    - Dynamic specialist spawning (Pillar 1)
    - Semantic checkpoints (Pillar 2)
    - Adaptive guards (Pillar 3)
    - Memory-informed prefetch (Pillar 4)

    Args:
        goal: Natural language goal description
        project_path: Path to the project
        config: Autonomous configuration (uses defaults if None)
        on_checkpoint: Callback when checkpoint is saved

    Yields:
        AgentEvent for each step of execution

    Example:
        >>> async for event in autonomous_goal(
        ...     goal="Implement user authentication",
        ...     project_path=Path.cwd(),
        ... ):
        ...     if event.type == EventType.SPECIALIST_SPAWNED:
        ...         print(f"Spawned: {event.data['role']}")
        ...     elif event.type == EventType.CHECKPOINT_SAVED:
        ...         print(f"Checkpoint: {event.data['phase']}")
    """
    from time import time

    from sunwell.agent.core import Agent
    from sunwell.context.session import SessionContext
    from sunwell.guardrails.system import GuardrailSystem
    from sunwell.memory.persistent import PersistentMemory
    from sunwell.naaru.checkpoint import AgentCheckpoint

    config = config or AutonomousConfig()
    state = AutonomousState(goal=goal, started_at=time())

    # Initialize components
    project_path = Path(project_path).resolve()
    memory = await PersistentMemory.load_async(project_path)

    # Check for existing checkpoint
    if config.auto_resume:
        checkpoint = AgentCheckpoint.find_latest_for_goal(project_path, goal)
        if checkpoint:
            yield checkpoint_found_event(
                phase=checkpoint.phase.value,
                checkpoint_at=checkpoint.checkpoint_at.isoformat(),
                goal=goal,
            )
            state.resumed_from_checkpoint = True
            state.current_phase = checkpoint.phase.value
            state.user_decisions = list(checkpoint.user_decisions)

    # Initialize guardrails with learning enabled
    guardrails = GuardrailSystem(
        repo_path=project_path,
        model=None,  # Will be set by agent
    )
    if config.enable_guard_learning:
        # Enable learning in classifier
        from sunwell.guardrails.classifier import SmartActionClassifier

        guardrails.classifier = SmartActionClassifier(
            trust_level=guardrails.config.trust_level,
            enable_learning=True,
            violation_store_path=project_path / ".sunwell" / "guard-violations",
        )

    # Start guardrail session
    session_start = await guardrails.start_session()

    yield AgentEvent(
        EventType.SESSION_START,
        {
            "session_id": session_start.session_id,
            "goal": goal,
            "auto_resume": state.resumed_from_checkpoint,
            "trust_level": config.trust_level,
        },
    )

    # Create session context
    session = SessionContext.create(
        goal=goal,
        cwd=project_path,
        memory=memory,
    )

    # Create agent with spawning enabled
    from sunwell.lenses.loader import resolve_lens_for_workspace

    lens = await resolve_lens_for_workspace(project_path)
    if lens and config.enable_spawning:
        # Enable spawning on lens
        lens.can_spawn = True
        lens.max_children = 3
        lens.spawn_budget_tokens = config.specialist_budget_tokens

    agent = Agent(
        cwd=project_path,
        lens=lens,
        auto_lens=True,
        stream_inference=True,
    )

    # Track execution time
    max_duration_seconds = config.max_duration_hours * 3600
    checkpoint_interval_seconds = config.checkpoint_interval_minutes * 60
    last_checkpoint_time = time()

    try:
        # Main execution loop
        async for event in agent.run(session, memory):
            yield event

            # Track state based on events
            if event.type == EventType.SPECIALIST_SPAWNED:
                state.specialists_spawned += 1

            # Check for checkpoint time
            current_time = time()
            if current_time - last_checkpoint_time >= checkpoint_interval_seconds:
                checkpoint_event = await agent._save_phase_checkpoint(
                    agent._current_phase,
                    f"Autonomous checkpoint at {state.current_phase}",
                )
                yield checkpoint_event
                state.checkpoint_count += 1
                last_checkpoint_time = current_time

                if on_checkpoint:
                    on_checkpoint(checkpoint_event)

            # Check duration limit
            if current_time - state.started_at >= max_duration_seconds:
                yield AgentEvent(
                    EventType.TIMEOUT,
                    {
                        "reason": "max_duration_exceeded",
                        "duration_hours": config.max_duration_hours,
                        "checkpoints_saved": state.checkpoint_count,
                    },
                )
                break

    except KeyboardInterrupt:
        # Save checkpoint on interrupt
        checkpoint_event = await agent._save_phase_checkpoint(
            agent._current_phase,
            "Interrupted by user",
        )
        yield checkpoint_event
        raise

    finally:
        # Final checkpoint
        checkpoint_event = await agent._save_phase_checkpoint(
            agent._current_phase,
            f"Session complete: {state.specialists_spawned} specialists, {state.checkpoint_count} checkpoints",
        )
        yield checkpoint_event

        # Get guard evolution suggestions
        if config.enable_guard_learning:
            evolutions = await guardrails.get_guard_evolutions()
            if evolutions:
                from sunwell.agent.events import guard_evolution_suggested_event
                for evo in evolutions[:3]:  # Top 3 suggestions
                    yield guard_evolution_suggested_event(
                        guard_id=evo.rule_id,
                        evolution_type=evo.evolution_type.value,
                        reason=evo.reason,
                        confidence=evo.confidence,
                    )

        # Cleanup
        await guardrails.cleanup_session()
        memory.sync()


async def resume_autonomous(
    goal: str,
    project_path: Path,
    config: AutonomousConfig | None = None,
) -> AsyncIterator[AgentEvent]:
    """Resume an interrupted autonomous workflow.

    Finds the most recent checkpoint for the goal and resumes execution
    from that point.

    Args:
        goal: The goal to resume
        project_path: Path to the project
        config: Autonomous configuration

    Yields:
        AgentEvent for each step of resumed execution
    """
    from sunwell.naaru.checkpoint import AgentCheckpoint

    checkpoint = AgentCheckpoint.find_latest_for_goal(project_path, goal)
    if not checkpoint:
        yield AgentEvent(
            EventType.ERROR,
            {"message": f"No checkpoint found for goal: {goal}"},
        )
        return

    # Resume with auto_resume enabled
    config = config or AutonomousConfig()
    config.auto_resume = True

    async for event in autonomous_goal(goal, project_path, config):
        yield event
