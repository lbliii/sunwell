"""Tool call normalization for different model formats.

Handles model-specific quirks and repairs common issues in tool call output:
- Llama: Extra whitespace, trailing commas
- Qwen: Sometimes uses 'function' key instead of 'tool'
- Small models: Nested arguments, missing fields, malformed JSON
"""

import json
import re
from dataclasses import dataclass

from sunwell.models.protocol import ToolCall


@dataclass(frozen=True, slots=True)
class NormalizationResult:
    """Result of tool call normalization."""

    tool_calls: tuple[ToolCall, ...]
    """Normalized tool calls extracted from the response."""

    repairs: tuple[str, ...]
    """Description of repairs made during normalization."""

    remaining_text: str
    """Text not part of tool calls (prose, explanations, etc.)."""


class ToolCallNormalizer:
    """Normalize tool calls from different model formats.

    Handles model-specific quirks:
    - Llama: Extra whitespace, inconsistent JSON
    - Qwen: Sometimes uses 'function' key instead of 'tool'
    - Small models: Nested arguments, missing fields
    """

    # Pattern for JSON in code blocks
    _JSON_BLOCK = re.compile(
        r"```(?:json)?\s*\n?(\{[^`]+\})\s*\n?```",
        re.DOTALL,
    )

    # Pattern for inline JSON tool calls (handles quoted and unquoted keys)
    _INLINE_JSON = re.compile(
        r'\{["\']?(?:tool|function|name)["\']?:\s*["\'][^}]+\}',
        re.DOTALL,
    )

    # Pattern for XML tool calls
    _XML_TOOL_CALL = re.compile(
        r"<tool_call>\s*<name>([^<]+)</name>\s*<arguments>(.*?)</arguments>\s*</tool_call>",
        re.DOTALL,
    )

    def normalize(
        self,
        response_text: str,
        model_family: str | None = None,
    ) -> NormalizationResult:
        """Normalize tool calls from model response.

        Args:
            response_text: Raw model response text
            model_family: Model family for family-specific handling

        Returns:
            NormalizationResult with parsed tool calls
        """
        tool_calls: list[ToolCall] = []
        repairs: list[str] = []
        remaining = response_text

        # Try JSON blocks first (most common)
        for match in self._JSON_BLOCK.finditer(response_text):
            json_str = match.group(1)
            tc, repair = self._parse_tool_json(json_str, model_family)
            if tc:
                tool_calls.append(tc)
                repairs.extend(repair)
                remaining = remaining.replace(match.group(0), "", 1)

        # Try inline JSON
        for match in self._INLINE_JSON.finditer(remaining):
            json_str = match.group(0)
            tc, repair = self._parse_tool_json(json_str, model_family)
            if tc:
                tool_calls.append(tc)
                repairs.extend(repair)
                remaining = remaining.replace(match.group(0), "", 1)

        # Try XML format
        for match in self._XML_TOOL_CALL.finditer(remaining):
            tc, repair = self._parse_xml_tool_call(match)
            if tc:
                tool_calls.append(tc)
                repairs.extend(repair)
                remaining = remaining.replace(match.group(0), "", 1)

        return NormalizationResult(
            tool_calls=tuple(tool_calls),
            repairs=tuple(repairs),
            remaining_text=remaining.strip(),
        )

    def _parse_tool_json(
        self,
        json_str: str,
        model_family: str | None,
    ) -> tuple[ToolCall | None, list[str]]:
        """Parse a JSON string into a ToolCall.

        Handles model-specific quirks and repairs common issues.
        """
        repairs: list[str] = []

        # Clean up common issues
        json_str = json_str.strip()

        # Llama: Often adds trailing commas
        if model_family == "llama":
            original = json_str
            json_str = re.sub(r",\s*}", "}", json_str)
            json_str = re.sub(r",\s*]", "]", json_str)
            if json_str != original:
                repairs.append("Removed trailing commas (Llama quirk)")

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            # Try to repair common JSON errors
            repaired = self._repair_json(json_str)
            if repaired:
                repairs.append("Repaired malformed JSON")
                try:
                    data = json.loads(repaired)
                except json.JSONDecodeError:
                    return None, repairs
            else:
                return None, repairs

        # Extract tool name (handle various key names)
        tool_name = (
            data.get("tool")
            or data.get("function")
            or data.get("name")
            or data.get("tool_name")
        )
        if not tool_name:
            return None, repairs

        if "function" in data and "tool" not in data:
            repairs.append("Mapped 'function' key to 'tool' (Qwen quirk)")

        # Extract arguments (handle various key names)
        args = (
            data.get("arguments")
            or data.get("args")
            or data.get("parameters")
            or data.get("params")
            or data.get("input")
            or {}
        )

        if "args" in data and "arguments" not in data:
            repairs.append("Mapped 'args' key to 'arguments'")

        # Handle nested arguments (small model quirk)
        if isinstance(args, dict) and "arguments" in args and len(args) == 1:
            repairs.append("Unnested double-wrapped arguments")
            args = args["arguments"]

        # Ensure args is a dict
        if not isinstance(args, dict):
            repairs.append("Converted non-dict arguments to empty dict")
            args = {}

        # Generate ID
        tool_id = f"normalized_{hash(json_str) % 10000}"

        return ToolCall(id=tool_id, name=tool_name, arguments=args), repairs

    def _parse_xml_tool_call(
        self,
        match: re.Match[str],
    ) -> tuple[ToolCall | None, list[str]]:
        """Parse an XML-style tool call."""
        repairs: list[str] = []

        tool_name = match.group(1).strip()
        args_xml = match.group(2).strip()

        # Parse XML arguments
        args: dict[str, str] = {}
        arg_pattern = re.compile(r"<(\w+)>([^<]*)</\1>")
        for arg_match in arg_pattern.finditer(args_xml):
            args[arg_match.group(1)] = arg_match.group(2)

        repairs.append("Parsed XML-style tool call")

        tool_id = f"xml_{hash(match.group(0)) % 10000}"
        return ToolCall(id=tool_id, name=tool_name, arguments=args), repairs

    def _repair_json(self, json_str: str) -> str | None:
        """Attempt to repair malformed JSON.

        Common repairs:
        - Single quotes → double quotes
        - Unquoted keys
        - Trailing commas
        - Missing closing braces
        """
        repaired = json_str

        # Single quotes to double quotes
        repaired = re.sub(r"'([^']*)'", r'"\1"', repaired)

        # Unquoted keys
        repaired = re.sub(
            r"(\{|,)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:", r'\1"\2":', repaired
        )

        # Trailing commas
        repaired = re.sub(r",\s*}", "}", repaired)
        repaired = re.sub(r",\s*]", "]", repaired)

        # Try to balance braces if missing
        open_braces = repaired.count("{")
        close_braces = repaired.count("}")
        if open_braces > close_braces:
            repaired += "}" * (open_braces - close_braces)

        # Validate it's parseable
        try:
            json.loads(repaired)
            return repaired
        except json.JSONDecodeError:
            return None
