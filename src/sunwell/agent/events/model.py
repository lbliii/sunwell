"""Model/inference visibility event factories (RFC-081).

Event factories for model generation lifecycle:
- model_start_event: Generation started
- model_tokens_event: Token batch received
- model_thinking_event: Reasoning content detected
- model_complete_event: Generation finished
- model_heartbeat_event: Periodic heartbeat during long generation
"""

from typing import Any

from sunwell.agent.events.types import AgentEvent, EventType


def model_start_event(
    task_id: str,
    model: str,
    prompt_tokens: int | None = None,
    estimated_time_s: float | None = None,
    **kwargs: Any,
) -> AgentEvent:
    """Create a model start event (RFC-081).

    Emitted when model generation begins. Shows spinner in CLI.

    Args:
        task_id: ID of the task triggering generation
        model: Model identifier (e.g., "gpt-oss:20b")
        prompt_tokens: Estimated prompt tokens (optional)
        estimated_time_s: Estimated generation time based on history (optional)
    """
    return AgentEvent(
        EventType.MODEL_START,
        {
            "task_id": task_id,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "estimated_time_s": estimated_time_s,
            **kwargs,
        },
    )


def model_tokens_event(
    task_id: str,
    tokens: str,
    token_count: int,
    tokens_per_second: float | None = None,
    **kwargs: Any,
) -> AgentEvent:
    """Create a model tokens event (RFC-081).

    Emitted in batches (every ~10 tokens) during streaming generation.
    Updates token counter and preview in CLI/Studio.

    Args:
        task_id: ID of the task generating
        tokens: The actual token text in this batch
        token_count: Cumulative token count so far
        tokens_per_second: Current generation speed (optional)
    """
    return AgentEvent(
        EventType.MODEL_TOKENS,
        {
            "task_id": task_id,
            "tokens": tokens,
            "token_count": token_count,
            "tokens_per_second": tokens_per_second,
            **kwargs,
        },
    )


def model_thinking_event(
    task_id: str,
    phase: str,
    content: str,
    is_complete: bool = False,
    **kwargs: Any,
) -> AgentEvent:
    """Create a model thinking event (RFC-081).

    Emitted when reasoning content is detected (<think>, Thinking..., etc.).
    Shows thinking preview panel in CLI/Studio.

    Args:
        task_id: ID of the task generating
        phase: Thinking phase ("think", "critic", "synthesize", "reasoning")
        content: The thinking content
        is_complete: True when thinking block closes
    """
    return AgentEvent(
        EventType.MODEL_THINKING,
        {
            "task_id": task_id,
            "phase": phase,
            "content": content,
            "is_complete": is_complete,
            **kwargs,
        },
    )


def model_complete_event(
    task_id: str,
    total_tokens: int,
    duration_s: float,
    tokens_per_second: float,
    time_to_first_token_ms: int | None = None,
    model: str | None = None,
    finish_reason: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    **kwargs: Any,
) -> AgentEvent:
    """Create a model complete event (RFC-081).

    Emitted when generation finishes. Shows final metrics.

    Args:
        task_id: ID of the task that generated
        total_tokens: Total tokens generated
        duration_s: Total generation time
        tokens_per_second: Average generation speed
        time_to_first_token_ms: Time to first token in milliseconds (optional)
        model: Model identifier used for generation (optional)
        finish_reason: Why generation stopped ("stop", "length", "tool_calls", etc.)
        prompt_tokens: Tokens in the prompt (optional)
        completion_tokens: Tokens in the completion (optional)
    """
    return AgentEvent(
        EventType.MODEL_COMPLETE,
        {
            "task_id": task_id,
            "total_tokens": total_tokens,
            "duration_s": duration_s,
            "tokens_per_second": tokens_per_second,
            "time_to_first_token_ms": time_to_first_token_ms,
            "model": model,
            "finish_reason": finish_reason,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            **kwargs,
        },
    )


def model_heartbeat_event(
    task_id: str,
    elapsed_s: float,
    token_count: int,
    **kwargs: Any,
) -> AgentEvent:
    """Create a model heartbeat event (RFC-081).

    Emitted periodically during long generations to show activity.

    Args:
        task_id: ID of the task generating
        elapsed_s: Time elapsed since generation started
        token_count: Current token count
    """
    return AgentEvent(
        EventType.MODEL_HEARTBEAT,
        {
            "task_id": task_id,
            "elapsed_s": elapsed_s,
            "token_count": token_count,
            **kwargs,
        },
    )
