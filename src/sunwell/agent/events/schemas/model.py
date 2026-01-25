"""Model event schemas."""

from typing import TypedDict


class ModelStartData(TypedDict, total=False):
    """Data for model_start event."""
    provider: str  # Required
    model: str  # Required


class ModelTokensData(TypedDict, total=False):
    """Data for model_tokens event."""
    tokens: int  # Required
    cumulative: bool


class ModelThinkingData(TypedDict, total=False):
    """Data for model_thinking event."""
    content: str  # Required


class ModelCompleteData(TypedDict, total=False):
    """Data for model_complete event."""
    duration_ms: int  # Required
    input_tokens: int | None
    output_tokens: int | None


class ModelHeartbeatData(TypedDict, total=False):
    """Data for model_heartbeat event."""
    elapsed_ms: int  # Required
