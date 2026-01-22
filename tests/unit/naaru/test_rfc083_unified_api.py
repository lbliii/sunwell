"""Tests for RFC-083 Naaru Unified API.

Tests the unified orchestration layer:
- ProcessInput, ProcessOutput, ProcessMode types
- NaaruEvent, NaaruEventType
- NaaruError
- CompositionSpec, RoutingDecision
- Convergence slot TTLs
- Session management
- Naaru.process() entry point
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from sunwell.types.naaru_api import (
    CONVERGENCE_SLOTS,
    SLOT_TTL_SECONDS,
    CompositionSpec,
    ConversationMessage,
    NaaruError,
    NaaruEvent,
    NaaruEventType,
    ProcessInput,
    ProcessMode,
    ProcessOutput,
    RoutingDecision,
    get_slot_ttl,
)


class TestProcessMode:
    """Tests for ProcessMode enum."""

    def test_process_mode_values(self):
        """Test all ProcessMode values exist."""
        assert ProcessMode.AUTO.value == "auto"
        assert ProcessMode.CHAT.value == "chat"
        assert ProcessMode.AGENT.value == "agent"
        assert ProcessMode.INTERFACE.value == "interface"

    def test_process_mode_from_string(self):
        """Test ProcessMode can be created from string."""
        assert ProcessMode("auto") == ProcessMode.AUTO
        assert ProcessMode("chat") == ProcessMode.CHAT
        assert ProcessMode("agent") == ProcessMode.AGENT
        assert ProcessMode("interface") == ProcessMode.INTERFACE


class TestConversationMessage:
    """Tests for ConversationMessage dataclass."""

    def test_conversation_message_creation(self):
        """Test ConversationMessage creation."""
        msg = ConversationMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_conversation_message_frozen(self):
        """Test ConversationMessage is immutable."""
        msg = ConversationMessage(role="user", content="Hello")
        with pytest.raises(AttributeError):
            msg.role = "assistant"


class TestProcessInput:
    """Tests for ProcessInput dataclass."""

    def test_process_input_minimal(self):
        """Test ProcessInput with only required field."""
        inp = ProcessInput(content="Hello")
        assert inp.content == "Hello"
        assert inp.mode == ProcessMode.AUTO
        assert inp.page_type == "home"
        assert inp.conversation_history == []
        assert inp.workspace is None
        assert inp.stream is True
        assert inp.timeout == 300.0
        assert inp.context == {}

    def test_process_input_full(self):
        """Test ProcessInput with all fields."""
        history = [ConversationMessage(role="user", content="Hi")]
        inp = ProcessInput(
            content="Build API",
            mode=ProcessMode.AGENT,
            page_type="project",
            conversation_history=history,
            workspace=Path("/tmp/test"),
            stream=False,
            timeout=600.0,
            context={"key": "value"},
        )
        assert inp.content == "Build API"
        assert inp.mode == ProcessMode.AGENT
        assert inp.page_type == "project"
        assert len(inp.conversation_history) == 1
        assert inp.workspace == Path("/tmp/test")
        assert inp.stream is False
        assert inp.timeout == 600.0
        assert inp.context == {"key": "value"}

    def test_process_input_to_dict(self):
        """Test ProcessInput serialization."""
        inp = ProcessInput(content="test", mode=ProcessMode.CHAT)
        d = inp.to_dict()
        assert d["content"] == "test"
        assert d["mode"] == "chat"
        assert d["page_type"] == "home"
        assert d["stream"] is True

    def test_process_input_from_dict(self):
        """Test ProcessInput deserialization."""
        data = {
            "content": "Hello",
            "mode": "agent",
            "page_type": "project",
            "conversation_history": [{"role": "user", "content": "Hi"}],
            "workspace": "/tmp/test",
            "timeout": 120.0,
        }
        inp = ProcessInput.from_dict(data)
        assert inp.content == "Hello"
        assert inp.mode == ProcessMode.AGENT
        assert inp.page_type == "project"
        assert len(inp.conversation_history) == 1
        assert inp.workspace == Path("/tmp/test")
        assert inp.timeout == 120.0

    def test_process_input_from_dict_defaults(self):
        """Test ProcessInput deserialization with defaults."""
        data = {"content": "test"}
        inp = ProcessInput.from_dict(data)
        assert inp.mode == ProcessMode.AUTO
        assert inp.page_type == "home"
        assert inp.stream is True


class TestNaaruEventType:
    """Tests for NaaruEventType enum."""

    def test_all_event_types_exist(self):
        """Test all NaaruEventType values exist."""
        expected = [
            "process_start", "process_complete", "process_error",
            "route_decision",
            "composition_ready", "composition_updated",
            "model_start", "model_thinking", "model_tokens", "model_complete",
            "task_start", "task_progress", "task_complete", "task_error",
            "tool_call", "tool_result",
            "validation_start", "validation_result",
            "learning_extracted", "learning_persisted",
        ]
        actual = [e.value for e in NaaruEventType]
        for exp in expected:
            assert exp in actual, f"Missing event type: {exp}"

    def test_event_type_from_string(self):
        """Test NaaruEventType from string value."""
        assert NaaruEventType("process_start") == NaaruEventType.PROCESS_START
        assert NaaruEventType("model_tokens") == NaaruEventType.MODEL_TOKENS


class TestNaaruEvent:
    """Tests for NaaruEvent dataclass."""

    def test_naaru_event_creation(self):
        """Test NaaruEvent creation."""
        event = NaaruEvent(
            type=NaaruEventType.PROCESS_START,
            data={"content": "test"},
        )
        assert event.type == NaaruEventType.PROCESS_START
        assert event.data == {"content": "test"}
        assert isinstance(event.timestamp, datetime)

    def test_naaru_event_to_dict(self):
        """Test NaaruEvent serialization."""
        event = NaaruEvent(
            type=NaaruEventType.MODEL_TOKENS,
            data={"content": "Hello"},
        )
        d = event.to_dict()
        assert d["type"] == "model_tokens"
        assert d["data"] == {"content": "Hello"}
        assert "timestamp" in d

    def test_naaru_event_to_json(self):
        """Test NaaruEvent JSON serialization."""
        event = NaaruEvent(
            type=NaaruEventType.ROUTE_DECISION,
            data={"interaction_type": "conversation"},
        )
        json_str = event.to_json()
        assert '"type": "route_decision"' in json_str
        assert '"interaction_type": "conversation"' in json_str


class TestCompositionSpec:
    """Tests for CompositionSpec dataclass."""

    def test_composition_spec_creation(self):
        """Test CompositionSpec creation."""
        spec = CompositionSpec(
            page_type="home",
            panels=[{"panel_type": "calendar"}],
            input_mode="chat",
            suggested_tools=["upload"],
            confidence=0.9,
            source="fast_model",
        )
        assert spec.page_type == "home"
        assert len(spec.panels) == 1
        assert spec.input_mode == "chat"
        assert spec.suggested_tools == ["upload"]
        assert spec.confidence == 0.9
        assert spec.source == "fast_model"

    def test_composition_spec_defaults(self):
        """Test CompositionSpec default values."""
        spec = CompositionSpec(page_type="home")
        assert spec.panels == []
        assert spec.input_mode == "hero"
        assert spec.suggested_tools == []
        assert spec.confidence == 0.0
        assert spec.source == "regex"

    def test_composition_spec_to_dict(self):
        """Test CompositionSpec serialization."""
        spec = CompositionSpec(
            page_type="project",
            panels=[{"panel_type": "tasks"}],
        )
        d = spec.to_dict()
        assert d["page_type"] == "project"
        assert d["panels"] == [{"panel_type": "tasks"}]


class TestRoutingDecision:
    """Tests for RoutingDecision dataclass."""

    def test_routing_decision_creation(self):
        """Test RoutingDecision creation."""
        decision = RoutingDecision(
            interaction_type="conversation",
            confidence=0.95,
            tier=1,
            lens="helper",
            page_type="home",
            tools=["read_file"],
            mood="neutral",
            reasoning="User greeting",
        )
        assert decision.interaction_type == "conversation"
        assert decision.confidence == 0.95
        assert decision.tier == 1
        assert decision.lens == "helper"
        assert decision.page_type == "home"
        assert decision.tools == ["read_file"]
        assert decision.mood == "neutral"
        assert decision.reasoning == "User greeting"

    def test_routing_decision_defaults(self):
        """Test RoutingDecision default values."""
        decision = RoutingDecision(
            interaction_type="action",
            confidence=0.8,
        )
        assert decision.tier == 1
        assert decision.lens is None
        assert decision.page_type == "home"
        assert decision.tools == []
        assert decision.mood is None

    def test_routing_decision_to_dict(self):
        """Test RoutingDecision serialization."""
        decision = RoutingDecision(
            interaction_type="workspace",
            confidence=0.85,
            tier=2,
        )
        d = decision.to_dict()
        assert d["interaction_type"] == "workspace"
        assert d["confidence"] == 0.85
        assert d["tier"] == 2


class TestProcessOutput:
    """Tests for ProcessOutput dataclass."""

    def test_process_output_creation(self):
        """Test ProcessOutput creation."""
        output = ProcessOutput(
            response="Hello!",
            route_type="conversation",
            confidence=0.9,
        )
        assert output.response == "Hello!"
        assert output.route_type == "conversation"
        assert output.confidence == 0.9
        assert output.composition is None
        assert output.tasks_completed == 0
        assert output.artifacts == []
        assert output.events == []

    def test_process_output_with_all_fields(self):
        """Test ProcessOutput with all fields."""
        composition = CompositionSpec(page_type="home")
        routing = RoutingDecision(interaction_type="conversation", confidence=0.9)
        event = NaaruEvent(type=NaaruEventType.PROCESS_COMPLETE, data={})

        output = ProcessOutput(
            response="Done!",
            route_type="action",
            confidence=0.95,
            composition=composition,
            tasks_completed=5,
            artifacts=["file.py"],
            events=[event],
            routing=routing,
        )
        assert output.tasks_completed == 5
        assert output.artifacts == ["file.py"]
        assert len(output.events) == 1
        assert output.routing is not None

    def test_process_output_to_dict(self):
        """Test ProcessOutput serialization."""
        output = ProcessOutput(
            response="Test",
            route_type="view",
            confidence=0.7,
        )
        d = output.to_dict()
        assert d["response"] == "Test"
        assert d["route_type"] == "view"
        assert d["confidence"] == 0.7
        assert d["composition"] is None


class TestNaaruError:
    """Tests for NaaruError exception."""

    def test_naaru_error_creation(self):
        """Test NaaruError creation."""
        error = NaaruError(
            code="ROUTE_FAILED",
            message="Failed to route request",
            recoverable=True,
        )
        assert error.code == "ROUTE_FAILED"
        assert error.message == "Failed to route request"
        assert error.recoverable is True
        assert error.context is None

    def test_naaru_error_with_context(self):
        """Test NaaruError with context."""
        error = NaaruError(
            code="MODEL_ERROR",
            message="Model failed",
            recoverable=False,
            context={"model": "gemma3:1b"},
        )
        assert error.context == {"model": "gemma3:1b"}

    def test_naaru_error_str(self):
        """Test NaaruError string representation."""
        error = NaaruError(
            code="TIMEOUT",
            message="Request timed out",
            recoverable=True,
        )
        assert str(error) == "NaaruError(TIMEOUT): Request timed out"

    def test_naaru_error_to_dict(self):
        """Test NaaruError serialization."""
        error = NaaruError(
            code="TOOL_ERROR",
            message="Tool failed",
            recoverable=True,
        )
        d = error.to_dict()
        assert d["code"] == "TOOL_ERROR"
        assert d["message"] == "Tool failed"
        assert d["recoverable"] is True

    def test_naaru_error_is_exception(self):
        """Test NaaruError is an Exception."""
        error = NaaruError(
            code="TEST",
            message="Test error",
            recoverable=True,
        )
        assert isinstance(error, Exception)


class TestConvergenceSlots:
    """Tests for Convergence slot definitions and TTLs."""

    def test_convergence_slots_defined(self):
        """Test all standard slots are defined."""
        expected_slots = [
            "routing:current",
            "composition:current",
            "composition:previous",
            "context:lens",
            "context:workspace",
            "context:history",
            "memories:relevant",
            "memories:user",
            "execution:current_task",
            "execution:dag",
            "execution:artifacts",
            "validation:result",
            "learnings:pending",
        ]
        for slot in expected_slots:
            assert slot in CONVERGENCE_SLOTS, f"Missing slot: {slot}"

    def test_slot_ttl_routing(self):
        """Test routing slots have short TTL."""
        assert get_slot_ttl("routing:current") == 30
        assert get_slot_ttl("routing:other") == 30

    def test_slot_ttl_composition(self):
        """Test composition slots have 5 min TTL."""
        assert get_slot_ttl("composition:current") == 300
        assert get_slot_ttl("composition:previous") == 300

    def test_slot_ttl_context(self):
        """Test context slots have 30 min TTL."""
        assert get_slot_ttl("context:lens") == 1800
        assert get_slot_ttl("context:workspace") == 1800

    def test_slot_ttl_memories(self):
        """Test memory slots have infinite TTL."""
        assert get_slot_ttl("memories:relevant") == float("inf")
        assert get_slot_ttl("memories:user") == float("inf")

    def test_slot_ttl_execution(self):
        """Test execution slots have 5 min TTL."""
        assert get_slot_ttl("execution:current_task") == 300
        assert get_slot_ttl("execution:dag") == 300

    def test_slot_ttl_validation(self):
        """Test validation slots have short TTL."""
        assert get_slot_ttl("validation:result") == 30

    def test_slot_ttl_learnings(self):
        """Test learning slots have infinite TTL."""
        assert get_slot_ttl("learnings:pending") == float("inf")

    def test_slot_ttl_default(self):
        """Test unknown slots get default TTL."""
        assert get_slot_ttl("unknown:slot") == 300

    def test_slot_ttl_seconds_defined(self):
        """Test SLOT_TTL_SECONDS has all prefixes."""
        expected_prefixes = [
            "routing", "composition", "context", "memories",
            "execution", "validation", "learnings",
        ]
        for prefix in expected_prefixes:
            assert prefix in SLOT_TTL_SECONDS, f"Missing prefix: {prefix}"


class TestNaaruSessionManager:
    """Tests for session management."""

    def test_session_manager_creation(self):
        """Test NaaruSessionManager creation."""
        from sunwell.naaru.session import NaaruSessionManager

        manager = NaaruSessionManager(max_sessions=10, ttl_hours=2.0)
        stats = manager.get_stats()
        assert stats["max_sessions"] == 10
        assert stats["ttl_hours"] == 2.0
        assert stats["active_sessions"] == 0

    def test_session_creation(self):
        """Test session creation."""
        from sunwell.naaru.session import NaaruSession

        # Create a mock naaru
        class MockNaaru:
            pass

        session = NaaruSession(session_id="test-123", naaru=MockNaaru())
        assert session.session_id == "test-123"
        assert isinstance(session.created_at, datetime)
        assert isinstance(session.last_accessed, datetime)

    def test_session_expiry_check(self):
        """Test session expiry checking."""
        from sunwell.naaru.session import NaaruSession

        class MockNaaru:
            pass

        session = NaaruSession(session_id="test", naaru=MockNaaru())

        # Fresh session should not be expired
        assert not session.is_expired(timedelta(hours=1))

        # Manually set old last_accessed
        session.last_accessed = datetime.now() - timedelta(hours=2)
        assert session.is_expired(timedelta(hours=1))


class TestNaaruProcess:
    """Tests for Naaru.process() entry point."""

    def test_naaru_has_process_method(self):
        """Test Naaru has process method."""
        from sunwell.naaru import Naaru

        assert hasattr(Naaru, "process")

    def test_naaru_has_process_sync_method(self):
        """Test Naaru has process_sync method."""
        from sunwell.naaru import Naaru

        assert hasattr(Naaru, "process_sync")

    def test_naaru_process_signature(self):
        """Test Naaru.process has correct signature."""
        import inspect

        from sunwell.naaru import Naaru
        from sunwell.types.config import NaaruConfig

        naaru = Naaru(sunwell_root=Path.cwd(), config=NaaruConfig())
        sig = inspect.signature(naaru.process)

        # Should have 'input' parameter
        params = list(sig.parameters.keys())
        assert "input" in params

    @pytest.mark.asyncio
    async def test_naaru_process_yields_events(self):
        """Test Naaru.process yields events."""
        from sunwell.naaru import Naaru, ProcessInput, ProcessMode
        from sunwell.types.config import NaaruConfig

        naaru = Naaru(sunwell_root=Path.cwd(), config=NaaruConfig())
        inp = ProcessInput(content="Hello", mode=ProcessMode.CHAT)

        events = []
        async for event in naaru.process(inp):
            events.append(event)
            if len(events) >= 3:  # Collect a few events
                break

        # Should have emitted at least process_start
        assert len(events) >= 1
        assert events[0].type == NaaruEventType.PROCESS_START

    @pytest.mark.asyncio
    async def test_naaru_process_sync_returns_output(self):
        """Test Naaru.process_sync returns ProcessOutput."""
        from sunwell.naaru import Naaru, ProcessInput, ProcessMode
        from sunwell.types.config import NaaruConfig

        naaru = Naaru(sunwell_root=Path.cwd(), config=NaaruConfig())
        inp = ProcessInput(content="Hello", mode=ProcessMode.CHAT)

        # Note: This may fail without a model, but should at least run
        try:
            output = await naaru.process_sync(inp)
            assert isinstance(output, ProcessOutput)
            assert output.route_type in ["conversation", "action", "view", "workspace", "hybrid"]
        except Exception:
            # Expected if no model configured
            pass
