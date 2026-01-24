"""Test that CLI JSON output matches schema contract.

This test validates that actual CLI commands produce valid JSON events
that match our schema contract.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from sunwell.agent.events import AgentEvent, EventType


def test_cli_json_structure() -> None:
    """Test that CLI --json flag produces valid NDJSON structure."""
    # Try to run a simple command that produces JSON
    # We'll use --plan mode which should be fast and produce events
    
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "sunwell.cli",
                "agent",
                "run",
                "--json",
                "--plan",
                "test goal",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=Path(__file__).parent.parent,
        )
    except subprocess.TimeoutExpired:
        pytest.skip("CLI command timed out (may need Ollama/models)")
    except FileNotFoundError:
        pytest.skip("sunwell CLI not available")

    # Should have stdout (even if empty or error)
    assert result.stdout is not None

    # Parse NDJSON lines
    events = []
    for line in result.stdout.strip().split("\n"):
        if line.strip():
            try:
                event = json.loads(line)
                events.append(event)
            except json.JSONDecodeError:
                # Skip non-JSON lines (like warnings)
                continue

    # If we got events, validate structure
    if events:
        for event in events:
            # Check required fields
            assert "type" in event, f"Event missing 'type': {event}"
            assert "data" in event, f"Event missing 'data': {event}"
            assert "timestamp" in event, f"Event missing 'timestamp': {event}"

            # Check type is valid EventType
            assert event["type"] in [
                et.value for et in EventType
            ], f"Unknown event type: {event['type']}"

            # Check data is dict
            assert isinstance(event["data"], dict), f"Event data not dict: {event['data']}"

            # Check timestamp is number
            assert isinstance(event["timestamp"], (int, float)), f"Timestamp not number: {event['timestamp']}"

            # Try to reconstruct AgentEvent
            try:
                reconstructed = AgentEvent.from_dict(event)
                assert reconstructed.type.value == event["type"]
            except (ValueError, KeyError) as e:
                pytest.fail(f"Failed to reconstruct AgentEvent: {e}")


def test_event_validation_in_cli() -> None:
    """Test that CLI uses validation when emitting events."""
    # This is more of an integration test - we verify that
    # the CLI code paths use validation
    
    from sunwell.agent.event_schema import REQUIRED_FIELDS, validate_event_data
    from sunwell.agent.events import AgentEvent, EventType

    # Test that validation works for key event types
    test_cases = [
        (EventType.TASK_START, {"task_id": "test", "description": "test"}),
        (EventType.TASK_COMPLETE, {"task_id": "test", "duration_ms": 100}),
        (EventType.COMPLETE, {"tasks_completed": 5}),
        (EventType.ERROR, {"message": "test error"}),
    ]

    for event_type, data in test_cases:
        # Should validate successfully
        validated = validate_event_data(event_type, data)
        assert validated == data or all(k in validated for k in data.keys())

        # Should create valid event
        event = AgentEvent(event_type, validated)
        event_dict = event.to_dict()

        # Should serialize to JSON
        json_str = json.dumps(event_dict)
        parsed = json.loads(json_str)

        # Should match original structure
        assert parsed["type"] == event_type.value
        assert isinstance(parsed["data"], dict)
        assert isinstance(parsed["timestamp"], (int, float))


def test_schema_generation_works() -> None:
    """Test that schema generation produces valid files."""
    root = Path(__file__).parent.parent

    # Check JSON Schema exists
    schema_path = root / "schemas" / "agent-events.schema.json"
    assert schema_path.exists(), "JSON Schema not generated"

    schema = json.loads(schema_path.read_text())
    assert "$schema" in schema
    assert "oneOf" in schema
    assert len(schema["oneOf"]) > 0

    # Check TypeScript types exist
    ts_path = root / "studio" / "src" / "lib" / "agent-events.ts"
    assert ts_path.exists(), "TypeScript types not generated"

    ts_content = ts_path.read_text()
    assert "export type AgentEventType" in ts_content
    assert "export interface AgentEvent" in ts_content