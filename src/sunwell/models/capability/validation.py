"""Validation-based retry loops for tool calling.

Provides structured validation feedback that enables models
to self-correct tool call errors.

Research Insight: Validation-based retry loops can improve
tool call success rate by 40%+ (LangGraph patterns).
"""

import json
from dataclasses import dataclass

from sunwell.models.protocol import Tool, ToolCall


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Result of tool call validation.

    Attributes:
        success: Whether validation passed.
        errors: List of validation errors.
        suggestions: Suggestions for fixing errors.
    """

    success: bool
    """Whether the tool call is valid."""

    errors: tuple[str, ...]
    """Validation error messages."""

    suggestions: tuple[str, ...]
    """Suggestions for fixing the errors."""


def validate_tool_call(tool_call: ToolCall, tool: Tool) -> ValidationResult:
    """Validate a tool call against its schema.

    Checks:
    - Required parameters are present
    - Parameter types match schema
    - Values are within valid ranges

    Args:
        tool_call: The tool call to validate
        tool: The tool definition with schema

    Returns:
        ValidationResult with errors and suggestions
    """
    errors: list[str] = []
    suggestions: list[str] = []

    schema = tool.parameters
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    arguments = tool_call.arguments

    # Check required parameters
    for param in required:
        if param not in arguments:
            errors.append(f"Missing required parameter: {param}")
            param_schema = properties.get(param, {})
            param_desc = param_schema.get("description", "")
            if param_desc:
                suggestions.append(f"Parameter '{param}': {param_desc}")
            else:
                suggestions.append(f"Add the '{param}' parameter")

    # Check parameter types
    for param, value in arguments.items():
        if param not in properties:
            errors.append(f"Unknown parameter: {param}")
            suggestions.append(f"Remove '{param}' or check spelling")
            continue

        param_schema = properties[param]
        expected_type = param_schema.get("type")

        if expected_type and not _type_matches(value, expected_type):
            errors.append(
                f"Parameter '{param}' has wrong type: "
                f"expected {expected_type}, got {type(value).__name__}"
            )
            suggestions.append(f"Convert '{param}' to {expected_type}")

    # Check enum constraints
    for param, value in arguments.items():
        if param in properties:
            enum_values = properties[param].get("enum")
            if enum_values and value not in enum_values:
                errors.append(
                    f"Parameter '{param}' has invalid value: "
                    f"got '{value}', expected one of {enum_values}"
                )
                suggestions.append(f"Use one of: {', '.join(str(v) for v in enum_values)}")

    return ValidationResult(
        success=len(errors) == 0,
        errors=tuple(errors),
        suggestions=tuple(suggestions),
    )


def _type_matches(value, expected_type: str) -> bool:
    """Check if a value matches the expected JSON Schema type."""
    type_map = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "array": list,
        "object": dict,
        "null": type(None),
    }

    expected = type_map.get(expected_type)
    if expected is None:
        return True  # Unknown type, assume valid

    return isinstance(value, expected)


def format_validation_feedback(result: ValidationResult, tool_name: str) -> str:
    """Format validation result for model feedback.

    Creates a structured message that helps the model
    understand and correct errors.

    Args:
        result: Validation result to format
        tool_name: Name of the tool

    Returns:
        Formatted feedback string
    """
    if result.success:
        return f"Tool call to '{tool_name}' is valid."

    lines = [f"Tool call to '{tool_name}' has validation errors:"]

    for error in result.errors:
        lines.append(f"  - {error}")

    if result.suggestions:
        lines.append("\nTo fix this:")
        for suggestion in result.suggestions:
            lines.append(f"  - {suggestion}")

    return "\n".join(lines)


def create_retry_prompt(
    tool_call: ToolCall,
    validation: ValidationResult,
    attempt: int,
) -> str:
    """Create a prompt for retrying a failed tool call.

    Args:
        tool_call: The failed tool call
        validation: Validation result with errors
        attempt: Current attempt number

    Returns:
        Prompt text for retry
    """
    lines = [
        f"Your tool call to '{tool_call.name}' failed validation (attempt {attempt}).",
        "",
        "Errors:",
    ]

    for error in validation.errors:
        lines.append(f"  - {error}")

    lines.append("")
    lines.append("Your original arguments:")
    lines.append(f"```json\n{json.dumps(tool_call.arguments, indent=2)}\n```")

    if validation.suggestions:
        lines.append("")
        lines.append("Suggestions:")
        for suggestion in validation.suggestions:
            lines.append(f"  - {suggestion}")

    lines.append("")
    lines.append("Please try again with corrected arguments.")

    return "\n".join(lines)
