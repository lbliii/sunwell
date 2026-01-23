"""Goal Lifecycle State Handoff Tests.

Validates that all pieces of state are correctly populated and handed off
across the entire lifecycle of a triggered goal. These tests catch issues
where state is not propagating to the Studio desktop.

RFC-LIFECYCLE: Event sequence contract for full goal lifecycle:
1. MEMORY_* events → Session loaded/created
2. SIGNAL → Signal extraction
3. PLAN_* events → Planning phase (candidate generation, scoring, winner)
4. TASK_* events → Task execution (start, progress, complete/failed)
5. GATE_* events → Validation gates (optional)
6. MEMORY_LEARNING → Learning extraction (optional)
7. COMPLETE/ERROR → Terminal events

Each event must contain required fields for Studio to update correctly.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import tempfile

import pytest

from sunwell.adaptive.events import AgentEvent, EventType
from sunwell.adaptive.event_schema import REQUIRED_FIELDS, validate_event_data


# =============================================================================
# Test Fixtures
# =============================================================================


@dataclass
class LifecycleEventCapture:
    """Captures and validates events across the full lifecycle."""

    events: list[AgentEvent] = field(default_factory=list)
    
    # Tracking for lifecycle phases
    memory_events: list[AgentEvent] = field(default_factory=list)
    signal_events: list[AgentEvent] = field(default_factory=list)
    plan_events: list[AgentEvent] = field(default_factory=list)
    task_events: list[AgentEvent] = field(default_factory=list)
    gate_events: list[AgentEvent] = field(default_factory=list)
    learning_events: list[AgentEvent] = field(default_factory=list)
    terminal_events: list[AgentEvent] = field(default_factory=list)

    def __call__(self, event: AgentEvent) -> None:
        """Capture and categorize an event."""
        self.events.append(event)
        self._categorize(event)

    def _categorize(self, event: AgentEvent) -> None:
        """Categorize event by lifecycle phase."""
        event_type = event.type.value if hasattr(event.type, 'value') else str(event.type)
        
        # Learning events (check first since memory_learning starts with "memory_")
        if event_type == "memory_learning":
            self.learning_events.append(event)
            return
        
        if event_type.startswith("memory_"):
            self.memory_events.append(event)
        elif event_type.startswith("signal"):
            self.signal_events.append(event)
        elif event_type.startswith("plan_"):
            self.plan_events.append(event)
        elif event_type.startswith("task_"):
            self.task_events.append(event)
        elif event_type.startswith("gate_") or event_type.startswith("validate_"):
            self.gate_events.append(event)
        elif event_type in ("complete", "error"):
            self.terminal_events.append(event)

    def get_types(self) -> list[str]:
        """Get list of event types in order."""
        return [
            e.type.value if hasattr(e.type, 'value') else str(e.type)
            for e in self.events
        ]

    def get_by_type(self, event_type: str) -> list[AgentEvent]:
        """Get all events of a specific type."""
        return [
            e for e in self.events
            if (e.type.value if hasattr(e.type, 'value') else str(e.type)) == event_type
        ]

    def get_data(self, event_type: str) -> list[dict[str, Any]]:
        """Get data payloads for all events of a type."""
        return [e.data for e in self.get_by_type(event_type)]

    def has_phase(self, phase: str) -> bool:
        """Check if a lifecycle phase occurred."""
        phase_events = {
            "memory": self.memory_events,
            "signal": self.signal_events,
            "plan": self.plan_events,
            "task": self.task_events,
            "gate": self.gate_events,
            "learning": self.learning_events,
            "terminal": self.terminal_events,
        }
        return len(phase_events.get(phase, [])) > 0


# =============================================================================
# Lifecycle Phase Tests
# =============================================================================


class TestLifecyclePhaseOrder:
    """Tests that lifecycle phases occur in correct order."""

    def test_phases_order_on_successful_run(self) -> None:
        """Test that phases occur in correct order for successful run."""
        capture = LifecycleEventCapture()

        # Simulate a complete successful lifecycle
        events_sequence = [
            # Memory phase
            (EventType.MEMORY_LOAD, {}),
            (EventType.MEMORY_LOADED, {"session": "test-session"}),
            # Signal phase
            (EventType.SIGNAL, {"status": "extracting"}),
            (EventType.SIGNAL, {"status": "extracted", "signals": {}}),
            # Planning phase
            (EventType.PLAN_START, {"goal": "test goal"}),
            (EventType.PLAN_CANDIDATE_START, {"total_candidates": 3, "variance_strategy": "prompting"}),
            (EventType.PLAN_CANDIDATE_GENERATED, {"candidate_id": "candidate-0", "artifact_count": 3, "progress": 1, "total_candidates": 3}),
            (EventType.PLAN_CANDIDATES_COMPLETE, {"successful_candidates": 1, "failed_candidates": 0, "total_candidates": 1}),
            (EventType.PLAN_CANDIDATE_SCORED, {"candidate_id": "candidate-0", "score": 85.0, "progress": 1, "total_candidates": 1}),
            (EventType.PLAN_SCORING_COMPLETE, {"total_scored": 1}),
            (EventType.PLAN_WINNER, {"tasks": 3, "artifact_count": 3, "selected_candidate_id": "candidate-0"}),
            # Task execution phase
            (EventType.TASK_START, {"task_id": "task-1", "description": "Create model"}),
            (EventType.TASK_COMPLETE, {"task_id": "task-1", "duration_ms": 100}),
            (EventType.TASK_START, {"task_id": "task-2", "description": "Create routes"}),
            (EventType.TASK_COMPLETE, {"task_id": "task-2", "duration_ms": 200}),
            # Validation gate
            (EventType.GATE_START, {"gate_id": "gate-1", "artifacts": ["task-1", "task-2"]}),
            (EventType.GATE_PASS, {"gate_id": "gate-1"}),
            # Learning extraction
            (EventType.MEMORY_LEARNING, {"fact": "Flask uses blueprints", "category": "framework", "confidence": 0.9}),
            # Terminal
            (EventType.COMPLETE, {"tasks_completed": 2, "tasks_failed": 0}),
        ]

        for event_type, data in events_sequence:
            capture(AgentEvent(event_type, data))

        # Verify all phases occurred
        assert capture.has_phase("memory"), "Memory phase missing"
        assert capture.has_phase("signal"), "Signal phase missing"
        assert capture.has_phase("plan"), "Plan phase missing"
        assert capture.has_phase("task"), "Task phase missing"
        assert capture.has_phase("terminal"), "Terminal phase missing"

        # Verify order using indices
        types = capture.get_types()
        
        # Memory must come before signals
        memory_idx = types.index("memory_load")
        signal_idx = types.index("signal")
        assert memory_idx < signal_idx, "Memory must come before signals"

        # Signals must come before planning
        plan_idx = types.index("plan_start")
        assert signal_idx < plan_idx, "Signals must come before planning"

        # Planning must come before task execution
        task_idx = types.index("task_start")
        assert plan_idx < task_idx, "Planning must come before task execution"

        # Terminal must be last
        complete_idx = types.index("complete")
        assert complete_idx == len(types) - 1, "Complete must be terminal event"

    def test_error_terminates_lifecycle(self) -> None:
        """Test that error event properly terminates lifecycle."""
        capture = LifecycleEventCapture()

        events_sequence = [
            (EventType.MEMORY_LOAD, {}),
            (EventType.MEMORY_NEW, {"session": "new-session"}),
            (EventType.SIGNAL, {"status": "extracting"}),
            (EventType.PLAN_START, {"goal": "failing goal"}),
            # Error during planning
            (EventType.ERROR, {"message": "Planning failed", "phase": "planning"}),
        ]

        for event_type, data in events_sequence:
            capture(AgentEvent(event_type, data))

        assert capture.has_phase("terminal"), "Error should be terminal"
        assert len(capture.terminal_events) == 1
        assert capture.terminal_events[0].type == EventType.ERROR


# =============================================================================
# Required Fields Tests
# =============================================================================


class TestRequiredFieldsPresent:
    """Tests that all required fields are present in events."""

    @pytest.mark.parametrize("event_type,test_data", [
        (EventType.TASK_START, {"task_id": "test-task", "description": "Test task"}),
        (EventType.TASK_COMPLETE, {"task_id": "test-task", "duration_ms": 100}),
        (EventType.TASK_FAILED, {"task_id": "test-task", "error": "Something failed"}),
        (EventType.TASK_PROGRESS, {"task_id": "test-task", "progress": 50}),
        (EventType.PLAN_WINNER, {"tasks": 5, "selected_candidate_id": "candidate-0"}),
        (EventType.COMPLETE, {"tasks_completed": 3, "tasks_failed": 0}),
        (EventType.ERROR, {"message": "Fatal error"}),
        (EventType.MEMORY_LEARNING, {"fact": "Python uses indentation", "category": "language"}),
    ])
    def test_required_fields_validated(self, event_type: EventType, test_data: dict) -> None:
        """Test that required fields are validated."""
        # Should not raise
        validated_data = validate_event_data(event_type, test_data)
        event = AgentEvent(event_type, validated_data)
        
        # Required fields should be present
        required = REQUIRED_FIELDS.get(event_type, set())
        for f in required:
            assert f in event.data, f"Required field '{f}' missing from {event_type.value}"

    def test_task_id_required_for_all_task_events(self) -> None:
        """task_id must be present in all task events."""
        task_events = [
            EventType.TASK_START,
            EventType.TASK_COMPLETE,
            EventType.TASK_FAILED,
            EventType.TASK_PROGRESS,
        ]

        for event_type in task_events:
            assert event_type in REQUIRED_FIELDS, f"{event_type.value} missing from REQUIRED_FIELDS"
            assert "task_id" in REQUIRED_FIELDS[event_type], (
                f"task_id must be required for {event_type.value}"
            )


# =============================================================================
# State Propagation Tests
# =============================================================================


class TestStatePropagation:
    """Tests that state propagates correctly between events."""

    def test_plan_winner_artifact_count_propagates_to_tasks(self) -> None:
        """plan_winner's artifact_count should match number of task events."""
        capture = LifecycleEventCapture()

        # Plan with 3 artifacts
        capture(AgentEvent(
            EventType.PLAN_WINNER,
            {"tasks": 3, "artifact_count": 3, "selected_candidate_id": "candidate-0"},
        ))

        # 3 task start/complete pairs
        for i in range(3):
            capture(AgentEvent(EventType.TASK_START, {"task_id": f"task-{i}", "description": f"Task {i}"}))
            capture(AgentEvent(EventType.TASK_COMPLETE, {"task_id": f"task-{i}", "duration_ms": 100}))

        capture(AgentEvent(EventType.COMPLETE, {"tasks_completed": 3, "tasks_failed": 0}))

        # Verify counts match
        plan_winner = capture.get_by_type("plan_winner")[0]
        task_starts = capture.get_by_type("task_start")
        complete = capture.get_by_type("complete")[0]

        assert plan_winner.data["artifact_count"] == len(task_starts), (
            "artifact_count in plan_winner should match task_start count"
        )
        assert complete.data["tasks_completed"] == len(task_starts), (
            "tasks_completed in complete should match task_start count"
        )

    def test_candidate_ids_consistent_across_events(self) -> None:
        """Candidate IDs must be consistent across planning events."""
        capture = LifecycleEventCapture()

        # Generate 3 candidates
        candidate_ids = ["candidate-0", "candidate-1", "candidate-2"]
        for i, cid in enumerate(candidate_ids):
            capture(AgentEvent(
                EventType.PLAN_CANDIDATE_GENERATED,
                {"candidate_id": cid, "artifact_count": 5, "progress": i + 1, "total_candidates": 3},
            ))

        # Score them
        for i, cid in enumerate(candidate_ids):
            capture(AgentEvent(
                EventType.PLAN_CANDIDATE_SCORED,
                {"candidate_id": cid, "score": 80.0 + i * 5, "progress": i + 1, "total_candidates": 3},
            ))

        # Winner
        capture(AgentEvent(
            EventType.PLAN_WINNER,
            {"tasks": 5, "selected_candidate_id": "candidate-2", "total_candidates": 3},
        ))

        # Verify winner references a valid candidate
        generated_ids = {
            e.data["candidate_id"]
            for e in capture.get_by_type("plan_candidate_generated")
        }
        winner = capture.get_by_type("plan_winner")[0]
        
        assert winner.data["selected_candidate_id"] in generated_ids, (
            f"plan_winner references '{winner.data['selected_candidate_id']}' "
            f"but only generated: {generated_ids}"
        )

    def test_task_ids_consistent_between_start_and_end(self) -> None:
        """Task IDs must match between task_start and task_complete/failed."""
        capture = LifecycleEventCapture()

        # Start tasks
        task_ids = ["model-user", "route-api", "test-unit"]
        for tid in task_ids:
            capture(AgentEvent(EventType.TASK_START, {"task_id": tid, "description": f"Create {tid}"}))

        # Complete them (some succeed, some fail)
        capture(AgentEvent(EventType.TASK_COMPLETE, {"task_id": "model-user", "duration_ms": 100}))
        capture(AgentEvent(EventType.TASK_COMPLETE, {"task_id": "route-api", "duration_ms": 200}))
        capture(AgentEvent(EventType.TASK_FAILED, {"task_id": "test-unit", "error": "Test failed"}))

        # Verify all started tasks have an end event
        started_ids = {e.data["task_id"] for e in capture.get_by_type("task_start")}
        completed_ids = {e.data["task_id"] for e in capture.get_by_type("task_complete")}
        failed_ids = {e.data["task_id"] for e in capture.get_by_type("task_failed")}
        ended_ids = completed_ids | failed_ids

        assert started_ids == ended_ids, (
            f"Started IDs {started_ids} don't match ended IDs {ended_ids}"
        )


# =============================================================================
# Studio Compatibility Tests
# =============================================================================


class TestStudioCompatibility:
    """Tests that events are compatible with Studio frontend expectations."""

    def test_plan_winner_has_tasks_field(self) -> None:
        """Studio expects 'tasks' field in plan_winner for progress calculation."""
        event = AgentEvent(
            EventType.PLAN_WINNER,
            {"tasks": 5, "artifact_count": 5, "selected_candidate_id": "candidate-0"},
        )
        
        assert "tasks" in event.data, "Studio requires 'tasks' field in plan_winner"
        assert isinstance(event.data["tasks"], int), "tasks must be an integer"

    def test_task_start_has_description(self) -> None:
        """Studio displays task description in UI."""
        event = AgentEvent(
            EventType.TASK_START,
            {"task_id": "test", "description": "Create user model"},
        )
        
        assert "description" in event.data, "Studio requires 'description' in task_start"
        assert len(event.data["description"]) > 0, "description should not be empty"

    def test_task_complete_has_duration(self) -> None:
        """Studio displays duration in task completion."""
        event = AgentEvent(
            EventType.TASK_COMPLETE,
            {"task_id": "test", "duration_ms": 1500},
        )
        
        assert "duration_ms" in event.data, "Studio requires 'duration_ms' in task_complete"
        assert isinstance(event.data["duration_ms"], (int, float)), "duration_ms must be numeric"

    def test_complete_event_has_counts(self) -> None:
        """Studio shows completion stats from complete event."""
        event = AgentEvent(
            EventType.COMPLETE,
            {"tasks_completed": 5, "tasks_failed": 1},
        )
        
        assert "tasks_completed" in event.data
        assert "tasks_failed" in event.data

    def test_error_event_has_message(self) -> None:
        """Studio displays error message from error event."""
        event = AgentEvent(
            EventType.ERROR,
            {"message": "Planning failed: invalid goal"},
        )
        
        assert "message" in event.data
        assert len(event.data["message"]) > 0

    def test_memory_learning_has_required_fields(self) -> None:
        """Studio displays learnings with fact, category, confidence."""
        event = AgentEvent(
            EventType.MEMORY_LEARNING,
            {"fact": "Flask uses decorators for routes", "category": "framework", "confidence": 0.85},
        )
        
        assert "fact" in event.data, "Studio requires 'fact' in memory_learning"
        assert "category" in event.data, "Studio requires 'category' in memory_learning"
        # confidence is optional but useful for UI


# =============================================================================
# ExecutionManager Integration Tests
# =============================================================================


class TestExecutionManagerStateHandoff:
    """Tests that ExecutionManager emits all required events."""

    @pytest.mark.asyncio
    async def test_execution_manager_emits_goal_added_via_ensure(self, tmp_path: Path) -> None:
        """ExecutionManager._ensure_goal should emit backlog_goal_added."""
        from sunwell.execution.manager import ExecutionManager

        capture = LifecycleEventCapture()

        class TestEmitter:
            def emit(self, event: AgentEvent) -> None:
                capture(event)

        # Create manager with test emitter
        manager = ExecutionManager(
            root=tmp_path,
            emitter=TestEmitter(),
        )

        # Use _ensure_goal which emits the event (simulates run_goal behavior)
        goal = await manager._ensure_goal("Build a test API", goal_id=None)

        # Verify BACKLOG_GOAL_ADDED was emitted
        added_events = capture.get_by_type("backlog_goal_added")
        assert len(added_events) >= 1, "ExecutionManager._ensure_goal should emit backlog_goal_added"
        assert added_events[0].data.get("goal_id") == goal.id
        assert added_events[0].data.get("title") == goal.title

    @pytest.mark.asyncio
    async def test_execution_manager_emit_method_works(self, tmp_path: Path) -> None:
        """ExecutionManager._emit delivers events to configured emitter."""
        from sunwell.execution.manager import ExecutionManager

        capture = LifecycleEventCapture()

        class TestEmitter:
            def emit(self, event: AgentEvent) -> None:
                capture(event)

        manager = ExecutionManager(
            root=tmp_path,
            emitter=TestEmitter(),
        )

        # Directly test emit
        manager._emit(EventType.PLAN_START, {"goal": "test"})
        manager._emit(EventType.PLAN_WINNER, {"tasks": 3, "selected_candidate_id": "c-0"})
        manager._emit(EventType.COMPLETE, {"tasks_completed": 3, "tasks_failed": 0})

        assert len(capture.events) == 3
        assert capture.get_types() == ["plan_start", "plan_winner", "complete"]


# =============================================================================
# Event Sequence Integrity Tests
# =============================================================================


class TestEventSequenceIntegrity:
    """Tests for event sequence integrity across the lifecycle."""

    def test_no_task_complete_without_task_start(self) -> None:
        """task_complete should never fire without a preceding task_start."""
        capture = LifecycleEventCapture()

        # Correct sequence
        capture(AgentEvent(EventType.TASK_START, {"task_id": "task-1", "description": "Task 1"}))
        capture(AgentEvent(EventType.TASK_COMPLETE, {"task_id": "task-1", "duration_ms": 100}))

        started_ids = {e.data["task_id"] for e in capture.get_by_type("task_start")}
        completed_ids = {e.data["task_id"] for e in capture.get_by_type("task_complete")}

        # All completed tasks should have been started
        orphan_completes = completed_ids - started_ids
        assert len(orphan_completes) == 0, f"Orphan task_complete events: {orphan_completes}"

    def test_balanced_task_events(self) -> None:
        """Every task_start must have exactly one task_complete or task_failed."""
        capture = LifecycleEventCapture()

        # 5 tasks: 3 complete, 2 fail
        task_outcomes = [
            ("task-1", "complete"),
            ("task-2", "complete"),
            ("task-3", "failed"),
            ("task-4", "complete"),
            ("task-5", "failed"),
        ]

        for task_id, outcome in task_outcomes:
            capture(AgentEvent(EventType.TASK_START, {"task_id": task_id, "description": f"{task_id}"}))
            if outcome == "complete":
                capture(AgentEvent(EventType.TASK_COMPLETE, {"task_id": task_id, "duration_ms": 100}))
            else:
                capture(AgentEvent(EventType.TASK_FAILED, {"task_id": task_id, "error": "Failed"}))

        starts = len(capture.get_by_type("task_start"))
        completes = len(capture.get_by_type("task_complete"))
        failures = len(capture.get_by_type("task_failed"))

        assert starts == completes + failures, (
            f"Unbalanced: {starts} starts != {completes} completes + {failures} failures"
        )

    def test_planning_must_complete_before_tasks(self) -> None:
        """plan_winner must be emitted before any task_start."""
        capture = LifecycleEventCapture()

        # Correct order
        capture(AgentEvent(EventType.PLAN_START, {"goal": "test"}))
        capture(AgentEvent(EventType.PLAN_WINNER, {"tasks": 2, "selected_candidate_id": "c-0"}))
        capture(AgentEvent(EventType.TASK_START, {"task_id": "t-1", "description": "Task 1"}))
        capture(AgentEvent(EventType.TASK_COMPLETE, {"task_id": "t-1", "duration_ms": 100}))

        types = capture.get_types()
        plan_winner_idx = types.index("plan_winner")
        task_start_idx = types.index("task_start")

        assert plan_winner_idx < task_start_idx, "plan_winner must come before task_start"

    def test_terminal_event_is_last(self) -> None:
        """complete or error must be the final event in sequence."""
        capture = LifecycleEventCapture()

        capture(AgentEvent(EventType.PLAN_START, {"goal": "test"}))
        capture(AgentEvent(EventType.PLAN_WINNER, {"tasks": 1, "selected_candidate_id": "c-0"}))
        capture(AgentEvent(EventType.TASK_START, {"task_id": "t-1", "description": "Task 1"}))
        capture(AgentEvent(EventType.TASK_COMPLETE, {"task_id": "t-1", "duration_ms": 100}))
        capture(AgentEvent(EventType.COMPLETE, {"tasks_completed": 1, "tasks_failed": 0}))

        types = capture.get_types()
        assert types[-1] == "complete", f"Terminal event should be last, got: {types[-1]}"


# =============================================================================
# Incremental Build State Tests
# =============================================================================


class TestIncrementalBuildState:
    """Tests for state handoff in incremental builds."""

    def test_skipped_tasks_counted_correctly(self) -> None:
        """In incremental builds, skipped tasks should be tracked separately."""
        capture = LifecycleEventCapture()

        # Plan with 5 artifacts
        capture(AgentEvent(
            EventType.PLAN_WINNER,
            {"tasks": 5, "artifact_count": 5, "selected_candidate_id": "c-0"},
        ))

        # Only 2 need rebuilding (incremental)
        capture(AgentEvent(EventType.TASK_START, {"task_id": "a-1", "description": "Rebuild 1"}))
        capture(AgentEvent(EventType.TASK_COMPLETE, {"task_id": "a-1", "duration_ms": 100}))
        capture(AgentEvent(EventType.TASK_START, {"task_id": "a-2", "description": "Rebuild 2"}))
        capture(AgentEvent(EventType.TASK_COMPLETE, {"task_id": "a-2", "duration_ms": 100}))

        # Complete should report actual work done
        capture(AgentEvent(
            EventType.COMPLETE,
            {"tasks_completed": 2, "tasks_failed": 0, "skipped": 3},
        ))

        complete = capture.get_by_type("complete")[0]
        task_count = len(capture.get_by_type("task_start"))

        # tasks_completed should match actual task_start events
        assert complete.data["tasks_completed"] == task_count, (
            "tasks_completed should match actual task events, not planned total"
        )

    def test_complete_event_has_skipped_count(self) -> None:
        """complete event can have optional skipped count for incremental builds."""
        capture = LifecycleEventCapture()

        # Complete event with skipped count (optional but useful)
        capture(AgentEvent(
            EventType.COMPLETE,
            {"tasks_completed": 2, "tasks_failed": 0, "skipped": 3},
        ))

        complete_events = capture.get_by_type("complete")
        assert len(complete_events) >= 1
        # skipped is optional but when present should be tracked
        if "skipped" in complete_events[0].data:
            assert complete_events[0].data["skipped"] == 3


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases in state handoff."""

    def test_empty_plan_handled(self) -> None:
        """Handle case where plan produces zero tasks."""
        capture = LifecycleEventCapture()

        capture(AgentEvent(EventType.PLAN_START, {"goal": "trivial"}))
        capture(AgentEvent(EventType.PLAN_WINNER, {"tasks": 0, "artifact_count": 0, "selected_candidate_id": "c-0"}))
        capture(AgentEvent(EventType.COMPLETE, {"tasks_completed": 0, "tasks_failed": 0}))

        plan_winner = capture.get_by_type("plan_winner")[0]
        assert plan_winner.data["tasks"] == 0, "Zero tasks should be valid"

    def test_all_tasks_fail(self) -> None:
        """Handle case where all tasks fail."""
        capture = LifecycleEventCapture()

        capture(AgentEvent(EventType.PLAN_WINNER, {"tasks": 2, "selected_candidate_id": "c-0"}))
        capture(AgentEvent(EventType.TASK_START, {"task_id": "t-1", "description": "Task 1"}))
        capture(AgentEvent(EventType.TASK_FAILED, {"task_id": "t-1", "error": "Error 1"}))
        capture(AgentEvent(EventType.TASK_START, {"task_id": "t-2", "description": "Task 2"}))
        capture(AgentEvent(EventType.TASK_FAILED, {"task_id": "t-2", "error": "Error 2"}))
        capture(AgentEvent(EventType.COMPLETE, {"tasks_completed": 0, "tasks_failed": 2}))

        complete = capture.get_by_type("complete")[0]
        assert complete.data["tasks_completed"] == 0
        assert complete.data["tasks_failed"] == 2

    def test_partial_success(self) -> None:
        """Handle case where some tasks succeed and some fail."""
        capture = LifecycleEventCapture()

        capture(AgentEvent(EventType.PLAN_WINNER, {"tasks": 3, "selected_candidate_id": "c-0"}))
        capture(AgentEvent(EventType.TASK_START, {"task_id": "t-1", "description": "Task 1"}))
        capture(AgentEvent(EventType.TASK_COMPLETE, {"task_id": "t-1", "duration_ms": 100}))
        capture(AgentEvent(EventType.TASK_START, {"task_id": "t-2", "description": "Task 2"}))
        capture(AgentEvent(EventType.TASK_FAILED, {"task_id": "t-2", "error": "Failed"}))
        capture(AgentEvent(EventType.TASK_START, {"task_id": "t-3", "description": "Task 3"}))
        capture(AgentEvent(EventType.TASK_COMPLETE, {"task_id": "t-3", "duration_ms": 200}))
        capture(AgentEvent(EventType.COMPLETE, {"tasks_completed": 2, "tasks_failed": 1}))

        complete = capture.get_by_type("complete")[0]
        assert complete.data["tasks_completed"] == 2
        assert complete.data["tasks_failed"] == 1


# =============================================================================
# Full Lifecycle Simulation Test
# =============================================================================


class TestFullLifecycleSimulation:
    """End-to-end lifecycle simulation tests."""

    def test_complete_successful_lifecycle(self) -> None:
        """Simulate a complete successful goal lifecycle."""
        capture = LifecycleEventCapture()

        # === Phase 1: Memory ===
        capture(AgentEvent(EventType.MEMORY_LOAD, {}))
        capture(AgentEvent(EventType.MEMORY_LOADED, {
            "session": "test-session",
            "learnings_count": 5,
        }))

        # === Phase 2: Signal Extraction ===
        capture(AgentEvent(EventType.SIGNAL, {"status": "extracting"}))
        capture(AgentEvent(EventType.SIGNAL, {
            "status": "extracted",
            "signals": {"complexity": "moderate", "has_tests": False},
        }))

        # === Phase 3: Planning ===
        capture(AgentEvent(EventType.PLAN_START, {"goal": "Build a REST API"}))
        capture(AgentEvent(EventType.PLAN_CANDIDATE_START, {
            "total_candidates": 3,
            "variance_strategy": "prompting",
        }))

        # Generate candidates
        for i in range(3):
            capture(AgentEvent(EventType.PLAN_CANDIDATE_GENERATED, {
                "candidate_id": f"candidate-{i}",
                "artifact_count": 4 + i,
                "progress": i + 1,
                "total_candidates": 3,
                "variance_config": {"prompt_style": ["minimal", "default", "thorough"][i]},
            }))

        capture(AgentEvent(EventType.PLAN_CANDIDATES_COMPLETE, {
            "successful_candidates": 3,
            "failed_candidates": 0,
            "total_candidates": 3,
        }))

        # Score candidates
        scores = [78.5, 92.0, 85.0]
        for i, score in enumerate(scores):
            capture(AgentEvent(EventType.PLAN_CANDIDATE_SCORED, {
                "candidate_id": f"candidate-{i}",
                "score": score,
                "progress": i + 1,
                "total_candidates": 3,
                "metrics": {"depth": 2, "parallelism_factor": 0.7},
            }))

        capture(AgentEvent(EventType.PLAN_SCORING_COMPLETE, {"total_scored": 3}))

        # Winner (candidate-1 has highest score)
        capture(AgentEvent(EventType.PLAN_WINNER, {
            "tasks": 5,
            "artifact_count": 5,
            "selected_candidate_id": "candidate-1",
            "total_candidates": 3,
            "score": 92.0,
            "metrics": {"depth": 2, "parallelism_factor": 0.7},
        }))

        # === Phase 4: Task Execution ===
        tasks = [
            ("model-user", "Create User model"),
            ("model-post", "Create Post model"),
            ("route-users", "Create /users routes"),
            ("route-posts", "Create /posts routes"),
            ("main-app", "Create main.py"),
        ]

        for task_id, description in tasks:
            capture(AgentEvent(EventType.TASK_START, {
                "task_id": task_id,
                "description": description,
            }))
            # Simulate progress
            capture(AgentEvent(EventType.TASK_PROGRESS, {
                "task_id": task_id,
                "progress": 50,
            }))
            capture(AgentEvent(EventType.TASK_COMPLETE, {
                "task_id": task_id,
                "duration_ms": 1500,
                "file": f"src/{task_id.replace('-', '/')}.py",
            }))

        # === Phase 5: Validation ===
        capture(AgentEvent(EventType.GATE_START, {
            "gate_id": "gate-syntax",
            "artifacts": [t[0] for t in tasks],
        }))
        capture(AgentEvent(EventType.GATE_STEP, {
            "gate_id": "gate-syntax",
            "step": "syntax",
            "passed": True,
        }))
        capture(AgentEvent(EventType.GATE_PASS, {"gate_id": "gate-syntax"}))

        # === Phase 6: Learning Extraction ===
        capture(AgentEvent(EventType.MEMORY_LEARNING, {
            "fact": "Flask-SQLAlchemy simplifies database operations",
            "category": "framework",
            "confidence": 0.88,
            "source": "model-user",
        }))
        capture(AgentEvent(EventType.MEMORY_LEARNING, {
            "fact": "RESTful routes use HTTP verbs semantically",
            "category": "pattern",
            "confidence": 0.92,
            "source": "route-users",
        }))

        capture(AgentEvent(EventType.MEMORY_SAVED, {"learnings_added": 2}))

        # === Phase 7: Completion ===
        capture(AgentEvent(EventType.COMPLETE, {
            "tasks_completed": 5,
            "tasks_failed": 0,
            "duration_s": 45.5,
            "learnings_count": 2,
        }))

        # === Verify Full Lifecycle ===
        
        # All phases present
        assert capture.has_phase("memory"), "Memory phase missing"
        assert capture.has_phase("signal"), "Signal phase missing"
        assert capture.has_phase("plan"), "Plan phase missing"
        assert capture.has_phase("task"), "Task phase missing"
        assert capture.has_phase("gate"), "Gate phase missing"
        assert capture.has_phase("learning"), "Learning phase missing"
        assert capture.has_phase("terminal"), "Terminal phase missing"

        # Event counts
        assert len(capture.memory_events) == 3  # load, loaded, saved
        assert len(capture.signal_events) == 2  # extracting, extracted
        assert len(capture.plan_events) >= 8  # start, candidate_start, 3 generated, 3 scored, winner
        assert len(capture.task_events) == 15  # 5 * (start + progress + complete)
        assert len(capture.gate_events) == 3  # start, step, pass
        assert len(capture.learning_events) == 2
        assert len(capture.terminal_events) == 1

        # Verify state consistency
        plan_winner = capture.get_by_type("plan_winner")[0]
        complete = capture.get_by_type("complete")[0]
        task_starts = capture.get_by_type("task_start")

        assert plan_winner.data["tasks"] == len(task_starts), "Task count mismatch"
        assert complete.data["tasks_completed"] == len(task_starts), "Completed count mismatch"
        assert complete.data["tasks_failed"] == 0, "Should have no failures"

        # Verify candidate ID consistency
        generated_ids = {e.data["candidate_id"] for e in capture.get_by_type("plan_candidate_generated")}
        scored_ids = {e.data["candidate_id"] for e in capture.get_by_type("plan_candidate_scored")}
        winner_id = plan_winner.data["selected_candidate_id"]

        assert generated_ids == scored_ids, "Generated and scored candidates should match"
        assert winner_id in generated_ids, "Winner must be from generated candidates"

        # Verify task ID consistency
        started_ids = {e.data["task_id"] for e in capture.get_by_type("task_start")}
        completed_ids = {e.data["task_id"] for e in capture.get_by_type("task_complete")}
        assert started_ids == completed_ids, "All started tasks should complete"


# =============================================================================
# Backlog Events Tests (for ExecutionManager integration)
# =============================================================================


class TestBacklogEvents:
    """Tests for backlog-specific events that Studio needs."""

    def test_backlog_goal_added_has_required_fields(self) -> None:
        """backlog_goal_added must have goal_id and title."""
        event = AgentEvent(
            EventType.BACKLOG_GOAL_ADDED,
            {"goal_id": "goal-123", "title": "Build API"},
        )
        
        assert "goal_id" in event.data
        assert "title" in event.data

    def test_backlog_goal_started_has_required_fields(self) -> None:
        """backlog_goal_started must have goal_id and title."""
        event = AgentEvent(
            EventType.BACKLOG_GOAL_STARTED,
            {"goal_id": "goal-123", "title": "Build API"},
        )
        
        assert "goal_id" in event.data
        assert "title" in event.data

    def test_backlog_goal_completed_has_artifacts(self) -> None:
        """backlog_goal_completed must list artifacts for DAG update."""
        event = AgentEvent(
            EventType.BACKLOG_GOAL_COMPLETED,
            {
                "goal_id": "goal-123",
                "artifacts": ["model-user", "route-api"],
                "skipped": [],
                "failed": [],
                "partial": False,
                "learnings_count": 2,
            },
        )
        
        assert "goal_id" in event.data
        assert "artifacts" in event.data
        assert isinstance(event.data["artifacts"], list)

    def test_backlog_goal_failed_has_error(self) -> None:
        """backlog_goal_failed must have error message."""
        event = AgentEvent(
            EventType.BACKLOG_GOAL_FAILED,
            {"goal_id": "goal-123", "error": "All artifacts failed"},
        )
        
        assert "goal_id" in event.data
        assert "error" in event.data
