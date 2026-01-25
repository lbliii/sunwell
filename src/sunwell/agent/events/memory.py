"""Unified memory event factories (RFC-MEMORY).

Event factories for memory lifecycle:
- orient_event: Memory loaded, constraints identified
- learning_added_event: New learning extracted
- decision_made_event: Architectural decision recorded
- failure_recorded_event: Failed approach recorded
- briefing_updated_event: Briefing saved for next session
"""

from typing import Any

from sunwell.agent.events.types import AgentEvent, EventType


def orient_event(
    learnings: int,
    constraints: int,
    dead_ends: int,
    **kwargs: Any,
) -> AgentEvent:
    """Create an orient event (RFC-MEMORY).

    Emitted when memory is loaded and constraints are identified.

    Args:
        learnings: Number of relevant learnings found
        constraints: Number of constraints identified
        dead_ends: Number of known dead ends
    """
    return AgentEvent(
        EventType.ORIENT,
        {
            "learnings": learnings,
            "constraints": constraints,
            "dead_ends": dead_ends,
            **kwargs,
        },
    )


def learning_added_event(
    fact: str,
    category: str,
    confidence: float = 1.0,
    **kwargs: Any,
) -> AgentEvent:
    """Create a learning added event (RFC-MEMORY).

    Emitted when a new learning is extracted and recorded.

    Args:
        fact: The learned fact
        category: Learning category
        confidence: Confidence level (0.0-1.0)
    """
    return AgentEvent(
        EventType.LEARNING_ADDED,
        {
            "fact": fact,
            "category": category,
            "confidence": confidence,
            **kwargs,
        },
    )


def decision_made_event(
    category: str,
    question: str,
    choice: str,
    rejected_count: int = 0,
    **kwargs: Any,
) -> AgentEvent:
    """Create a decision made event (RFC-MEMORY).

    Emitted when an architectural decision is recorded.

    Args:
        category: Decision category (e.g., 'database', 'auth')
        question: What decision was made
        choice: What was chosen
        rejected_count: Number of rejected alternatives
    """
    return AgentEvent(
        EventType.DECISION_MADE,
        {
            "category": category,
            "question": question,
            "choice": choice,
            "rejected_count": rejected_count,
            **kwargs,
        },
    )


def failure_recorded_event(
    description: str,
    error_type: str,
    context: str,
    **kwargs: Any,
) -> AgentEvent:
    """Create a failure recorded event (RFC-MEMORY).

    Emitted when a failed approach is recorded.

    Args:
        description: What was attempted
        error_type: Type of failure
        context: What we were trying to achieve
    """
    return AgentEvent(
        EventType.FAILURE_RECORDED,
        {
            "description": description,
            "error_type": error_type,
            "context": context,
            **kwargs,
        },
    )


def briefing_updated_event(
    status: str,
    next_action: str | None,
    hot_files: list[str] | None = None,
    **kwargs: Any,
) -> AgentEvent:
    """Create a briefing updated event (RFC-MEMORY).

    Emitted when briefing is saved for next session.

    Args:
        status: New briefing status
        next_action: Suggested next action
        hot_files: Files relevant to next session
    """
    return AgentEvent(
        EventType.BRIEFING_UPDATED,
        {
            "status": status,
            "next_action": next_action,
            "hot_files": hot_files or [],
            **kwargs,
        },
    )
