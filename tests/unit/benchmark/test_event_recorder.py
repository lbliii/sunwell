"""Unit tests for EventRecorder.

These tests verify that EventRecorder correctly extracts structured data
from agent events, particularly around tool call recording.
"""

import pytest

from sunwell.agent.events import AgentEvent, EventType
from sunwell.benchmark.journeys.recorder import EventRecorder, ToolCallRecord


class TestEventRecorderToolExtraction:
    """Tests for tool call extraction from events."""

    def test_extracts_tool_name_from_tool_name_key(self) -> None:
        """EventRecorder should extract tool name from 'tool_name' key.
        
        This is the canonical key used by tool_start_event() in agent/events/tool.py.
        """
        recorder = EventRecorder()
        
        # Simulate event with 'tool_name' key (from tool_start_event)
        event = AgentEvent(
            EventType.TOOL_START,
            {
                "tool_name": "list_env",
                "tool_call_id": "call_123",
                "arguments": {"verbose": True},
            },
        )
        
        recorder._handle_event(event)
        
        assert len(recorder.tool_calls) == 1
        assert recorder.tool_calls[0].name == "list_env"
        assert recorder.tool_calls[0].arguments == {"verbose": True}

    def test_extracts_tool_name_from_tool_key(self) -> None:
        """EventRecorder should also accept 'tool' key for backwards compat."""
        recorder = EventRecorder()
        
        # Simulate event with 'tool' key (legacy format)
        event = AgentEvent(
            EventType.TOOL_START,
            {
                "tool": "read_file",
                "args": {"path": "/tmp/test.txt"},
            },
        )
        
        recorder._handle_event(event)
        
        assert len(recorder.tool_calls) == 1
        assert recorder.tool_calls[0].name == "read_file"

    def test_extracts_tool_name_from_name_key(self) -> None:
        """EventRecorder should also accept 'name' key as fallback."""
        recorder = EventRecorder()
        
        event = AgentEvent(
            EventType.TOOL_START,
            {
                "name": "write_file",
                "arguments": {"path": "/tmp/out.txt", "content": "hello"},
            },
        )
        
        recorder._handle_event(event)
        
        assert len(recorder.tool_calls) == 1
        assert recorder.tool_calls[0].name == "write_file"

    def test_prefers_tool_name_over_tool_and_name(self) -> None:
        """When multiple keys present, 'tool_name' takes precedence."""
        recorder = EventRecorder()
        
        event = AgentEvent(
            EventType.TOOL_START,
            {
                "tool_name": "correct_tool",
                "tool": "wrong_tool",
                "name": "also_wrong",
                "arguments": {},
            },
        )
        
        recorder._handle_event(event)
        
        assert len(recorder.tool_calls) == 1
        assert recorder.tool_calls[0].name == "correct_tool"

    def test_handles_missing_tool_name_gracefully(self) -> None:
        """When no tool name key present, should record empty string."""
        recorder = EventRecorder()
        
        event = AgentEvent(
            EventType.TOOL_START,
            {
                "arguments": {"some_arg": "value"},
            },
        )
        
        recorder._handle_event(event)
        
        assert len(recorder.tool_calls) == 1
        assert recorder.tool_calls[0].name == ""

    def test_has_tool_call_matches_recorded_tools(self) -> None:
        """has_tool_call() should correctly match recorded tool names."""
        recorder = EventRecorder()
        
        for tool_name in ["list_env", "read_file", "write_file"]:
            event = AgentEvent(
                EventType.TOOL_START,
                {"tool_name": tool_name, "arguments": {}},
            )
            recorder._handle_event(event)
        
        assert recorder.has_tool_call("list_env")
        assert recorder.has_tool_call("read_file")
        assert recorder.has_tool_call("write_file")
        assert not recorder.has_tool_call("shell")
        assert not recorder.has_tool_call("")


class TestEventRecorderToolComplete:
    """Tests for TOOL_COMPLETE event handling."""

    def test_updates_tool_result_on_complete(self) -> None:
        """TOOL_COMPLETE should update the matching tool call with result."""
        recorder = EventRecorder()
        
        # First, tool starts
        recorder._handle_event(AgentEvent(
            EventType.TOOL_START,
            {"tool_name": "read_file", "arguments": {"path": "test.txt"}},
        ))
        
        # Then, tool completes
        recorder._handle_event(AgentEvent(
            EventType.TOOL_COMPLETE,
            {"tool_name": "read_file", "result": "file contents here"},
        ))
        
        assert len(recorder.tool_calls) == 1
        assert recorder.tool_calls[0].result == "file contents here"
        assert recorder.tool_calls[0].success is True


class TestEventRecorderToolError:
    """Tests for TOOL_ERROR event handling."""

    def test_marks_tool_as_failed_on_error(self) -> None:
        """TOOL_ERROR should mark the tool call as failed."""
        recorder = EventRecorder()
        
        recorder._handle_event(AgentEvent(
            EventType.TOOL_START,
            {"tool_name": "shell", "arguments": {"command": "bad_cmd"}},
        ))
        
        recorder._handle_event(AgentEvent(
            EventType.TOOL_ERROR,
            {"tool": "shell", "error": "Command not found"},
        ))
        
        assert len(recorder.tool_calls) == 1
        assert recorder.tool_calls[0].success is False
        assert recorder.tool_calls[0].error == "Command not found"


class TestEventRecorderLifecycle:
    """Tests for recorder lifecycle management."""

    def test_start_stop_idempotent(self) -> None:
        """Multiple start/stop calls should be safe."""
        recorder = EventRecorder()
        
        recorder.start()
        recorder.start()  # Should not error
        recorder.stop()
        recorder.stop()  # Should not error

    def test_context_manager(self) -> None:
        """EventRecorder should work as context manager."""
        with EventRecorder() as recorder:
            assert recorder._unsubscribe is not None
        assert recorder._unsubscribe is None

    def test_reset_clears_all_data(self) -> None:
        """reset() should clear all recorded data."""
        recorder = EventRecorder()
        
        recorder._handle_event(AgentEvent(
            EventType.TOOL_START,
            {"tool_name": "test", "arguments": {}},
        ))
        
        assert len(recorder.tool_calls) == 1
        
        recorder.reset()
        
        assert len(recorder.tool_calls) == 0
        assert len(recorder.events) == 0


class TestEventRecorderArguments:
    """Tests for argument extraction."""

    def test_extracts_arguments_key(self) -> None:
        """Should extract arguments from 'arguments' key."""
        recorder = EventRecorder()
        
        recorder._handle_event(AgentEvent(
            EventType.TOOL_START,
            {"tool_name": "edit_file", "arguments": {"path": "f.py", "old_content": "a", "new_content": "b"}},
        ))
        
        assert recorder.tool_calls[0].arguments == {"path": "f.py", "old_content": "a", "new_content": "b"}

    def test_extracts_args_key_fallback(self) -> None:
        """Should fall back to 'args' key if 'arguments' not present."""
        recorder = EventRecorder()
        
        recorder._handle_event(AgentEvent(
            EventType.TOOL_START,
            {"tool_name": "read_file", "args": {"path": "test.txt"}},
        ))
        
        assert recorder.tool_calls[0].arguments == {"path": "test.txt"}

    def test_empty_arguments_when_missing(self) -> None:
        """Should default to empty dict when no arguments provided."""
        recorder = EventRecorder()
        
        recorder._handle_event(AgentEvent(
            EventType.TOOL_START,
            {"tool_name": "list_env"},
        ))
        
        assert recorder.tool_calls[0].arguments == {}
