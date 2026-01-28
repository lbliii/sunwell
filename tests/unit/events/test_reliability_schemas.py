"""Tests for reliability event schemas.

Verifies that the 8 reliability-related event schemas are:
- Properly defined as TypedDict classes
- Registered in EVENT_SCHEMAS
- Have appropriate REQUIRED_FIELDS entries
"""

import pytest

from sunwell.agent.events import EventType
from sunwell.agent.events.schemas import (
    EVENT_SCHEMAS,
    REQUIRED_FIELDS,
    BudgetExhaustedData,
    BudgetWarningData,
    CircuitBreakerOpenData,
    HealthCheckFailedData,
    HealthWarningData,
    ReliabilityHallucinationData,
    ReliabilityWarningData,
    TimeoutData,
)


# =============================================================================
# Schema Registration Tests
# =============================================================================


class TestReliabilitySchemaRegistration:
    """Test that all reliability schemas are registered."""

    @pytest.mark.parametrize(
        "event_type,schema_class",
        [
            (EventType.RELIABILITY_WARNING, ReliabilityWarningData),
            (EventType.RELIABILITY_HALLUCINATION, ReliabilityHallucinationData),
            (EventType.CIRCUIT_BREAKER_OPEN, CircuitBreakerOpenData),
            (EventType.BUDGET_EXHAUSTED, BudgetExhaustedData),
            (EventType.BUDGET_WARNING, BudgetWarningData),
            (EventType.HEALTH_CHECK_FAILED, HealthCheckFailedData),
            (EventType.HEALTH_WARNING, HealthWarningData),
            (EventType.TIMEOUT, TimeoutData),
        ],
        ids=[
            "reliability_warning",
            "reliability_hallucination",
            "circuit_breaker_open",
            "budget_exhausted",
            "budget_warning",
            "health_check_failed",
            "health_warning",
            "timeout",
        ],
    )
    def test_schema_registered(
        self, event_type: EventType, schema_class: type
    ) -> None:
        """Verify each reliability event type is registered with correct schema."""
        assert event_type in EVENT_SCHEMAS, f"{event_type.value} not in EVENT_SCHEMAS"
        assert EVENT_SCHEMAS[event_type] == schema_class


class TestReliabilityRequiredFields:
    """Test that required fields are defined for reliability events."""

    @pytest.mark.parametrize(
        "event_type,expected_fields",
        [
            (EventType.RELIABILITY_WARNING, {"warning"}),
            (EventType.RELIABILITY_HALLUCINATION, {"detected_pattern"}),
            (EventType.CIRCUIT_BREAKER_OPEN, {"state", "consecutive_failures", "failure_threshold"}),
            (EventType.BUDGET_EXHAUSTED, {"spent", "budget"}),
            (EventType.BUDGET_WARNING, {"remaining"}),
            (EventType.HEALTH_CHECK_FAILED, {"errors"}),
            (EventType.HEALTH_WARNING, {"warnings"}),
            (EventType.TIMEOUT, {"operation"}),
        ],
        ids=[
            "reliability_warning",
            "reliability_hallucination",
            "circuit_breaker_open",
            "budget_exhausted",
            "budget_warning",
            "health_check_failed",
            "health_warning",
            "timeout",
        ],
    )
    def test_required_fields_defined(
        self, event_type: EventType, expected_fields: set[str]
    ) -> None:
        """Verify each reliability event has correct required fields."""
        assert event_type in REQUIRED_FIELDS, f"{event_type.value} not in REQUIRED_FIELDS"
        assert REQUIRED_FIELDS[event_type] == expected_fields


# =============================================================================
# Schema Structure Tests
# =============================================================================


class TestReliabilitySchemaStructure:
    """Test the structure of reliability TypedDict schemas."""

    def test_reliability_warning_data_fields(self) -> None:
        """Test ReliabilityWarningData has expected fields."""
        # TypedDict annotations should include expected fields
        annotations = ReliabilityWarningData.__annotations__
        assert "warning" in annotations
        assert "context" in annotations

    def test_reliability_hallucination_data_fields(self) -> None:
        """Test ReliabilityHallucinationData has expected fields."""
        annotations = ReliabilityHallucinationData.__annotations__
        assert "detected_pattern" in annotations
        assert "evidence" in annotations
        assert "severity" in annotations

    def test_circuit_breaker_open_data_fields(self) -> None:
        """Test CircuitBreakerOpenData has expected fields."""
        annotations = CircuitBreakerOpenData.__annotations__
        assert "state" in annotations
        assert "consecutive_failures" in annotations
        assert "failure_threshold" in annotations

    def test_budget_exhausted_data_fields(self) -> None:
        """Test BudgetExhaustedData has expected fields."""
        annotations = BudgetExhaustedData.__annotations__
        assert "spent" in annotations
        assert "budget" in annotations
        assert "percentage_used" in annotations

    def test_budget_warning_data_fields(self) -> None:
        """Test BudgetWarningData has expected fields."""
        annotations = BudgetWarningData.__annotations__
        assert "remaining" in annotations
        assert "percentage_remaining" in annotations

    def test_health_check_failed_data_fields(self) -> None:
        """Test HealthCheckFailedData has expected fields."""
        annotations = HealthCheckFailedData.__annotations__
        assert "errors" in annotations
        assert "error_count" in annotations

    def test_health_warning_data_fields(self) -> None:
        """Test HealthWarningData has expected fields."""
        annotations = HealthWarningData.__annotations__
        assert "warnings" in annotations
        assert "warning_count" in annotations

    def test_timeout_data_fields(self) -> None:
        """Test TimeoutData has expected fields."""
        annotations = TimeoutData.__annotations__
        assert "operation" in annotations
        assert "timeout_seconds" in annotations
        assert "elapsed_seconds" in annotations


# =============================================================================
# Factory Integration Tests
# =============================================================================


class TestReliabilityFactoryIntegration:
    """Test that factory functions produce valid data for schemas."""

    def test_circuit_breaker_open_event_factory(self) -> None:
        """Test circuit_breaker_open_event produces valid data."""
        from sunwell.agent.events import circuit_breaker_open_event

        event = circuit_breaker_open_event(
            state="open",
            consecutive_failures=5,
            failure_threshold=3,
        )

        assert event.data["state"] == "open"
        assert event.data["consecutive_failures"] == 5
        assert event.data["failure_threshold"] == 3

    def test_budget_exhausted_event_factory(self) -> None:
        """Test tool_loop_budget_exhausted_event produces valid data."""
        from sunwell.agent.events import tool_loop_budget_exhausted_event

        event = tool_loop_budget_exhausted_event(spent=1000, budget=1000)

        assert event.data["spent"] == 1000
        assert event.data["budget"] == 1000
        assert event.data["percentage_used"] == 100.0

    def test_budget_warning_event_factory(self) -> None:
        """Test tool_loop_budget_warning_event produces valid data."""
        from sunwell.agent.events import tool_loop_budget_warning_event

        event = tool_loop_budget_warning_event(remaining=100, percentage=0.1)

        assert event.data["remaining"] == 100
        assert event.data["percentage_remaining"] == 10.0

    def test_health_check_failed_event_factory(self) -> None:
        """Test health_check_failed_event produces valid data."""
        from sunwell.agent.events import health_check_failed_event

        event = health_check_failed_event(errors=["Error 1", "Error 2"])

        assert event.data["errors"] == ["Error 1", "Error 2"]
        assert event.data["error_count"] == 2
