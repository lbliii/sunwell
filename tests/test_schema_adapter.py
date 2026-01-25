"""Tests for schema adapters.

Covers Journeys A1 (Receive tools) and A2 (Format schema).
"""

import pytest

from sunwell.models.capability.schema import (
    AnthropicSchemaAdapter,
    OllamaSchemaAdapter,
    OpenAISchemaAdapter,
    get_schema_adapter,
)
from sunwell.models.protocol import Tool


@pytest.fixture
def sample_tools() -> tuple[Tool, ...]:
    """Create sample tools for testing."""
    return (
        Tool(
            name="read_file",
            description="Read the contents of a file at the specified path.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The file path to read",
                    }
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="write_file",
            description="Write content to a file.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        ),
    )


class TestOpenAISchemaAdapter:
    """Test OpenAI schema adapter."""

    def test_convert_tools_format(self, sample_tools: tuple[Tool, ...]):
        """Tools should be wrapped in function format."""
        adapter = OpenAISchemaAdapter()
        result = adapter.convert_tools(sample_tools)

        assert len(result) == 2
        assert result[0]["type"] == "function"
        assert result[0]["function"]["name"] == "read_file"
        assert "parameters" in result[0]["function"]

    def test_strict_mode_enabled_by_default(self, sample_tools: tuple[Tool, ...]):
        """Strict mode should be enabled by default."""
        adapter = OpenAISchemaAdapter()
        result = adapter.convert_tools(sample_tools)

        assert result[0]["function"]["strict"] is True

    def test_strict_mode_adds_additional_properties(self, sample_tools: tuple[Tool, ...]):
        """Strict mode should add additionalProperties: false."""
        adapter = OpenAISchemaAdapter()
        result = adapter.convert_tools(sample_tools)

        params = result[0]["function"]["parameters"]
        assert params["additionalProperties"] is False

    def test_strict_mode_can_be_disabled(self, sample_tools: tuple[Tool, ...]):
        """Strict mode can be disabled."""
        adapter = OpenAISchemaAdapter(strict_mode=False)
        result = adapter.convert_tools(sample_tools)

        assert "strict" not in result[0]["function"]

    def test_convert_tool_choice_auto(self):
        """Tool choice 'auto' should pass through."""
        adapter = OpenAISchemaAdapter()
        assert adapter.convert_tool_choice("auto") == "auto"

    def test_convert_tool_choice_none(self):
        """Tool choice 'none' should pass through."""
        adapter = OpenAISchemaAdapter()
        assert adapter.convert_tool_choice("none") == "none"

    def test_convert_tool_choice_required(self):
        """Tool choice 'required' should pass through."""
        adapter = OpenAISchemaAdapter()
        assert adapter.convert_tool_choice("required") == "required"

    def test_convert_tool_choice_specific_tool(self):
        """Specific tool name should become function dict."""
        adapter = OpenAISchemaAdapter()
        result = adapter.convert_tool_choice("read_file")

        assert result == {"type": "function", "function": {"name": "read_file"}}

    def test_convert_tool_choice_dict_passthrough(self):
        """Dict tool_choice should pass through unchanged."""
        adapter = OpenAISchemaAdapter()
        choice = {"type": "function", "function": {"name": "custom"}}
        assert adapter.convert_tool_choice(choice) == choice


class TestAnthropicSchemaAdapter:
    """Test Anthropic schema adapter."""

    def test_convert_tools_uses_input_schema(self, sample_tools: tuple[Tool, ...]):
        """Anthropic uses input_schema instead of parameters."""
        adapter = AnthropicSchemaAdapter()
        result = adapter.convert_tools(sample_tools)

        assert len(result) == 2
        assert "input_schema" in result[0]
        assert "parameters" not in result[0]
        assert result[0]["name"] == "read_file"

    def test_strict_schema_adds_required_fields(self, sample_tools: tuple[Tool, ...]):
        """Anthropic strict schema should add required fields."""
        adapter = AnthropicSchemaAdapter()
        result = adapter.convert_tools(sample_tools)

        schema = result[0]["input_schema"]
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False
        assert "properties" in schema

    def test_convert_tool_choice_auto(self):
        """Tool choice 'auto' becomes dict format."""
        adapter = AnthropicSchemaAdapter()
        result = adapter.convert_tool_choice("auto")

        assert result == {"type": "auto"}

    def test_convert_tool_choice_required(self):
        """Tool choice 'required' becomes 'any' type."""
        adapter = AnthropicSchemaAdapter()
        result = adapter.convert_tool_choice("required")

        assert result == {"type": "any"}

    def test_convert_tool_choice_none(self):
        """Tool choice 'none' returns None (don't send tools)."""
        adapter = AnthropicSchemaAdapter()
        assert adapter.convert_tool_choice("none") is None

    def test_convert_tool_choice_specific_tool(self):
        """Specific tool name becomes tool type."""
        adapter = AnthropicSchemaAdapter()
        result = adapter.convert_tool_choice("read_file")

        assert result == {"type": "tool", "name": "read_file"}


class TestOllamaSchemaAdapter:
    """Test Ollama schema adapter."""

    def test_convert_tools_openai_compatible(self, sample_tools: tuple[Tool, ...]):
        """Ollama format should be OpenAI-compatible."""
        adapter = OllamaSchemaAdapter()
        result = adapter.convert_tools(sample_tools)

        assert len(result) == 2
        assert result[0]["type"] == "function"
        assert result[0]["function"]["name"] == "read_file"

    def test_description_truncation(self):
        """Long descriptions should be truncated."""
        long_desc = "x" * 600
        tool = Tool(name="test", description=long_desc, parameters={})

        adapter = OllamaSchemaAdapter(max_description_length=500)
        result = adapter.convert_tools((tool,))

        desc = result[0]["function"]["description"]
        assert len(desc) == 500
        assert desc.endswith("...")

    def test_short_description_not_truncated(self, sample_tools: tuple[Tool, ...]):
        """Short descriptions should not be truncated."""
        adapter = OllamaSchemaAdapter()
        result = adapter.convert_tools(sample_tools)

        desc = result[0]["function"]["description"]
        assert not desc.endswith("...")

    def test_no_strict_mode(self, sample_tools: tuple[Tool, ...]):
        """Ollama should not add strict mode."""
        adapter = OllamaSchemaAdapter()
        result = adapter.convert_tools(sample_tools)

        assert "strict" not in result[0]["function"]


class TestGetSchemaAdapter:
    """Test adapter factory function."""

    def test_get_openai_adapter(self):
        """Should return OpenAI adapter for 'openai'."""
        adapter = get_schema_adapter("openai")
        assert isinstance(adapter, OpenAISchemaAdapter)

    def test_get_anthropic_adapter(self):
        """Should return Anthropic adapter for 'anthropic'."""
        adapter = get_schema_adapter("anthropic")
        assert isinstance(adapter, AnthropicSchemaAdapter)

    def test_get_ollama_adapter(self):
        """Should return Ollama adapter for 'ollama'."""
        adapter = get_schema_adapter("ollama")
        assert isinstance(adapter, OllamaSchemaAdapter)

    def test_get_groq_adapter(self):
        """Groq should use OpenAI adapter."""
        adapter = get_schema_adapter("groq")
        assert isinstance(adapter, OpenAISchemaAdapter)

    def test_unknown_provider_defaults_to_openai(self):
        """Unknown providers should default to OpenAI format."""
        adapter = get_schema_adapter("unknown-provider")
        assert isinstance(adapter, OpenAISchemaAdapter)

    def test_case_insensitive(self):
        """Provider names should be case-insensitive."""
        adapter = get_schema_adapter("OpenAI")
        assert isinstance(adapter, OpenAISchemaAdapter)

        adapter = get_schema_adapter("ANTHROPIC")
        assert isinstance(adapter, AnthropicSchemaAdapter)
