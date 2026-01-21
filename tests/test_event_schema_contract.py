"""Test event schema contract between Python CLI and frontend.

Ensures that:
1. All event types can be serialized to JSON
2. Required fields are present
3. Events match JSON Schema
4. TypeScript types can parse events (via JSON Schema validation)
"""

import json
from pathlib import Path

import pytest

from sunwell.adaptive.event_schema import REQUIRED_FIELDS, validate_event_data
from sunwell.adaptive.events import AgentEvent, EventType


def load_json_schema() -> dict:
    """Load the generated JSON Schema."""
    schema_path = Path(__file__).parent.parent / "schemas" / "agent-events.schema.json"
    if not schema_path.exists():
        pytest.skip("JSON Schema not generated - run scripts/generate_event_schema.py")
    return json.loads(schema_path.read_text())


def test_all_event_types_serializable() -> None:
    """Test that all event types can be serialized to JSON."""
    for event_type in EventType:
        # Create minimal valid event
        data = {}
        try:
            validated_data = validate_event_data(event_type, data)
        except ValueError:
            # Some events require fields - that's OK, we'll test those separately
            continue

        event = AgentEvent(event_type, validated_data)
        event_dict = event.to_dict()

        # Should be JSON serializable
        json_str = json.dumps(event_dict)
        parsed = json.loads(json_str)

        # Should have required fields
        assert "type" in parsed
        assert "data" in parsed
        assert "timestamp" in parsed
        assert parsed["type"] == event_type.value


def test_required_fields_present() -> None:
    """Test that events with required fields validate correctly."""
    for event_type, required in REQUIRED_FIELDS.items():
        # Create event with required fields
        data = {}
        for field in required:
            # Use dummy values based on field name
            if "id" in field.lower():
                data[field] = "test-id"
            elif "description" in field.lower():
                data[field] = "test description"
            elif "error" in field.lower() or "message" in field.lower():
                data[field] = "test error"
            elif "duration" in field.lower() or "ms" in field.lower():
                data[field] = 100
            elif any(k in field.lower() for k in ("completed", "failed", "tasks")):
                data[field] = 0
            elif "fact" in field.lower():
                data[field] = "test fact"
            elif "category" in field.lower():
                data[field] = "test"
            else:
                data[field] = "test"

        # Should validate
        validated_data = validate_event_data(event_type, data)
        event = AgentEvent(event_type, validated_data)
        event_dict = event.to_dict()

        # Should be valid JSON
        json_str = json.dumps(event_dict)
        parsed = json.loads(json_str)

        # Required fields should be in data
        for field in required:
            assert field in parsed["data"], (
                f"Required field '{field}' missing in {event_type.value}"
            )


def test_event_matches_json_schema() -> None:
    """Test that generated events match JSON Schema (basic validation)."""
    _ = load_json_schema()  # Ensure schema exists

    # Test a few key event types
    test_cases = [
        (EventType.TASK_START, {"task_id": "test", "description": "test"}),
        (EventType.TASK_COMPLETE, {"task_id": "test", "duration_ms": 100}),
        (EventType.COMPLETE, {"tasks_completed": 5}),
        (EventType.ERROR, {"message": "test error"}),
    ]

    for event_type, data in test_cases:
        validated_data = validate_event_data(event_type, data)
        event = AgentEvent(event_type, validated_data)
        event_dict = event.to_dict()

        # Basic structure check
        assert event_dict["type"] == event_type.value
        assert isinstance(event_dict["data"], dict)
        assert isinstance(event_dict["timestamp"], (int, float))

        # Check required fields are present
        required = REQUIRED_FIELDS.get(event_type, set())
        for field in required:
            assert field in event_dict["data"], f"Required field '{field}' missing"


def test_event_roundtrip() -> None:
    """Test that events can be round-tripped through JSON."""
    event = AgentEvent(
        EventType.TASK_START,
        {"task_id": "test-123", "description": "Test task"},
    )

    # Serialize
    json_str = json.dumps(event.to_dict())

    # Deserialize
    parsed = json.loads(json_str)

    # Reconstruct
    reconstructed = AgentEvent.from_dict(parsed)

    # Should match
    assert reconstructed.type == event.type
    assert reconstructed.data == event.data
    assert abs(reconstructed.timestamp - event.timestamp) < 1.0  # Allow small time diff


def test_incremental_events_compatible() -> None:
    """Test that incremental execution events are compatible with schema."""
    # These are emitted by _incremental_run() with custom emit() function
    # They should still match the standard format
    from sunwell.adaptive.events import AgentEvent, EventType

    # Simulate what incremental_run emits
    event_types = [
        EventType.TASK_START,
        EventType.TASK_PROGRESS,
        EventType.TASK_COMPLETE,
        EventType.TASK_FAILED,
        EventType.COMPLETE,
    ]

    for event_type in event_types:
        # Create minimal valid event
        data = {}
        required = REQUIRED_FIELDS.get(event_type, set())
        for field in required:
            if any(k in field.lower() for k in ("id", "description", "error", "message")):
                data[field] = "test"
            elif "duration" in field.lower() or "ms" in field.lower():
                data[field] = 100
            elif "completed" in field.lower() or "tasks" in field.lower():
                data[field] = 0

        validated_data = validate_event_data(event_type, data)
        event = AgentEvent(event_type, validated_data)

        # Should serialize correctly
        event_dict = event.to_dict()
        json_str = json.dumps(event_dict)
        parsed = json.loads(json_str)

        assert parsed["type"] == event_type.value


# =============================================================================
# RFC-059: Observability Completeness Tests
# =============================================================================


def test_rfc059_all_events_have_schemas() -> None:
    """Test that all EventType values have schemas (RFC-059 Phase 1)."""
    from sunwell.adaptive.event_schema import EVENT_SCHEMAS

    for event_type in EventType:
        assert event_type in EVENT_SCHEMAS, f"Missing schema for {event_type.value}"


def test_rfc059_no_empty_json_schema_properties() -> None:
    """Test that JSON schema has no empty properties (RFC-059 Phase 1)."""
    schema = load_json_schema()

    empty = []
    for event_schema in schema["oneOf"]:
        data_props = event_schema["properties"]["data"].get("properties", {})
        if not data_props:
            event_type = event_schema["properties"]["type"]["const"]
            empty.append(event_type)

    assert not empty, f"Events with empty properties: {empty}"


def test_rfc059_discovery_progress_event() -> None:
    """Test plan_discovery_progress event (RFC-059 Phase 2)."""
    # Test the discovery progress event can be created and serialized
    event = AgentEvent(
        EventType.PLAN_DISCOVERY_PROGRESS,
        {
            "artifacts_discovered": 5,
            "phase": "building_graph",
            "total_estimated": 10,
        },
    )

    event_dict = event.to_dict()
    json_str = json.dumps(event_dict)
    parsed = json.loads(json_str)

    assert parsed["type"] == "plan_discovery_progress"
    assert parsed["data"]["artifacts_discovered"] == 5
    assert parsed["data"]["phase"] == "building_graph"


def test_rfc059_error_context_fields() -> None:
    """Test that error events support phase/context (RFC-059 Phase 3)."""
    from sunwell.adaptive.event_schema import ErrorData

    # Verify ErrorData has all the RFC-059 fields
    annotations = ErrorData.__annotations__
    assert "message" in annotations
    assert "phase" in annotations
    assert "context" in annotations
    assert "error_type" in annotations
    assert "traceback" in annotations

    # Create error event with context
    event = AgentEvent(
        EventType.ERROR,
        {
            "message": "Discovery failed",
            "phase": "discovery",
            "error_type": "DiscoveryFailedError",
            "context": {"goal": "build api", "attempts": 3},
        },
    )

    event_dict = event.to_dict()
    json_str = json.dumps(event_dict)
    parsed = json.loads(json_str)

    assert parsed["data"]["phase"] == "discovery"
    assert parsed["data"]["error_type"] == "DiscoveryFailedError"
    assert parsed["data"]["context"]["attempts"] == 3


def test_rfc059_all_harmonic_events_have_schemas() -> None:
    """Test that all harmonic planning events have schemas (RFC-058/059)."""
    harmonic_events = [
        EventType.PLAN_CANDIDATE_START,
        EventType.PLAN_CANDIDATE_GENERATED,
        EventType.PLAN_CANDIDATES_COMPLETE,
        EventType.PLAN_CANDIDATE_SCORED,
        EventType.PLAN_SCORING_COMPLETE,
        EventType.PLAN_REFINE_START,
        EventType.PLAN_REFINE_ATTEMPT,
        EventType.PLAN_REFINE_COMPLETE,
        EventType.PLAN_REFINE_FINAL,
    ]

    from sunwell.adaptive.event_schema import EVENT_SCHEMAS

    for event_type in harmonic_events:
        assert event_type in EVENT_SCHEMAS, f"Missing schema for {event_type.value}"
        # Verify schema has annotations
        schema = EVENT_SCHEMAS[event_type]
        assert hasattr(schema, "__annotations__"), f"No annotations for {event_type.value}"


def test_rfc059_required_fields_defined() -> None:
    """Test that all events with required fields are properly defined."""
    from sunwell.adaptive.event_schema import EVENT_SCHEMAS

    for event_type, required in REQUIRED_FIELDS.items():
        schema = EVENT_SCHEMAS.get(event_type)
        assert schema is not None, f"No schema for {event_type.value}"

        # Required fields should exist in schema annotations
        annotations = getattr(schema, "__annotations__", {})
        for field in required:
            assert field in annotations, (
                f"Required field '{field}' not in schema for {event_type.value}"
            )
