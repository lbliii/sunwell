"""Duration estimation from plan data (RFC: Plan-Based Duration Estimation).

Provides accurate task duration estimates using:
- Task metadata (estimated_effort, mode, tools)
- Plan metrics (depth, estimated_waves, parallelism_factor)
- Historical calibration from past executions

Example:
    >>> from sunwell.agent.estimation import estimate_from_plan, ExecutionHistory
    >>> history = ExecutionHistory.load(project_path)
    >>> estimate = estimate_from_plan(task_graph, metrics, history)
    >>> print(f"Estimated: {estimate.seconds}s ({estimate.task_summary})")
"""

from sunwell.agent.estimation.duration import (
    DurationEstimate,
    estimate_from_plan,
    format_duration,
)
from sunwell.agent.estimation.history import (
    ExecutionHistory,
    HistorySample,
    PlanProfile,
)

__all__ = [
    "DurationEstimate",
    "estimate_from_plan",
    "format_duration",
    "ExecutionHistory",
    "HistorySample",
    "PlanProfile",
]
