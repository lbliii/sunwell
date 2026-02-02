"""Plan-based duration estimation (RFC: Plan-Based Duration Estimation).

Estimates task duration from actual plan data rather than heuristics.

Uses:
- Per-task estimated_effort: trivial=10s, small=30s, medium=60s, large=120s
- TaskMode factors: GENERATE=1.5, MODIFY=1.0, EXECUTE=0.5, RESEARCH=2.0
- Plan metrics: depth, parallelism_factor, estimated_waves
- Historical calibration when available
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sunwell.planning.naaru.types import TaskMode

if TYPE_CHECKING:
    from sunwell.agent.core.task_graph import TaskGraph
    from sunwell.agent.estimation.history import ExecutionHistory
    from sunwell.planning.naaru.planners.metrics import PlanMetrics


# Base duration per effort level (seconds)
EFFORT_BASE_SECONDS: dict[str, int] = {
    "trivial": 10,
    "small": 30,
    "medium": 60,
    "large": 120,
}

# Mode multipliers for execution time
MODE_FACTORS: dict[TaskMode, float] = {
    TaskMode.SELF_IMPROVE: 2.0,  # Most complex - modifying agent itself
    TaskMode.GENERATE: 1.5,      # Creating new content
    TaskMode.MODIFY: 1.0,        # Baseline - modifying existing
    TaskMode.EXECUTE: 0.5,       # Running commands is fast
    TaskMode.RESEARCH: 2.0,      # Gathering info takes time
    TaskMode.COMPOSITE: 1.5,     # Multi-step tasks
}


@dataclass(frozen=True, slots=True)
class DurationEstimate:
    """Duration estimate with confidence bounds.

    Attributes:
        seconds: Point estimate in seconds
        confidence_low: Lower bound (P25 from history, or 0.7x estimate)
        confidence_high: Upper bound (P75 from history, or 1.5x estimate)
        task_count: Number of tasks in plan
        task_summary: Human-readable summary, e.g., "12 tasks across 8 files"
    """

    seconds: int
    confidence_low: int
    confidence_high: int
    task_count: int
    task_summary: str


def estimate_from_plan(
    task_graph: TaskGraph,
    metrics: PlanMetrics | None = None,
    history: ExecutionHistory | None = None,
) -> DurationEstimate:
    """Estimate duration from actual plan data.

    Args:
        task_graph: The task graph with all tasks
        metrics: Plan metrics (depth, parallelism, etc.)
        history: Historical execution data for calibration

    Returns:
        DurationEstimate with seconds, confidence range, and summary
    """
    tasks = task_graph.tasks

    if not tasks:
        return DurationEstimate(
            seconds=0,
            confidence_low=0,
            confidence_high=0,
            task_count=0,
            task_summary="No tasks",
        )

    # Calculate base duration from task metadata
    total_seconds = 0.0
    for task in tasks:
        # Base time from estimated_effort
        effort = task.estimated_effort.lower() if task.estimated_effort else "medium"
        base = EFFORT_BASE_SECONDS.get(effort, EFFORT_BASE_SECONDS["medium"])

        # Mode multiplier
        mode_factor = MODE_FACTORS.get(task.mode, 1.0)

        # Tool complexity: more tools = slightly longer
        tool_factor = 1.0 + (len(task.tools) * 0.1) if task.tools else 1.0

        task_seconds = base * mode_factor * tool_factor
        total_seconds += task_seconds

    # Adjust for parallelism using plan metrics
    if metrics is not None:
        # parallelism_factor: higher means more tasks can run in parallel
        # We reduce total time by this factor (capped to not go below depth-based minimum)
        parallelism_factor = max(metrics.parallelism_factor, 0.1)

        # Critical path sets minimum time (depth * average task time)
        avg_task_time = total_seconds / len(tasks) if tasks else 0
        critical_path_min = metrics.depth * avg_task_time * 0.5

        # Adjusted time: total / parallelism, but at least critical path
        adjusted = total_seconds / (1 + parallelism_factor * 0.5)
        total_seconds = max(adjusted, critical_path_min)

    # Apply historical calibration if available
    calibration_factor = 1.0
    confidence_low_factor = 0.7
    confidence_high_factor = 1.5

    if history is not None and metrics is not None:
        from sunwell.agent.estimation.history import PlanProfile

        profile = PlanProfile.from_task_graph(task_graph, metrics)
        cal = history.calibration_factor(profile)
        if cal is not None:
            calibration_factor = cal

        interval = history.confidence_interval(profile)
        if interval is not None:
            low_ratio, high_ratio = interval
            confidence_low_factor = low_ratio
            confidence_high_factor = high_ratio

    estimated_seconds = int(total_seconds * calibration_factor)

    # Build task summary
    task_summary = _build_task_summary(tasks)

    return DurationEstimate(
        seconds=estimated_seconds,
        confidence_low=int(estimated_seconds * confidence_low_factor),
        confidence_high=int(estimated_seconds * confidence_high_factor),
        task_count=len(tasks),
        task_summary=task_summary,
    )


def _build_task_summary(tasks: list) -> str:
    """Build human-readable task summary.

    Examples:
        "12 tasks across 8 files"
        "5 tasks (3 generate, 2 modify)"
        "1 task"
    """
    count = len(tasks)
    if count == 0:
        return "No tasks"
    if count == 1:
        return "1 task"

    # Count unique target files
    files: set[str] = set()
    for task in tasks:
        if task.target_path:
            files.add(task.target_path)
        if task.modifies:
            files.update(task.modifies)

    # Count modes
    mode_counts: dict[TaskMode, int] = {}
    for task in tasks:
        mode_counts[task.mode] = mode_counts.get(task.mode, 0) + 1

    # Build summary
    if files:
        file_count = len(files)
        summary = f"{count} tasks across {file_count} file{'s' if file_count != 1 else ''}"
    else:
        # Show mode breakdown
        mode_parts = []
        for mode in [TaskMode.GENERATE, TaskMode.MODIFY, TaskMode.EXECUTE, TaskMode.RESEARCH]:
            if mode in mode_counts:
                mode_parts.append(f"{mode_counts[mode]} {mode.value}")
        if mode_parts:
            summary = f"{count} tasks ({', '.join(mode_parts[:2])})"
        else:
            summary = f"{count} tasks"

    return summary


def format_duration(seconds: int) -> str:
    """Format seconds as human-readable duration.

    Examples:
        15 -> "15s"
        90 -> "1m 30s"
        3665 -> "1h 1m"
    """
    if seconds < 60:
        return f"{seconds}s"

    minutes = seconds // 60
    remaining_seconds = seconds % 60

    if minutes < 60:
        if remaining_seconds > 0:
            return f"{minutes}m {remaining_seconds}s"
        return f"{minutes}m"

    hours = minutes // 60
    remaining_minutes = minutes % 60

    if remaining_minutes > 0:
        return f"{hours}h {remaining_minutes}m"
    return f"{hours}h"
