"""Tests for adaptive emulation prompts.

Covers Journey E6 (Context overflow handling).
"""

import pytest

from sunwell.models.capability.emulation import (
    build_emulation_prompt,
    format_tool_descriptions,
    optimize_tool_definitions,
)
from sunwell.models.capability.registry import ModelCapability
from sunwell.models.core.protocol import Tool


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
                    "path": {"type": "string", "description": "The file path to read"},
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="write_file",
            description="Write content to a file at the specified path.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "The file path"},
                    "content": {"type": "string", "description": "Content to write"},
                },
                "required": ["path", "content"],
            },
        ),
    )


@pytest.fixture
def many_tools() -> tuple[Tool, ...]:
    """Create many tools for context overflow testing."""
    return tuple(
        Tool(
            name=f"tool_{i}",
            description=f"This is tool number {i} with a moderately long description " * 5,
            parameters={"type": "object", "properties": {"arg": {"type": "string"}}},
        )
        for i in range(50)
    )


class TestFormatToolDescriptions:
    """Test tool description formatting."""

    def test_full_format(self, sample_tools: tuple[Tool, ...]):
        """Full format includes all details."""
        result = format_tool_descriptions(sample_tools, compact=False)

        assert "### read_file" in result
        assert "### write_file" in result
        assert "Parameters:" in result
        assert "(required)" in result

    def test_compact_format(self, sample_tools: tuple[Tool, ...]):
        """Compact format is minimal."""
        result = format_tool_descriptions(sample_tools, compact=True)

        assert "### " not in result  # No headers
        assert "- read_file(" in result
        assert len(result) < 500  # Much shorter

    def test_compact_truncates_description(self):
        """Compact format truncates long descriptions."""
        tool = Tool(
            name="test",
            description="x" * 200,
            parameters={"type": "object", "properties": {"a": {"type": "string"}}},
        )
        result = format_tool_descriptions((tool,), compact=True)

        # Description should be truncated to ~80 chars
        assert "..." in result


class TestBuildEmulationPrompt:
    """Test adaptive prompt building."""

    def test_standard_prompt(self, sample_tools: tuple[Tool, ...]):
        """Standard prompt for normal models."""
        capability = ModelCapability(context_window=32000, emulation_style="json")
        prompt = build_emulation_prompt(sample_tools, capability)

        assert '"tool"' in prompt
        assert '"arguments"' in prompt
        assert "read_file" in prompt

    def test_compact_prompt_for_small_context(self, sample_tools: tuple[Tool, ...]):
        """Small context models get compact prompt."""
        capability = ModelCapability(context_window=4096, emulation_style="json")
        prompt = build_emulation_prompt(sample_tools, capability)

        # Compact prompt is shorter
        assert len(prompt) < 1000

    def test_parallel_prompt(self, sample_tools: tuple[Tool, ...]):
        """Parallel-capable models get parallel prompt."""
        capability = ModelCapability(parallel_tools=True, emulation_style="json")
        prompt = build_emulation_prompt(sample_tools, capability)

        assert "multiple tools" in prompt.lower() or "one per tool" in prompt.lower()

    def test_xml_style_prompt(self, sample_tools: tuple[Tool, ...]):
        """XML style preference is respected."""
        capability = ModelCapability(emulation_style="xml")
        prompt = build_emulation_prompt(sample_tools, capability)

        assert "<tool_call>" in prompt
        assert "<name>" in prompt


class TestOptimizeToolDefinitions:
    """Test tool optimization for context constraints (E6)."""

    def test_no_optimization_large_context(self, many_tools: tuple[Tool, ...]):
        """Large context windows don't need optimization."""
        capability = ModelCapability(context_window=128000)
        result = optimize_tool_definitions(many_tools, capability)

        assert len(result) == len(many_tools)

    def test_reduces_tools_small_context(self, many_tools: tuple[Tool, ...]):
        """Small context windows get fewer tools."""
        capability = ModelCapability(context_window=4096)
        result = optimize_tool_definitions(many_tools, capability)

        assert len(result) < len(many_tools)

    def test_truncates_descriptions_tiny_context(self, many_tools: tuple[Tool, ...]):
        """Very small contexts get truncated descriptions."""
        capability = ModelCapability(context_window=2048)
        result = optimize_tool_definitions(many_tools, capability)

        for tool in result:
            # Description should be truncated
            assert len(tool.description) <= 210  # 200 + "..."

    def test_prioritizes_by_task_hint(self, many_tools: tuple[Tool, ...]):
        """Task hint affects tool ordering."""
        # Add a tool that matches the task
        file_tool = Tool(
            name="write_file",
            description="Write content to a file",
            parameters={"type": "object", "properties": {}},
        )
        tools_with_file = many_tools + (file_tool,)

        capability = ModelCapability(context_window=4096)
        result = optimize_tool_definitions(
            tools_with_file, capability, task_hint="write a python file"
        )

        # write_file should be prioritized and included
        result_names = [t.name for t in result]
        assert "write_file" in result_names

    def test_preserves_tool_parameters(self, sample_tools: tuple[Tool, ...]):
        """Optimization preserves parameter schemas."""
        capability = ModelCapability(context_window=4096)
        result = optimize_tool_definitions(sample_tools, capability)

        assert len(result) > 0
        assert result[0].parameters == sample_tools[0].parameters

    def test_returns_tuple(self, sample_tools: tuple[Tool, ...]):
        """Result should be a tuple (immutable)."""
        capability = ModelCapability(context_window=4096)
        result = optimize_tool_definitions(sample_tools, capability)

        assert isinstance(result, tuple)
