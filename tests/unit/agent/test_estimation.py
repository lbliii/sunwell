"""Tests for plan-based duration estimation (RFC: Plan-Based Duration Estimation).

Tests cover:
- DurationEstimate creation and fields
- estimate_from_plan() with various task graphs
- PlanProfile creation and similarity scoring
- ExecutionHistory loading, recording, and calibration
- Integration with TaskGraph and PlanMetrics
"""

import json
import tempfile
from pathlib import Path

import pytest

from sunwell.agent.core.task_graph import TaskGraph
from sunwell.agent.estimation import (
    DurationEstimate,
    ExecutionHistory,
    HistorySample,
    PlanProfile,
    estimate_from_plan,
    format_duration,
)
from sunwell.planning.naaru.planners.metrics import PlanMetrics
from sunwell.planning.naaru.types import Task, TaskMode


# ═══════════════════════════════════════════════════════════════════════════════
# Duration Estimation Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestDurationEstimate:
    """Tests for DurationEstimate dataclass."""

    def test_basic_fields(self) -> None:
        """DurationEstimate has all required fields."""
        estimate = DurationEstimate(
            seconds=300,
            confidence_low=210,
            confidence_high=450,
            task_count=5,
            task_summary="5 tasks across 3 files",
        )

        assert estimate.seconds == 300
        assert estimate.confidence_low == 210
        assert estimate.confidence_high == 450
        assert estimate.task_count == 5
        assert estimate.task_summary == "5 tasks across 3 files"

    def test_immutable(self) -> None:
        """DurationEstimate is frozen (immutable)."""
        estimate = DurationEstimate(
            seconds=100,
            confidence_low=70,
            confidence_high=150,
            task_count=2,
            task_summary="2 tasks",
        )

        with pytest.raises(AttributeError):
            estimate.seconds = 200  # type: ignore


class TestEstimateFromPlan:
    """Tests for estimate_from_plan() function."""

    def test_empty_task_graph(self) -> None:
        """Empty task graph returns zero estimate."""
        task_graph = TaskGraph()
        metrics = PlanMetrics(
            depth=1,
            width=0,
            leaf_count=0,
            artifact_count=0,
            parallelism_factor=0.0,
            balance_factor=0.0,
            file_conflicts=0,
            estimated_waves=1,
        )

        estimate = estimate_from_plan(task_graph, metrics)

        assert estimate.seconds == 0
        assert estimate.task_count == 0
        assert estimate.task_summary == "No tasks"

    def test_single_task_medium_effort(self) -> None:
        """Single medium-effort task estimate."""
        task = Task(
            id="task-1",
            description="Create user model",
            mode=TaskMode.GENERATE,
            estimated_effort="medium",
        )
        task_graph = TaskGraph(tasks=[task])
        metrics = PlanMetrics(
            depth=1,
            width=1,
            leaf_count=1,
            artifact_count=1,
            parallelism_factor=1.0,
            balance_factor=1.0,
            file_conflicts=0,
            estimated_waves=1,
        )

        estimate = estimate_from_plan(task_graph, metrics)

        # medium (60s) * GENERATE (1.5) = 90s base
        assert estimate.seconds > 0
        assert estimate.task_count == 1
        assert "1 task" in estimate.task_summary

    def test_multiple_tasks_with_files(self) -> None:
        """Multiple tasks with target files."""
        tasks = [
            Task(
                id="task-1",
                description="Create model",
                mode=TaskMode.GENERATE,
                estimated_effort="medium",
                target_path="src/models/user.py",
            ),
            Task(
                id="task-2",
                description="Create API endpoint",
                mode=TaskMode.GENERATE,
                estimated_effort="large",
                target_path="src/api/users.py",
            ),
            Task(
                id="task-3",
                description="Add tests",
                mode=TaskMode.GENERATE,
                estimated_effort="small",
                target_path="tests/test_users.py",
            ),
        ]
        task_graph = TaskGraph(tasks=tasks)
        metrics = PlanMetrics(
            depth=2,
            width=2,
            leaf_count=2,
            artifact_count=3,
            parallelism_factor=0.67,
            balance_factor=1.0,
            file_conflicts=0,
            estimated_waves=2,
        )

        estimate = estimate_from_plan(task_graph, metrics)

        assert estimate.seconds > 0
        assert estimate.task_count == 3
        assert "3 tasks" in estimate.task_summary
        assert "3 files" in estimate.task_summary

    def test_effort_levels(self) -> None:
        """Different effort levels produce different estimates."""
        metrics = PlanMetrics(
            depth=1, width=1, leaf_count=1, artifact_count=1,
            parallelism_factor=1.0, balance_factor=1.0,
            file_conflicts=0, estimated_waves=1,
        )

        trivial_task = Task(
            id="t", description="x", mode=TaskMode.MODIFY, estimated_effort="trivial"
        )
        large_task = Task(
            id="t", description="x", mode=TaskMode.MODIFY, estimated_effort="large"
        )

        trivial_estimate = estimate_from_plan(TaskGraph(tasks=[trivial_task]), metrics)
        large_estimate = estimate_from_plan(TaskGraph(tasks=[large_task]), metrics)

        # Large tasks should take longer than trivial
        assert large_estimate.seconds > trivial_estimate.seconds

    def test_mode_factors(self) -> None:
        """Different task modes have different time factors."""
        metrics = PlanMetrics(
            depth=1, width=1, leaf_count=1, artifact_count=1,
            parallelism_factor=1.0, balance_factor=1.0,
            file_conflicts=0, estimated_waves=1,
        )

        execute_task = Task(
            id="t", description="x", mode=TaskMode.EXECUTE, estimated_effort="medium"
        )
        research_task = Task(
            id="t", description="x", mode=TaskMode.RESEARCH, estimated_effort="medium"
        )

        execute_estimate = estimate_from_plan(TaskGraph(tasks=[execute_task]), metrics)
        research_estimate = estimate_from_plan(TaskGraph(tasks=[research_task]), metrics)

        # Research (2.0x) should take longer than Execute (0.5x)
        assert research_estimate.seconds > execute_estimate.seconds


class TestFormatDuration:
    """Tests for format_duration() helper."""

    def test_seconds_only(self) -> None:
        """Durations under 60 seconds."""
        assert format_duration(0) == "0s"
        assert format_duration(15) == "15s"
        assert format_duration(59) == "59s"

    def test_minutes_only(self) -> None:
        """Even minutes."""
        assert format_duration(60) == "1m"
        assert format_duration(120) == "2m"
        assert format_duration(300) == "5m"

    def test_minutes_and_seconds(self) -> None:
        """Minutes with remaining seconds."""
        assert format_duration(90) == "1m 30s"
        assert format_duration(135) == "2m 15s"

    def test_hours(self) -> None:
        """Durations in hours."""
        assert format_duration(3600) == "1h"
        assert format_duration(3660) == "1h 1m"
        assert format_duration(7200) == "2h"


# ═══════════════════════════════════════════════════════════════════════════════
# Plan Profile Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestPlanProfile:
    """Tests for PlanProfile fingerprinting."""

    def test_from_task_graph(self) -> None:
        """Create profile from task graph and metrics."""
        tasks = [
            Task(
                id="task-1",
                description="Create model",
                mode=TaskMode.GENERATE,
                estimated_effort="medium",
                tools=frozenset(["file_write"]),
            ),
            Task(
                id="task-2",
                description="Modify config",
                mode=TaskMode.MODIFY,
                estimated_effort="small",
                tools=frozenset(["file_write", "file_read"]),
            ),
        ]
        task_graph = TaskGraph(tasks=tasks)
        metrics = PlanMetrics(
            depth=2,
            width=1,
            leaf_count=1,
            artifact_count=2,
            parallelism_factor=0.5,
            balance_factor=0.5,
            file_conflicts=0,
            estimated_waves=2,
        )

        profile = PlanProfile.from_task_graph(task_graph, metrics)

        assert profile.task_count == 2
        assert profile.depth == 2
        assert profile.estimated_waves == 2
        assert profile.tool_count == 2  # file_write and file_read

    def test_similarity_identical(self) -> None:
        """Identical profiles have similarity 1.0."""
        profile = PlanProfile(
            task_count=5,
            mode_distribution=(("generate", 3), ("modify", 2)),
            effort_distribution=(("medium", 5),),
            tool_count=3,
            depth=2,
            estimated_waves=2,
        )

        assert profile.similarity_score(profile) == 1.0

    def test_similarity_different(self) -> None:
        """Different profiles have similarity < 1.0."""
        profile1 = PlanProfile(
            task_count=5,
            mode_distribution=(("generate", 5),),
            effort_distribution=(("medium", 5),),
            tool_count=3,
            depth=2,
            estimated_waves=2,
        )
        profile2 = PlanProfile(
            task_count=20,  # Very different
            mode_distribution=(("research", 20),),
            effort_distribution=(("large", 20),),
            tool_count=10,
            depth=5,
            estimated_waves=5,
        )

        similarity = profile1.similarity_score(profile2)
        assert 0.0 <= similarity < 1.0

    def test_serialization_roundtrip(self) -> None:
        """Profile survives serialization roundtrip."""
        profile = PlanProfile(
            task_count=3,
            mode_distribution=(("generate", 2), ("modify", 1)),
            effort_distribution=(("medium", 3),),
            tool_count=2,
            depth=2,
            estimated_waves=2,
        )

        data = profile.to_dict()
        restored = PlanProfile.from_dict(data)

        assert restored.task_count == profile.task_count
        assert restored.mode_distribution == profile.mode_distribution
        assert restored.depth == profile.depth


# ═══════════════════════════════════════════════════════════════════════════════
# Execution History Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestExecutionHistory:
    """Tests for ExecutionHistory tracking."""

    def test_record_sample(self) -> None:
        """Record execution sample."""
        history = ExecutionHistory()
        profile = PlanProfile(
            task_count=5,
            mode_distribution=(("generate", 5),),
            effort_distribution=(("medium", 5),),
            tool_count=2,
            depth=2,
            estimated_waves=2,
        )

        history.record(profile, estimated_seconds=300, actual_seconds=350)

        assert len(history.samples) == 1
        assert history.samples[0].estimated_seconds == 300
        assert history.samples[0].actual_seconds == 350

    def test_calibration_factor_insufficient_samples(self) -> None:
        """Calibration requires minimum samples."""
        history = ExecutionHistory()
        profile = PlanProfile(
            task_count=5,
            mode_distribution=(("generate", 5),),
            effort_distribution=(("medium", 5),),
            tool_count=2,
            depth=2,
            estimated_waves=2,
        )

        # Only 1 sample - below threshold
        history.record(profile, estimated_seconds=300, actual_seconds=350)

        assert history.calibration_factor(profile) is None

    def test_calibration_factor_with_samples(self) -> None:
        """Calibration factor from similar samples."""
        history = ExecutionHistory()
        profile = PlanProfile(
            task_count=5,
            mode_distribution=(("generate", 5),),
            effort_distribution=(("medium", 5),),
            tool_count=2,
            depth=2,
            estimated_waves=2,
        )

        # Add enough samples
        history.record(profile, estimated_seconds=300, actual_seconds=360)  # 1.2x
        history.record(profile, estimated_seconds=300, actual_seconds=330)  # 1.1x
        history.record(profile, estimated_seconds=300, actual_seconds=390)  # 1.3x

        factor = history.calibration_factor(profile)

        assert factor is not None
        # Average of 1.2, 1.1, 1.3 = 1.2
        assert 1.1 <= factor <= 1.3

    def test_disk_persistence(self) -> None:
        """History survives save/load cycle."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            profile = PlanProfile(
                task_count=3,
                mode_distribution=(("generate", 3),),
                effort_distribution=(("medium", 3),),
                tool_count=1,
                depth=1,
                estimated_waves=1,
            )

            # Save
            history1 = ExecutionHistory(_project_path=project_path)
            history1.record(profile, estimated_seconds=100, actual_seconds=120)
            history1.record(profile, estimated_seconds=100, actual_seconds=110)
            saved = history1.save(project_path)
            assert saved == 2

            # Load
            history2 = ExecutionHistory.load(project_path)
            assert len(history2.samples) == 2
            assert history2.samples[0].estimated_seconds == 100

    def test_max_samples_limit(self) -> None:
        """History trims old samples when limit exceeded."""
        history = ExecutionHistory()
        profile = PlanProfile(
            task_count=1,
            mode_distribution=(),
            effort_distribution=(),
            tool_count=0,
            depth=1,
            estimated_waves=1,
        )

        # Record more than MAX_SAMPLES
        for i in range(ExecutionHistory.MAX_SAMPLES + 100):
            history.record(profile, estimated_seconds=100, actual_seconds=100)

        assert len(history.samples) <= ExecutionHistory.MAX_SAMPLES


class TestHistorySample:
    """Tests for HistorySample dataclass."""

    def test_accuracy_ratio(self) -> None:
        """Accuracy ratio calculation."""
        profile = PlanProfile(
            task_count=1,
            mode_distribution=(),
            effort_distribution=(),
            tool_count=0,
            depth=1,
            estimated_waves=1,
        )

        # Under-estimate: actual took longer
        sample1 = HistorySample(
            profile=profile,
            estimated_seconds=100,
            actual_seconds=150,
            timestamp="2026-01-01T00:00:00",
        )
        assert sample1.accuracy_ratio == 1.5

        # Over-estimate: actual was faster
        sample2 = HistorySample(
            profile=profile,
            estimated_seconds=100,
            actual_seconds=50,
            timestamp="2026-01-01T00:00:00",
        )
        assert sample2.accuracy_ratio == 0.5

        # Perfect estimate
        sample3 = HistorySample(
            profile=profile,
            estimated_seconds=100,
            actual_seconds=100,
            timestamp="2026-01-01T00:00:00",
        )
        assert sample3.accuracy_ratio == 1.0
