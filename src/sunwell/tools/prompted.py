"""Prompted Tool Calling for Small Models (RFC-029).

Enables tool use for models that don't support native tool calling APIs
by teaching them a simple tag-based format and parsing from text output.

Format:
    [TOOL:tool_name("arg1", "arg2")]

Examples:
    [TOOL:get_expertise("async patterns")]
    [TOOL:verify_against_expertise("def retry(): pass")]
    [TOOL:list_expertise_areas()]
"""


import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.models import ToolCall


# =============================================================================
# Tag Parser
# =============================================================================

# Pattern to match [TOOL:name(args)]
TOOL_TAG_PATTERN = re.compile(
    r'\[TOOL:(\w+)\(([^)]*)\)\]',
    re.DOTALL
)


@dataclass(frozen=True, slots=True)
class ParsedToolCall:
    """A tool call parsed from text output."""

    name: str
    arguments: dict[str, str]
    raw_match: str


def parse_tool_tags(text: str) -> list[ParsedToolCall]:
    """Parse tool tags from model text output.

    Args:
        text: Model output text that may contain [TOOL:name(args)] tags

    Returns:
        List of parsed tool calls
    """
    calls = []

    for match in TOOL_TAG_PATTERN.finditer(text):
        name = match.group(1)
        args_str = match.group(2).strip()

        # Parse arguments - handle simple quoted strings
        arguments = _parse_arguments(name, args_str)

        calls.append(ParsedToolCall(
            name=name,
            arguments=arguments,
            raw_match=match.group(0),
        ))

    return calls


def _parse_arguments(tool_name: str, args_str: str) -> dict[str, str]:
    """Parse argument string into dict.

    Handles:
        "topic"                    -> {"topic": "topic"}
        "async patterns"           -> {"topic": "async patterns"}
        "code here"                -> {"code": "code here"}
    """
    if not args_str:
        return {}

    # Remove surrounding quotes if present
    args_str = args_str.strip()
    if (args_str.startswith('"') and args_str.endswith('"')) or \
       (args_str.startswith("'") and args_str.endswith("'")):
        args_str = args_str[1:-1]

    # Map tool names to expected argument names
    arg_map = {
        "get_expertise": "topic",
        "verify_against_expertise": "code",
        "list_expertise_areas": None,  # No args
    }

    arg_name = arg_map.get(tool_name, "input")

    if arg_name is None:
        return {}

    return {arg_name: args_str}


def strip_tool_tags(text: str) -> str:
    """Remove tool tags from text, leaving the rest.

    Useful for getting the non-tool content from model output.
    """
    return TOOL_TAG_PATTERN.sub('', text).strip()


def has_tool_tags(text: str) -> bool:
    """Check if text contains any tool tags."""
    return bool(TOOL_TAG_PATTERN.search(text))


# =============================================================================
# System Prompt for Prompted Tool Calling
# =============================================================================

PROMPTED_TOOLS_SYSTEM = """## IMPORTANT: You MUST Use Expert Tools

Before writing any code, you MUST first request expert guidance using a tool tag.

### Tool Format
[TOOL:get_expertise("topic")]

### Required Steps

1. FIRST: Output a tool tag to get guidance
2. WAIT: You'll receive expert best practices
3. THEN: Write your code following that guidance

### Example

Task: Write a retry decorator

Your response MUST start with:
[TOOL:get_expertise("retry decorator patterns")]

Then after receiving guidance, write the code.

### Available Tools
- [TOOL:get_expertise("topic")] - Get best practices (USE THIS FIRST)
- [TOOL:verify_against_expertise("code")] - Check your code
- [TOOL:list_expertise_areas()] - See available topics

YOU MUST OUTPUT A TOOL TAG BEFORE WRITING CODE."""


def get_prompted_tools_system() -> str:
    """Get the system prompt for prompted tool calling."""
    return PROMPTED_TOOLS_SYSTEM


# =============================================================================
# Integration with Benchmark Runner
# =============================================================================

def convert_to_tool_calls(parsed: list[ParsedToolCall]) -> list[ToolCall]:
    """Convert parsed tool tags to ToolCall objects for consistency.

    This allows the same handler code to work with both native and
    prompted tool calling.
    """
    from sunwell.models import ToolCall

    return [
        ToolCall(
            id=f"prompted_{i}",
            name=p.name,
            arguments=p.arguments,
        )
        for i, p in enumerate(parsed)
    ]
