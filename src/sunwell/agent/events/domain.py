"""Domain detection events (RFC-DOMAINS).

Events for domain detection during agent execution.
"""

from sunwell.agent.events.types import AgentEvent, EventType


def domain_detected_event(
    domain_type: str,
    confidence: float,
    tools_package: str | None = None,
    validators: list[str] | None = None,
) -> AgentEvent:
    """Create a domain detected event.

    Args:
        domain_type: The detected domain type (e.g., 'code', 'research')
        confidence: Detection confidence (0.0-1.0)
        tools_package: Package path for domain tools
        validators: List of enabled validator names

    Returns:
        AgentEvent for domain detection
    """
    return AgentEvent(
        EventType.DOMAIN_DETECTED,
        {
            "domain_type": domain_type,
            "confidence": confidence,
            "tools_package": tools_package,
            "validators": validators or [],
        },
    )
