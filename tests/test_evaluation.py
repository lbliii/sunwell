"""Tests for evaluation framework."""

import pytest

from sunwell.models.capability.evaluation import (
    EvaluationLogger,
    ToolCallEvent,
    ToolEvaluationMetrics,
    get_logger,
    get_metrics,
    log_tool_call,
)


class TestToolEvaluationMetrics:
    """Test ToolEvaluationMetrics dataclass."""

    def test_overall_success_rate(self):
        """Should calculate correct success rate."""
        metrics = ToolEvaluationMetrics(
            total_tasks=10,
            successful_tasks=8,
            tool_selection_accuracy=0.9,
            parameter_accuracy=0.85,
            first_attempt_success=0.7,
            avg_tokens_per_task=100.0,
            avg_retries_per_task=0.5,
            repairs_applied=3,
        )
        assert metrics.overall_success_rate == 0.8

    def test_zero_tasks(self):
        """Should handle zero tasks."""
        metrics = ToolEvaluationMetrics(
            total_tasks=0,
            successful_tasks=0,
            tool_selection_accuracy=0.0,
            parameter_accuracy=0.0,
            first_attempt_success=0.0,
            avg_tokens_per_task=0.0,
            avg_retries_per_task=0.0,
            repairs_applied=0,
        )
        assert metrics.overall_success_rate == 0.0


class TestEvaluationLogger:
    """Test EvaluationLogger."""

    def test_log_and_compute(self):
        """Should log events and compute metrics."""
        logger = EvaluationLogger()

        # Log some events
        logger.log_call(
            task_id="task1",
            tool_name="read_file",
            parameters={"path": "test.py"},
            success=True,
            tokens_used=50,
        )
        logger.log_call(
            task_id="task2",
            tool_name="write_file",
            parameters={"path": "out.py"},
            success=False,
            error="Permission denied",
            tokens_used=75,
        )
        logger.log_call(
            task_id="task2",
            tool_name="write_file",
            parameters={"path": "out.py"},
            success=True,
            attempt=2,
            tokens_used=80,
        )

        metrics = logger.compute_metrics()

        assert metrics.total_tasks == 2
        assert metrics.successful_tasks == 2  # Both tasks eventually succeeded
        assert metrics.first_attempt_success == 0.5  # Only task1 succeeded first try

    def test_clear(self):
        """Should clear all events."""
        logger = EvaluationLogger()
        logger.log_call("task1", "test", {}, True)
        logger.clear()

        metrics = logger.compute_metrics()
        assert metrics.total_tasks == 0

    def test_tool_selection_accuracy(self):
        """Should track tool selection accuracy when expected is provided."""
        logger = EvaluationLogger()

        logger.log_call(
            task_id="task1",
            tool_name="read_file",
            parameters={},
            success=True,
            expected_tool="read_file",
        )
        logger.log_call(
            task_id="task2",
            tool_name="write_file",
            parameters={},
            success=True,
            expected_tool="read_file",  # Wrong tool!
        )

        metrics = logger.compute_metrics()
        assert metrics.tool_selection_accuracy == 0.5


class TestGlobalLogger:
    """Test global logger functions."""

    def test_get_logger(self):
        """Should return global logger."""
        logger = get_logger()
        assert isinstance(logger, EvaluationLogger)

    def test_log_tool_call(self):
        """Should log to global logger."""
        get_logger().clear()

        log_tool_call("test_task", "test_tool", {"arg": "value"}, True)

        metrics = get_metrics()
        assert metrics.total_tasks == 1

        # Clean up
        get_logger().clear()


class TestToolCallEvent:
    """Test ToolCallEvent dataclass."""

    def test_immutable(self):
        """ToolCallEvent should be immutable."""
        event = ToolCallEvent(
            task_id="1",
            tool_name="test",
            expected_tool=None,
            parameters={},
            expected_parameters=None,
            success=True,
            error=None,
            attempt=1,
            tokens_used=0,
            repairs=(),
        )
        with pytest.raises(AttributeError):
            event.success = False  # type: ignore
