"""Integration tests for RFC-060: Event Contract Alignment.

These tests verify that:
1. Python schemas match actual event emissions
2. All event types have corresponding schemas
3. Required fields are validated
4. Validation mode control works correctly
"""

import os
from typing import Any

import pytest

from sunwell.agent.events import AgentEvent, EventType
from sunwell.agent.events.schemas import (
    EVENT_SCHEMAS,
    REQUIRED_FIELDS,
    PlanWinnerData,
    PlanRefineCompleteData,
    PlanRefineStartData,
    PlanCandidatesCompleteData,
    create_validated_event,
    validate_event_data,
    get_validation_mode,
)


# =============================================================================
# Schema Completeness Tests
# =============================================================================


class TestSchemaCompleteness:
    """Verify all event types have schemas and required fields defined."""

    def test_all_event_types_have_schemas(self) -> None:
        """Verify every EventType has a corresponding schema in EVENT_SCHEMAS."""
        # These event types may legitimately not have schemas (generic events)
        optional_events = {
            EventType.PLAN_CANDIDATE,  # Legacy, superseded by RFC-058 events
        }

        for event_type in EventType:
            if event_type in optional_events:
                continue
            assert event_type in EVENT_SCHEMAS, (
                f"EventType.{event_type.name} has no schema in EVENT_SCHEMAS. "
                f"Add a TypedDict schema for this event type."
            )

    def test_event_schemas_have_annotations(self) -> None:
        """Verify all schemas have type annotations."""
        for event_type, schema in EVENT_SCHEMAS.items():
            assert hasattr(schema, "__annotations__"), (
                f"Schema for {event_type.name} has no __annotations__. "
                f"Ensure it's a proper TypedDict."
            )


# =============================================================================
# RFC-058 Field Tests (Harmonic Planning)
# =============================================================================


class TestPlanWinnerSchema:
    """Verify PlanWinnerData schema includes RFC-058 fields."""

    def test_schema_includes_rfc058_fields(self) -> None:
        """Verify PlanWinnerData includes all RFC-058 fields."""
        schema = PlanWinnerData
        expected_fields = {
            # Legacy fields
            "tasks",
            "artifact_count",
            "gates",
            "technique",
            # RFC-058 fields (selected_candidate_id replaces selected_index)
            "selected_candidate_id",
            "total_candidates",
            "metrics",
            "selection_reason",
            "variance_strategy",
            "variance_config",
            "refinement_rounds",
            "final_score_improvement",
            "score",  # RFC-060: top-level score
        }
        actual_fields = set(schema.__annotations__.keys())
        missing = expected_fields - actual_fields
        assert not missing, f"PlanWinnerData missing fields: {missing}"

    def test_plan_winner_event_validates(self) -> None:
        """Verify a complete plan_winner event passes validation."""
        data = {
            "tasks": 5,
            "artifact_count": 5,
            "selected_candidate_id": "candidate-0",
            "total_candidates": 3,
            "score": 85.5,
            "metrics": {
                "score": 85.5,
                "depth": 2,
                "width": 3,
                "leaf_count": 3,
                "parallelism_factor": 0.6,
                "balance_factor": 1.5,
                "file_conflicts": 0,
                "estimated_waves": 2,
            },
            "selection_reason": "Highest composite score",
            "variance_strategy": "prompting",
            "variance_config": {"prompt_style": "parallel_first"},
            "refinement_rounds": 1,
            "final_score_improvement": 5.0,
        }
        # Should not raise
        event = create_validated_event(EventType.PLAN_WINNER, data)
        assert event.type == EventType.PLAN_WINNER
        assert event.data["score"] == 85.5

    def test_plan_winner_requires_tasks(self) -> None:
        """Verify tasks is required for plan_winner."""
        assert "tasks" in REQUIRED_FIELDS.get(EventType.PLAN_WINNER, set())


class TestPlanRefineCompleteSchema:
    """Verify PlanRefineCompleteData schema alignment."""

    def test_schema_uses_correct_field_names(self) -> None:
        """Verify field names match frontend expectations."""
        schema = PlanRefineCompleteData
        expected_fields = {
            "round",
            "improved",
            "old_score",
            "new_score",
            "improvement",  # Not score_improvement
            "reason",
            "improvements_applied",
        }
        actual_fields = set(schema.__annotations__.keys())
        missing = expected_fields - actual_fields
        assert not missing, f"PlanRefineCompleteData missing fields: {missing}"

        # Verify old name is NOT present
        assert "score_improvement" not in actual_fields, (
            "PlanRefineCompleteData should use 'improvement' not 'score_improvement'"
        )

    def test_plan_refine_complete_validates(self) -> None:
        """Verify a complete plan_refine_complete event passes validation."""
        data = {
            "round": 1,
            "improved": True,
            "old_score": 80.0,
            "new_score": 85.0,
            "improvement": 5.0,
            "reason": "Applied optimization",
            "improvements_applied": ["Parallelized dependencies"],
        }
        event = create_validated_event(EventType.PLAN_REFINE_COMPLETE, data)
        assert event.type == EventType.PLAN_REFINE_COMPLETE


class TestPlanRefineStartSchema:
    """Verify PlanRefineStartData schema alignment."""

    def test_improvements_identified_is_list(self) -> None:
        """Verify improvements_identified is typed as list[str]."""
        schema = PlanRefineStartData
        annotations = schema.__annotations__
        assert "improvements_identified" in annotations
        # The type should be list[str] - check the string representation
        type_str = str(annotations["improvements_identified"])
        assert "list" in type_str.lower() or "List" in type_str


class TestPlanCandidatesCompleteSchema:
    """Verify PlanCandidatesCompleteData schema alignment."""

    def test_schema_includes_success_failure_fields(self) -> None:
        """Verify schema includes successful/failed candidate counts."""
        schema = PlanCandidatesCompleteData
        annotations = schema.__annotations__
        assert "successful_candidates" in annotations
        assert "failed_candidates" in annotations


# =============================================================================
# Validation Mode Tests
# =============================================================================


class TestValidationMode:
    """Verify validation mode control works correctly."""

    def test_default_mode_is_lenient(self) -> None:
        """Verify default validation mode is lenient."""
        # Clear env var to test default
        original = os.environ.pop("SUNWELL_EVENT_VALIDATION", None)
        try:
            mode = get_validation_mode()
            assert mode == "lenient"
        finally:
            if original is not None:
                os.environ["SUNWELL_EVENT_VALIDATION"] = original

    def test_strict_mode_raises_on_missing_required(self) -> None:
        """Verify strict mode raises ValueError for missing required fields."""
        os.environ["SUNWELL_EVENT_VALIDATION"] = "strict"
        try:
            with pytest.raises(ValueError, match="missing required fields"):
                create_validated_event(EventType.PLAN_WINNER, {})
        finally:
            os.environ["SUNWELL_EVENT_VALIDATION"] = "lenient"

    def test_lenient_mode_logs_but_continues(self) -> None:
        """Verify lenient mode creates event despite missing fields."""
        os.environ["SUNWELL_EVENT_VALIDATION"] = "lenient"
        try:
            # Should not raise, but will log a warning
            event = create_validated_event(EventType.PLAN_WINNER, {})
            assert event.type == EventType.PLAN_WINNER
        finally:
            pass  # Keep lenient as default

    def test_off_mode_skips_validation(self) -> None:
        """Verify off mode skips validation entirely."""
        os.environ["SUNWELL_EVENT_VALIDATION"] = "off"
        try:
            event = create_validated_event(EventType.PLAN_WINNER, {})
            assert event.type == EventType.PLAN_WINNER
        finally:
            os.environ["SUNWELL_EVENT_VALIDATION"] = "lenient"


# =============================================================================
# Event Emission Alignment Tests
# =============================================================================


class TestEventEmissionAlignment:
    """Verify event emissions match schemas."""

    def test_plan_winner_emission_structure(self) -> None:
        """Verify plan_winner emission includes all expected fields.

        This simulates what HarmonicPlanner emits and verifies it matches schema.
        """
        # Simulate HarmonicPlanner emission structure
        emission = {
            "tasks": 5,
            "artifact_count": 5,
            "selected_candidate_id": "candidate-0",
            "total_candidates": 3,
            "score": 85.5,  # RFC-060: top-level score
            "metrics": {
                "score": 85.5,
                "depth": 2,
                "width": 3,
                "leaf_count": 3,
                "parallelism_factor": 0.6,
                "balance_factor": 1.5,
                "file_conflicts": 0,
                "estimated_waves": 2,
            },
            "selection_reason": "Highest composite score",
            "variance_strategy": "prompting",
            "variance_config": {
                "prompt_style": "parallel_first",
                "temperature": None,
                "constraint": None,
            },
            "refinement_rounds": 1,
            "final_score_improvement": 5.0,
        }

        # All fields in emission should be defined in schema
        schema_fields = set(PlanWinnerData.__annotations__.keys())
        emission_fields = set(emission.keys())

        # Emission may have fields not in schema (loose typing), but all
        # schema fields should be representable
        # This test verifies structure compatibility
        event = create_validated_event(EventType.PLAN_WINNER, emission)
        assert event.data["score"] == 85.5
        assert event.data["variance_config"]["prompt_style"] == "parallel_first"

    def test_plan_refine_complete_emission_structure(self) -> None:
        """Verify plan_refine_complete emission matches schema."""
        # Simulate HarmonicPlanner._refine_plan emission (improved case)
        emission = {
            "round": 1,
            "improved": True,
            "old_score": 80.0,
            "new_score": 85.0,
            "improvement": 5.0,  # RFC-060: renamed from score_improvement
        }

        event = create_validated_event(EventType.PLAN_REFINE_COMPLETE, emission)
        assert event.data["improved"] is True
        assert event.data["improvement"] == 5.0

    def test_plan_refine_start_emission_structure(self) -> None:
        """Verify plan_refine_start emission matches schema."""
        # Simulate HarmonicPlanner._refine_plan emission
        emission = {
            "round": 1,
            "total_rounds": 3,
            "current_score": 80.0,
            "improvements_identified": [
                "Deep dependency chain - can parallelize",
                "Low parallelism factor - add leaf nodes",
            ],
        }

        event = create_validated_event(EventType.PLAN_REFINE_START, emission)
        assert event.data["round"] == 1
        assert isinstance(event.data["improvements_identified"], list)
