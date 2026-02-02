"""Unit tests for SessionStore and related types."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from sunwell.planning.naaru.session_store import SessionStore, SessionSummary
from sunwell.planning.naaru.types import (
    CompletedTask,
    SessionConfig,
    SessionState,
    SessionStatus,
)


class TestCompletedTask:
    """Test CompletedTask serialization."""

    def test_to_dict(self) -> None:
        """Test CompletedTask.to_dict() serialization."""
        task = CompletedTask(
            opportunity_id="opp-123",
            proposal_id="prop-456",
            result="auto_applied",
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            details=(("key1", "value1"), ("key2", 42)),
        )

        data = task.to_dict()

        assert data["opportunity_id"] == "opp-123"
        assert data["proposal_id"] == "prop-456"
        assert data["result"] == "auto_applied"
        assert data["timestamp"] == "2024-01-15T10:30:00"
        assert data["details"] == {"key1": "value1", "key2": 42}

    def test_from_dict(self) -> None:
        """Test CompletedTask.from_dict() deserialization."""
        data = {
            "opportunity_id": "opp-789",
            "proposal_id": None,
            "result": "queued",
            "timestamp": "2024-02-20T14:45:00",
            "details": {"foo": "bar"},
        }

        task = CompletedTask.from_dict(data)

        assert task.opportunity_id == "opp-789"
        assert task.proposal_id is None
        assert task.result == "queued"
        assert task.timestamp == datetime(2024, 2, 20, 14, 45, 0)
        assert dict(task.details) == {"foo": "bar"}

    def test_roundtrip(self) -> None:
        """Test CompletedTask serialization roundtrip."""
        original = CompletedTask(
            opportunity_id="opp-abc",
            proposal_id="prop-def",
            result="failed",
            timestamp=datetime(2024, 3, 10, 8, 0, 0),
            details=(("error", "timeout"),),
        )

        data = original.to_dict()
        restored = CompletedTask.from_dict(data)

        assert restored.opportunity_id == original.opportunity_id
        assert restored.proposal_id == original.proposal_id
        assert restored.result == original.result
        assert restored.timestamp == original.timestamp
        # Details are converted to/from dict, so compare as dict
        assert dict(restored.details) == dict(original.details)


class TestSessionState:
    """Test SessionState serialization."""

    def test_to_dict_includes_completed(self) -> None:
        """Test SessionState.to_dict() includes completed tasks."""
        state = SessionState(
            session_id="sess-123",
            config=SessionConfig(goals=("test goal",)),
            status=SessionStatus.PAUSED,
        )
        state.completed = [
            CompletedTask(
                opportunity_id="opp-1",
                proposal_id="prop-1",
                result="auto_applied",
                timestamp=datetime(2024, 1, 1, 12, 0, 0),
            ),
        ]

        data = state.to_dict()

        assert len(data["completed"]) == 1
        assert data["completed"][0]["opportunity_id"] == "opp-1"

    def test_from_dict_loads_completed(self) -> None:
        """Test SessionState.from_dict() loads completed tasks."""
        data = {
            "session_id": "sess-456",
            "config": {"goals": ["test goal"]},
            "status": "running",
            "started_at": "2024-01-15T10:00:00",
            "completed": [
                {
                    "opportunity_id": "opp-2",
                    "proposal_id": "prop-2",
                    "result": "queued",
                    "timestamp": "2024-01-15T11:00:00",
                    "details": {},
                },
            ],
        }

        state = SessionState.from_dict(data)

        assert len(state.completed) == 1
        assert state.completed[0].opportunity_id == "opp-2"
        assert state.completed[0].result == "queued"

    def test_roundtrip_with_completed(self) -> None:
        """Test SessionState roundtrip preserves completed tasks."""
        original = SessionState(
            session_id="sess-789",
            config=SessionConfig(goals=("goal 1", "goal 2")),
            status=SessionStatus.COMPLETED,
        )
        original.completed = [
            CompletedTask(
                opportunity_id="opp-a",
                proposal_id=None,
                result="auto_applied",
                timestamp=datetime(2024, 2, 1, 9, 0, 0),
            ),
            CompletedTask(
                opportunity_id="opp-b",
                proposal_id="prop-b",
                result="failed",
                timestamp=datetime(2024, 2, 1, 9, 30, 0),
                details=(("reason", "timeout"),),
            ),
        ]

        data = original.to_dict()
        restored = SessionState.from_dict(data)

        assert len(restored.completed) == 2
        assert restored.completed[0].opportunity_id == "opp-a"
        assert restored.completed[1].opportunity_id == "opp-b"
        assert dict(restored.completed[1].details) == {"reason": "timeout"}


class TestSessionStore:
    """Test SessionStore persistence."""

    @pytest.fixture
    def temp_store(self) -> SessionStore:
        """Create a SessionStore with a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield SessionStore(sessions_dir=Path(tmpdir))

    def test_save_and_load(self, temp_store: SessionStore) -> None:
        """Test saving and loading a session."""
        state = SessionState(
            session_id="test-session",
            config=SessionConfig(goals=("test goal",)),
            status=SessionStatus.RUNNING,
        )

        temp_store.save(state)
        loaded = temp_store.load("test-session")

        assert loaded is not None
        assert loaded.session_id == "test-session"
        assert loaded.status == SessionStatus.RUNNING

    def test_load_nonexistent(self, temp_store: SessionStore) -> None:
        """Test loading a nonexistent session returns None."""
        result = temp_store.load("nonexistent")
        assert result is None

    def test_delete(self, temp_store: SessionStore) -> None:
        """Test deleting a session."""
        state = SessionState(
            session_id="to-delete",
            config=SessionConfig(goals=("goal",)),
        )
        temp_store.save(state)

        assert temp_store.delete("to-delete") is True
        assert temp_store.load("to-delete") is None

    def test_delete_nonexistent(self, temp_store: SessionStore) -> None:
        """Test deleting a nonexistent session returns False."""
        assert temp_store.delete("nonexistent") is False

    def test_list_sessions(self, temp_store: SessionStore) -> None:
        """Test listing sessions."""
        # Create multiple sessions
        for i in range(3):
            state = SessionState(
                session_id=f"session-{i}",
                config=SessionConfig(goals=(f"goal {i}",)),
                status=SessionStatus.RUNNING if i == 0 else SessionStatus.COMPLETED,
            )
            temp_store.save(state)

        sessions = temp_store.list_sessions()

        assert len(sessions) == 3

    def test_list_sessions_filter_by_status(self, temp_store: SessionStore) -> None:
        """Test listing sessions filtered by status."""
        state1 = SessionState(
            session_id="running-1",
            config=SessionConfig(goals=("goal",)),
            status=SessionStatus.RUNNING,
        )
        state2 = SessionState(
            session_id="completed-1",
            config=SessionConfig(goals=("goal",)),
            status=SessionStatus.COMPLETED,
        )
        temp_store.save(state1)
        temp_store.save(state2)

        running = temp_store.list_sessions(status=SessionStatus.RUNNING)
        completed = temp_store.list_sessions(status=SessionStatus.COMPLETED)

        assert len(running) == 1
        assert running[0].session_id == "running-1"
        assert len(completed) == 1
        assert completed[0].session_id == "completed-1"

    def test_get_resumable_sessions(self, temp_store: SessionStore) -> None:
        """Test getting resumable sessions (PAUSED or RUNNING)."""
        states = [
            SessionState(
                session_id="paused-1",
                config=SessionConfig(goals=("goal",)),
                status=SessionStatus.PAUSED,
            ),
            SessionState(
                session_id="running-1",
                config=SessionConfig(goals=("goal",)),
                status=SessionStatus.RUNNING,
            ),
            SessionState(
                session_id="completed-1",
                config=SessionConfig(goals=("goal",)),
                status=SessionStatus.COMPLETED,
            ),
            SessionState(
                session_id="failed-1",
                config=SessionConfig(goals=("goal",)),
                status=SessionStatus.FAILED,
            ),
        ]
        for state in states:
            temp_store.save(state)

        resumable = temp_store.get_resumable_sessions()

        assert len(resumable) == 2
        resumable_ids = {s.session_id for s in resumable}
        assert "paused-1" in resumable_ids
        assert "running-1" in resumable_ids

    def test_update_status(self, temp_store: SessionStore) -> None:
        """Test updating session status."""
        state = SessionState(
            session_id="to-update",
            config=SessionConfig(goals=("goal",)),
            status=SessionStatus.RUNNING,
        )
        temp_store.save(state)

        result = temp_store.update_status(
            "to-update",
            SessionStatus.PAUSED,
            reason="User interrupted",
        )

        assert result is True

        loaded = temp_store.load("to-update")
        assert loaded is not None
        assert loaded.status == SessionStatus.PAUSED
        assert loaded.stop_reason == "User interrupted"

    def test_set_metadata(self, temp_store: SessionStore) -> None:
        """Test setting session metadata."""
        state = SessionState(
            session_id="with-metadata",
            config=SessionConfig(goals=("goal",)),
        )
        temp_store.save(state)

        temp_store.set_metadata(
            "with-metadata",
            project_id="proj-123",
            workspace_id="/path/to/workspace",
        )

        sessions = temp_store.list_sessions()
        session = next(s for s in sessions if s.session_id == "with-metadata")

        assert session.project_id == "proj-123"
        assert session.workspace_id == "/path/to/workspace"
