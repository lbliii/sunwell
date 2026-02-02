"""Intent and domain event schemas."""

from typing import TypedDict


class IntentClassifiedData(TypedDict, total=False):
    """Data for intent_classified event (Conversational DAG)."""

    path: list[str]  # Required - DAG path nodes
    path_formatted: str  # Required - Human-readable path
    confidence: float  # Required - Classification confidence
    reasoning: str  # Required - Why this classification
    requires_approval: bool
    tool_scope: str | None
    depth: int


class NodeTransitionData(TypedDict, total=False):
    """Data for node_transition event (Conversational DAG)."""

    from_node: str  # Required
    to_node: str  # Required
    path: list[str]  # Required - New path after transition
    path_formatted: str  # Required
    reason: str


class DomainDetectedData(TypedDict, total=False):
    """Data for domain_detected event (RFC-DOMAINS)."""

    domain_type: str  # Required - e.g., 'code', 'research'
    confidence: float  # Required - Detection confidence
    tools_package: str | None
    validators: list[str]  # Required - Enabled validators
