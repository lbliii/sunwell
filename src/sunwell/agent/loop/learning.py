"""Learning injection for the agentic tool loop."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.agent.learning import LearningStore

logger = logging.getLogger(__name__)


async def get_learnings_prompt(
    task_description: str,
    learning_store: LearningStore | None,
    enable_tool_learning: bool = True,
) -> str | None:
    """Get relevant learnings and tool suggestions for the task (RFC-134).

    Args:
        task_description: The task to get learnings for
        learning_store: Learning store to query
        enable_tool_learning: Whether to include tool suggestions

    Returns:
        Formatted prompt with learnings and tool suggestions, or None
    """
    if not learning_store:
        return None

    try:
        sections: list[str] = []

        # Get relevant learnings
        relevant = learning_store.get_relevant(task_description)
        if relevant:
            learnings_text = "\n".join(f"- {learning.fact}" for learning in relevant[:5])
            sections.append(f"Apply these known facts from past experience:\n{learnings_text}")
            logger.info(
                "Learning injection: Applied %d learnings from memory",
                len(relevant[:5]),
                extra={"learnings_count": len(relevant[:5])},
            )

        # RFC-134: Get tool suggestions based on task type
        if enable_tool_learning:
            from sunwell.agent.learning import classify_task_type

            task_type = classify_task_type(task_description)
            tool_suggestion = learning_store.format_tool_suggestions(task_type)
            if tool_suggestion:
                sections.append(tool_suggestion)
                logger.info(
                    "Tool suggestion: %s for task type '%s'",
                    tool_suggestion,
                    task_type,
                )

        return "\n\n".join(sections) if sections else None

    except Exception as e:
        logger.warning("Failed to get learnings: %s", e)
        return None
