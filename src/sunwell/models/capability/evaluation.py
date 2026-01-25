"""Evaluation framework for tool calling effectiveness.

Provides metrics and logging for evaluating tool calling quality.

Research Insight: "Evaluation-driven development" with systematic testing
dramatically improves tool calling effectiveness (Anthropic/MCP best practices).
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class ToolEvaluationMetrics:
    """Metrics for evaluating tool calling effectiveness.

    Attributes:
        total_tasks: Total evaluation tasks attempted.
        successful_tasks: Tasks completed successfully.
        tool_selection_accuracy: Percentage of correct tool selections.
        parameter_accuracy: Percentage of correctly mapped parameters.
        first_attempt_success: Percentage succeeding on first try.
        avg_tokens_per_task: Average tokens used per task.
        avg_retries_per_task: Average retry attempts per task.
        repairs_applied: Total JSON/schema repairs applied.
    """

    total_tasks: int
    successful_tasks: int
    tool_selection_accuracy: float
    parameter_accuracy: float
    first_attempt_success: float
    avg_tokens_per_task: float
    avg_retries_per_task: float
    repairs_applied: int

    @property
    def overall_success_rate(self) -> float:
        """Overall success rate."""
        if self.total_tasks == 0:
            return 0.0
        return self.successful_tasks / self.total_tasks


@dataclass(frozen=True, slots=True)
class ToolCallEvent:
    """Single tool call event for evaluation logging.

    Attributes:
        task_id: Unique identifier for the task.
        tool_name: Name of the tool called.
        expected_tool: Expected tool (if known).
        parameters: Parameters passed to the tool.
        expected_parameters: Expected parameters (if known).
        success: Whether the call succeeded.
        error: Error message if failed.
        attempt: Attempt number (1-indexed).
        tokens_used: Tokens used for this call.
        repairs: Repairs applied during normalization.
        timestamp: When the event occurred.
    """

    task_id: str
    tool_name: str
    expected_tool: str | None
    parameters: dict
    expected_parameters: dict | None
    success: bool
    error: str | None
    attempt: int
    tokens_used: int
    repairs: tuple[str, ...]
    timestamp: datetime = field(default_factory=datetime.now)


class EvaluationLogger:
    """Logger for tool calling evaluation events.

    Collects events and computes metrics.
    """

    def __init__(self) -> None:
        self._events: list[ToolCallEvent] = []

    def log_event(self, event: ToolCallEvent) -> None:
        """Log a tool call event."""
        self._events.append(event)

    def log_call(
        self,
        task_id: str,
        tool_name: str,
        parameters: dict,
        success: bool,
        error: str | None = None,
        attempt: int = 1,
        tokens_used: int = 0,
        repairs: tuple[str, ...] = (),
        expected_tool: str | None = None,
        expected_parameters: dict | None = None,
    ) -> None:
        """Convenience method to log a tool call."""
        event = ToolCallEvent(
            task_id=task_id,
            tool_name=tool_name,
            expected_tool=expected_tool,
            parameters=parameters,
            expected_parameters=expected_parameters,
            success=success,
            error=error,
            attempt=attempt,
            tokens_used=tokens_used,
            repairs=repairs,
        )
        self.log_event(event)

    def compute_metrics(self) -> ToolEvaluationMetrics:
        """Compute evaluation metrics from logged events."""
        if not self._events:
            return ToolEvaluationMetrics(
                total_tasks=0,
                successful_tasks=0,
                tool_selection_accuracy=0.0,
                parameter_accuracy=0.0,
                first_attempt_success=0.0,
                avg_tokens_per_task=0.0,
                avg_retries_per_task=0.0,
                repairs_applied=0,
            )

        # Group events by task
        tasks: dict[str, list[ToolCallEvent]] = {}
        for event in self._events:
            tasks.setdefault(event.task_id, []).append(event)

        total_tasks = len(tasks)
        successful_tasks = 0
        first_attempt_successes = 0
        correct_tool_selections = 0
        correct_parameters = 0
        total_tokens = 0
        total_retries = 0
        total_repairs = 0
        tasks_with_expected = 0

        for task_id, events in tasks.items():
            # Task success = last event was successful
            if events and events[-1].success:
                successful_tasks += 1

            # First attempt success
            if events and events[0].success:
                first_attempt_successes += 1

            # Tool selection accuracy
            for event in events:
                if event.expected_tool is not None:
                    tasks_with_expected += 1
                    if event.tool_name == event.expected_tool:
                        correct_tool_selections += 1
                    if event.expected_parameters is not None:
                        if event.parameters == event.expected_parameters:
                            correct_parameters += 1

            # Tokens and retries
            total_tokens += sum(e.tokens_used for e in events)
            total_retries += len(events) - 1  # First attempt doesn't count as retry
            total_repairs += sum(len(e.repairs) for e in events)

        return ToolEvaluationMetrics(
            total_tasks=total_tasks,
            successful_tasks=successful_tasks,
            tool_selection_accuracy=(
                correct_tool_selections / tasks_with_expected if tasks_with_expected else 0.0
            ),
            parameter_accuracy=(
                correct_parameters / tasks_with_expected if tasks_with_expected else 0.0
            ),
            first_attempt_success=first_attempt_successes / total_tasks if total_tasks else 0.0,
            avg_tokens_per_task=total_tokens / total_tasks if total_tasks else 0.0,
            avg_retries_per_task=total_retries / total_tasks if total_tasks else 0.0,
            repairs_applied=total_repairs,
        )

    def clear(self) -> None:
        """Clear all logged events."""
        self._events.clear()

    @property
    def events(self) -> list[ToolCallEvent]:
        """Get all logged events."""
        return list(self._events)


# Global logger instance for convenience
_global_logger = EvaluationLogger()


def get_logger() -> EvaluationLogger:
    """Get the global evaluation logger."""
    return _global_logger


def log_tool_call(
    task_id: str,
    tool_name: str,
    parameters: dict,
    success: bool,
    **kwargs,
) -> None:
    """Log a tool call to the global logger."""
    _global_logger.log_call(task_id, tool_name, parameters, success, **kwargs)


def get_metrics() -> ToolEvaluationMetrics:
    """Get metrics from the global logger."""
    return _global_logger.compute_metrics()
