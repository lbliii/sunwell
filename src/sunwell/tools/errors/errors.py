"""Structured tool errors with recovery hints.

Provides categorized error codes and intelligent retry strategies
based on error type. Enables systematic error handling and escalation.

Research Insight: Error responses should steer agents toward
better behavior with specific, actionable guidance (MCP best practices).
"""

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Literal


class ToolErrorCode(Enum):
    """Categorized tool error codes for intelligent handling."""

    VALIDATION = "validation"
    """Bad arguments (missing, wrong type, invalid format)."""

    PERMISSION = "permission"
    """Path security, trust level insufficient."""

    NOT_FOUND = "not_found"
    """File, resource, or tool not found."""

    TIMEOUT = "timeout"
    """Operation timed out."""

    RATE_LIMIT = "rate_limit"
    """Rate limit exceeded."""

    MODEL_REFUSAL = "model_refusal"
    """Model refused to call tool or provided invalid call."""

    EXECUTION = "execution"
    """Runtime error during tool execution."""

    NETWORK = "network"
    """Network-related failure (for web tools)."""

    CANCELLED = "cancelled"
    """Operation was cancelled by user or system."""


@dataclass(frozen=True, slots=True)
class ToolError:
    """Structured tool execution error with recovery hints.

    Enables intelligent retry strategies based on error type.

    Attributes:
        code: Categorized error code.
        message: Human-readable error message.
        recoverable: Whether this error might succeed on retry.
        retry_strategy: Suggested retry approach.
        suggested_fix: Specific suggestion for fixing the error.
        details: Additional error context.
    """

    code: ToolErrorCode
    """Categorized error code."""

    message: str
    """Human-readable error message."""

    recoverable: bool
    """Whether this error might succeed on retry."""

    retry_strategy: Literal["same", "rephrase", "escalate", "abort"] | None = None
    """Suggested retry approach:
    - same: Retry with identical arguments (transient error)
    - rephrase: Have model try different arguments
    - escalate: Use more capable strategy (interference/vortex)
    - abort: Don't retry, escalate to user
    """

    suggested_fix: str | None = None
    """Specific suggestion for fixing the error."""

    details: dict | None = None
    """Additional error context."""

    @classmethod
    def from_exception(cls, e: Exception, tool_name: str) -> ToolError:
        """Create ToolError from a Python exception.

        Maps exception types to error codes and recovery strategies.

        Research Insight: Error responses should steer agents toward
        better behavior with specific, actionable guidance.

        Args:
            e: The exception that occurred
            tool_name: Name of the tool that failed

        Returns:
            ToolError with appropriate categorization and hints
        """
        # FileNotFoundError
        if isinstance(e, FileNotFoundError):
            return cls(
                code=ToolErrorCode.NOT_FOUND,
                message=str(e),
                recoverable=True,
                retry_strategy="rephrase",
                suggested_fix=(
                    "File not found. Try:\n"
                    "1. Use list_files to see available files in the directory\n"
                    "2. Check if path is relative vs absolute\n"
                    "3. Verify the parent directory exists"
                ),
            )

        # PermissionError
        if isinstance(e, PermissionError):
            return cls(
                code=ToolErrorCode.PERMISSION,
                message=str(e),
                recoverable=False,
                retry_strategy="abort",
                suggested_fix=(
                    "Permission denied. This path may be:\n"
                    "- Outside the workspace directory\n"
                    "- A protected system file\n"
                    "- Blocked by security policy"
                ),
            )

        # TimeoutError / asyncio.TimeoutError
        if isinstance(e, TimeoutError):
            return cls(
                code=ToolErrorCode.TIMEOUT,
                message=f"Tool {tool_name} timed out",
                recoverable=True,
                retry_strategy="same",
                suggested_fix=(
                    "Operation timed out. Try:\n"
                    "1. Break into smaller operations\n"
                    "2. Use more specific filters/parameters\n"
                    "3. Check if the resource is responding"
                ),
            )

        # ValueError (validation errors)
        if isinstance(e, ValueError):
            return cls(
                code=ToolErrorCode.VALIDATION,
                message=str(e),
                recoverable=True,
                retry_strategy="rephrase",
                suggested_fix=(
                    f"Invalid arguments for {tool_name}. Try:\n"
                    "1. Check the expected parameter types\n"
                    "2. Ensure required parameters are provided\n"
                    "3. Verify values are within valid ranges"
                ),
            )

        # TypeError (validation errors)
        if isinstance(e, TypeError):
            return cls(
                code=ToolErrorCode.VALIDATION,
                message=str(e),
                recoverable=True,
                retry_strategy="rephrase",
                suggested_fix=(
                    f"Type error in {tool_name} arguments. Try:\n"
                    "1. Check parameter types match expected types\n"
                    "2. Ensure strings are quoted, numbers are not\n"
                    "3. Verify list/dict parameters are properly formatted"
                ),
            )

        # KeyboardInterrupt / CancelledError
        if isinstance(e, (KeyboardInterrupt, asyncio.CancelledError)):
            return cls(
                code=ToolErrorCode.CANCELLED,
                message="Operation was cancelled",
                recoverable=False,
                retry_strategy="abort",
            )

        # Check for rate limit errors (by message content)
        error_str = str(e).lower()
        if "rate limit" in error_str or "too many requests" in error_str:
            return cls(
                code=ToolErrorCode.RATE_LIMIT,
                message=str(e),
                recoverable=True,
                retry_strategy="same",
                suggested_fix=(
                    "Rate limited. The operation will be retried automatically.\n"
                    "Consider batching similar operations to reduce API calls."
                ),
            )

        # Check for network-related errors
        if any(word in error_str for word in ["connection", "network", "dns", "socket", "refused"]):
            return cls(
                code=ToolErrorCode.NETWORK,
                message=str(e),
                recoverable=True,
                retry_strategy="same",
                suggested_fix=(
                    "Network error. This is usually transient.\n"
                    "The operation will be retried automatically."
                ),
            )

        # Default: execution error
        return cls(
            code=ToolErrorCode.EXECUTION,
            message=str(e),
            recoverable=True,
            retry_strategy="escalate",
            suggested_fix=(
                f"Tool '{tool_name}' failed unexpectedly.\n"
                "Consider trying with different parameters or an alternative approach."
            ),
            details={"exception_type": type(e).__name__},
        )


def should_retry(error: ToolError, attempt: int, max_attempts: int = 3) -> bool:
    """Determine if a tool call should be retried.

    Args:
        error: The error that occurred
        attempt: Current attempt number (1-indexed)
        max_attempts: Maximum retry attempts

    Returns:
        True if should retry
    """
    if not error.recoverable:
        return False

    if attempt >= max_attempts:
        return False

    if error.retry_strategy == "abort":
        return False

    return True


def get_retry_strategy(error: ToolError, attempt: int) -> str:
    """Get the appropriate retry strategy based on error and attempt.

    Escalates strategy as attempts increase.

    Args:
        error: The error that occurred
        attempt: Current attempt number

    Returns:
        Strategy name: "same", "rephrase", "interference", "vortex"
    """
    # Unrecoverable errors should abort
    if not error.recoverable or error.retry_strategy == "abort":
        return "abort"

    # Same strategy stays the same
    if error.retry_strategy == "same":
        return "same"

    # Rephrase escalates after first attempt
    if error.retry_strategy == "rephrase":
        if attempt == 1:
            return "rephrase"
        if attempt == 2:
            return "interference"
        return "vortex"

    # Escalate pattern
    if error.retry_strategy == "escalate":
        if attempt == 1:
            return "same"
        if attempt == 2:
            return "interference"
        return "vortex"

    return "same"


def format_error_for_model(error: ToolError) -> str:
    """Format error for inclusion in model prompt.

    Creates a structured, actionable error message that helps
    the model correct its approach.

    Args:
        error: The error to format

    Returns:
        Formatted error string for model consumption
    """
    parts = [f"Error: {error.code.value}"]
    parts.append(f"Message: {error.message}")

    if error.suggested_fix:
        parts.append(f"\nSuggestion:\n{error.suggested_fix}")

    if not error.recoverable:
        parts.append("\nThis error cannot be resolved by retrying.")

    return "\n".join(parts)
