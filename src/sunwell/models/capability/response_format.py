"""Response format control for tool results.

Controls the verbosity of tool result output to optimize
token usage while maintaining usefulness.

Research Insight: Concise mode can save ~70% tokens
without significant information loss.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ResponseFormat(Enum):
    """Response verbosity levels."""

    DETAILED = "detailed"
    """Full output with all context."""

    CONCISE = "concise"
    """Summarized output with key information."""

    MINIMAL = "minimal"
    """Bare minimum output (success/failure + key data)."""


@dataclass(frozen=True, slots=True)
class FormattedResult:
    """A formatted tool result.

    Attributes:
        content: The formatted content string.
        original_length: Original content length.
        formatted_length: Formatted content length.
        format_used: Format level applied.
    """

    content: str
    """Formatted result content."""

    original_length: int
    """Original content length in characters."""

    formatted_length: int
    """Formatted content length in characters."""

    format_used: ResponseFormat
    """Format level that was applied."""

    @property
    def compression_ratio(self) -> float:
        """Calculate compression ratio."""
        if self.original_length == 0:
            return 1.0
        return self.formatted_length / self.original_length


def format_tool_result(
    result: Any,
    format_level: ResponseFormat = ResponseFormat.DETAILED,
    max_length: int | None = None,
) -> FormattedResult:
    """Format a tool result according to the specified format level.

    Args:
        result: Raw tool result (string, dict, etc.)
        format_level: Desired verbosity level
        max_length: Optional maximum length for output

    Returns:
        FormattedResult with formatted content
    """
    # Convert result to string
    if isinstance(result, str):
        original = result
    elif isinstance(result, dict):
        import json

        original = json.dumps(result, indent=2)
    elif isinstance(result, (list, tuple)):
        import json

        original = json.dumps(list(result), indent=2)
    else:
        original = str(result)

    original_len = len(original)

    # Apply format level
    if format_level == ResponseFormat.DETAILED:
        formatted = original
    elif format_level == ResponseFormat.CONCISE:
        formatted = _make_concise(original)
    else:  # MINIMAL
        formatted = _make_minimal(original)

    # Apply max length if specified
    if max_length and len(formatted) > max_length:
        formatted = formatted[: max_length - 3] + "..."

    return FormattedResult(
        content=formatted,
        original_length=original_len,
        formatted_length=len(formatted),
        format_used=format_level,
    )


def _make_concise(text: str) -> str:
    """Make text concise by removing redundancy."""
    lines = text.split("\n")

    # Remove empty lines
    lines = [line for line in lines if line.strip()]

    # Truncate very long lines
    lines = [line[:200] + "..." if len(line) > 200 else line for line in lines]

    # Limit total lines
    if len(lines) > 20:
        lines = lines[:18] + ["...", f"({len(lines) - 18} more lines)"]

    return "\n".join(lines)


def _make_minimal(text: str) -> str:
    """Make text minimal - just essential info."""
    lines = text.split("\n")

    # Take first few non-empty lines
    non_empty = [line.strip() for line in lines if line.strip()]
    if len(non_empty) > 5:
        return "\n".join(non_empty[:5]) + f"\n... ({len(non_empty) - 5} more)"

    return "\n".join(non_empty)


def get_recommended_format(
    context_remaining: int | None,
    result_size: int,
) -> ResponseFormat:
    """Get recommended format based on context constraints.

    Args:
        context_remaining: Remaining context window tokens (None = unlimited)
        result_size: Size of the result to format

    Returns:
        Recommended ResponseFormat
    """
    if context_remaining is None:
        return ResponseFormat.DETAILED

    # Estimate tokens (rough: 4 chars per token)
    result_tokens = result_size // 4

    # Check strictest constraint first
    # If result would take more than 50%, use minimal
    if result_tokens > context_remaining * 0.5:
        return ResponseFormat.MINIMAL

    # If result would take more than 20% of remaining context, use concise
    if result_tokens > context_remaining * 0.2:
        return ResponseFormat.CONCISE

    return ResponseFormat.DETAILED
