"""Tests for typed streaming.

Covers Journeys A11 (Report to human) and H3 (Observe progress).
"""

import pytest

from sunwell.models.capability.streaming import (
    StreamChunk,
    StreamChunkType,
    ToolStreamParser,
)


class TestStreamChunk:
    """Test StreamChunk dataclass."""

    def test_text_chunk(self):
        """Create a text chunk."""
        chunk = StreamChunk(type=StreamChunkType.TEXT, content="Hello")
        assert chunk.type == StreamChunkType.TEXT
        assert chunk.content == "Hello"
        assert chunk.tool_name is None

    def test_tool_chunk(self):
        """Create a tool chunk."""
        chunk = StreamChunk(
            type=StreamChunkType.TOOL_END,
            tool_name="write_file",
            tool_call_id="tc_123",
            is_complete=True,
        )
        assert chunk.is_complete is True
        assert chunk.tool_name == "write_file"

    def test_immutable(self):
        """StreamChunk should be immutable."""
        chunk = StreamChunk(type=StreamChunkType.TEXT, content="test")
        with pytest.raises(AttributeError):
            chunk.content = "changed"  # type: ignore


class TestToolStreamParser:
    """Test ToolStreamParser for incremental parsing."""

    def test_text_only(self):
        """Parse text-only response."""
        parser = ToolStreamParser()
        chunks = parser.feed("Hello, how can I help?")
        chunks += parser.finalize()

        text_chunks = [c for c in chunks if c.type == StreamChunkType.TEXT]
        assert len(text_chunks) >= 1
        combined = "".join(c.content or "" for c in text_chunks)
        assert "Hello" in combined

    def test_tool_start_detection(self):
        """Detect start of tool call."""
        parser = ToolStreamParser()
        chunks = parser.feed('Let me help: {"tool"')
        chunks += parser.feed(': "write_file", "arguments": {"path": "test.py"}}')
        chunks += parser.finalize()

        types = [c.type for c in chunks]
        assert StreamChunkType.TOOL_START in types
        assert StreamChunkType.TOOL_ARGS in types

    def test_tool_name_extraction(self):
        """Extract tool name from streaming call."""
        parser = ToolStreamParser()
        chunks = parser.feed('{"tool": "read_file", "arguments": {"path": "x.py"}}')
        chunks += parser.finalize()

        tool_chunks = [c for c in chunks if c.tool_name]
        assert any(c.tool_name == "read_file" for c in tool_chunks)

    def test_tool_end_detection(self):
        """Detect end of tool call."""
        parser = ToolStreamParser()
        chunks = parser.feed('{"tool": "read_file", "arguments": {"path": "x.py"}}')
        chunks += parser.finalize()

        end_chunks = [c for c in chunks if c.type == StreamChunkType.TOOL_END]
        assert len(end_chunks) >= 1

    def test_code_block_format(self):
        """Handle JSON in code block."""
        parser = ToolStreamParser()
        chunks = parser.feed('```json\n{"tool": "read_file", "arguments": {}}\n```')
        chunks += parser.finalize()

        types = [c.type for c in chunks]
        assert StreamChunkType.TOOL_START in types

    def test_multiple_tools(self):
        """Parse multiple tool calls."""
        parser = ToolStreamParser()
        chunks = parser.feed('''
        {"tool": "read_file", "arguments": {"path": "a.py"}}
        {"tool": "read_file", "arguments": {"path": "b.py"}}
        ''')
        chunks += parser.finalize()

        starts = [c for c in chunks if c.type == StreamChunkType.TOOL_START]
        assert len(starts) == 2

    def test_incremental_streaming(self):
        """Simulate incremental token streaming."""
        parser = ToolStreamParser()

        # Feed tokens incrementally
        chunks = []
        chunks += parser.feed('{"too')
        chunks += parser.feed('l": "rea')
        chunks += parser.feed('d_file", "arg')
        chunks += parser.feed('uments": {"path')
        chunks += parser.feed('": "test.py"}}')
        chunks += parser.finalize()

        # Should detect tool start and get name
        types = [c.type for c in chunks]
        assert StreamChunkType.TOOL_START in types

        tool_chunks = [c for c in chunks if c.tool_name]
        assert any(c.tool_name == "read_file" for c in tool_chunks)

    def test_text_before_tool(self):
        """Text before tool call should be emitted."""
        parser = ToolStreamParser()
        chunks = parser.feed('I will read the file. {"tool": "read_file", "arguments": {}}')
        chunks += parser.finalize()

        text_chunks = [c for c in chunks if c.type == StreamChunkType.TEXT]
        combined = "".join(c.content or "" for c in text_chunks)
        assert "read the file" in combined

    def test_finalize_incomplete_tool_call(self):
        """Incomplete tool call should be marked as such."""
        parser = ToolStreamParser()
        chunks = parser.feed('{"tool": "read_file", "arguments":')
        # Don't complete the JSON
        chunks += parser.finalize()

        end_chunks = [c for c in chunks if c.type == StreamChunkType.TOOL_END]
        assert len(end_chunks) == 1
        assert end_chunks[0].is_complete is False

    def test_reset(self):
        """Parser can be reset for reuse."""
        parser = ToolStreamParser()
        parser.feed('{"tool": "test"}')
        parser.reset()

        # After reset, should be clean
        chunks = parser.feed('{"tool": "new_tool", "arguments": {}}')
        chunks += parser.finalize()

        tool_chunks = [c for c in chunks if c.tool_name]
        assert all(c.tool_name != "test" for c in tool_chunks if c.tool_name)


class TestStreamChunkType:
    """Test StreamChunkType enum."""

    def test_all_types_exist(self):
        """All expected types should exist."""
        assert StreamChunkType.TEXT
        assert StreamChunkType.TOOL_START
        assert StreamChunkType.TOOL_ARGS
        assert StreamChunkType.TOOL_END
        assert StreamChunkType.THINKING

    def test_values(self):
        """Types should have string values."""
        assert StreamChunkType.TEXT.value == "text"
        assert StreamChunkType.TOOL_START.value == "tool_start"
