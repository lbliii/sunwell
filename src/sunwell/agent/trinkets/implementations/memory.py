"""Memory trinket - injects historical context from conversation memory.

Priority 70, context placement.
Not cacheable - turn-dependent.

Ported from memory/simulacrum/core/retrieval/context_assembler.py
"""

import logging
from typing import TYPE_CHECKING

from sunwell.agent.trinkets.base import (
    BaseTrinket,
    TrinketContext,
    TrinketPlacement,
    TrinketSection,
)

if TYPE_CHECKING:
    from sunwell.memory.simulacrum.core.store import SimulacrumStore

logger = logging.getLogger(__name__)


class MemoryTrinket(BaseTrinket):
    """Injects historical context from conversation memory.

    Retrieves relevant turns, learnings, and episode history
    from the simulacrum store based on the current task.

    Uses hierarchical chunking (hot/warm/cold tiers) to build
    optimal context within token budget.

    Example output:
        ## Relevant History

        [Earlier context: I implemented the user authentication flow
        with JWT tokens. The user preferred bcrypt for password hashing.]

        User: Can you add password reset functionality?
        Me: I'll implement password reset with email verification...
    """

    def __init__(
        self,
        store: SimulacrumStore | None,
        max_tokens: int = 2000,
    ) -> None:
        """Initialize with simulacrum store.

        Args:
            store: SimulacrumStore for memory retrieval.
            max_tokens: Maximum tokens for context.
        """
        self.store = store
        self.max_tokens = max_tokens

    def get_section_name(self) -> str:
        """Return unique identifier."""
        return "memory"

    async def generate(self, context: TrinketContext) -> TrinketSection | None:
        """Generate memory context section.

        Returns None if no store or no relevant context.
        """
        if not self.store:
            return None

        try:
            # Try async retrieval first (with semantic search)
            memory_context = await self._get_context_async(context.task)

            if not memory_context:
                return None

            return TrinketSection(
                name="memory",
                content=memory_context,
                placement=TrinketPlacement.CONTEXT,
                priority=70,  # Last in context - task description comes after
                cacheable=False,  # Turn-dependent
            )

        except Exception as e:
            logger.warning("Memory trinket failed: %s", e)
            return None

    async def _get_context_async(self, task: str) -> str | None:
        """Get memory context using async retrieval.

        Args:
            task: The task to find relevant context for.

        Returns:
            Formatted context string or None.
        """
        # Check if store has context assembler
        if hasattr(self.store, "_context_assembler") and self.store._context_assembler:
            assembler = self.store._context_assembler
            return await assembler.get_context_for_prompt_async(
                query=task,
                max_tokens=self.max_tokens,
            )

        # Fall back to simple retrieval from DAG
        if hasattr(self.store, "_hot_dag"):
            return self._simple_context_from_dag(task)

        return None

    def _simple_context_from_dag(self, task: str) -> str | None:
        """Get simple context from DAG without semantic search.

        Args:
            task: The task description (unused in simple retrieval).

        Returns:
            Formatted context string or None.
        """
        if not hasattr(self.store, "_hot_dag"):
            return None

        dag = self.store._hot_dag
        turns = list(dag.iter_all_turns())

        if not turns:
            return None

        # Get recent turns (last 10)
        recent = turns[-10:]

        parts = ["## Recent Conversation"]
        for turn in recent:
            role = "User" if turn.turn_type.value == "user" else "Me"
            content = turn.content[:300]
            if len(turn.content) > 300:
                content += "..."
            parts.append(f"\n**{role}**: {content}")

        return "\n".join(parts)
