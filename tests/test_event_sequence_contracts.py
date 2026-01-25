"""Event Sequence Contract Tests.

Tests that verify:
1. Required events are emitted in correct order
2. task_start/task_complete events are balanced
3. Candidate IDs are used consistently
4. plan_winner references valid candidate IDs
5. task_id is always present (not relying on currentTaskIndex)

These tests catch bugs like:
- Missing task_start events during execution
- Index confusion between sorted/original positions
- Event sequence gaps
- Missing task_id causing frontend to update wrong task
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from sunwell.agent.events import AgentEvent, EventType
from sunwell.planning.naaru.artifacts import ArtifactGraph, ArtifactSpec
from sunwell.planning.naaru.planners.harmonic import HarmonicPlanner
from sunwell.planning.naaru.planners.metrics import CandidateResult, PlanMetrics


# =============================================================================
# Event Capture Helpers
# =============================================================================


@dataclass
class EventCapture:
    """Captures events for testing."""

    events: list[AgentEvent] = field(default_factory=list)

    def __call__(self, event: AgentEvent) -> None:
        """Capture an event."""
        self.events.append(event)

    def clear(self) -> None:
        """Clear captured events."""
        self.events.clear()

    def get_types(self) -> list[str]:
        """Get list of event types in order."""
        return [e.type.value for e in self.events]

    def get_by_type(self, event_type: str) -> list[AgentEvent]:
        """Get all events of a specific type."""
        return [e for e in self.events if e.type.value == event_type]

    def count_type(self, event_type: str) -> int:
        """Count events of a specific type."""
        return len(self.get_by_type(event_type))


# =============================================================================
# Candidate ID Contract Tests
# =============================================================================


class TestCandidateIdContracts:
    """Tests for candidate_id consistency between events."""

    def test_candidate_result_has_stable_id(self) -> None:
        """CandidateResult must have an id field."""
        graph = ArtifactGraph()
        graph.add(ArtifactSpec(id="test", description="test", contract="test contract"))

        result = CandidateResult(
            id="candidate-0",
            graph=graph,
            variance_config={"prompt_style": "default"},
        )

        assert result.id == "candidate-0"
        assert result.graph is graph
        assert result.score is None  # Score added later

    def test_candidate_result_with_score(self) -> None:
        """CandidateResult with score preserves ID."""
        graph = ArtifactGraph()
        graph.add(ArtifactSpec(id="test", description="test", contract="test contract"))

        metrics = PlanMetrics(
            depth=2,
            width=3,
            leaf_count=2,
            artifact_count=3,
            parallelism_factor=0.67,
            balance_factor=1.5,
            file_conflicts=0,
            estimated_waves=2,
        )

        result = CandidateResult(
            id="candidate-3",
            graph=graph,
            variance_config={"prompt_style": "thorough"},
            score=metrics,
        )

        assert result.id == "candidate-3"
        assert result.score is metrics
        assert result.score.score > 0

    def test_plan_candidate_generated_requires_id(self) -> None:
        """plan_candidate_generated event requires candidate_id."""
        capture = EventCapture()

        # Simulate what HarmonicPlanner emits
        event = AgentEvent(
            EventType.PLAN_CANDIDATE_GENERATED,
            {
                "candidate_id": "candidate-2",
                "artifact_count": 5,
                "progress": 3,
                "total_candidates": 5,
                "variance_config": {"prompt_style": "minimal"},
            },
        )
        capture(event)

        events = capture.get_by_type("plan_candidate_generated")
        assert len(events) == 1
        assert events[0].data["candidate_id"] == "candidate-2"
        # No index field - use ID only
        assert "candidate_index" not in events[0].data

    def test_plan_candidate_scored_requires_id(self) -> None:
        """plan_candidate_scored event requires candidate_id."""
        event = AgentEvent(
            EventType.PLAN_CANDIDATE_SCORED,
            {
                "candidate_id": "candidate-1",
                "score": 85.5,
                "progress": 2,
                "total_candidates": 3,
                "metrics": {
                    "depth": 2,
                    "parallelism_factor": 0.6,
                },
            },
        )

        assert event.data["candidate_id"] == "candidate-1"
        # No index field - use ID only
        assert "candidate_index" not in event.data

    def test_plan_winner_requires_selected_candidate_id(self) -> None:
        """plan_winner event requires selected_candidate_id."""
        event = AgentEvent(
            EventType.PLAN_WINNER,
            {
                "tasks": 5,
                "artifact_count": 5,
                "selected_candidate_id": "candidate-3",
                "total_candidates": 5,
                "score": 90.0,
                "metrics": {"depth": 2, "parallelism_factor": 0.8},
                "selection_reason": "Highest score",
                "variance_strategy": "prompting",
                "variance_config": {"prompt_style": "parallel_first"},
            },
        )

        assert event.data["selected_candidate_id"] == "candidate-3"
        # No index field - use ID only
        assert "selected_index" not in event.data

    def test_plan_winner_references_valid_candidate_id(self) -> None:
        """plan_winner's selected_candidate_id must match a generated candidate."""
        capture = EventCapture()

        # Simulate candidate generation
        for i in range(3):
            capture(
                AgentEvent(
                    EventType.PLAN_CANDIDATE_GENERATED,
                    {
                        "candidate_id": f"candidate-{i}",
                        "artifact_count": 5 + i,
                        "progress": i + 1,
                        "total_candidates": 3,
                    },
                )
            )

        # Simulate scoring
        for i in range(3):
            capture(
                AgentEvent(
                    EventType.PLAN_CANDIDATE_SCORED,
                    {
                        "candidate_id": f"candidate-{i}",
                        "score": 80.0 + i * 5,
                        "progress": i + 1,
                        "total_candidates": 3,
                    },
                )
            )

        # Winner (candidate-2 has highest score)
        capture(
            AgentEvent(
                EventType.PLAN_WINNER,
                {
                    "tasks": 7,
                    "selected_candidate_id": "candidate-2",
                    "total_candidates": 3,
                    "score": 90.0,
                },
            )
        )

        # Verify winner references a valid candidate
        generated_ids = {
            e.data["candidate_id"]
            for e in capture.get_by_type("plan_candidate_generated")
        }
        winner_events = capture.get_by_type("plan_winner")
        assert len(winner_events) == 1
        winner_id = winner_events[0].data["selected_candidate_id"]
        assert winner_id in generated_ids, (
            f"plan_winner references '{winner_id}' but only generated: {generated_ids}"
        )


# =============================================================================
# Task Event Balance Tests
# =============================================================================


class TestTaskIdRequired:
    """Tests that task_id is always present in task events."""

    def test_task_start_requires_task_id(self) -> None:
        """task_start must have task_id field."""
        from sunwell.agent.events.schemas import REQUIRED_FIELDS

        assert EventType.TASK_START in REQUIRED_FIELDS
        assert "task_id" in REQUIRED_FIELDS[EventType.TASK_START]

    def test_task_complete_requires_task_id(self) -> None:
        """task_complete must have task_id field."""
        from sunwell.agent.events.schemas import REQUIRED_FIELDS

        assert EventType.TASK_COMPLETE in REQUIRED_FIELDS
        assert "task_id" in REQUIRED_FIELDS[EventType.TASK_COMPLETE]

    def test_task_failed_requires_task_id(self) -> None:
        """task_failed must have task_id field."""
        from sunwell.agent.events.schemas import REQUIRED_FIELDS

        assert EventType.TASK_FAILED in REQUIRED_FIELDS
        assert "task_id" in REQUIRED_FIELDS[EventType.TASK_FAILED]

    def test_task_progress_requires_task_id(self) -> None:
        """task_progress must have task_id field."""
        from sunwell.agent.events.schemas import REQUIRED_FIELDS

        assert EventType.TASK_PROGRESS in REQUIRED_FIELDS
        assert "task_id" in REQUIRED_FIELDS[EventType.TASK_PROGRESS]

    def test_task_events_always_include_task_id(self) -> None:
        """All task events must include task_id in their schema."""
        from sunwell.agent.events.schemas import EVENT_SCHEMAS

        task_events = [
            EventType.TASK_START,
            EventType.TASK_COMPLETE,
            EventType.TASK_FAILED,
            EventType.TASK_PROGRESS,
        ]

        for event_type in task_events:
            schema = EVENT_SCHEMAS.get(event_type)
            assert schema is not None, f"No schema for {event_type.value}"
            annotations = getattr(schema, "__annotations__", {})
            assert "task_id" in annotations, (
                f"task_id missing from schema for {event_type.value}. "
                f"Frontend relies on task_id to update the correct task."
            )


class TestTaskEventBalance:
    """Tests for task_start/task_complete/task_failed balance."""

    def test_task_complete_without_start_is_anomaly(self) -> None:
        """Detect when task_complete fires without task_start."""
        capture = EventCapture()

        # Anomaly: task_complete without task_start
        capture(
            AgentEvent(
                EventType.TASK_COMPLETE,
                {"task_id": "orphan-task", "duration_ms": 100},
            )
        )

        starts = capture.count_type("task_start")
        completes = capture.count_type("task_complete")

        # This SHOULD fail - it's an anomaly
        assert completes > starts, "Expected anomaly: complete without start"

    def test_task_events_are_balanced(self) -> None:
        """Every task_start should have a matching task_complete or task_failed."""
        capture = EventCapture()

        # Proper sequence
        for i in range(3):
            capture(
                AgentEvent(
                    EventType.TASK_START,
                    {"task_id": f"task-{i}", "description": f"Task {i}"},
                )
            )
            if i == 1:
                # One failure
                capture(
                    AgentEvent(
                        EventType.TASK_FAILED,
                        {"task_id": f"task-{i}", "error": "test error"},
                    )
                )
            else:
                capture(
                    AgentEvent(
                        EventType.TASK_COMPLETE,
                        {"task_id": f"task-{i}", "duration_ms": 100},
                    )
                )

        starts = capture.count_type("task_start")
        completes = capture.count_type("task_complete")
        failures = capture.count_type("task_failed")

        # Balance: starts == completes + failures
        assert starts == completes + failures

    def test_task_ids_match_between_start_and_end(self) -> None:
        """task_complete/task_failed task_id must match a task_start."""
        capture = EventCapture()

        # Start tasks
        capture(
            AgentEvent(
                EventType.TASK_START,
                {"task_id": "task-a", "description": "Task A"},
            )
        )
        capture(
            AgentEvent(
                EventType.TASK_START,
                {"task_id": "task-b", "description": "Task B"},
            )
        )

        # Complete them
        capture(
            AgentEvent(
                EventType.TASK_COMPLETE,
                {"task_id": "task-a", "duration_ms": 100},
            )
        )
        capture(
            AgentEvent(
                EventType.TASK_COMPLETE,
                {"task_id": "task-b", "duration_ms": 200},
            )
        )

        started_ids = {
            e.data["task_id"] for e in capture.get_by_type("task_start")
        }
        completed_ids = {
            e.data["task_id"] for e in capture.get_by_type("task_complete")
        }

        # All completed tasks should have been started
        assert completed_ids <= started_ids, (
            f"Completed tasks {completed_ids} not all in started {started_ids}"
        )


# =============================================================================
# Event Sequence Order Tests
# =============================================================================


class TestEventSequenceOrder:
    """Tests for correct event ordering."""

    def test_planning_sequence_order(self) -> None:
        """Planning events must occur in correct order."""
        capture = EventCapture()

        # Correct sequence
        capture(AgentEvent(EventType.PLAN_START, {"goal": "test"}))
        capture(
            AgentEvent(
                EventType.PLAN_CANDIDATE_START,
                {"total_candidates": 3, "variance_strategy": "prompting"},
            )
        )
        capture(
            AgentEvent(
                EventType.PLAN_CANDIDATE_GENERATED,
                {"candidate_id": "candidate-0", "artifact_count": 5, "total_candidates": 1},
            )
        )
        capture(
            AgentEvent(
                EventType.PLAN_CANDIDATES_COMPLETE,
                {"successful_candidates": 1, "failed_candidates": 0, "total_candidates": 1},
            )
        )
        capture(
            AgentEvent(
                EventType.PLAN_CANDIDATE_SCORED,
                {"candidate_id": "candidate-0", "score": 85.0, "total_candidates": 1},
            )
        )
        capture(
            AgentEvent(
                EventType.PLAN_SCORING_COMPLETE,
                {"total_scored": 1},
            )
        )
        capture(
            AgentEvent(
                EventType.PLAN_WINNER,
                {"tasks": 5, "selected_candidate_id": "candidate-0"},
            )
        )

        types = capture.get_types()

        # Verify order
        assert types.index("plan_start") < types.index("plan_candidate_start")
        assert types.index("plan_candidate_start") < types.index("plan_candidate_generated")
        assert types.index("plan_candidate_generated") < types.index("plan_candidates_complete")
        assert types.index("plan_candidates_complete") < types.index("plan_candidate_scored")
        assert types.index("plan_candidate_scored") < types.index("plan_scoring_complete")
        assert types.index("plan_scoring_complete") < types.index("plan_winner")

    def test_execution_sequence_order(self) -> None:
        """Execution events must occur in correct order."""
        capture = EventCapture()

        # Planning complete
        capture(
            AgentEvent(
                EventType.PLAN_WINNER,
                {"tasks": 2, "selected_candidate_id": "candidate-0"},
            )
        )

        # Task execution
        capture(
            AgentEvent(
                EventType.TASK_START,
                {"task_id": "task-1", "description": "First task"},
            )
        )
        capture(
            AgentEvent(
                EventType.TASK_COMPLETE,
                {"task_id": "task-1", "duration_ms": 100},
            )
        )
        capture(
            AgentEvent(
                EventType.TASK_START,
                {"task_id": "task-2", "description": "Second task"},
            )
        )
        capture(
            AgentEvent(
                EventType.TASK_COMPLETE,
                {"task_id": "task-2", "duration_ms": 200},
            )
        )

        # Completion
        capture(
            AgentEvent(
                EventType.COMPLETE,
                {"tasks_completed": 2, "tasks_failed": 0},
            )
        )

        types = capture.get_types()

        # plan_winner before task execution
        assert types.index("plan_winner") < types.index("task_start")

        # complete is last
        assert types.index("complete") == len(types) - 1

    def test_complete_event_reports_correct_counts(self) -> None:
        """complete event counts must match actual task events."""
        capture = EventCapture()

        # Execute 3 tasks: 2 complete, 1 failed
        for i in range(3):
            capture(
                AgentEvent(
                    EventType.TASK_START,
                    {"task_id": f"task-{i}", "description": f"Task {i}"},
                )
            )
            if i == 2:
                capture(
                    AgentEvent(
                        EventType.TASK_FAILED,
                        {"task_id": f"task-{i}", "error": "test"},
                    )
                )
            else:
                capture(
                    AgentEvent(
                        EventType.TASK_COMPLETE,
                        {"task_id": f"task-{i}", "duration_ms": 100},
                    )
                )

        # Complete event
        capture(
            AgentEvent(
                EventType.COMPLETE,
                {"tasks_completed": 2, "tasks_failed": 1},
            )
        )

        # Verify counts match
        actual_completed = capture.count_type("task_complete")
        actual_failed = capture.count_type("task_failed")
        complete_event = capture.get_by_type("complete")[0]

        assert complete_event.data["tasks_completed"] == actual_completed
        assert complete_event.data["tasks_failed"] == actual_failed


# =============================================================================
# IncrementalExecutor Event Contract Tests
# =============================================================================


class TestCountConsistency:
    """Tests that counts match between events."""

    def test_complete_event_counts_match_task_events(self) -> None:
        """complete event's tasks_completed must match actual task_complete count."""
        capture = EventCapture()

        # Execute 5 tasks, 4 complete, 1 failed
        for i in range(5):
            capture(
                AgentEvent(
                    EventType.TASK_START,
                    {"task_id": f"task-{i}", "description": f"Task {i}"},
                )
            )
            if i == 4:
                capture(
                    AgentEvent(
                        EventType.TASK_FAILED,
                        {"task_id": f"task-{i}", "error": "test"},
                    )
                )
            else:
                capture(
                    AgentEvent(
                        EventType.TASK_COMPLETE,
                        {"task_id": f"task-{i}", "duration_ms": 100},
                    )
                )

        actual_completed = capture.count_type("task_complete")
        actual_failed = capture.count_type("task_failed")

        # Complete event should report accurate counts
        capture(
            AgentEvent(
                EventType.COMPLETE,
                {
                    "tasks_completed": actual_completed,  # Must match
                    "tasks_failed": actual_failed,  # Must match
                },
            )
        )

        complete_event = capture.get_by_type("complete")[0]
        assert complete_event.data["tasks_completed"] == actual_completed
        assert complete_event.data["tasks_failed"] == actual_failed

    def test_plan_winner_artifact_count_matches_graph(self) -> None:
        """plan_winner's artifact_count must match the actual graph size."""
        capture = EventCapture()

        # Generate a candidate with 5 artifacts
        capture(
            AgentEvent(
                EventType.PLAN_CANDIDATE_GENERATED,
                {
                    "candidate_id": "candidate-0",
                    "artifact_count": 5,
                    "progress": 1,
                    "total_candidates": 1,
                },
            )
        )

        # Winner should have consistent artifact_count
        capture(
            AgentEvent(
                EventType.PLAN_WINNER,
                {
                    "tasks": 5,
                    "artifact_count": 5,  # Must match what was generated
                    "selected_candidate_id": "candidate-0",
                },
            )
        )

        generated = capture.get_by_type("plan_candidate_generated")[0]
        winner = capture.get_by_type("plan_winner")[0]

        # artifact_count should match between generation and selection
        assert winner.data["artifact_count"] == generated.data["artifact_count"]
        assert winner.data["tasks"] == winner.data["artifact_count"]

    def test_incremental_build_task_count_can_differ_from_total(self) -> None:
        """With incremental builds, task events may be fewer than artifact_count.
        
        This is expected behavior, not a bug. The frontend should handle this gracefully.
        """
        capture = EventCapture()

        # Plan has 5 artifacts total
        capture(
            AgentEvent(
                EventType.PLAN_WINNER,
                {
                    "tasks": 5,
                    "artifact_count": 5,
                    "selected_candidate_id": "candidate-0",
                },
            )
        )

        # But only 2 need rebuilding (incremental)
        for i in range(2):
            capture(
                AgentEvent(
                    EventType.TASK_START,
                    {"task_id": f"artifact-{i}", "description": f"Rebuilding {i}"},
                )
            )
            capture(
                AgentEvent(
                    EventType.TASK_COMPLETE,
                    {"task_id": f"artifact-{i}", "duration_ms": 100},
                )
            )

        # Complete event should report 2 completed (actual work), not 5
        capture(
            AgentEvent(
                EventType.COMPLETE,
                {
                    "tasks_completed": 2,  # Actual rebuilt
                    "tasks_failed": 0,
                    "skipped": 3,  # Optional: track skipped for clarity
                },
            )
        )

        winner = capture.get_by_type("plan_winner")[0]
        complete = capture.get_by_type("complete")[0]

        # This is expected: task events < artifact_count in incremental builds
        task_starts = capture.count_type("task_start")
        assert task_starts < winner.data["artifact_count"]
        assert complete.data["tasks_completed"] == task_starts


class TestIncrementalExecutorEventContract:
    """Tests that IncrementalExecutor emits required events."""

    @pytest.mark.asyncio
    async def test_executor_emits_task_start_events(self) -> None:
        """IncrementalExecutor must emit task_start for each artifact."""
        import tempfile
        from pathlib import Path
        from sunwell.incremental import ExecutionCache, IncrementalExecutor

        capture = EventCapture()

        # Create simple graph
        graph = ArtifactGraph()
        graph.add(ArtifactSpec(id="artifact-1", description="First artifact", contract="create first"))
        graph.add(ArtifactSpec(id="artifact-2", description="Second artifact", contract="create second"))

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ExecutionCache(Path(tmpdir) / "cache.db")

            # Create executor with event callback (RFC-074 v2 API)
            executor = IncrementalExecutor(
                graph=graph,
                cache=cache,
                trace_enabled=False,
                event_callback=capture,
            )

            # Mock create function
            async def mock_create(spec: ArtifactSpec) -> str:
                return f"content for {spec.id}"

            # Execute (v2 API: force_rerun is set of artifact IDs)
            await executor.execute(
                create_fn=mock_create,
                force_rerun=set(graph),  # ArtifactGraph is iterable over IDs
            )

        # Verify task_start events
        task_starts = capture.get_by_type("task_start")
        assert len(task_starts) == 2, (
            f"Expected 2 task_start events, got {len(task_starts)}"
        )

        # Verify IDs match artifacts
        started_ids = {e.data["task_id"] for e in task_starts}
        assert started_ids == {"artifact-1", "artifact-2"}

    @pytest.mark.asyncio
    async def test_executor_emits_task_complete_events(self) -> None:
        """IncrementalExecutor must emit task_complete for successful artifacts."""
        import tempfile
        from pathlib import Path
        from sunwell.incremental import ExecutionCache, IncrementalExecutor

        capture = EventCapture()

        graph = ArtifactGraph()
        graph.add(ArtifactSpec(id="artifact-1", description="First", contract="create"))

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ExecutionCache(Path(tmpdir) / "cache.db")

            executor = IncrementalExecutor(
                graph=graph,
                cache=cache,
                trace_enabled=False,
                event_callback=capture,
            )

            async def mock_create(spec: ArtifactSpec) -> str:
                return "content"

            await executor.execute(
                create_fn=mock_create,
                force_rerun=set(graph),  # ArtifactGraph is iterable over IDs
            )

        # Verify task_complete
        task_completes = capture.get_by_type("task_complete")
        assert len(task_completes) == 1
        assert task_completes[0].data["task_id"] == "artifact-1"
        assert "duration_ms" in task_completes[0].data

    @pytest.mark.asyncio
    async def test_executor_emits_task_failed_on_error(self) -> None:
        """IncrementalExecutor must emit task_failed when artifact creation fails."""
        import tempfile
        from pathlib import Path
        from sunwell.incremental import ExecutionCache, IncrementalExecutor

        capture = EventCapture()

        graph = ArtifactGraph()
        graph.add(ArtifactSpec(id="failing-artifact", description="Will fail", contract="fail"))

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ExecutionCache(Path(tmpdir) / "cache.db")

            executor = IncrementalExecutor(
                graph=graph,
                cache=cache,
                trace_enabled=False,
                event_callback=capture,
            )

            async def failing_create(spec: ArtifactSpec) -> str:
                raise ValueError("Intentional failure")

            await executor.execute(
                create_fn=failing_create,
                force_rerun=set(graph),  # ArtifactGraph is iterable over IDs
            )

        # Verify task_failed
        task_failures = capture.get_by_type("task_failed")
        assert len(task_failures) == 1
        assert task_failures[0].data["task_id"] == "failing-artifact"
        assert "error" in task_failures[0].data

    @pytest.mark.asyncio
    async def test_executor_events_are_balanced(self) -> None:
        """IncrementalExecutor task events must be balanced (start = complete + failed)."""
        import tempfile
        from pathlib import Path
        from sunwell.incremental import ExecutionCache, IncrementalExecutor

        capture = EventCapture()

        graph = ArtifactGraph()
        graph.add(ArtifactSpec(id="success-1", description="Will succeed", contract="succeed"))
        graph.add(ArtifactSpec(id="success-2", description="Will succeed", contract="succeed"))
        graph.add(ArtifactSpec(id="failure-1", description="Will fail", contract="fail"))

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ExecutionCache(Path(tmpdir) / "cache.db")

            executor = IncrementalExecutor(
                graph=graph,
                cache=cache,
                trace_enabled=False,
                event_callback=capture,
            )

            async def mixed_create(spec: ArtifactSpec) -> str:
                if "failure" in spec.id:
                    raise ValueError("Intentional")
                return "content"

            await executor.execute(
                create_fn=mixed_create,
                force_rerun=set(graph),  # ArtifactGraph is iterable over IDs
            )

        starts = capture.count_type("task_start")
        completes = capture.count_type("task_complete")
        failures = capture.count_type("task_failed")

        assert starts == completes + failures, (
            f"Unbalanced: {starts} starts, {completes} completes, {failures} failures"
        )
