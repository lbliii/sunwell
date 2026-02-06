"""Unit tests for CLI render context."""

import pytest

from sunwell.interface.cli.core.render_context import (
    RenderContext,
    RenderPhase,
    TaskGroup,
    TimelineEvent,
    ToolCall,
    TREE,
    get_render_context,
    reset_render_context,
    should_reduce_motion,
    is_plain_mode,
)


class TestRenderPhase:
    """Tests for RenderPhase enum."""

    def test_all_phases_defined(self):
        """All expected phases exist."""
        assert RenderPhase.IDLE.value == "idle"
        assert RenderPhase.UNDERSTANDING.value == "understanding"
        assert RenderPhase.PLANNING.value == "planning"
        assert RenderPhase.CRAFTING.value == "crafting"
        assert RenderPhase.VERIFYING.value == "verifying"
        assert RenderPhase.FIXING.value == "fixing"
        assert RenderPhase.COMPLETE.value == "complete"


class TestTreeCharacters:
    """Tests for tree drawing characters."""

    def test_tree_chars_defined(self):
        """All tree characters are defined."""
        assert "branch" in TREE
        assert "last" in TREE
        assert "pipe" in TREE
        assert "space" in TREE
        assert "top" in TREE


class TestTaskGroup:
    """Tests for TaskGroup dataclass."""

    def test_create_task_group(self):
        """Can create a task group with required fields."""
        task = TaskGroup(
            task_id="1",
            description="Test task",
            task_number=1,
            total_tasks=5,
        )
        assert task.task_id == "1"
        assert task.description == "Test task"
        assert task.task_number == 1
        assert task.total_tasks == 5
        assert task.started is False
        assert task.completed is False
        assert task.duration_ms == 0
        assert task.gates == []
        assert task.tools == []
        assert task.files_created == []
        assert task.files_modified == []


class TestToolCall:
    """Tests for ToolCall dataclass."""

    def test_create_tool_call(self):
        """Can create a tool call."""
        tool = ToolCall(name="write_file")
        assert tool.name == "write_file"
        assert tool.completed is False
        assert tool.success is True
        assert tool.duration_ms == 0
        assert tool.error is None
        assert tool.started_at > 0


class TestRenderContext:
    """Tests for RenderContext."""

    def test_initial_state(self):
        """Context starts in IDLE phase."""
        ctx = RenderContext()
        assert ctx.phase == RenderPhase.IDLE
        assert ctx.current_task is None
        assert ctx.current_tool is None
        assert ctx.task_count == 0
        assert ctx.total_tasks == 0
        assert ctx.learnings == []
        assert ctx.total_tokens == 0
        assert ctx.total_cost == 0.0

    def test_indent(self):
        """Indent returns correct indentation."""
        ctx = RenderContext()
        assert ctx.indent(0) == "  "
        assert ctx.indent(1) == "    "
        assert ctx.indent(2) == "      "

    def test_tree_line_branch(self):
        """Tree line returns correct connector."""
        ctx = RenderContext()
        line = ctx.tree_line(0, is_last=False)
        assert TREE["branch"] in line

    def test_tree_line_last(self):
        """Tree line returns last connector."""
        ctx = RenderContext()
        line = ctx.tree_line(0, is_last=True)
        assert TREE["last"] in line

    def test_tree_line_first(self):
        """Tree line returns top connector."""
        ctx = RenderContext()
        line = ctx.tree_line(0, is_first=True)
        assert TREE["top"] in line

    def test_continuation_line_with_more(self):
        """Continuation line with more items."""
        ctx = RenderContext()
        line = ctx.continuation_line(0, has_more=True)
        assert TREE["pipe"] in line

    def test_continuation_line_no_more(self):
        """Continuation line without more items."""
        ctx = RenderContext()
        line = ctx.continuation_line(0, has_more=False)
        assert TREE["space"] in line

    def test_transition_phase(self):
        """Phase transition works correctly."""
        ctx = RenderContext()
        
        # First transition should render
        assert ctx.transition_phase(RenderPhase.UNDERSTANDING) is True
        assert ctx.phase == RenderPhase.UNDERSTANDING
        
        # Same phase should not render
        assert ctx.transition_phase(RenderPhase.UNDERSTANDING) is False
        
        # New phase should render
        assert ctx.transition_phase(RenderPhase.CRAFTING) is True
        assert ctx.phase == RenderPhase.CRAFTING

    def test_transition_verifying_from_crafting_no_header(self):
        """Verifying from crafting doesn't show header (gates inline)."""
        ctx = RenderContext()
        ctx.transition_phase(RenderPhase.CRAFTING)
        
        # VERIFYING from CRAFTING should not render header
        assert ctx.transition_phase(RenderPhase.VERIFYING) is False

    def test_start_task(self):
        """Starting a task creates a task group."""
        ctx = RenderContext()
        task = ctx.start_task("1", "Test task", 1, 5)
        
        assert ctx.current_task is task
        assert task.task_id == "1"
        assert task.description == "Test task"
        assert task.task_number == 1
        assert task.total_tasks == 5
        assert task.started is True
        assert ctx.task_count == 1
        assert ctx.total_tasks == 5

    def test_complete_task(self):
        """Completing a task updates duration."""
        ctx = RenderContext()
        ctx.start_task("1", "Test", 1, 1)
        ctx.complete_task(duration_ms=1234)
        
        assert ctx.current_task.completed is True
        assert ctx.current_task.duration_ms == 1234

    def test_add_gate(self):
        """Adding a gate to current task."""
        ctx = RenderContext()
        ctx.start_task("1", "Test", 1, 1)
        ctx.add_gate("lint", passed=True, details="OK")
        
        assert len(ctx.current_task.gates) == 1
        assert ctx.current_task.gates[0] == ("lint", True, "OK")

    def test_is_last_task(self):
        """Check if current task is the last."""
        ctx = RenderContext()
        
        # No task
        assert ctx.is_last_task() is False
        
        # First of 3
        ctx.start_task("1", "Test", 1, 3)
        assert ctx.is_last_task() is False
        
        # Last of 3
        ctx.start_task("3", "Test", 3, 3)
        assert ctx.is_last_task() is True

    # Tool tracking tests

    def test_start_tool(self):
        """Starting a tool creates a tool call."""
        ctx = RenderContext()
        ctx.start_task("1", "Test", 1, 1)
        
        tool = ctx.start_tool("write_file")
        assert ctx.current_tool is tool
        assert tool.name == "write_file"
        assert tool in ctx.current_task.tools

    def test_complete_tool(self):
        """Completing a tool updates state."""
        ctx = RenderContext()
        ctx.start_task("1", "Test", 1, 1)
        ctx.start_tool("write_file")
        ctx.complete_tool(success=True)
        
        assert ctx.current_tool is None
        tool = ctx.current_task.tools[0]
        assert tool.completed is True
        assert tool.success is True

    def test_complete_tool_with_error(self):
        """Completing a tool with error."""
        ctx = RenderContext()
        ctx.start_task("1", "Test", 1, 1)
        ctx.start_tool("write_file")
        ctx.complete_tool(success=False, error="Permission denied")
        
        tool = ctx.current_task.tools[0]
        assert tool.success is False
        assert tool.error == "Permission denied"

    def test_has_active_tool(self):
        """Check for active tool."""
        ctx = RenderContext()
        assert ctx.has_active_tool() is False
        
        ctx.start_task("1", "Test", 1, 1)
        ctx.start_tool("test")
        assert ctx.has_active_tool() is True
        
        ctx.complete_tool()
        assert ctx.has_active_tool() is False

    # File tracking tests

    def test_add_file_created(self):
        """Track created files."""
        ctx = RenderContext()
        ctx.start_task("1", "Test", 1, 1)
        
        ctx.add_file_created("src/foo.py")
        assert "src/foo.py" in ctx.files_created
        assert "src/foo.py" in ctx.current_task.files_created
        
        # Duplicate should not add twice
        ctx.add_file_created("src/foo.py")
        assert ctx.files_created.count("src/foo.py") == 1

    def test_add_file_modified(self):
        """Track modified files."""
        ctx = RenderContext()
        ctx.start_task("1", "Test", 1, 1)
        
        ctx.add_file_modified("src/bar.py")
        assert "src/bar.py" in ctx.files_modified
        assert "src/bar.py" in ctx.current_task.files_modified

    # Metrics tests

    def test_add_tokens(self):
        """Track token usage."""
        ctx = RenderContext()
        ctx.add_tokens(1000, cost=0.01)
        ctx.add_tokens(500, cost=0.005)
        
        assert ctx.total_tokens == 1500
        assert ctx.total_cost == 0.015

    def test_get_elapsed_seconds(self):
        """Get elapsed time."""
        ctx = RenderContext()
        elapsed = ctx.get_elapsed_seconds()
        assert elapsed >= 0
        assert elapsed < 1  # Should be very small

    def test_get_session_summary(self):
        """Get session summary dict."""
        ctx = RenderContext()
        ctx.add_tokens(1000)
        ctx.add_file_created("foo.py")
        ctx.add_learning("Python project")
        ctx.task_count = 5
        
        summary = ctx.get_session_summary()
        assert summary["total_tokens"] == 1000
        assert summary["files_created"] == 1
        assert summary["learnings"] == 1
        assert summary["tasks_completed"] == 5

    # Convergence tests

    def test_start_convergence(self):
        """Start tracking convergence loop."""
        ctx = RenderContext()
        ctx.start_convergence(5)
        
        assert ctx.convergence_max == 5
        assert ctx.convergence_iteration == 0
        assert ctx.is_fixing is False

    def test_next_convergence_iteration(self):
        """Advance convergence iteration."""
        ctx = RenderContext()
        ctx.start_convergence(5)
        
        assert ctx.next_convergence_iteration() == 1
        assert ctx.next_convergence_iteration() == 2
        assert ctx.convergence_iteration == 2

    def test_in_convergence(self):
        """Check if in convergence loop."""
        ctx = RenderContext()
        assert ctx.in_convergence() is False
        
        ctx.start_convergence(3)
        assert ctx.in_convergence() is True

    def test_start_and_end_fixing(self):
        """Track fixing state."""
        ctx = RenderContext()
        ctx.start_convergence(3)
        
        ctx.start_fixing()
        assert ctx.is_fixing is True
        assert ctx.phase == RenderPhase.FIXING
        
        ctx.end_fixing()
        assert ctx.is_fixing is False

    # Learning tests

    def test_add_learning(self):
        """Add and deduplicate learnings."""
        ctx = RenderContext()
        ctx.add_learning("Python project")
        ctx.add_learning("Python project")
        ctx.add_learning("TypeScript project")
        
        assert len(ctx.learnings) == 3  # All stored
        assert ctx.learning_counts["Python project"] == 2
        assert ctx.learning_counts["TypeScript project"] == 1

    def test_get_batched_learnings(self):
        """Get deduplicated learnings with counts."""
        ctx = RenderContext()
        ctx.add_learning("A")
        ctx.add_learning("A")
        ctx.add_learning("B")
        
        batched = ctx.get_batched_learnings()
        assert len(batched) == 2
        assert ("A", 2) in batched
        assert ("B", 1) in batched

    def test_clear_learnings(self):
        """Clear accumulated learnings."""
        ctx = RenderContext()
        ctx.add_learning("A")
        ctx.clear_learnings()
        
        assert ctx.learnings == []
        assert ctx.learning_counts == {}

    # Reset tests

    def test_reset(self):
        """Reset clears all state."""
        ctx = RenderContext()
        ctx.transition_phase(RenderPhase.CRAFTING)
        ctx.start_task("1", "Test", 1, 5)
        ctx.add_tokens(1000)
        ctx.add_learning("A")
        ctx.start_convergence(3)
        
        ctx.reset()
        
        assert ctx.phase == RenderPhase.IDLE
        assert ctx.current_task is None
        assert ctx.task_count == 0
        assert ctx.total_tokens == 0
        assert ctx.learnings == []
        assert ctx.convergence_max == 0


class TestTimelineEvent:
    """Tests for TimelineEvent dataclass."""

    def test_create_timeline_event(self):
        """Can create a timeline event."""
        event = TimelineEvent(
            timestamp=1000.0,
            description="Test event",
            phase="crafting",
        )
        assert event.timestamp == 1000.0
        assert event.description == "Test event"
        assert event.phase == "crafting"
        assert event.completed is False
        assert event.duration_ms == 0


class TestTimelineTracking:
    """Tests for timeline tracking in RenderContext."""

    def test_add_timeline_event(self):
        """Add events to timeline."""
        ctx = RenderContext()
        ctx.transition_phase(RenderPhase.CRAFTING)
        
        event = ctx.add_timeline_event("Task started")
        
        assert len(ctx.timeline) == 1
        assert event.description == "Task started"
        assert event.phase == "crafting"
        assert event.completed is False

    def test_complete_timeline_event(self):
        """Complete a timeline event."""
        ctx = RenderContext()
        event = ctx.add_timeline_event("Task")
        ctx.complete_timeline_event(event, duration_ms=500)
        
        assert event.completed is True
        assert event.duration_ms == 500

    def test_get_timeline_for_render(self):
        """Get timeline in render format."""
        ctx = RenderContext()
        ctx.add_timeline_event("Event 1", completed=True)
        ctx.add_timeline_event("Event 2", completed=False)
        
        render_data = ctx.get_timeline_for_render()
        
        assert len(render_data) == 2
        # Each item is (timestamp_str, description, is_complete)
        assert render_data[0][1] == "Event 1"
        assert render_data[0][2] is True
        assert render_data[1][1] == "Event 2"
        assert render_data[1][2] is False

    def test_timeline_cleared_on_reset(self):
        """Timeline is cleared on reset."""
        ctx = RenderContext()
        ctx.add_timeline_event("Event")
        ctx.reset()
        
        assert len(ctx.timeline) == 0


class TestStreaming:
    """Tests for streaming text state."""

    def test_start_streaming(self):
        """Start streaming mode."""
        ctx = RenderContext()
        ctx.start_streaming()
        
        assert ctx.is_streaming is True
        assert ctx.streaming_text == ""

    def test_append_streaming(self):
        """Append text to streaming buffer."""
        ctx = RenderContext()
        ctx.start_streaming()
        
        result = ctx.append_streaming("Hello ")
        assert result == "Hello "
        
        result = ctx.append_streaming("world")
        assert result == "Hello world"

    def test_end_streaming(self):
        """End streaming returns final text."""
        ctx = RenderContext()
        ctx.start_streaming()
        ctx.append_streaming("Final text")
        
        final = ctx.end_streaming()
        
        assert final == "Final text"
        assert ctx.is_streaming is False
        assert ctx.streaming_text == ""

    def test_streaming_cleared_on_reset(self):
        """Streaming state cleared on reset."""
        ctx = RenderContext()
        ctx.start_streaming()
        ctx.append_streaming("test")
        ctx.reset()
        
        assert ctx.is_streaming is False
        assert ctx.streaming_text == ""


class TestAccessibility:
    """Tests for accessibility features."""

    def test_reduced_motion_default(self, monkeypatch):
        """Reduced motion respects environment."""
        monkeypatch.delenv("SUNWELL_REDUCED_MOTION", raising=False)
        monkeypatch.delenv("NO_COLOR", raising=False)
        
        assert should_reduce_motion() is False

    def test_reduced_motion_with_env_var(self, monkeypatch):
        """Reduced motion enabled by env var."""
        monkeypatch.setenv("SUNWELL_REDUCED_MOTION", "1")
        
        assert should_reduce_motion() is True

    def test_reduced_motion_with_no_color(self, monkeypatch):
        """Reduced motion enabled by NO_COLOR."""
        monkeypatch.setenv("NO_COLOR", "1")
        
        assert should_reduce_motion() is True

    def test_plain_mode_default(self, monkeypatch):
        """Plain mode respects environment."""
        monkeypatch.delenv("SUNWELL_PLAIN", raising=False)
        monkeypatch.delenv("NO_COLOR", raising=False)
        
        assert is_plain_mode() is False

    def test_plain_mode_with_env_var(self, monkeypatch):
        """Plain mode enabled by env var."""
        monkeypatch.setenv("SUNWELL_PLAIN", "1")
        
        assert is_plain_mode() is True

    def test_context_has_accessibility_flags(self):
        """Context tracks accessibility settings."""
        ctx = RenderContext()
        
        # Should have these attributes
        assert hasattr(ctx, "reduced_motion")
        assert hasattr(ctx, "plain_mode")
        assert isinstance(ctx.reduced_motion, bool)
        assert isinstance(ctx.plain_mode, bool)


class TestStatusBarIntegration:
    """Tests for StatusBar integration with RenderContext."""

    def test_has_status_bar_default_false(self):
        """No StatusBar attached by default."""
        ctx = RenderContext()
        assert ctx.has_status_bar() is False

    def test_attach_status_bar(self):
        """Can attach a StatusBar."""
        from unittest.mock import MagicMock
        
        ctx = RenderContext()
        mock_bar = MagicMock()
        mock_bar.metrics = MagicMock()
        
        ctx.attach_status_bar(mock_bar)
        
        assert ctx.has_status_bar() is True
        # Should sync initial metrics
        mock_bar.update.assert_called_once()

    def test_detach_status_bar(self):
        """Can detach a StatusBar."""
        from unittest.mock import MagicMock
        
        ctx = RenderContext()
        mock_bar = MagicMock()
        mock_bar.metrics = MagicMock()
        ctx.attach_status_bar(mock_bar)
        
        result = ctx.detach_status_bar()
        
        assert result is mock_bar
        assert ctx.has_status_bar() is False

    def test_detach_returns_none_when_not_attached(self):
        """Detach returns None when no StatusBar attached."""
        ctx = RenderContext()
        result = ctx.detach_status_bar()
        assert result is None

    def test_update_status_with_bar(self):
        """update_status syncs metrics to StatusBar."""
        from unittest.mock import MagicMock
        
        ctx = RenderContext()
        mock_bar = MagicMock()
        mock_bar.metrics = MagicMock()
        ctx.attach_status_bar(mock_bar)
        
        # Clear the initial call from attach
        mock_bar.update.reset_mock()
        
        # Add some metrics
        ctx.add_tokens(1000, 0.05)
        ctx.update_status()
        
        # Should have synced cost
        assert mock_bar.metrics.cost == 0.05
        mock_bar.update.assert_called_once()

    def test_update_status_without_bar(self):
        """update_status is safe when no StatusBar attached."""
        ctx = RenderContext()
        ctx.add_tokens(1000, 0.05)
        
        # Should not raise
        ctx.update_status()

    def test_reset_detaches_status_bar(self):
        """reset() clears StatusBar reference."""
        from unittest.mock import MagicMock
        
        ctx = RenderContext()
        mock_bar = MagicMock()
        mock_bar.metrics = MagicMock()
        ctx.attach_status_bar(mock_bar)
        
        ctx.reset()
        
        assert ctx.has_status_bar() is False


class TestLiveSession:
    """Tests for live_session context manager."""

    def test_live_session_without_status(self):
        """live_session without status bar."""
        from sunwell.interface.cli.core.events import live_session
        
        reset_render_context()
        
        with live_session(enable_status=False) as ctx:
            assert ctx is not None
            assert ctx.has_status_bar() is False

    def test_live_session_yields_context(self):
        """live_session yields RenderContext."""
        from sunwell.interface.cli.core.events import live_session
        
        reset_render_context()
        
        with live_session(enable_status=False) as ctx:
            assert isinstance(ctx, RenderContext)


class TestModuleFunctions:
    """Tests for module-level functions."""

    def test_get_render_context_singleton(self):
        """get_render_context returns singleton."""
        ctx1 = get_render_context()
        ctx2 = get_render_context()
        assert ctx1 is ctx2

    def test_reset_render_context(self):
        """reset_render_context resets the singleton."""
        ctx = get_render_context()
        ctx.add_tokens(1000)
        
        reset_render_context()
        
        ctx2 = get_render_context()
        assert ctx2.total_tokens == 0
