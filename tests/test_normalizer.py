"""Tests for tool call normalization.

Covers Journeys A4 (Parse tool calls), E1 (Model refuses), E2 (Malformed JSON).
"""

import pytest

from sunwell.models.capability.normalizer import NormalizationResult, ToolCallNormalizer


class TestNormalizeStandardJSON:
    """Test normalization of standard JSON tool calls."""

    def test_json_block_format(self):
        """Parse tool call from JSON code block."""
        normalizer = ToolCallNormalizer()
        result = normalizer.normalize('''
        Here's what I'll do:

        ```json
        {"tool": "write_file", "arguments": {"path": "test.py", "content": "print('hi')"}}
        ```
        ''')

        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "write_file"
        assert result.tool_calls[0].arguments["path"] == "test.py"

    def test_inline_json_format(self):
        """Parse tool call from inline JSON."""
        normalizer = ToolCallNormalizer()
        result = normalizer.normalize('''
        {"tool": "read_file", "arguments": {"path": "test.py"}}
        ''')

        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "read_file"

    def test_multiple_tool_calls(self):
        """Parse multiple tool calls from response."""
        normalizer = ToolCallNormalizer()
        result = normalizer.normalize('''
        ```json
        {"tool": "read_file", "arguments": {"path": "a.py"}}
        ```

        ```json
        {"tool": "read_file", "arguments": {"path": "b.py"}}
        ```
        ''')

        assert len(result.tool_calls) == 2

    def test_remaining_text_extracted(self):
        """Text around tool calls should be preserved."""
        normalizer = ToolCallNormalizer()
        result = normalizer.normalize('''
        I'll read the file first.

        ```json
        {"tool": "read_file", "arguments": {"path": "test.py"}}
        ```

        Let me analyze the contents.
        ''')

        assert "read the file" in result.remaining_text
        assert "analyze the contents" in result.remaining_text


class TestNormalizeLlamaQuirks:
    """Test Llama-specific quirk handling."""

    def test_trailing_commas(self):
        """Llama often adds trailing commas."""
        normalizer = ToolCallNormalizer()
        result = normalizer.normalize(
            '{"tool": "read_file", "arguments": {"path": "test.py",}}',
            model_family="llama",
        )

        assert len(result.tool_calls) == 1
        assert "trailing commas" in result.repairs[0].lower()

    def test_trailing_comma_in_array(self):
        """Handle trailing commas in arrays too."""
        normalizer = ToolCallNormalizer()
        result = normalizer.normalize(
            '{"tool": "list_files", "arguments": {"paths": ["a.py", "b.py",]}}',
            model_family="llama",
        )

        assert len(result.tool_calls) == 1


class TestNormalizeQwenQuirks:
    """Test Qwen-specific quirk handling."""

    def test_function_key(self):
        """Qwen sometimes uses 'function' instead of 'tool'."""
        normalizer = ToolCallNormalizer()
        result = normalizer.normalize(
            '{"function": "list_files", "arguments": {"path": "."}}',
            model_family="qwen",
        )

        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "list_files"
        assert any("function" in r.lower() for r in result.repairs)


class TestNormalizeSmallModelQuirks:
    """Test small model quirk handling."""

    def test_nested_arguments(self):
        """Small models sometimes double-wrap arguments."""
        normalizer = ToolCallNormalizer()
        result = normalizer.normalize(
            '{"tool": "read_file", "arguments": {"arguments": {"path": "test.py"}}}'
        )

        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].arguments["path"] == "test.py"
        assert any("unnested" in r.lower() for r in result.repairs)

    def test_args_key_instead_of_arguments(self):
        """Some models use 'args' instead of 'arguments'."""
        normalizer = ToolCallNormalizer()
        result = normalizer.normalize('{"tool": "read_file", "args": {"path": "test.py"}}')

        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].arguments["path"] == "test.py"


class TestRepairJSON:
    """Test JSON repair functionality."""

    def test_single_quotes(self):
        """Single quotes should be converted to double quotes."""
        normalizer = ToolCallNormalizer()
        result = normalizer.normalize("{'tool': 'read_file', 'arguments': {'path': 'test.py'}}")

        assert len(result.tool_calls) == 1
        assert "Repaired" in result.repairs[0]

    def test_unquoted_keys(self):
        """Unquoted keys should be quoted."""
        normalizer = ToolCallNormalizer()
        result = normalizer.normalize('{tool: "read_file", arguments: {path: "test.py"}}')

        assert len(result.tool_calls) == 1

    def test_missing_closing_brace(self):
        """Missing closing brace should be added."""
        normalizer = ToolCallNormalizer()
        result = normalizer.normalize('{"tool": "read_file", "arguments": {"path": "test.py"}')

        assert len(result.tool_calls) == 1


class TestNormalizeXML:
    """Test XML-style tool call parsing."""

    def test_xml_format(self):
        """Parse XML-style tool calls."""
        normalizer = ToolCallNormalizer()
        result = normalizer.normalize('''
        <tool_call>
        <name>read_file</name>
        <arguments>
        <path>test.py</path>
        </arguments>
        </tool_call>
        ''')

        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "read_file"
        assert result.tool_calls[0].arguments["path"] == "test.py"


class TestNoToolCalls:
    """Test handling of responses without tool calls (E1)."""

    def test_no_tool_calls(self):
        """Response without tool calls should return empty list."""
        normalizer = ToolCallNormalizer()
        result = normalizer.normalize("I don't need to use any tools for this.")

        assert len(result.tool_calls) == 0
        assert result.remaining_text == "I don't need to use any tools for this."

    def test_invalid_json(self):
        """Invalid JSON that can't be repaired returns empty list."""
        normalizer = ToolCallNormalizer()
        result = normalizer.normalize("{completely invalid {{{ json")

        assert len(result.tool_calls) == 0


class TestNormalizationResult:
    """Test NormalizationResult dataclass."""

    def test_immutable(self):
        """NormalizationResult should be immutable."""
        result = NormalizationResult(
            tool_calls=(),
            repairs=(),
            remaining_text="test",
        )
        with pytest.raises(AttributeError):
            result.remaining_text = "changed"  # type: ignore
