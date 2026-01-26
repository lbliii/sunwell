"""Tests for Agent Constellation spawn types (RFC-130).

Tests specialist spawning types and lifecycle.
"""

from datetime import datetime, timedelta

import pytest

from sunwell.agent.utils.spawn import (
    SpawnDepthExceededError,
    SpawnRequest,
    SpecialistResult,
    SpecialistState,
)


class TestSpawnDepthExceededError:
    """Tests for SpawnDepthExceededError exception."""

    def test_exception_message(self) -> None:
        """Exception has informative message."""
        exc = SpawnDepthExceededError(current_depth=4, max_depth=3)

        assert "4" in str(exc)
        assert "3" in str(exc)
        assert exc.current_depth == 4
        assert exc.max_depth == 3

    def test_exception_is_exception(self) -> None:
        """SpawnDepthExceededError is a proper exception."""
        with pytest.raises(SpawnDepthExceededError):
            raise SpawnDepthExceededError(current_depth=5, max_depth=3)


class TestSpawnRequest:
    """Tests for SpawnRequest dataclass."""

    def test_minimal_request(self) -> None:
        """SpawnRequest works with minimal fields."""
        request = SpawnRequest(
            parent_id="agent-main",
            role="code_reviewer",
            focus="Review auth module",
            reason="Needs security expertise",
        )

        assert request.parent_id == "agent-main"
        assert request.role == "code_reviewer"
        assert request.focus == "Review auth module"
        assert request.reason == "Needs security expertise"
        assert request.tools == ()
        assert request.context_keys == ()
        assert request.budget_tokens == 5_000

    def test_full_request(self) -> None:
        """SpawnRequest accepts all fields."""
        request = SpawnRequest(
            parent_id="specialist-1",
            role="debugger",
            focus="Fix memory leak",
            reason="Runtime error analysis",
            tools=("read_file", "grep", "run_command"),
            context_keys=("error_log", "stack_trace"),
            budget_tokens=10_000,
        )

        assert request.tools == ("read_file", "grep", "run_command")
        assert request.context_keys == ("error_log", "stack_trace")
        assert request.budget_tokens == 10_000

    def test_request_is_frozen(self) -> None:
        """SpawnRequest is immutable."""
        request = SpawnRequest(
            parent_id="agent-main",
            role="reviewer",
            focus="Review code",
            reason="Quality check",
        )

        with pytest.raises(AttributeError):
            request.role = "different_role"  # type: ignore

    def test_to_dict(self) -> None:
        """to_dict serializes all fields."""
        request = SpawnRequest(
            parent_id="agent-main",
            role="architect",
            focus="Design API",
            reason="Complex architecture",
            tools=("read_file",),
            budget_tokens=8_000,
        )

        data = request.to_dict()

        assert data["parent_id"] == "agent-main"
        assert data["role"] == "architect"
        assert data["focus"] == "Design API"
        assert data["reason"] == "Complex architecture"
        assert data["tools"] == ["read_file"]
        assert data["budget_tokens"] == 8_000

    def test_from_dict(self) -> None:
        """from_dict deserializes correctly."""
        data = {
            "parent_id": "agent-main",
            "role": "tester",
            "focus": "Write unit tests",
            "reason": "Test coverage",
            "tools": ["read_file", "write_file"],
            "context_keys": ["code_context"],
            "budget_tokens": 3_000,
        }

        request = SpawnRequest.from_dict(data)

        assert request.parent_id == "agent-main"
        assert request.role == "tester"
        assert request.tools == ("read_file", "write_file")
        assert request.context_keys == ("code_context",)
        assert request.budget_tokens == 3_000

    def test_from_dict_with_defaults(self) -> None:
        """from_dict handles missing optional fields."""
        data = {
            "parent_id": "agent-main",
            "role": "helper",
            "focus": "Do something",
            "reason": "Needed",
        }

        request = SpawnRequest.from_dict(data)

        assert request.tools == ()
        assert request.context_keys == ()
        assert request.budget_tokens == 5_000


class TestSpecialistState:
    """Tests for SpecialistState dataclass."""

    def test_initial_state(self) -> None:
        """SpecialistState initializes as running."""
        state = SpecialistState(
            id="specialist-123",
            parent_id="agent-main",
            focus="Review code",
        )

        assert state.id == "specialist-123"
        assert state.is_running
        assert state.completed_at is None
        assert state.result is None
        assert state.tokens_used == 0

    def test_mark_complete(self) -> None:
        """mark_complete updates state correctly."""
        state = SpecialistState(
            id="specialist-456",
            parent_id="agent-main",
            focus="Fix bug",
        )

        state.mark_complete(result="Bug fixed", tokens_used=1_500)

        assert not state.is_running
        assert state.completed_at is not None
        assert state.result == "Bug fixed"
        assert state.tokens_used == 1_500

    def test_duration_while_running(self) -> None:
        """duration_seconds is None while running."""
        state = SpecialistState(
            id="specialist-789",
            parent_id="agent-main",
            focus="Analyze code",
        )

        assert state.duration_seconds is None

    def test_duration_after_complete(self) -> None:
        """duration_seconds calculates correctly after completion."""
        start = datetime.now()
        state = SpecialistState(
            id="specialist-abc",
            parent_id="agent-main",
            focus="Process data",
            started_at=start,
        )

        # Complete after simulated delay
        state.mark_complete(result="Done", tokens_used=500)

        assert state.duration_seconds is not None
        assert state.duration_seconds >= 0

    def test_to_dict(self) -> None:
        """to_dict serializes state."""
        state = SpecialistState(
            id="specialist-def",
            parent_id="agent-main",
            focus="Generate code",
            depth=1,
        )

        data = state.to_dict()

        assert data["id"] == "specialist-def"
        assert data["parent_id"] == "agent-main"
        assert data["focus"] == "Generate code"
        assert data["depth"] == 1
        assert data["completed_at"] is None
        assert "started_at" in data

    def test_to_dict_completed(self) -> None:
        """to_dict includes completion data."""
        state = SpecialistState(
            id="specialist-ghi",
            parent_id="agent-main",
            focus="Review PR",
        )
        state.mark_complete(result={"approved": True}, tokens_used=800)

        data = state.to_dict()

        assert data["completed_at"] is not None
        assert data["result"] == {"approved": True}
        assert data["tokens_used"] == 800

    def test_from_dict(self) -> None:
        """from_dict deserializes state."""
        now = datetime.now()
        data = {
            "id": "specialist-jkl",
            "parent_id": "agent-main",
            "focus": "Debug issue",
            "started_at": now.isoformat(),
            "completed_at": None,
            "result": None,
            "tokens_used": 0,
            "depth": 2,
        }

        state = SpecialistState.from_dict(data)

        assert state.id == "specialist-jkl"
        assert state.depth == 2
        assert state.is_running

    def test_from_dict_completed(self) -> None:
        """from_dict handles completed state."""
        start = datetime.now()
        end = start + timedelta(seconds=5)
        data = {
            "id": "specialist-mno",
            "parent_id": "agent-main",
            "focus": "Analyze logs",
            "started_at": start.isoformat(),
            "completed_at": end.isoformat(),
            "result": "Found 3 errors",
            "tokens_used": 1200,
            "depth": 0,
        }

        state = SpecialistState.from_dict(data)

        assert not state.is_running
        assert state.result == "Found 3 errors"
        assert state.tokens_used == 1200


class TestSpecialistResult:
    """Tests for SpecialistResult dataclass."""

    def test_successful_result(self) -> None:
        """SpecialistResult captures success."""
        result = SpecialistResult(
            specialist_id="specialist-pqr",
            success=True,
            output={"files_fixed": ["auth.py", "models.py"]},
            summary="Fixed 2 files",
            tokens_used=2_000,
            duration_seconds=15.5,
            learnings=("Always check null", "Use type hints"),
        )

        assert result.success
        assert result.specialist_id == "specialist-pqr"
        assert result.tokens_used == 2_000
        assert len(result.learnings) == 2

    def test_failed_result(self) -> None:
        """SpecialistResult captures failure."""
        result = SpecialistResult(
            specialist_id="specialist-stu",
            success=False,
            output=None,
            summary="Could not resolve dependency conflict",
        )

        assert not result.success
        assert result.output is None

    def test_result_is_frozen(self) -> None:
        """SpecialistResult is immutable."""
        result = SpecialistResult(
            specialist_id="specialist-vwx",
            success=True,
            output="Done",
            summary="Completed",
        )

        with pytest.raises(AttributeError):
            result.success = False  # type: ignore

    def test_to_dict(self) -> None:
        """to_dict serializes result."""
        result = SpecialistResult(
            specialist_id="specialist-yz",
            success=True,
            output={"status": "ok"},
            summary="All checks passed",
            tokens_used=500,
            duration_seconds=3.2,
            learnings=("Pattern A is better",),
        )

        data = result.to_dict()

        assert data["specialist_id"] == "specialist-yz"
        assert data["success"] is True
        assert data["output"] == {"status": "ok"}
        assert data["learnings"] == ["Pattern A is better"]
        assert data["duration_seconds"] == 3.2
