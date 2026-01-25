"""Tests for structured tool errors.

Covers Journeys A6 (Receive result), A7 (Handle result), A9 (Retry/escalate),
A10 (Escalate/abort), H9 (Debug failure), E7 (Rate limit), E8 (Network failure).
"""

import asyncio

import pytest

from sunwell.tools.errors import (
    ToolError,
    ToolErrorCode,
    format_error_for_model,
    get_retry_strategy,
    should_retry,
)


class TestToolErrorFromException:
    """Test ToolError.from_exception() mapping (Journey A6)."""

    def test_file_not_found(self):
        """FileNotFoundError maps to NOT_FOUND."""
        e = FileNotFoundError("foo.py")
        error = ToolError.from_exception(e, "read_file")

        assert error.code == ToolErrorCode.NOT_FOUND
        assert error.recoverable is True
        assert error.retry_strategy == "rephrase"
        assert error.suggested_fix is not None

    def test_permission_denied(self):
        """PermissionError maps to PERMISSION (unrecoverable)."""
        e = PermissionError("Cannot write to /etc/passwd")
        error = ToolError.from_exception(e, "write_file")

        assert error.code == ToolErrorCode.PERMISSION
        assert error.recoverable is False
        assert error.retry_strategy == "abort"
        assert "security" in error.suggested_fix.lower()

    def test_timeout(self):
        """TimeoutError maps to TIMEOUT."""
        e = TimeoutError()
        error = ToolError.from_exception(e, "run_command")

        assert error.code == ToolErrorCode.TIMEOUT
        assert error.recoverable is True
        assert error.retry_strategy == "same"

    def test_value_error(self):
        """ValueError maps to VALIDATION."""
        e = ValueError("Invalid argument: negative number")
        error = ToolError.from_exception(e, "process_data")

        assert error.code == ToolErrorCode.VALIDATION
        assert error.recoverable is True
        assert error.retry_strategy == "rephrase"

    def test_type_error(self):
        """TypeError maps to VALIDATION."""
        e = TypeError("Expected string, got int")
        error = ToolError.from_exception(e, "format_text")

        assert error.code == ToolErrorCode.VALIDATION
        assert error.recoverable is True

    def test_rate_limit(self):
        """Rate limit messages map to RATE_LIMIT (E7)."""
        e = Exception("Rate limit exceeded: too many requests")
        error = ToolError.from_exception(e, "api_call")

        assert error.code == ToolErrorCode.RATE_LIMIT
        assert error.recoverable is True
        assert error.retry_strategy == "same"

    def test_network_failure(self):
        """Network errors map to NETWORK (E8)."""
        e = Exception("Connection refused to api.example.com")
        error = ToolError.from_exception(e, "web_fetch")

        assert error.code == ToolErrorCode.NETWORK
        assert error.recoverable is True
        assert error.retry_strategy == "same"

    def test_cancelled(self):
        """CancelledError maps to CANCELLED."""
        e = asyncio.CancelledError()
        error = ToolError.from_exception(e, "long_task")

        assert error.code == ToolErrorCode.CANCELLED
        assert error.recoverable is False
        assert error.retry_strategy == "abort"

    def test_unknown_exception(self):
        """Unknown exceptions map to EXECUTION."""
        e = RuntimeError("Something unexpected happened")
        error = ToolError.from_exception(e, "process")

        assert error.code == ToolErrorCode.EXECUTION
        assert error.recoverable is True
        assert error.retry_strategy == "escalate"
        assert error.details is not None
        assert error.details["exception_type"] == "RuntimeError"


class TestShouldRetry:
    """Test retry decision logic (Journeys A7, A9)."""

    def test_recoverable_error_first_attempt(self):
        """Recoverable errors should retry on first attempt."""
        error = ToolError(
            code=ToolErrorCode.NOT_FOUND,
            message="File not found",
            recoverable=True,
            retry_strategy="rephrase",
        )
        assert should_retry(error, attempt=1) is True

    def test_recoverable_error_max_attempts(self):
        """Should not retry after max attempts."""
        error = ToolError(
            code=ToolErrorCode.TIMEOUT,
            message="Timed out",
            recoverable=True,
            retry_strategy="same",
        )
        assert should_retry(error, attempt=1) is True
        assert should_retry(error, attempt=2) is True
        assert should_retry(error, attempt=3) is False

    def test_unrecoverable_error(self):
        """Unrecoverable errors should not retry (A10)."""
        error = ToolError(
            code=ToolErrorCode.PERMISSION,
            message="Permission denied",
            recoverable=False,
            retry_strategy="abort",
        )
        assert should_retry(error, attempt=1) is False

    def test_abort_strategy(self):
        """Abort strategy should not retry."""
        error = ToolError(
            code=ToolErrorCode.CANCELLED,
            message="Cancelled",
            recoverable=False,
            retry_strategy="abort",
        )
        assert should_retry(error, attempt=1) is False


class TestGetRetryStrategy:
    """Test retry strategy selection (Journey A9)."""

    def test_same_strategy(self):
        """Same strategy returns same on all attempts."""
        error = ToolError(
            code=ToolErrorCode.TIMEOUT,
            message="Timeout",
            recoverable=True,
            retry_strategy="same",
        )
        assert get_retry_strategy(error, attempt=1) == "same"
        assert get_retry_strategy(error, attempt=2) == "same"
        assert get_retry_strategy(error, attempt=3) == "same"

    def test_rephrase_escalates(self):
        """Rephrase strategy escalates over attempts."""
        error = ToolError(
            code=ToolErrorCode.VALIDATION,
            message="Invalid args",
            recoverable=True,
            retry_strategy="rephrase",
        )
        assert get_retry_strategy(error, attempt=1) == "rephrase"
        assert get_retry_strategy(error, attempt=2) == "interference"
        assert get_retry_strategy(error, attempt=3) == "vortex"

    def test_escalate_strategy(self):
        """Escalate strategy progresses through levels."""
        error = ToolError(
            code=ToolErrorCode.EXECUTION,
            message="Failed",
            recoverable=True,
            retry_strategy="escalate",
        )
        assert get_retry_strategy(error, attempt=1) == "same"
        assert get_retry_strategy(error, attempt=2) == "interference"
        assert get_retry_strategy(error, attempt=3) == "vortex"

    def test_abort_strategy(self):
        """Abort strategy returns abort."""
        error = ToolError(
            code=ToolErrorCode.PERMISSION,
            message="Denied",
            recoverable=False,
            retry_strategy="abort",
        )
        assert get_retry_strategy(error, attempt=1) == "abort"


class TestFormatErrorForModel:
    """Test error formatting for model consumption (Journey H9)."""

    def test_basic_format(self):
        """Error is formatted with code and message."""
        error = ToolError(
            code=ToolErrorCode.NOT_FOUND,
            message="File not found: test.py",
            recoverable=True,
        )
        formatted = format_error_for_model(error)

        assert "not_found" in formatted
        assert "test.py" in formatted

    def test_includes_suggestion(self):
        """Suggested fix is included."""
        error = ToolError(
            code=ToolErrorCode.VALIDATION,
            message="Invalid path",
            recoverable=True,
            suggested_fix="Check the path format",
        )
        formatted = format_error_for_model(error)

        assert "Check the path format" in formatted

    def test_unrecoverable_warning(self):
        """Unrecoverable errors have warning."""
        error = ToolError(
            code=ToolErrorCode.PERMISSION,
            message="Denied",
            recoverable=False,
        )
        formatted = format_error_for_model(error)

        assert "cannot be resolved" in formatted.lower()


class TestToolErrorDataclass:
    """Test ToolError dataclass properties."""

    def test_immutable(self):
        """ToolError should be immutable."""
        error = ToolError(
            code=ToolErrorCode.EXECUTION,
            message="Test",
            recoverable=True,
        )
        with pytest.raises(AttributeError):
            error.message = "changed"  # type: ignore

    def test_default_values(self):
        """Default values should be sensible."""
        error = ToolError(
            code=ToolErrorCode.EXECUTION,
            message="Test",
            recoverable=True,
        )
        assert error.retry_strategy is None
        assert error.suggested_fix is None
        assert error.details is None


class TestToolErrorCode:
    """Test ToolErrorCode enum."""

    def test_all_codes_exist(self):
        """All expected codes should exist."""
        assert ToolErrorCode.VALIDATION
        assert ToolErrorCode.PERMISSION
        assert ToolErrorCode.NOT_FOUND
        assert ToolErrorCode.TIMEOUT
        assert ToolErrorCode.RATE_LIMIT
        assert ToolErrorCode.MODEL_REFUSAL
        assert ToolErrorCode.EXECUTION
        assert ToolErrorCode.NETWORK
        assert ToolErrorCode.CANCELLED

    def test_values(self):
        """Codes should have string values."""
        assert ToolErrorCode.VALIDATION.value == "validation"
        assert ToolErrorCode.TIMEOUT.value == "timeout"
