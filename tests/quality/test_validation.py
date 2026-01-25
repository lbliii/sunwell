"""Tests for validation-based retry loops."""

import pytest

from sunwell.models.capability.validation import (
    ValidationResult,
    create_retry_prompt,
    format_validation_feedback,
    validate_tool_call,
)
from sunwell.models.core.protocol import Tool, ToolCall


class TestValidateToolCall:
    """Test tool call validation."""

    def test_valid_call(self):
        """Valid call should pass."""
        tool = Tool(
            name="read_file",
            description="Read a file",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        )
        call = ToolCall(id="1", name="read_file", arguments={"path": "test.py"})

        result = validate_tool_call(call, tool)

        assert result.success is True
        assert len(result.errors) == 0

    def test_missing_required_param(self):
        """Missing required param should fail."""
        tool = Tool(
            name="read_file",
            description="Read a file",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string", "description": "File path"}},
                "required": ["path"],
            },
        )
        call = ToolCall(id="1", name="read_file", arguments={})

        result = validate_tool_call(call, tool)

        assert result.success is False
        assert any("missing" in e.lower() for e in result.errors)
        assert len(result.suggestions) > 0

    def test_wrong_type(self):
        """Wrong type should fail."""
        tool = Tool(
            name="process",
            description="Process data",
            parameters={
                "type": "object",
                "properties": {"count": {"type": "integer"}},
            },
        )
        call = ToolCall(id="1", name="process", arguments={"count": "not an int"})

        result = validate_tool_call(call, tool)

        assert result.success is False
        assert any("wrong type" in e.lower() for e in result.errors)

    def test_unknown_param(self):
        """Unknown params should be flagged."""
        tool = Tool(
            name="test",
            description="Test",
            parameters={
                "type": "object",
                "properties": {"known": {"type": "string"}},
            },
        )
        call = ToolCall(id="1", name="test", arguments={"unknown": "value"})

        result = validate_tool_call(call, tool)

        assert result.success is False
        assert any("unknown" in e.lower() for e in result.errors)

    def test_invalid_enum_value(self):
        """Invalid enum value should fail."""
        tool = Tool(
            name="set_mode",
            description="Set mode",
            parameters={
                "type": "object",
                "properties": {"mode": {"type": "string", "enum": ["fast", "slow"]}},
            },
        )
        call = ToolCall(id="1", name="set_mode", arguments={"mode": "invalid"})

        result = validate_tool_call(call, tool)

        assert result.success is False
        assert any("invalid value" in e.lower() for e in result.errors)


class TestFormatValidationFeedback:
    """Test validation feedback formatting."""

    def test_success_format(self):
        """Success should have positive message."""
        result = ValidationResult(success=True, errors=(), suggestions=())
        formatted = format_validation_feedback(result, "test_tool")

        assert "valid" in formatted.lower()

    def test_error_format(self):
        """Errors should be listed."""
        result = ValidationResult(
            success=False,
            errors=("Missing required parameter: path",),
            suggestions=("Add the 'path' parameter",),
        )
        formatted = format_validation_feedback(result, "read_file")

        assert "validation errors" in formatted.lower()
        assert "path" in formatted


class TestCreateRetryPrompt:
    """Test retry prompt creation."""

    def test_includes_errors(self):
        """Prompt should include errors."""
        call = ToolCall(id="1", name="test", arguments={"bad": "value"})
        validation = ValidationResult(
            success=False,
            errors=("Unknown parameter: bad",),
            suggestions=("Remove 'bad'",),
        )

        prompt = create_retry_prompt(call, validation, attempt=1)

        assert "failed validation" in prompt.lower()
        assert "unknown parameter" in prompt.lower()
        assert "attempt 1" in prompt.lower()

    def test_includes_original_args(self):
        """Prompt should show original arguments."""
        call = ToolCall(id="1", name="test", arguments={"key": "value"})
        validation = ValidationResult(success=False, errors=("Error",), suggestions=())

        prompt = create_retry_prompt(call, validation, attempt=1)

        assert '"key"' in prompt
        assert '"value"' in prompt
