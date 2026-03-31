"""Structured logging helpers for tool surface and lifecycle (RFC observability)."""

import logging

logger = logging.getLogger(__name__)


def log_tool_surface_assembled(
    *,
    tool_count: int,
    total_estimated_tokens: int,
    fingerprint: str,
    deferred_count: int,
) -> None:
    logger.info(
        "tool_surface_assembled",
        extra={
            "event": "tool_surface_assembled",
            "tool_count": tool_count,
            "total_estimated_tokens": total_estimated_tokens,
            "fingerprint": fingerprint,
            "deferred_count": deferred_count,
        },
    )


def log_tool_collision(tool_name: str, winning_source: str, losing_source: str) -> None:
    logger.warning(
        "tool_collision_resolved",
        extra={
            "event": "tool_collision_resolved",
            "tool_name": tool_name,
            "winning_source": winning_source,
            "losing_source": losing_source,
        },
    )


def log_tool_deferred(tool_name: str, schema_token_estimate: int, reason: str) -> None:
    logger.info(
        "tool_deferred",
        extra={
            "event": "tool_deferred",
            "tool_name": tool_name,
            "schema_token_estimate": schema_token_estimate,
            "reason": reason,
        },
    )


def log_tool_materialized(tool_name: str, trigger: str) -> None:
    logger.info(
        "tool_materialized",
        extra={
            "event": "tool_materialized",
            "tool_name": tool_name,
            "trigger": trigger,
        },
    )


def log_generate_tool_surface_tokens(total_estimated_tokens: int, fingerprint: str) -> None:
    """Per model.generate() call — surface token budget for prompt debugging."""
    logger.info(
        "model_generate_tool_surface",
        extra={
            "event": "model_generate_tool_surface",
            "total_estimated_tokens": total_estimated_tokens,
            "fingerprint": fingerprint,
        },
    )
