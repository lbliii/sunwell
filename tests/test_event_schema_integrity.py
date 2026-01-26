"""Comprehensive event schema integrity tests.

These tests ensure schema/factory alignment and prevent regressions where:
- Factories produce fields that don't match REQUIRED_FIELDS
- TypedDict schemas don't match factory outputs
- Field naming conventions are inconsistent
- Generated artifacts get out of sync

Based on lessons learned from bug bash of sunwell.agent.events package.
"""

import importlib
import inspect
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable, get_type_hints

import pytest

from sunwell.agent.events import AgentEvent, EventType
from sunwell.agent.events.schemas import EVENT_SCHEMAS, REQUIRED_FIELDS


# =============================================================================
# Test 1: Factory Output Validation
# =============================================================================


def get_event_factories() -> dict[EventType, Callable[[], AgentEvent]]:
    """Build a mapping of EventType to factory functions with test data."""
    from sunwell.agent.events import convergence as conv
    from sunwell.agent.events import integration as integ
    from sunwell.agent.events import lifecycle
    from sunwell.agent.events import memory as mem
    from sunwell.agent.events import model as mdl
    from sunwell.agent.events import tool
    from sunwell.agent.events.types import AgentEvent, EventType

    # Factory functions with minimal valid arguments
    return {
        # Lifecycle events
        EventType.TASK_START: lambda: lifecycle.task_start_event("task-1", "Test task"),
        EventType.TASK_COMPLETE: lambda: lifecycle.task_complete_event("task-1", 100),
        # TASK_FAILED has no dedicated factory - create directly
        EventType.TASK_FAILED: lambda: AgentEvent(
            EventType.TASK_FAILED, {"task_id": "task-1", "error": "Test error"}
        ),
        EventType.COMPLETE: lambda: lifecycle.complete_event(5, 3, 10.5),
        # Convergence events
        EventType.CONVERGENCE_START: lambda: conv.convergence_start_event(
            ["file.py"], ["lint"], 5
        ),
        EventType.CONVERGENCE_ITERATION_START: lambda: conv.convergence_iteration_start_event(
            1, ["file.py"]
        ),
        EventType.CONVERGENCE_ITERATION_COMPLETE: lambda: conv.convergence_iteration_complete_event(
            1, True, 0, []
        ),
        EventType.CONVERGENCE_FIXING: lambda: conv.convergence_fixing_event(1, 3),
        EventType.CONVERGENCE_STABLE: lambda: conv.convergence_stable_event(2, 500),
        EventType.CONVERGENCE_TIMEOUT: lambda: conv.convergence_timeout_event(3),
        EventType.CONVERGENCE_STUCK: lambda: conv.convergence_stuck_event(3, ["error1"]),
        EventType.CONVERGENCE_MAX_ITERATIONS: lambda: conv.convergence_max_iterations_event(5),
        EventType.CONVERGENCE_BUDGET_EXCEEDED: lambda: conv.convergence_budget_exceeded_event(
            1000, 2000
        ),
        # Model events
        EventType.MODEL_START: lambda: mdl.model_start_event("task-1", "gpt-4", 100, 5.0),
        EventType.MODEL_TOKENS: lambda: mdl.model_tokens_event("task-1", "hello", 50, 25.0),
        EventType.MODEL_THINKING: lambda: mdl.model_thinking_event(
            "task-1", "reasoning", "thinking...", False
        ),
        EventType.MODEL_COMPLETE: lambda: mdl.model_complete_event(
            "task-1", 500, 10.5, 47.6, 150
        ),
        EventType.MODEL_HEARTBEAT: lambda: mdl.model_heartbeat_event("task-1", 5.0, 250),
        # Integration/Briefing events
        EventType.BRIEFING_LOADED: lambda: integ.briefing_loaded_event(
            "mission", "active", True, False
        ),
        EventType.BRIEFING_SAVED: lambda: integ.briefing_saved_event("complete", "next", 5),
        EventType.PREFETCH_START: lambda: integ.prefetch_start_event("briefing"),
        EventType.PREFETCH_COMPLETE: lambda: integ.prefetch_complete_event(
            10, 5, ["skill1", "skill2"]
        ),
        # Tool events
        EventType.TOOL_START: lambda: tool.tool_start_event("read_file", "call-1", {"path": "/"}),
        EventType.TOOL_COMPLETE: lambda: tool.tool_complete_event(
            "read_file", "call-1", True, "content", 50
        ),
        EventType.TOOL_ERROR: lambda: tool.tool_error_event("read_file", "call-1", "Not found"),
        EventType.TOOL_LOOP_START: lambda: tool.tool_loop_start_event("task desc", 10, 5),
        EventType.TOOL_LOOP_TURN: lambda: tool.tool_loop_turn_event(1, 3),
        EventType.TOOL_LOOP_COMPLETE: lambda: tool.tool_loop_complete_event(5, 15, "done"),
        # Memory events
        EventType.ORIENT: lambda: mem.orient_event(5, 3, 2),
        EventType.LEARNING_ADDED: lambda: mem.learning_added_event("fact", "category", 0.9),
        EventType.DECISION_MADE: lambda: mem.decision_made_event("cat", "q?", "choice", 2),
        EventType.FAILURE_RECORDED: lambda: mem.failure_recorded_event("desc", "type", "ctx"),
        EventType.BRIEFING_UPDATED: lambda: mem.briefing_updated_event(
            "status", "next", ["file.py"]
        ),
    }


class TestFactoryOutputValidation:
    """Test that factory functions produce all required fields."""

    @pytest.fixture
    def factories(self) -> dict[EventType, Callable[[], AgentEvent]]:
        return get_event_factories()

    def test_factories_produce_required_fields(
        self, factories: dict[EventType, Callable[[], AgentEvent]]
    ) -> None:
        """Every factory should produce all fields listed in REQUIRED_FIELDS."""
        failures = []

        for event_type, factory in factories.items():
            required = REQUIRED_FIELDS.get(event_type, set())
            if not required:
                continue

            try:
                event = factory()
                missing = required - set(event.data.keys())
                if missing:
                    failures.append(f"{event_type.value}: missing {missing}")
            except Exception as e:
                failures.append(f"{event_type.value}: factory error - {e}")

        assert not failures, "Factory/REQUIRED_FIELDS mismatches:\n" + "\n".join(failures)

    @pytest.mark.parametrize(
        "event_type",
        [et for et in EventType if et in REQUIRED_FIELDS],
        ids=lambda et: et.value,
    )
    def test_individual_factory_required_fields(
        self,
        event_type: EventType,
        factories: dict[EventType, Callable[[], AgentEvent]],
    ) -> None:
        """Individual test per event type for better failure isolation."""
        if event_type not in factories:
            pytest.skip(f"No test factory for {event_type.value}")

        factory = factories[event_type]
        event = factory()
        required = REQUIRED_FIELDS.get(event_type, set())
        missing = required - set(event.data.keys())

        assert not missing, f"Missing required fields: {missing}"


# =============================================================================
# Test 2: Schema Coverage
# =============================================================================


class TestSchemaCoverage:
    """Ensure every EventType has a corresponding schema."""

    def test_all_event_types_have_schemas(self) -> None:
        """Every EventType enum value must have a schema in EVENT_SCHEMAS."""
        missing = [et.value for et in EventType if et not in EVENT_SCHEMAS]
        assert not missing, f"EventTypes missing schemas: {missing}"

    def test_no_orphan_schemas(self) -> None:
        """EVENT_SCHEMAS should not contain keys that aren't EventType values."""
        valid_types = set(EventType)
        orphans = [k for k in EVENT_SCHEMAS if k not in valid_types]
        assert not orphans, f"Orphan schemas (not in EventType): {orphans}"


# =============================================================================
# Test 3: Field Type Consistency
# =============================================================================


class TestFieldTypeConsistency:
    """Test that factory outputs match TypedDict type annotations."""

    def test_required_fields_exist_in_schema(self) -> None:
        """REQUIRED_FIELDS entries must exist in corresponding TypedDict."""
        failures = []

        for event_type, required in REQUIRED_FIELDS.items():
            schema = EVENT_SCHEMAS.get(event_type)
            if not schema:
                failures.append(f"{event_type.value}: no schema")
                continue

            annotations = get_type_hints(schema) if hasattr(schema, "__annotations__") else {}
            unknown = required - set(annotations.keys())
            if unknown:
                failures.append(f"{event_type.value}: required fields {unknown} not in schema")

        assert not failures, "REQUIRED_FIELDS/schema mismatches:\n" + "\n".join(failures)


# =============================================================================
# Test 4: Unit Naming Convention
# =============================================================================


class TestUnitNamingConvention:
    """Enforce consistent unit naming in field names."""

    def test_time_field_naming_convention(self) -> None:
        """Fields with time values should use consistent suffixes.

        - _ms suffix: int milliseconds
        - _s suffix: float seconds
        - _seconds suffix: float seconds
        """
        issues = []

        for event_type, schema in EVENT_SCHEMAS.items():
            try:
                annotations = get_type_hints(schema)
            except Exception:
                continue

            for field, type_hint in annotations.items():
                # Check _ms fields are int
                if field.endswith("_ms"):
                    # Allow int or int | None
                    type_str = str(type_hint)
                    if "int" not in type_str:
                        issues.append(
                            f"{event_type.value}.{field}: _ms field should be int, got {type_hint}"
                        )

                # Check _s fields are float
                if field.endswith("_s") and not field.endswith("_ms"):
                    type_str = str(type_hint)
                    if "float" not in type_str:
                        issues.append(
                            f"{event_type.value}.{field}: _s field should be float, got {type_hint}"
                        )

        # Report issues but don't fail - this is advisory
        if issues:
            pytest.xfail("Unit naming convention issues:\n" + "\n".join(issues))


# =============================================================================
# Test 5: Bidirectional Sync
# =============================================================================


class TestBidirectionalSync:
    """Ensure schemas and REQUIRED_FIELDS stay in sync."""

    def test_required_fields_are_subset_of_schema(self) -> None:
        """Every required field must exist in the schema."""
        failures = []

        for event_type, required in REQUIRED_FIELDS.items():
            schema = EVENT_SCHEMAS.get(event_type)
            if not schema:
                continue

            try:
                annotations = get_type_hints(schema)
            except Exception:
                annotations = getattr(schema, "__annotations__", {})

            missing = required - set(annotations.keys())
            if missing:
                failures.append(f"{event_type.value}: {missing} not in schema")

        assert not failures, "Sync issues:\n" + "\n".join(failures)


# =============================================================================
# Test 6: Generated Artifact Freshness
# =============================================================================


class TestGeneratedArtifactFreshness:
    """Ensure generated schema files are up-to-date."""

    def test_json_schema_is_current(self) -> None:
        """JSON schema should match what generate_event_schema.py produces."""
        schema_path = Path(__file__).parent.parent / "schemas" / "agent-events.schema.json"
        if not schema_path.exists():
            pytest.skip("JSON Schema file not found")

        # Read current schema
        current_schema = json.loads(schema_path.read_text())

        # Generate fresh schema
        script_path = Path(__file__).parent.parent / "scripts" / "generate_event_schema.py"
        if not script_path.exists():
            pytest.skip("generate_event_schema.py not found")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Temporarily redirect output
            tmp_schema = Path(tmpdir) / "test-schema.json"

            # Import and run the generator
            try:
                from scripts.generate_event_schema import generate_json_schema

                fresh_schema = generate_json_schema()

                # Compare event count
                current_events = {
                    e["properties"]["type"]["const"] for e in current_schema.get("oneOf", [])
                }
                fresh_events = {
                    e["properties"]["type"]["const"] for e in fresh_schema.get("oneOf", [])
                }

                missing = fresh_events - current_events
                extra = current_events - fresh_events

                if missing:
                    pytest.fail(
                        f"JSON schema is stale - missing events: {missing}. "
                        "Run: python scripts/generate_event_schema.py"
                    )
                if extra:
                    pytest.fail(
                        f"JSON schema has extra events: {extra}. "
                        "Run: python scripts/generate_event_schema.py"
                    )

            except ImportError:
                pytest.skip("Could not import generate_event_schema")


# =============================================================================
# Test 7: Property-Based Factory Tests
# =============================================================================


class TestFactoryRobustness:
    """Test factories handle various inputs gracefully."""

    def test_convergence_events_handle_edge_cases(self) -> None:
        """Convergence factories should handle edge case values."""
        from sunwell.agent.events import convergence as conv

        # Zero iteration
        event = conv.convergence_iteration_start_event(0, [])
        assert event.data["iteration"] == 0

        # Empty lists
        event = conv.convergence_start_event([], [], 0)
        assert event.data["files"] == []
        assert event.data["gates"] == []

        # Large iteration numbers
        event = conv.convergence_iteration_complete_event(999, False, 100, [])
        assert event.data["iteration"] == 999

    def test_model_events_handle_edge_cases(self) -> None:
        """Model factories should handle edge case values."""
        from sunwell.agent.events import model as mdl

        # Empty tokens
        event = mdl.model_tokens_event("task-1", "", 0, 0.0)
        assert event.data["tokens"] == ""

        # Zero duration
        event = mdl.model_complete_event("task-1", 0, 0.0, 0.0, None)
        assert event.data["duration_s"] == 0.0

    def test_tool_events_handle_edge_cases(self) -> None:
        """Tool factories should handle edge case values."""
        from sunwell.agent.events import tool

        # Empty tool name (edge case, but should not crash)
        event = tool.tool_start_event("", "call-1", {})
        assert event.data["tool_name"] == ""

        # Large arguments dict
        big_args = {f"arg_{i}": f"value_{i}" for i in range(100)}
        event = tool.tool_start_event("test", "call-1", big_args)
        assert len(event.data["arguments"]) == 100


# =============================================================================
# Test 8: Cross-Module Import Test
# =============================================================================


class TestSchemaExports:
    """Test that all schema exports are properly exposed."""

    def test_all_exports_importable(self) -> None:
        """Everything in __all__ should be importable."""
        from sunwell.agent.events import schemas

        if not hasattr(schemas, "__all__"):
            pytest.skip("No __all__ defined")

        failures = []
        for name in schemas.__all__:
            if not hasattr(schemas, name):
                failures.append(name)

        assert not failures, f"Missing exports: {failures}"

    def test_event_schemas_values_are_typeddict(self) -> None:
        """All EVENT_SCHEMAS values should be TypedDict classes."""
        from typing import _TypedDictMeta  # type: ignore[attr-defined]

        failures = []
        for event_type, schema in EVENT_SCHEMAS.items():
            if not isinstance(schema, _TypedDictMeta):
                failures.append(f"{event_type.value}: {type(schema)} is not TypedDict")

        assert not failures, "Invalid schema types:\n" + "\n".join(failures)

    def test_required_fields_values_are_sets(self) -> None:
        """All REQUIRED_FIELDS values should be sets of strings."""
        failures = []
        for event_type, fields in REQUIRED_FIELDS.items():
            if not isinstance(fields, set):
                failures.append(f"{event_type.value}: {type(fields)} is not set")
            elif not all(isinstance(f, str) for f in fields):
                failures.append(f"{event_type.value}: contains non-string field names")

        assert not failures, "Invalid REQUIRED_FIELDS:\n" + "\n".join(failures)


# =============================================================================
# Test 9: Event Serialization Integrity
# =============================================================================


class TestEventSerializationIntegrity:
    """Test that events serialize and deserialize correctly."""

    @pytest.fixture
    def factories(self) -> dict[EventType, Callable[[], AgentEvent]]:
        return get_event_factories()

    def test_all_factory_events_json_serializable(
        self, factories: dict[EventType, Callable[[], AgentEvent]]
    ) -> None:
        """All factory-created events should be JSON serializable."""
        failures = []

        for event_type, factory in factories.items():
            try:
                event = factory()
                json_str = json.dumps(event.to_dict())
                parsed = json.loads(json_str)
                assert parsed["type"] == event_type.value
            except Exception as e:
                failures.append(f"{event_type.value}: {e}")

        assert not failures, "Serialization failures:\n" + "\n".join(failures)

    def test_event_roundtrip_preserves_data(
        self, factories: dict[EventType, Callable[[], AgentEvent]]
    ) -> None:
        """Events should roundtrip through JSON without data loss."""
        failures = []

        for event_type, factory in factories.items():
            try:
                event = factory()
                json_str = json.dumps(event.to_dict())
                parsed = json.loads(json_str)
                reconstructed = AgentEvent.from_dict(parsed)

                # Compare data
                if event.data != reconstructed.data:
                    failures.append(
                        f"{event_type.value}: data mismatch\n"
                        f"  original: {event.data}\n"
                        f"  reconstructed: {reconstructed.data}"
                    )
            except Exception as e:
                failures.append(f"{event_type.value}: {e}")

        assert not failures, "Roundtrip failures:\n" + "\n".join(failures)


# =============================================================================
# Test 10: Strict Validation Mode
# =============================================================================


class TestStrictValidationMode:
    """Test that strict validation catches schema violations."""

    @pytest.fixture
    def factories(self) -> dict[EventType, Callable[[], AgentEvent]]:
        return get_event_factories()

    def test_factories_pass_strict_validation(
        self,
        factories: dict[EventType, Callable[[], AgentEvent]],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Factory outputs should pass strict validation."""
        from sunwell.agent.events.schemas import validate_event_data

        # Set strict validation mode via environment variable
        monkeypatch.setenv("SUNWELL_EVENT_VALIDATION", "strict")

        failures = []

        for event_type, factory in factories.items():
            try:
                event = factory()
                # This should not raise in strict mode
                validate_event_data(event_type, event.data)
            except ValueError as e:
                failures.append(f"{event_type.value}: {e}")
            except Exception as e:
                # Other exceptions are unexpected
                failures.append(f"{event_type.value}: unexpected error - {e}")

        assert not failures, "Strict validation failures:\n" + "\n".join(failures)
