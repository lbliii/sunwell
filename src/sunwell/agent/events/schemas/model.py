"""Model event schemas."""

from typing import TypedDict


class ModelStartData(TypedDict, total=False):
    """Data for model_start event.

    Note: Factory provides task_id/model/prompt_tokens/estimated_time_s.
    """

    task_id: str
    model: str  # Required
    prompt_tokens: int | None
    estimated_time_s: float | None


class ModelTokensData(TypedDict, total=False):
    """Data for model_tokens event.

    Note: Factory provides tokens as string (text), token_count as int.
    """

    task_id: str
    tokens: str  # The actual token text
    token_count: int  # Cumulative count
    tokens_per_second: float | None
    cumulative: bool | None


class ModelThinkingData(TypedDict, total=False):
    """Data for model_thinking event."""

    task_id: str
    phase: str
    content: str  # Required
    is_complete: bool


class ModelCompleteData(TypedDict, total=False):
    """Data for model_complete event.

    Note: Factory provides duration_s (seconds), not duration_ms.
    """

    task_id: str
    total_tokens: int
    duration_s: float
    tokens_per_second: float
    time_to_first_token_ms: int | None
    input_tokens: int | None
    output_tokens: int | None


class ModelHeartbeatData(TypedDict, total=False):
    """Data for model_heartbeat event.

    Note: Factory provides elapsed_s (seconds), not elapsed_ms.
    """

    task_id: str
    elapsed_s: float
    token_count: int
