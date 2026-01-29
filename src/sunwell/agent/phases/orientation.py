"""OrientationPhase - Load memory context and identify constraints.

Part of the Agent phase extraction (Week 3 refactoring).

The orientation phase:
1. Loads relevant memory context (learnings, constraints, dead ends)
2. Loads briefing if available
3. Resolves lens for the goal
4. Prepares the agent for planning

This is the first phase extracted from Agent to make the codebase more modular.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.agent.events import (
    AgentEvent,
    briefing_loaded_event,
    lens_selected_event,
    orient_event,
)

if TYPE_CHECKING:
    from sunwell.foundation.core.lens import Lens
    from sunwell.memory import PersistentMemory
    from sunwell.memory.briefing import Briefing
    from sunwell.memory.core.types import MemoryContext


@dataclass(frozen=True, slots=True)
class OrientationResult:
    """Result of the orientation phase.

    Contains all the context needed for subsequent phases.
    """

    memory_ctx: MemoryContext
    """Memory context (learnings, constraints, dead_ends)."""

    briefing: Briefing | None
    """Briefing if available."""

    lens: Lens | None
    """Resolved lens."""

    lens_selection_reason: str | None = None
    """Why this lens was selected."""


@dataclass(slots=True)
class OrientationPhase:
    """Orientation phase - load memory and context.

    This is the first phase in the agent execution flow:
    Orient → Plan → Execute → Learn

    The orientation phase gathers all the context needed for planning:
    - Memory context (what we know, what to avoid)
    - Briefing (mission, hazards, hints)
    - Lens (domain expertise)
    """

    goal: str
    """The goal to orient around."""

    memory: PersistentMemory
    """Memory to query for context."""

    project_path: Path | None = None
    """Project path for lens resolution."""

    briefing: Briefing | None = None
    """Optional pre-loaded briefing."""

    provided_lens: Lens | None = None
    """Optional pre-selected lens."""

    auto_lens: bool = True
    """Whether to auto-select lens if not provided."""

    async def run(self) -> AsyncIterator[AgentEvent | OrientationResult]:
        """Execute the orientation phase.

        Yields:
            AgentEvent for progress tracking
            OrientationResult as final event with gathered context
        """
        # Step 1: Load memory context
        memory_ctx = await self.memory.get_relevant(self.goal)

        yield orient_event(
            learnings=len(memory_ctx.learnings),
            constraints=len(memory_ctx.constraints),
            dead_ends=len(memory_ctx.dead_ends),
        )

        # Step 2: Load briefing if available
        if self.briefing:
            yield briefing_loaded_event(
                mission=self.briefing.mission,
                status=self.briefing.status.value,
                has_hazards=len(self.briefing.hazards) > 0,
                has_dispatch_hints=bool(
                    self.briefing.predicted_skills or self.briefing.suggested_lens
                ),
            )

        # Step 3: Resolve lens
        lens = self.provided_lens
        lens_reason = None

        if lens is None and self.auto_lens:
            from sunwell.agent.utils.lens import resolve_lens_for_goal

            resolution = await resolve_lens_for_goal(
                goal=self.goal,
                project_path=self.project_path,
                auto_select=True,
            )
            if resolution.lens:
                lens = resolution.lens
                lens_reason = resolution.reason
                yield lens_selected_event(
                    name=resolution.lens.metadata.name,
                    source=resolution.source,
                    confidence=resolution.confidence,
                    reason=resolution.reason,
                )

        # Return final result
        yield OrientationResult(
            memory_ctx=memory_ctx,
            briefing=self.briefing,
            lens=lens,
            lens_selection_reason=lens_reason,
        )
