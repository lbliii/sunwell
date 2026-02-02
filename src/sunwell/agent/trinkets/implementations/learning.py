"""Learning trinket - injects relevant learnings from memory.

Priority 30, system placement.
Not cacheable - learnings are task-dependent.

Ported from agent/loop/learning.py:get_learnings_prompt()
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
    from sunwell.agent.learning import LearningStore

logger = logging.getLogger(__name__)


class LearningTrinket(BaseTrinket):
    """Injects relevant learnings from past experience.

    Queries the learning store for facts, patterns, and constraints
    relevant to the current task. Uses first-person voice for
    reduced epistemic distance.

    Example output:
        ## What I've Learned

        Apply these from my past experience:
        - I know: This project uses FastAPI with SQLAlchemy
        - I prefer: pytest over unittest for testing
        - I must: Always add type hints to public functions

        For code tasks, I should consider: read_file, write_file, edit_file
    """

    def __init__(
        self,
        learning_store: LearningStore | None,
        enable_tool_learning: bool = True,
    ) -> None:
        """Initialize with learning store.

        Args:
            learning_store: Store to query for relevant learnings.
            enable_tool_learning: Whether to include tool suggestions.
        """
        self.learning_store = learning_store
        self.enable_tool_learning = enable_tool_learning

    def get_section_name(self) -> str:
        """Return unique identifier."""
        return "learnings"

    async def generate(self, context: TrinketContext) -> TrinketSection | None:
        """Generate learnings section.

        Returns None if no learning store or no relevant learnings.
        """
        if not self.learning_store:
            return None

        try:
            sections: list[str] = []

            # Get relevant learnings
            relevant = self.learning_store.get_relevant(context.task)
            if relevant:
                # Use first-person voice
                lines = []
                for learning in relevant[:5]:
                    prefix = learning._first_person_prefix()
                    lines.append(f"- {prefix} {learning.fact}")

                learnings_text = "\n".join(lines)
                sections.append(
                    f"## What I've Learned\n\n"
                    f"Apply these from my past experience:\n{learnings_text}"
                )

                logger.info(
                    "Learning trinket: Applied %d learnings from memory",
                    len(relevant[:5]),
                    extra={"learnings_count": len(relevant[:5])},
                )

            # RFC-134: Get tool suggestions based on task type
            if self.enable_tool_learning:
                from sunwell.agent.learning import classify_task_type

                task_type = classify_task_type(context.task)
                tool_suggestion = self.learning_store.format_tool_suggestions(task_type)
                if tool_suggestion:
                    sections.append(tool_suggestion)
                    logger.info(
                        "Learning trinket: Tool suggestion for task type '%s'",
                        task_type,
                    )

            if not sections:
                return None

            return TrinketSection(
                name="learnings",
                content="\n\n".join(sections),
                placement=TrinketPlacement.SYSTEM,
                priority=30,  # After briefing, before tool guidance
                cacheable=False,  # Task-dependent
            )

        except Exception as e:
            logger.warning("Learning trinket failed: %s", e)
            return None
