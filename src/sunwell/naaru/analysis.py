"""Task graph analysis and visualization utilities (RFC-034).

This module provides utilities for analyzing and visualizing task graphs
with parallelization potential, contract relationships, and resource conflicts.

Example:
    >>> from sunwell.naaru.analysis import visualize_task_graph, analyze_parallelism
    >>>
    >>> diagram = visualize_task_graph(tasks)
    >>> print(diagram)  # Mermaid diagram
    >>>
    >>> analysis = analyze_parallelism(tasks)
    >>> print(f"Potential speedup: {analysis['parallelization_ratio']:.1f}x")
"""


from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sunwell.naaru.types import Task


def visualize_task_graph(tasks: list[Task]) -> str:
    """Generate a Mermaid diagram of the task graph (RFC-034).

    The diagram shows:
    - Tasks grouped by parallel_group (subgraphs)
    - Contract tasks marked with 📜 icon
    - Implementation tasks marked with 🔧 icon
    - Dependency arrows between tasks

    Args:
        tasks: List of Task objects

    Returns:
        Mermaid diagram string

    Example output:
        ```
        graph TD
            subgraph contracts
                1a[📜 Define User protocol]
                1b[📜 Define Auth interface]
            end
            subgraph implementations
                2a[🔧 Implement User model]
                2b[🔧 Implement Auth service]
            end
            1a --> 2a
            1a --> 2b
            1b --> 2b
        ```
    """
    lines = ["graph TD"]

    # Group by parallel_group
    groups: dict[str, list] = defaultdict(list)
    for task in tasks:
        group = task.parallel_group or "ungrouped"
        groups[group].append(task)

    # Create subgraphs for each group
    for group_name, group_tasks in groups.items():
        lines.append(f"    subgraph {group_name}")
        for task in group_tasks:
            icon = "📜" if task.is_contract else "🔧"
            # Truncate description for readability
            desc = task.description[:35]
            if len(task.description) > 35:
                desc += "..."
            # Escape special characters for Mermaid
            desc = desc.replace('"', "'").replace("[", "(").replace("]", ")")
            lines.append(f'        {task.id}["{icon} {desc}"]')
        lines.append("    end")

    # Add edges for dependencies
    for task in tasks:
        for dep in task.depends_on:
            lines.append(f"    {dep} --> {task.id}")

    return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class ParallelismAnalysis:
    """Analysis of parallelization potential for a task graph (RFC-034).

    Attributes:
        total_tasks: Total number of tasks
        contract_tasks: Number of tasks defining interfaces
        implementation_tasks: Number of tasks implementing interfaces
        max_parallel_width: Maximum tasks that can run simultaneously
        critical_path_length: Minimum sequential steps required
        parallelization_ratio: total_tasks / critical_path_length (theoretical speedup)
        phases: Tuple of phases with task counts
        potential_conflicts: Tasks with overlapping modifies sets
    """

    total_tasks: int
    contract_tasks: int
    implementation_tasks: int
    max_parallel_width: int
    critical_path_length: int
    parallelization_ratio: float
    phases: tuple[dict[str, Any], ...]
    potential_conflicts: tuple[tuple[str, str, frozenset[str]], ...]

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "total_tasks": self.total_tasks,
            "contract_tasks": self.contract_tasks,
            "implementation_tasks": self.implementation_tasks,
            "max_parallel_width": self.max_parallel_width,
            "critical_path_length": self.critical_path_length,
            "parallelization_ratio": self.parallelization_ratio,
            "phases": list(self.phases),
            "potential_conflicts": [
                {"task_a": a, "task_b": b, "overlapping_files": list(files)}
                for a, b, files in self.potential_conflicts
            ],
        }


def analyze_parallelism(tasks: list[Task]) -> ParallelismAnalysis:
    """Analyze parallelization potential of a task graph (RFC-034).

    This function computes metrics about how parallelizable the task graph is,
    including the theoretical speedup and any resource conflicts that would
    prevent parallelization.

    Args:
        tasks: List of Task objects

    Returns:
        ParallelismAnalysis with detailed metrics

    Example:
        >>> analysis = analyze_parallelism(tasks)
        >>> print(f"Tasks: {analysis.total_tasks}")
        >>> print(f"Contracts: {analysis.contract_tasks}")
        >>> print(f"Max parallel: {analysis.max_parallel_width}")
        >>> print(f"Speedup: {analysis.parallelization_ratio:.1f}x")
    """
    if not tasks:
        return ParallelismAnalysis(
            total_tasks=0,
            contract_tasks=0,
            implementation_tasks=0,
            max_parallel_width=0,
            critical_path_length=0,
            parallelization_ratio=1.0,
            phases=(),
            potential_conflicts=(),
        )

    # Count task types
    total_tasks = len(tasks)
    contract_tasks = sum(1 for t in tasks if t.is_contract)
    implementation_tasks = total_tasks - contract_tasks

    # Compute critical path length (longest dependency chain)
    task_map = {t.id: t for t in tasks}
    critical_path_length = _compute_critical_path(tasks, task_map)

    # Compute max parallel width (most tasks runnable at once)
    max_parallel_width = _compute_max_parallel_width(tasks, task_map)

    # Compute phases
    phases = tuple(_compute_phases(tasks))

    # Find potential conflicts (convert sets to frozensets for immutability)
    potential_conflicts = tuple(
        (a, b, frozenset(files)) for a, b, files in _find_conflicts(tasks)
    )

    # Compute parallelization ratio
    parallelization_ratio = (
        total_tasks / critical_path_length if critical_path_length > 0 else 1.0
    )

    return ParallelismAnalysis(
        total_tasks=total_tasks,
        contract_tasks=contract_tasks,
        implementation_tasks=implementation_tasks,
        max_parallel_width=max_parallel_width,
        critical_path_length=critical_path_length,
        parallelization_ratio=parallelization_ratio,
        phases=phases,
        potential_conflicts=potential_conflicts,
    )


def _compute_critical_path(tasks: list, task_map: dict) -> int:
    """Compute the critical path length (longest dependency chain)."""
    # Memoized depth computation
    depths: dict[str, int] = {}

    def get_depth(task_id: str) -> int:
        if task_id in depths:
            return depths[task_id]

        task = task_map.get(task_id)
        if task is None:
            return 0

        if not task.depends_on:
            depths[task_id] = 1
        else:
            max_dep_depth = max(get_depth(dep) for dep in task.depends_on)
            depths[task_id] = max_dep_depth + 1

        return depths[task_id]

    # Compute depth for all tasks
    for task in tasks:
        get_depth(task.id)

    return max(depths.values()) if depths else 0


def _compute_max_parallel_width(tasks: list, task_map: dict) -> int:
    """Compute maximum number of tasks that can run in parallel."""
    if not tasks:
        return 0

    # Group tasks by their "level" (all dependencies at previous levels)
    levels: dict[int, list] = defaultdict(list)
    depths: dict[str, int] = {}

    def get_depth(task_id: str) -> int:
        if task_id in depths:
            return depths[task_id]

        task = task_map.get(task_id)
        if task is None:
            return 0

        if not task.depends_on:
            depths[task_id] = 0
        else:
            depths[task_id] = max(get_depth(dep) for dep in task.depends_on) + 1

        return depths[task_id]

    for task in tasks:
        level = get_depth(task.id)
        levels[level].append(task)

    # Find the level with most tasks
    return max(len(level_tasks) for level_tasks in levels.values()) if levels else 0


def _compute_phases(tasks: list) -> list[dict[str, Any]]:
    """Compute phases based on parallel_group annotations."""
    groups: dict[str, list] = defaultdict(list)

    for task in tasks:
        group = task.parallel_group or "ungrouped"
        groups[group].append(task)

    phases = []
    for name, group_tasks in groups.items():
        # Check if all tasks in the group can run in parallel (no file conflicts)
        all_modifies: set[str] = set()
        has_conflict = False
        for task in group_tasks:
            if task.modifies & all_modifies:
                has_conflict = True
                break
            all_modifies.update(task.modifies)

        phases.append({
            "name": name,
            "tasks": len(group_tasks),
            "parallel": not has_conflict,
            "contract_count": sum(1 for t in group_tasks if t.is_contract),
        })

    return phases


def _find_conflicts(tasks: list) -> list[tuple[str, str, set[str]]]:
    """Find pairs of tasks with overlapping modifies sets."""
    conflicts = []

    for i, task_a in enumerate(tasks):
        for task_b in tasks[i + 1:]:
            overlap = task_a.modifies & task_b.modifies
            if overlap:
                conflicts.append((task_a.id, task_b.id, overlap))

    return conflicts


async def validate_contracts(
    tasks: list[Task],
    completed_ids: set[str],
) -> list[str]:
    """Validate that completed implementations satisfy their contracts (RFC-034).

    This runs after task execution to verify the produced artifacts
    actually conform to the declared interfaces.

    Note: This is a placeholder for future implementation. Full contract
    validation would require:
    - mypy/pyright for type checking generated code
    - Runtime Protocol checks
    - LLM-based verification

    Args:
        tasks: List of all tasks
        completed_ids: Set of completed task IDs

    Returns:
        List of validation errors (empty if all valid)
    """
    from sunwell.naaru.types import TaskStatus

    errors = []

    # Build a map of artifact producers
    artifact_producers: dict[str, str] = {}
    for task in tasks:
        for artifact in task.produces:
            artifact_producers[artifact] = task.id

    for task in tasks:
        if task.status != TaskStatus.COMPLETED:
            continue
        if not task.contract:
            continue

        # Find the contract task
        contract_task_id = artifact_producers.get(task.contract)
        if not contract_task_id:
            errors.append(
                f"Task {task.id} references unknown contract: {task.contract}"
            )
            continue

        # Check if the contract task completed
        if contract_task_id not in completed_ids:
            errors.append(
                f"Task {task.id} depends on contract {task.contract} "
                f"but contract task {contract_task_id} did not complete"
            )
            continue

        # TODO: Actually verify the implementation satisfies the protocol
        # This could use:
        # - mypy --no-incremental for type checking
        # - Runtime isinstance() checks
        # - LLM-based verification ("Does X satisfy protocol Y?")

    return errors


def format_execution_summary(tasks: list[Task]) -> str:
    """Format a summary of task execution with parallelization stats (RFC-034).

    Args:
        tasks: List of executed tasks

    Returns:
        Formatted summary string
    """
    from sunwell.naaru.types import TaskStatus

    total = len(tasks)
    completed = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)
    failed = sum(1 for t in tasks if t.status == TaskStatus.FAILED)
    skipped = sum(1 for t in tasks if t.status == TaskStatus.SKIPPED)

    analysis = analyze_parallelism(tasks)

    lines = [
        "═" * 50,
        "📊 Task Execution Summary (RFC-034)",
        "═" * 50,
        "",
        f"Total Tasks: {total}",
        f"  ✅ Completed: {completed}",
        f"  ❌ Failed: {failed}",
        f"  ⏭️  Skipped: {skipped}",
        "",
        "Parallelization Analysis:",
        f"  📜 Contract tasks: {analysis.contract_tasks}",
        f"  🔧 Implementation tasks: {analysis.implementation_tasks}",
        f"  ⚡ Max parallel width: {analysis.max_parallel_width}",
        f"  📏 Critical path length: {analysis.critical_path_length}",
        f"  🚀 Theoretical speedup: {analysis.parallelization_ratio:.1f}x",
        "",
    ]

    if analysis.phases:
        lines.append("Phases:")
        for phase in analysis.phases:
            parallel_icon = "⚡" if phase["parallel"] else "→"
            lines.append(
                f"  {parallel_icon} {phase['name']}: "
                f"{phase['tasks']} tasks "
                f"({phase['contract_count']} contracts)"
            )
        lines.append("")

    if analysis.potential_conflicts:
        lines.append(f"⚠️ Potential Conflicts: {len(analysis.potential_conflicts)}")
        for task_a, task_b, files in analysis.potential_conflicts[:5]:
            lines.append(f"  • {task_a} ↔ {task_b}: {', '.join(list(files)[:3])}")
        if len(analysis.potential_conflicts) > 5:
            lines.append(f"  ... and {len(analysis.potential_conflicts) - 5} more")

    lines.append("═" * 50)

    return "\n".join(lines)
