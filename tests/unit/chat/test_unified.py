"""Tests for UnifiedChatLoop (RFC-135).

Verifies the unified chat-agent experience state machine.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from sunwell.agent.chat import (
    ChatCheckpoint,
    ChatCheckpointType,
    CheckpointResponse,
    IntentClassification,
    IntentNode,
    LoopState,
    UnifiedChatLoop,
)


class TestLoopState:
    """Tests for LoopState enum."""

    def test_all_states_defined(self) -> None:
        """All expected states exist."""
        states = {s.value for s in LoopState}
        assert "idle" in states
        assert "classifying" in states
        assert "conversing" in states
        assert "planning" in states
        assert "confirming" in states
        assert "executing" in states
        assert "interrupted" in states
        assert "completed" in states
        assert "error" in states


class TestCheckpointResponse:
    """Tests for CheckpointResponse convenience properties."""

    def test_proceed_y(self) -> None:
        """'y' means proceed."""
        assert CheckpointResponse("y").proceed
        assert CheckpointResponse("Y").proceed
        assert CheckpointResponse("yes").proceed
        assert CheckpointResponse("YES").proceed

    def test_proceed_no(self) -> None:
        """Other values don't mean proceed."""
        assert not CheckpointResponse("n").proceed
        assert not CheckpointResponse("abort").proceed

    def test_abort(self) -> None:
        """Abort detection."""
        assert CheckpointResponse("abort").abort
        assert CheckpointResponse("q").abort
        assert CheckpointResponse("quit").abort
        assert not CheckpointResponse("y").abort

    def test_skip(self) -> None:
        """Skip detection."""
        assert CheckpointResponse("s").skip
        assert CheckpointResponse("skip").skip
        assert CheckpointResponse("n").skip
        assert not CheckpointResponse("y").skip

    def test_edit(self) -> None:
        """Edit detection."""
        assert CheckpointResponse("e").edit
        assert CheckpointResponse("edit").edit
        assert not CheckpointResponse("y").edit

    def test_retry(self) -> None:
        """Retry detection."""
        assert CheckpointResponse("r").retry
        assert CheckpointResponse("retry").retry
        assert not CheckpointResponse("y").retry

    def test_autofix(self) -> None:
        """Autofix detection."""
        assert CheckpointResponse("a").autofix
        assert CheckpointResponse("auto-fix").autofix
        assert CheckpointResponse("fix").autofix
        assert not CheckpointResponse("y").autofix

    def test_additional_input(self) -> None:
        """Additional input is stored."""
        r = CheckpointResponse("respond", additional_input="more details")
        assert r.choice == "respond"
        assert r.additional_input == "more details"


class TestChatCheckpoint:
    """Tests for ChatCheckpoint dataclass."""

    def test_frozen(self) -> None:
        """Checkpoint is immutable."""
        c = ChatCheckpoint(
            type=ChatCheckpointType.CONFIRMATION,
            message="test",
        )
        with pytest.raises(AttributeError):
            c.message = "changed"  # type: ignore[misc]

    def test_confirmation_checkpoint(self) -> None:
        """Confirmation checkpoint has expected fields."""
        c = ChatCheckpoint(
            type=ChatCheckpointType.CONFIRMATION,
            message="Plan ready. Proceed?",
            options=("Y", "n", "edit"),
            default="Y",
        )
        assert c.type == ChatCheckpointType.CONFIRMATION
        assert "Proceed" in c.message
        assert "Y" in c.options
        assert c.default == "Y"

    def test_failure_checkpoint(self) -> None:
        """Failure checkpoint has error and recovery options."""
        c = ChatCheckpoint(
            type=ChatCheckpointType.FAILURE,
            message="Validation failed",
            error="Type error on line 42",
            recovery_options=("auto-fix", "skip", "abort"),
            default="auto-fix",
        )
        assert c.type == ChatCheckpointType.FAILURE
        assert c.error == "Type error on line 42"
        assert "auto-fix" in c.recovery_options

    def test_completion_checkpoint(self) -> None:
        """Completion checkpoint has summary and files."""
        c = ChatCheckpoint(
            type=ChatCheckpointType.COMPLETION,
            message="Done",
            summary="Created 2 files, modified 1",
            files_changed=("src/new.py", "tests/test_new.py", "README.md"),
        )
        assert c.type == ChatCheckpointType.COMPLETION
        assert c.summary is not None
        assert len(c.files_changed) == 3


class TestUnifiedChatLoopInit:
    """Tests for UnifiedChatLoop initialization."""

    def test_init_defaults(self) -> None:
        """Default initialization."""
        model = MagicMock()
        workspace = Path("/tmp/test")
        loop = UnifiedChatLoop(
            model=model,
            tool_executor=None,
            workspace=workspace,
        )
        assert loop.model is model
        # Path resolves symlinks (macOS: /tmp -> /private/tmp)
        assert loop.workspace == workspace.resolve()
        assert loop.auto_confirm is False
        assert loop.stream_progress is True
        assert loop.state == LoopState.IDLE

    def test_init_custom_options(self) -> None:
        """Custom options are applied."""
        model = MagicMock()
        loop = UnifiedChatLoop(
            model=model,
            tool_executor=None,
            workspace=Path("/tmp/test"),
            auto_confirm=True,
            stream_progress=False,
        )
        assert loop.auto_confirm is True
        assert loop.stream_progress is False

    def test_is_executing_property(self) -> None:
        """is_executing reflects state."""
        model = MagicMock()
        loop = UnifiedChatLoop(
            model=model,
            tool_executor=None,
            workspace=Path("/tmp/test"),
        )
        assert loop.is_executing is False
        loop._state = LoopState.EXECUTING
        assert loop.is_executing is True
        loop._state = LoopState.PLANNING
        assert loop.is_executing is True
        loop._state = LoopState.CONVERSING
        assert loop.is_executing is False

    def test_request_cancel(self) -> None:
        """Cancel request sets flag."""
        model = MagicMock()
        loop = UnifiedChatLoop(
            model=model,
            tool_executor=None,
            workspace=Path("/tmp/test"),
        )
        assert loop._cancel_requested is False
        loop.request_cancel()
        assert loop._cancel_requested is True


class TestPlanFormatting:
    """Tests for plan summary formatting."""

    def test_format_plan_with_counts_only(self) -> None:
        """Format plan when only counts are provided."""
        from sunwell.agent.chat.execution import format_plan_summary

        plan_data = {"tasks": 5, "gates": 2}
        result = format_plan_summary(plan_data)
        assert "5 tasks" in result
        assert "2 validation gates" in result
        assert "Proceed?" in result

    def test_format_plan_with_task_list(self) -> None:
        """Format plan with detailed task list."""
        from sunwell.agent.chat.execution import format_plan_summary

        plan_data = {
            "tasks": 3,
            "gates": 1,
            "task_list": [
                {"description": "Create user model"},
                {"description": "Add authentication endpoint"},
                {"description": "Write tests"},
            ],
        }
        result = format_plan_summary(plan_data)
        assert "Create user model" in result
        assert "Add authentication endpoint" in result
        assert "Write tests" in result

    def test_format_plan_truncates_long_list(self) -> None:
        """Only first 10 tasks shown, with '... and N more'."""
        from sunwell.agent.chat.execution import format_plan_summary

        plan_data = {
            "tasks": 15,
            "gates": 0,
            "task_list": [{"description": f"Task {i}"} for i in range(15)],
        }
        result = format_plan_summary(plan_data)
        assert "Task 9" in result  # 10th task (0-indexed)
        assert "Task 10" not in result  # 11th task hidden
        assert "... and 5 more" in result

    def test_format_plan_empty(self) -> None:
        """Empty plan still shows structure."""
        from sunwell.agent.chat.execution import format_plan_summary

        plan_data = {"tasks": 0, "gates": 0}
        result = format_plan_summary(plan_data)
        assert "0 tasks" in result
        assert "Proceed?" in result


class TestCommandHandling:
    """Tests for /slash command handling."""

    @pytest.fixture
    def loop(self) -> UnifiedChatLoop:
        """Create loop for testing."""
        model = MagicMock()
        return UnifiedChatLoop(
            model=model,
            tool_executor=None,
            workspace=Path("/tmp/test"),
        )

    def test_agent_command_returns_goal(self, loop: UnifiedChatLoop) -> None:
        """/agent <goal> returns (None, goal)."""
        response, goal = loop._handle_command("/agent Add user auth")
        assert response is None
        assert goal == "Add user auth"

    def test_agent_command_without_goal(self, loop: UnifiedChatLoop) -> None:
        """/agent without argument returns unknown command."""
        response, goal = loop._handle_command("/agent")
        assert "Unknown command" in response
        assert goal is None

    def test_chat_command(self, loop: UnifiedChatLoop) -> None:
        """/chat returns conversation mode message."""
        response, goal = loop._handle_command("/chat")
        assert "conversation mode" in response.lower()
        assert goal is None

    def test_abort_not_executing(self, loop: UnifiedChatLoop) -> None:
        """/abort when not executing returns no execution message."""
        response, goal = loop._handle_command("/abort")
        assert "No execution" in response
        assert goal is None

    def test_abort_while_executing(self, loop: UnifiedChatLoop) -> None:
        """/abort while executing requests cancel."""
        loop._state = LoopState.EXECUTING
        response, goal = loop._handle_command("/abort")
        assert "Cancellation requested" in response
        assert loop._cancel_requested

    def test_status_command(self, loop: UnifiedChatLoop) -> None:
        """/status shows state, history count, and tools status."""
        loop.conversation_history = [{"role": "user", "content": "hi"}]
        response, goal = loop._handle_command("/status")
        assert "idle" in response.lower()
        assert "1 messages" in response
        assert "Tools: disabled" in response

    def test_tools_on_when_disabled(self, loop: UnifiedChatLoop) -> None:
        """/tools on enables tool executor when disabled."""
        assert loop.tool_executor is None
        response, goal = loop._handle_command("/tools on")
        assert "enabled" in response.lower()
        assert loop.tool_executor is not None
        assert goal is None

    def test_tools_on_when_already_enabled(self) -> None:
        """/tools on when already enabled returns message."""
        model = MagicMock()
        mock_executor = MagicMock()
        loop = UnifiedChatLoop(
            model=model,
            tool_executor=mock_executor,
            workspace=Path("/tmp/test"),
        )
        response, goal = loop._handle_command("/tools on")
        assert "already enabled" in response.lower()
        assert loop.tool_executor is mock_executor

    def test_tools_off_when_enabled(self) -> None:
        """/tools off disables tool executor when enabled."""
        model = MagicMock()
        mock_executor = MagicMock()
        loop = UnifiedChatLoop(
            model=model,
            tool_executor=mock_executor,
            workspace=Path("/tmp/test"),
        )
        response, goal = loop._handle_command("/tools off")
        assert "disabled" in response.lower()
        assert loop.tool_executor is None

    def test_tools_off_when_already_disabled(self, loop: UnifiedChatLoop) -> None:
        """/tools off when already disabled returns message."""
        assert loop.tool_executor is None
        response, goal = loop._handle_command("/tools off")
        assert "already disabled" in response.lower()

    def test_tools_no_arg_shows_status(self, loop: UnifiedChatLoop) -> None:
        """/tools without argument shows current status."""
        response, goal = loop._handle_command("/tools")
        assert "disabled" in response.lower()
        assert "/tools on" in response or "/tools off" in response

    def test_unknown_command(self, loop: UnifiedChatLoop) -> None:
        """Unknown command returns error message."""
        response, goal = loop._handle_command("/unknown")
        assert "Unknown command" in response
        assert goal is None


class TestEventDataIntegration:
    """Tests verifying event data keys match expectations."""

    def test_plan_winner_event_keys(self) -> None:
        """PLAN_WINNER event has expected keys."""
        from sunwell.agent.events import plan_winner_event

        event = plan_winner_event(tasks=5, gates=2, technique="harmonic")
        assert event.data["tasks"] == 5
        assert event.data["gates"] == 2
        assert event.data["technique"] == "harmonic"

    def test_complete_event_keys(self) -> None:
        """COMPLETE event has expected keys."""
        from sunwell.agent.events import complete_event

        event = complete_event(tasks_completed=5, gates_passed=2, duration_s=1.5)
        assert event.data["tasks_completed"] == 5
        assert event.data["gates_passed"] == 2
        assert event.data["duration_s"] == 1.5

    def test_task_start_event_keys(self) -> None:
        """TASK_START event has expected keys."""
        from sunwell.agent.events import task_start_event

        event = task_start_event(task_id="task-1", description="Create file")
        assert event.data["task_id"] == "task-1"
        assert event.data["description"] == "Create file"

    def test_task_complete_event_keys(self) -> None:
        """TASK_COMPLETE event has expected keys."""
        from sunwell.agent.events import task_complete_event

        event = task_complete_event(task_id="task-1", duration_ms=150)
        assert event.data["task_id"] == "task-1"
        assert event.data["duration_ms"] == 150

    def test_gate_fail_event_keys(self) -> None:
        """GATE_FAIL event has expected keys for error handling."""
        from sunwell.agent.events import EventType, AgentEvent

        # Gate fail events should have error info
        event = AgentEvent(
            EventType.GATE_FAIL,
            {"gate_name": "typecheck", "error_message": "Type error on line 42"},
        )
        assert event.data["gate_name"] == "typecheck"
        assert event.data["error_message"] == "Type error on line 42"
