"""Tests for the Tool Invocation Tracker."""

import pytest

from sunwell.tools.tracking.tracker import (
    InvocationTracker,
    ToolCategory,
    TOOL_CATEGORIES,
    can_self_correct,
    get_self_correction_strategy,
)


class TestToolCategories:
    """Tests for tool categorization."""

    def test_write_file_is_output(self):
        """write_file should be OUTPUT category."""
        assert TOOL_CATEGORIES["write_file"] == ToolCategory.OUTPUT

    def test_read_file_is_input(self):
        """read_file should be INPUT category."""
        assert TOOL_CATEGORIES["read_file"] == ToolCategory.INPUT

    def test_web_search_is_query(self):
        """web_search should be QUERY category."""
        assert TOOL_CATEGORIES["web_search"] == ToolCategory.QUERY


class TestCanSelfCorrect:
    """Tests for self-correction capability detection."""

    def test_write_file_can_self_correct(self):
        """write_file can be self-corrected."""
        assert can_self_correct("write_file") is True

    def test_edit_file_can_self_correct(self):
        """edit_file can be self-corrected."""
        assert can_self_correct("edit_file") is True

    def test_run_command_can_self_correct(self):
        """run_command can be self-corrected."""
        assert can_self_correct("run_command") is True

    def test_read_file_cannot_self_correct(self):
        """read_file cannot be self-corrected (it's an input)."""
        assert can_self_correct("read_file") is False

    def test_search_cannot_self_correct(self):
        """search cannot be self-corrected (it's an input)."""
        assert can_self_correct("search") is False


class TestSelfCorrectionStrategies:
    """Tests for self-correction strategy lookup."""

    def test_write_file_strategy(self):
        """write_file should use write_model_output strategy."""
        assert get_self_correction_strategy("write_file") == "write_model_output"

    def test_edit_file_strategy(self):
        """edit_file should use apply_model_diff strategy."""
        assert get_self_correction_strategy("edit_file") == "apply_model_diff"

    def test_run_command_strategy(self):
        """run_command should use execute_suggested_command strategy."""
        assert get_self_correction_strategy("run_command") == "execute_suggested_command"

    def test_read_file_has_no_strategy(self):
        """read_file has no self-correction strategy."""
        assert get_self_correction_strategy("read_file") is None


class TestInvocationTracker:
    """Tests for the InvocationTracker class."""

    def test_record_invocation(self):
        """Should record a tool invocation."""
        tracker = InvocationTracker()

        inv = tracker.record(
            tool_name="write_file",
            arguments={"path": "test.py", "content": "print('hi')"},
            result="Success",
            success=True,
        )

        assert inv.tool_name == "write_file"
        assert inv.arguments["path"] == "test.py"
        assert inv.success is True
        assert len(tracker.invocations) == 1

    def test_was_called(self):
        """Should detect if a tool was called."""
        tracker = InvocationTracker()

        tracker.record("write_file", {"path": "x.py"}, success=True)

        assert tracker.was_called("write_file") is True
        assert tracker.was_called("read_file") is False

    def test_was_called_with(self):
        """Should detect if a tool was called with specific args."""
        tracker = InvocationTracker()

        tracker.record("write_file", {"path": "x.py", "content": "code"}, success=True)
        tracker.record("write_file", {"path": "y.py", "content": "more"}, success=True)

        assert tracker.was_called_with("write_file", path="x.py") is True
        assert tracker.was_called_with("write_file", path="y.py") is True
        assert tracker.was_called_with("write_file", path="z.py") is False

    def test_get_calls(self):
        """Should get all invocations of a specific tool."""
        tracker = InvocationTracker()

        tracker.record("write_file", {"path": "a.py"}, success=True)
        tracker.record("read_file", {"path": "b.py"}, success=True)
        tracker.record("write_file", {"path": "c.py"}, success=True)

        write_calls = tracker.get_calls("write_file")
        assert len(write_calls) == 2
        assert write_calls[0].arguments["path"] == "a.py"
        assert write_calls[1].arguments["path"] == "c.py"

    def test_get_successful_calls(self):
        """Should get only successful invocations."""
        tracker = InvocationTracker()

        tracker.record("write_file", {"path": "a.py"}, success=True)
        tracker.record("write_file", {"path": "b.py"}, success=False)
        tracker.record("write_file", {"path": "c.py"}, success=True)

        successful = tracker.get_successful_calls("write_file")
        assert len(successful) == 2
        assert all(inv.success for inv in successful)

    def test_get_output_tool_calls(self):
        """Should get only OUTPUT category tool calls."""
        tracker = InvocationTracker()

        tracker.record("write_file", {"path": "a.py"}, success=True)
        tracker.record("read_file", {"path": "b.py"}, success=True)
        tracker.record("edit_file", {"path": "c.py"}, success=True)

        output_calls = tracker.get_output_tool_calls()
        assert len(output_calls) == 2
        assert all(inv.tool_name in ("write_file", "edit_file") for inv in output_calls)

    def test_get_missing_invocations(self):
        """Should identify missing expected tool calls."""
        tracker = InvocationTracker()

        tracker.record("write_file", {"path": "a.py"}, success=True)

        expected = {
            "write_file": [
                {"path": "a.py"},  # Called ✓
                {"path": "b.py"},  # Not called ✗
            ],
            "edit_file": [
                {"path": "c.py"},  # Not called ✗
            ],
        }

        missing = tracker.get_missing_invocations(expected)

        assert "write_file" in missing
        assert len(missing["write_file"]) == 1
        assert missing["write_file"][0]["path"] == "b.py"

        assert "edit_file" in missing
        assert len(missing["edit_file"]) == 1

    def test_summary(self):
        """Should provide accurate summary statistics."""
        tracker = InvocationTracker()

        tracker.record("write_file", {"path": "a.py"}, success=True)
        tracker.record("write_file", {"path": "b.py"}, success=False, error="Permission denied")
        tracker.record("read_file", {"path": "c.py"}, success=True)
        tracker.record("write_file", {"path": "d.py"}, success=True, self_corrected=True)

        summary = tracker.summary()

        assert summary["total"] == 4
        assert summary["successful"] == 3
        assert summary["failed"] == 1
        assert summary["self_corrected"] == 1
        assert summary["by_tool"]["write_file"] == 3
        assert summary["by_tool"]["read_file"] == 1

    def test_clear(self):
        """Should clear all invocations."""
        tracker = InvocationTracker()

        tracker.record("write_file", {"path": "a.py"}, success=True)
        tracker.record("read_file", {"path": "b.py"}, success=True)

        assert len(tracker.invocations) == 2

        tracker.clear()

        assert len(tracker.invocations) == 0
        assert tracker.was_called("write_file") is False
