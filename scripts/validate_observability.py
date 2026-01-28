#!/usr/bin/env python3
"""Validate observability enhancements are working.

Quick script to verify:
1. New event types are being emitted
2. EventRecorder captures them correctly
3. New assertions work

Usage:
    python scripts/validate_observability.py
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_recorder_captures_new_event_types():
    """Test that EventRecorder extracts data from new event types."""
    from sunwell.agent.events import EventType
    from sunwell.agent.events.types import AgentEvent
    from sunwell.benchmark.journeys.recorder import EventRecorder

    recorder = EventRecorder()

    # Simulate SIGNAL_ROUTE event
    route_event = AgentEvent(
        type=EventType.SIGNAL_ROUTE,
        data={
            "confidence": 0.75,
            "strategy": "interference",
            "threshold_vortex": 0.6,
            "threshold_interference": 0.85,
        },
    )
    recorder._handle_event(route_event)

    # Simulate MODEL_COMPLETE event with metrics
    model_event = AgentEvent(
        type=EventType.MODEL_COMPLETE,
        data={
            "model": "test-model",
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "tokens_per_second": 25.0,
            "duration_s": 6.0,
            "finish_reason": "stop",
        },
    )
    recorder._handle_event(model_event)

    # Simulate GATE_PASS event
    gate_event = AgentEvent(
        type=EventType.GATE_PASS,
        data={
            "gate_id": "syntax",
            "gate_type": "syntax",
            "duration_ms": 50,
        },
    )
    recorder._handle_event(gate_event)

    # Simulate RELIABILITY_WARNING event
    reliability_event = AgentEvent(
        type=EventType.RELIABILITY_WARNING,
        data={
            "failure_type": "no_tools_when_needed",
            "confidence": 0.8,
            "message": "Model did not use tools",
            "suggested_action": "Retry with different prompt",
        },
    )
    recorder._handle_event(reliability_event)

    # Verify routing was captured
    assert len(recorder.routings) == 1
    assert recorder.routings[0].strategy == "interference"
    assert recorder.routings[0].confidence == 0.75
    print("✓ Routing events captured correctly")

    # Verify model metrics were captured
    assert len(recorder.model_metrics) == 1
    assert recorder.model_metrics[0].model == "test-model"
    assert recorder.model_metrics[0].total_tokens == 150
    print("✓ Model metrics captured correctly")

    # Verify validation was captured
    assert len(recorder.validations) == 1
    assert recorder.validations[0].passed is True
    assert recorder.validations[0].gate_type == "syntax"
    print("✓ Validation events captured correctly")

    # Verify reliability issues were captured
    assert len(recorder.reliability_issues) == 1
    assert recorder.reliability_issues[0].failure_type == "no_tools_when_needed"
    print("✓ Reliability events captured correctly")

    # Test query methods
    assert recorder.routing_strategy == "interference"
    assert recorder.total_tokens == 150
    assert recorder.has_reliability_issue()
    assert recorder.validation_passed()
    print("✓ Query methods work correctly")

    print("\n✅ All recorder tests passed!")


def test_new_assertions():
    """Test that new assertion methods work."""
    from sunwell.agent.events import EventType
    from sunwell.agent.events.types import AgentEvent
    from sunwell.benchmark.journeys.assertions import BehavioralAssertions
    from sunwell.benchmark.journeys.recorder import EventRecorder
    from sunwell.benchmark.journeys.types import Expectation

    assertions = BehavioralAssertions()
    recorder = EventRecorder()

    # Add test events
    recorder._handle_event(AgentEvent(
        type=EventType.SIGNAL_ROUTE,
        data={"confidence": 0.9, "strategy": "single_shot"},
    ))
    recorder._handle_event(AgentEvent(
        type=EventType.MODEL_COMPLETE,
        data={"total_tokens": 100},
    ))
    recorder._handle_event(AgentEvent(
        type=EventType.GATE_PASS,
        data={"gate_id": "lint", "gate_type": "lint"},
    ))

    # Test routing strategy assertion
    result = assertions.check_routing_strategy(recorder, "single_shot")
    assert result.passed, f"Expected single_shot, got: {result.message}"
    print("✓ check_routing_strategy works")

    # Test validation assertion
    result = assertions.check_validation_passed(recorder)
    assert result.passed, f"Expected validation to pass: {result.message}"
    print("✓ check_validation_passed works")

    # Test no reliability issues assertion
    result = assertions.check_no_reliability_issues(recorder)
    assert result.passed, f"Expected no reliability issues: {result.message}"
    print("✓ check_no_reliability_issues works")

    # Test token budget assertion
    result = assertions.check_token_budget(recorder, max_tokens=500)
    assert result.passed, f"Expected under budget: {result.message}"
    print("✓ check_token_budget works")

    # Test check_all with new expectations
    expectation = Expectation(
        routing_strategy="single_shot",
        validation_must_pass=True,
        no_reliability_issues=True,
        max_tokens=500,
    )
    report = assertions.check_all(recorder, expectation)
    assert report.passed, f"Expected all to pass: {report.failures()}"
    print("✓ check_all with new expectations works")

    print("\n✅ All assertion tests passed!")


def test_event_factories():
    """Test new event factory functions."""
    from sunwell.agent.events import (
        goal_received_event,
        goal_complete_event,
        goal_failed_event,
        signal_route_event,
    )

    # Test goal events
    event = goal_received_event(goal="Test task")
    assert event.data["goal"] == "Test task"
    print("✓ goal_received_event works")

    event = goal_complete_event(turns=5, tools_called=3)
    assert event.data["turns"] == 5
    assert event.data["tools_called"] == 3
    print("✓ goal_complete_event works")

    event = goal_failed_event(error="Test error", turn=2)
    assert event.data["error"] == "Test error"
    print("✓ goal_failed_event works")

    # Test routing event
    event = signal_route_event(confidence=0.8, strategy="interference")
    assert event.data["confidence"] == 0.8
    assert event.data["strategy"] == "interference"
    print("✓ signal_route_event works")

    print("\n✅ All event factory tests passed!")


def main():
    """Run all validation tests."""
    print("=" * 60)
    print("Validating Observability Enhancements")
    print("=" * 60)
    print()

    print("1. Testing Event Factories")
    print("-" * 40)
    test_event_factories()
    print()

    print("2. Testing EventRecorder Extraction")
    print("-" * 40)
    test_recorder_captures_new_event_types()
    print()

    print("3. Testing New Assertions")
    print("-" * 40)
    test_new_assertions()
    print()

    print("=" * 60)
    print("🎉 All validations passed!")
    print("=" * 60)
    print()
    print("To run the full journey tests:")
    print("  python -m sunwell.benchmark.journeys.cli run benchmark/journeys/observability/")


if __name__ == "__main__":
    main()
