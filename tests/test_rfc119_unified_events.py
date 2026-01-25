"""Tests for RFC-119: Unified Event Bus.

Tests the event bus, run state management, and CLI server bridge
for unified CLI/Studio visibility.
"""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import directly from modules to avoid FastAPI dependency in __init__
from sunwell.interface.server.events import BusEvent, EventBus
from sunwell.interface.server.runs import RunManager, RunState

# Import new event types for testing
from sunwell.agent.events import (
    EventType,
    orient_event,
    learning_added_event,
    decision_made_event,
    failure_recorded_event,
    briefing_updated_event,
)


class TestNewEventTypes:
    """Tests for new event types (RFC: Architecture Proposal)."""

    def test_orient_event_type(self) -> None:
        """EventType.ORIENT should exist."""
        assert EventType.ORIENT.value == "orient"

    def test_learning_added_event_type(self) -> None:
        """EventType.LEARNING_ADDED should exist."""
        assert EventType.LEARNING_ADDED.value == "learning_added"

    def test_decision_made_event_type(self) -> None:
        """EventType.DECISION_MADE should exist."""
        assert EventType.DECISION_MADE.value == "decision_made"

    def test_failure_recorded_event_type(self) -> None:
        """EventType.FAILURE_RECORDED should exist."""
        assert EventType.FAILURE_RECORDED.value == "failure_recorded"

    def test_briefing_updated_event_type(self) -> None:
        """EventType.BRIEFING_UPDATED should exist."""
        assert EventType.BRIEFING_UPDATED.value == "briefing_updated"

    def test_orient_event_factory(self) -> None:
        """orient_event() should create proper event."""
        event = orient_event(learnings=5, constraints=3, dead_ends=2)

        assert event.type == EventType.ORIENT
        assert event.data["learnings"] == 5
        assert event.data["constraints"] == 3
        assert event.data["dead_ends"] == 2

    def test_learning_added_event_factory(self) -> None:
        """learning_added_event() should create proper event."""
        event = learning_added_event(
            fact="API uses REST",
            category="architecture",
            confidence=0.95,
        )

        assert event.type == EventType.LEARNING_ADDED
        assert event.data["fact"] == "API uses REST"
        assert event.data["category"] == "architecture"

    def test_decision_made_event_factory(self) -> None:
        """decision_made_event() should create proper event."""
        event = decision_made_event(
            category="database",
            question="Which database to use?",
            choice="PostgreSQL",
            rejected_count=2,
        )

        assert event.type == EventType.DECISION_MADE
        assert event.data["choice"] == "PostgreSQL"
        assert event.data["rejected_count"] == 2

    def test_failure_recorded_event_factory(self) -> None:
        """failure_recorded_event() should create proper event."""
        event = failure_recorded_event(
            description="Connection pool exhausted",
            error_type="resource_exhaustion",
            context="database connection",
        )

        assert event.type == EventType.FAILURE_RECORDED
        assert event.data["description"] == "Connection pool exhausted"

    def test_briefing_updated_event_factory(self) -> None:
        """briefing_updated_event() should create proper event."""
        event = briefing_updated_event(
            status="in_progress",
            next_action="Add authentication",
            hot_files=["src/api.py"],
        )

        assert event.type == EventType.BRIEFING_UPDATED
        assert event.data["status"] == "in_progress"
        assert event.data["next_action"] == "Add authentication"


class TestBusEvent:
    """Tests for BusEvent dataclass."""

    def test_create_event(self) -> None:
        """BusEvent should create with all required fields."""
        now = datetime.now(UTC)
        event = BusEvent(
            v=1,
            run_id="run-123",
            type="task_start",
            data={"task_id": "t1"},
            timestamp=now,
            source="cli",
            project_id="proj-456",
        )

        assert event.v == 1
        assert event.run_id == "run-123"
        assert event.type == "task_start"
        assert event.data == {"task_id": "t1"}
        assert event.source == "cli"
        assert event.project_id == "proj-456"

    def test_to_dict(self) -> None:
        """BusEvent.to_dict() should serialize correctly."""
        now = datetime.now(UTC)
        event = BusEvent(
            v=1,
            run_id="run-123",
            type="task_complete",
            data={"result": "success"},
            timestamp=now,
            source="studio",
            project_id=None,
        )

        d = event.to_dict()
        assert d["v"] == 1
        assert d["run_id"] == "run-123"
        assert d["type"] == "task_complete"
        assert d["data"] == {"result": "success"}
        assert d["source"] == "studio"
        assert d["project_id"] is None
        assert d["timestamp"] == now.isoformat()

    def test_frozen(self) -> None:
        """BusEvent should be immutable (frozen)."""
        event = BusEvent(
            v=1,
            run_id="run-123",
            type="test",
            data={},
            timestamp=datetime.now(UTC),
            source="cli",
        )
        with pytest.raises(AttributeError):
            event.run_id = "different"  # type: ignore


class TestEventBus:
    """Tests for EventBus class."""

    @pytest.fixture
    def event_bus(self) -> EventBus:
        return EventBus()

    @pytest.fixture
    def mock_websocket(self) -> MagicMock:
        ws = MagicMock()
        ws.send_json = AsyncMock()
        return ws

    @pytest.mark.asyncio
    async def test_subscribe(self, event_bus: EventBus, mock_websocket: MagicMock) -> None:
        """EventBus should accept subscriptions."""
        result = await event_bus.subscribe(mock_websocket)
        assert result is True
        assert event_bus.subscriber_count == 1

    @pytest.mark.asyncio
    async def test_subscribe_with_filter(
        self, event_bus: EventBus, mock_websocket: MagicMock
    ) -> None:
        """EventBus should accept subscriptions with project filter."""
        result = await event_bus.subscribe(mock_websocket, project_filter="proj-123")
        assert result is True
        assert event_bus.subscriber_count == 1

    @pytest.mark.asyncio
    async def test_subscribe_at_capacity(self, event_bus: EventBus) -> None:
        """EventBus should reject subscriptions when at capacity."""
        # Fill to capacity
        for i in range(EventBus.MAX_SUBSCRIBERS):
            ws = MagicMock()
            await event_bus.subscribe(ws)

        # Next subscription should fail
        overflow_ws = MagicMock()
        result = await event_bus.subscribe(overflow_ws)
        assert result is False
        assert event_bus.subscriber_count == EventBus.MAX_SUBSCRIBERS

    @pytest.mark.asyncio
    async def test_unsubscribe(
        self, event_bus: EventBus, mock_websocket: MagicMock
    ) -> None:
        """EventBus should remove subscribers."""
        await event_bus.subscribe(mock_websocket)
        assert event_bus.subscriber_count == 1

        await event_bus.unsubscribe(mock_websocket)
        assert event_bus.subscriber_count == 0

    @pytest.mark.asyncio
    async def test_unsubscribe_nonexistent(self, event_bus: EventBus) -> None:
        """EventBus.unsubscribe() should not error for unknown websockets."""
        ws = MagicMock()
        await event_bus.unsubscribe(ws)  # Should not raise
        assert event_bus.subscriber_count == 0

    @pytest.mark.asyncio
    async def test_broadcast(
        self, event_bus: EventBus, mock_websocket: MagicMock
    ) -> None:
        """EventBus should broadcast events to subscribers."""
        await event_bus.subscribe(mock_websocket)

        event = BusEvent(
            v=1,
            run_id="run-123",
            type="task_start",
            data={},
            timestamp=datetime.now(UTC),
            source="cli",
        )
        await event_bus.broadcast(event)

        mock_websocket.send_json.assert_called_once()
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["run_id"] == "run-123"
        assert call_args["type"] == "task_start"

    @pytest.mark.asyncio
    async def test_broadcast_with_project_filter(self, event_bus: EventBus) -> None:
        """EventBus should filter events by project_id."""
        ws_proj_a = MagicMock()
        ws_proj_a.send_json = AsyncMock()
        ws_proj_b = MagicMock()
        ws_proj_b.send_json = AsyncMock()
        ws_no_filter = MagicMock()
        ws_no_filter.send_json = AsyncMock()

        await event_bus.subscribe(ws_proj_a, project_filter="proj-a")
        await event_bus.subscribe(ws_proj_b, project_filter="proj-b")
        await event_bus.subscribe(ws_no_filter)

        # Send event for project A
        event = BusEvent(
            v=1,
            run_id="run-123",
            type="task_start",
            data={},
            timestamp=datetime.now(UTC),
            source="cli",
            project_id="proj-a",
        )
        await event_bus.broadcast(event)

        # Only ws_proj_a and ws_no_filter should receive
        ws_proj_a.send_json.assert_called_once()
        ws_proj_b.send_json.assert_not_called()
        ws_no_filter.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_drops_slow_consumers(self, event_bus: EventBus) -> None:
        """EventBus should drop subscribers that timeout."""
        slow_ws = MagicMock()
        slow_ws.send_json = AsyncMock(side_effect=asyncio.TimeoutError())

        await event_bus.subscribe(slow_ws)
        assert event_bus.subscriber_count == 1

        event = BusEvent(
            v=1,
            run_id="run-123",
            type="test",
            data={},
            timestamp=datetime.now(UTC),
            source="cli",
        )
        await event_bus.broadcast(event)

        # Slow consumer should be dropped
        assert event_bus.subscriber_count == 0


class TestRunState:
    """Tests for RunState dataclass."""

    def test_create_run_state(self) -> None:
        """RunState should create with defaults."""
        run = RunState(run_id="run-123", goal="Build API")

        assert run.run_id == "run-123"
        assert run.goal == "Build API"
        assert run.status == "pending"
        assert run.source == "studio"  # Default
        assert run.started_at is not None
        assert run.completed_at is None
        assert not run.is_cancelled
        assert run.use_v2 is False  # Default

    def test_run_state_with_source(self) -> None:
        """RunState should accept source parameter."""
        run = RunState(run_id="run-123", goal="Fix bug", source="cli")
        assert run.source == "cli"

    def test_run_state_with_use_v2(self) -> None:
        """RunState should accept use_v2 parameter."""
        run = RunState(run_id="run-123", goal="Build API", use_v2=True)
        assert run.use_v2 is True

    def test_cancel(self) -> None:
        """RunState.cancel() should update status and completed_at."""
        run = RunState(run_id="run-123", goal="Test")
        assert run.completed_at is None

        run.cancel()

        assert run.is_cancelled
        assert run.status == "cancelled"
        assert run.completed_at is not None

    def test_complete(self) -> None:
        """RunState.complete() should update status and completed_at."""
        run = RunState(run_id="run-123", goal="Test")
        assert run.completed_at is None

        run.complete()

        assert run.status == "complete"
        assert run.completed_at is not None

    def test_complete_with_error_status(self) -> None:
        """RunState.complete() should accept custom status."""
        run = RunState(run_id="run-123", goal="Test")
        run.complete(status="error")

        assert run.status == "error"
        assert run.completed_at is not None


class TestRunManager:
    """Tests for RunManager class."""

    def test_create_run(self) -> None:
        """RunManager should create runs with unique IDs."""
        manager = RunManager()

        run1 = manager.create_run(goal="Goal 1")
        run2 = manager.create_run(goal="Goal 2")

        assert run1.run_id != run2.run_id
        assert run1.goal == "Goal 1"
        assert run2.goal == "Goal 2"

    def test_create_run_with_source(self) -> None:
        """RunManager.create_run() should accept source parameter."""
        manager = RunManager()

        run = manager.create_run(goal="CLI task", source="cli")

        assert run.source == "cli"

    def test_create_run_with_use_v2(self) -> None:
        """RunManager.create_run() should accept use_v2 parameter."""
        manager = RunManager()

        run = manager.create_run(goal="V2 task", use_v2=True)

        assert run.use_v2 is True

    def test_get_run(self) -> None:
        """RunManager should retrieve runs by ID."""
        manager = RunManager()

        created = manager.create_run(goal="Test")
        retrieved = manager.get_run(created.run_id)

        assert retrieved is not None
        assert retrieved.run_id == created.run_id

    def test_get_run_not_found(self) -> None:
        """RunManager.get_run() should return None for unknown IDs."""
        manager = RunManager()

        result = manager.get_run("nonexistent-id")

        assert result is None

    def test_list_runs(self) -> None:
        """RunManager should list all runs."""
        manager = RunManager()

        manager.create_run(goal="Run 1")
        manager.create_run(goal="Run 2")
        manager.create_run(goal="Run 3")

        runs = manager.list_runs()

        assert len(runs) == 3

    def test_cleanup_at_capacity(self) -> None:
        """RunManager should cleanup completed runs when at capacity."""
        manager = RunManager(max_runs=5)

        # Create runs and complete some
        for i in range(4):
            run = manager.create_run(goal=f"Run {i}")
            if i < 2:
                run.complete()

        # This should trigger cleanup
        manager.create_run(goal="Overflow run")

        # Should have cleaned up some completed runs
        runs = manager.list_runs()
        assert len(runs) <= 5


class TestServerBridge:
    """Tests for CLI server bridge."""

    @pytest.mark.asyncio
    async def test_detect_server_available(self) -> None:
        """detect_server() should return URL when server responds."""
        from sunwell.interface.cli.server_bridge import detect_server

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await detect_server("http://test:8080")

            assert result == "http://test:8080"

    @pytest.mark.asyncio
    async def test_detect_server_unavailable(self) -> None:
        """detect_server() should return None when server not running."""
        import httpx

        from sunwell.interface.cli.server_bridge import detect_server

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_client_class.return_value = mock_client

            result = await detect_server("http://test:9999")

            assert result is None

    @pytest.mark.asyncio
    async def test_detect_server_timeout(self) -> None:
        """detect_server() should return None on timeout."""
        import httpx

        from sunwell.interface.cli.server_bridge import detect_server

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_client_class.return_value = mock_client

            result = await detect_server()

            assert result is None
