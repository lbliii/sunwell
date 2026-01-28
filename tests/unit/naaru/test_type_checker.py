"""Tests for mypy type checker integration."""

import pytest

from sunwell.planning.naaru.verification.type_checker import (
    _parse_mypy_output,
    parse_protocol_errors,
)
from sunwell.planning.naaru.verification.types import TypeCheckResult


class TestParseMypyOutput:
    """Tests for _parse_mypy_output function."""

    def test_parse_errors(self) -> None:
        """Parse error lines from mypy output."""
        stdout = """
service.py:10: error: Missing return statement [return]
service.py:15: error: Incompatible return type [return-value]
Found 2 errors in 1 file
"""
        errors, warnings = _parse_mypy_output(stdout, "")

        assert len(errors) == 2
        assert "Missing return statement" in errors[0]
        assert "Incompatible return type" in errors[1]

    def test_parse_warnings(self) -> None:
        """Parse warning and note lines from mypy output."""
        stdout = """
service.py:5: warning: Unused variable [var-not-used]
service.py:8: note: See documentation for details
"""
        errors, warnings = _parse_mypy_output(stdout, "")

        assert len(errors) == 0
        assert len(warnings) == 2

    def test_filter_summary_lines(self) -> None:
        """Filter out summary lines."""
        stdout = """
service.py:10: error: Type error [type-error]
Found 1 error in 1 file
Success: no issues found
"""
        errors, warnings = _parse_mypy_output(stdout, "")

        assert len(errors) == 1
        assert "Found" not in errors[0]
        assert "Success" not in errors[0]

    def test_empty_output(self) -> None:
        """Handle empty output."""
        errors, warnings = _parse_mypy_output("", "")

        assert len(errors) == 0
        assert len(warnings) == 0


class TestParseProtocolErrors:
    """Tests for parse_protocol_errors function."""

    def test_detect_protocol_incompatibility(self) -> None:
        """Detect Protocol incompatibility errors."""
        output = """
error: Type "UserService" is not compatible with Protocol "UserProtocol"
note: "UserService" is missing method "get_name"
"""
        errors = parse_protocol_errors(output)

        assert len(errors) == 2

    def test_detect_missing_method(self) -> None:
        """Detect missing method errors."""
        output = """
error: Class "Service" is missing method "process"
"""
        errors = parse_protocol_errors(output)

        assert len(errors) == 1
        assert "missing" in errors[0].lower()

    def test_detect_incompatible_signature(self) -> None:
        """Detect incompatible signature errors."""
        output = """
error: Method has incompatible signature with Protocol
error: Incompatible return type "int" expected "str"
"""
        errors = parse_protocol_errors(output)

        assert len(errors) == 2

    def test_detect_incompatible_argument_type(self) -> None:
        """Detect incompatible argument type errors."""
        output = """
error: Argument 1 has incompatible argument type "int"; expected "str"
"""
        errors = parse_protocol_errors(output)

        assert len(errors) == 1

    def test_ignore_non_protocol_errors(self) -> None:
        """Ignore errors not related to Protocol compliance."""
        output = """
error: Name "undefined_var" is not defined
error: Unsupported operand types for +
"""
        errors = parse_protocol_errors(output)

        assert len(errors) == 0


class TestTypeCheckResult:
    """Tests for TypeCheckResult dataclass."""

    def test_passed_result(self) -> None:
        """Create a passed result."""
        result = TypeCheckResult(
            passed=True,
            errors=(),
            warnings=(),
            exit_code=0,
            duration_ms=100,
        )

        assert result.passed is True
        assert len(result.errors) == 0

    def test_failed_result(self) -> None:
        """Create a failed result."""
        result = TypeCheckResult(
            passed=False,
            errors=("Type error found",),
            warnings=(),
            exit_code=1,
            duration_ms=250,
        )

        assert result.passed is False
        assert len(result.errors) == 1
        assert result.exit_code == 1

    def test_immutable(self) -> None:
        """TypeCheckResult fields are immutable (tuple)."""
        result = TypeCheckResult(
            passed=True,
            errors=("error1", "error2"),
            warnings=(),
            exit_code=0,
        )

        # Attempting to modify should fail (tuples are immutable)
        with pytest.raises((TypeError, AttributeError)):
            result.errors.append("error3")  # type: ignore
