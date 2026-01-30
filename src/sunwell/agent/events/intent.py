"""Intent classification events for Conversational DAG Architecture.

Events for tracking user intent classification through the DAG tree.
"""

from sunwell.agent.events.types import AgentEvent, EventType


def intent_classified_event(
    path: tuple[str, ...],
    confidence: float,
    reasoning: str,
    requires_approval: bool = False,
    tool_scope: str | None = None,
) -> AgentEvent:
    """Create an intent classification event.

    Args:
        path: The classified DAG path (e.g., ("conversation", "act", "write"))
        confidence: Confidence score 0.0-1.0
        reasoning: Explanation of the classification
        requires_approval: Whether this path requires user approval
        tool_scope: Tool trust level required (e.g., "READ_ONLY", "WORKSPACE")

    Returns:
        AgentEvent for intent classification
    """
    return AgentEvent(
        type=EventType.INTENT_CLASSIFIED,
        data={
            "path": list(path),
            "path_formatted": " → ".join(path),
            "confidence": confidence,
            "reasoning": reasoning,
            "requires_approval": requires_approval,
            "tool_scope": tool_scope,
            "depth": len(path),
        },
    )


def node_transition_event(
    from_node: str,
    to_node: str,
    new_path: tuple[str, ...],
    reason: str = "",
) -> AgentEvent:
    """Create a node transition event.

    Args:
        from_node: Source node in the DAG
        to_node: Target node in the DAG
        new_path: The new complete path after transition
        reason: Why the transition occurred

    Returns:
        AgentEvent for node transition
    """
    return AgentEvent(
        type=EventType.NODE_TRANSITION,
        data={
            "from_node": from_node,
            "to_node": to_node,
            "path": list(new_path),
            "path_formatted": " → ".join(new_path),
            "reason": reason,
        },
    )
