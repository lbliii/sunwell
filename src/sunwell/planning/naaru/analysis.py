"""Task graph analysis and visualization utilities (RFC-034).

This module provides utilities for analyzing and visualizing task graphs
with parallelization potential, contract relationships, and resource conflicts.

Example:
    >>> from sunwell.planning.naaru.analysis import visualize_task_graph, analyze_parallelism
    >>>
    >>> diagram = visualize_task_graph(tasks)
    >>> print(diagram)  # Mermaid diagram
    >>>
    >>> analysis = analyze_parallelism(tasks)
    >>> print(f"Potential speedup: {analysis['parallelization_ratio']:.1f}x")
"""


from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sunwell.llm.types import ModelProtocol
    from sunwell.planning.naaru.types import Task
    from sunwell.planning.naaru.verification import ContractVerificationResult


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
    workspace: Path | None = None,
    model: "ModelProtocol | None" = None,
) -> tuple[list[str], list["ContractVerificationResult"]]:
    """Validate that completed implementations satisfy their contracts (RFC-034).

    This runs after task execution to verify the produced artifacts
    actually conform to the declared interfaces using a tiered approach:
    1. AST Analysis - Fast structural checks
    2. Static Type Check - mypy verification
    3. LLM Verification - Semantic analysis (fallback, if model provided)

    Args:
        tasks: List of all tasks
        completed_ids: Set of completed task IDs
        workspace: Workspace root directory (defaults to cwd)
        model: Optional LLM model for Tier 3 semantic verification

    Returns:
        Tuple of (errors, verification_results):
        - errors: List of validation error messages
        - verification_results: List of ContractVerificationResult objects
    """
    from sunwell.planning.naaru.types import TaskStatus
    from sunwell.planning.naaru.verification import (
        ContractVerificationResult,
        ContractVerifier,
        VerificationStatus,
    )

    errors: list[str] = []
    results: list[ContractVerificationResult] = []

    if workspace is None:
        workspace = Path.cwd()

    # Build maps for task and artifact lookups
    task_map: dict[str, Task] = {t.id: t for t in tasks}
    artifact_producers: dict[str, str] = {}
    for task in tasks:
        for artifact in task.produces:
            artifact_producers[artifact] = task.id

    # Initialize verifier
    verifier = ContractVerifier(
        workspace=workspace,
        model=model,
        skip_llm=model is None,
    )

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

        contract_task = task_map.get(contract_task_id)
        if contract_task is None:
            errors.append(f"Contract task {contract_task_id} not found in task map")
            continue

        # Determine file paths for verification
        impl_file = _find_implementation_file(task, workspace)
        contract_file = _find_contract_file(contract_task, workspace)

        if impl_file is None:
            errors.append(
                f"Task {task.id}: Cannot determine implementation file path"
            )
            continue

        if contract_file is None:
            errors.append(
                f"Task {task.id}: Cannot determine contract file path for {task.contract}"
            )
            continue

        # Run verification
        result = await verifier.verify(
            implementation_file=impl_file,
            contract_file=contract_file,
            protocol_name=task.contract,
        )
        results.append(result)

        # Report failures
        if result.status == VerificationStatus.FAILED:
            mismatch_details = "; ".join(
                f"{m.method_name}: {m.issue}"
                for m in result.all_mismatches[:3]
            )
            errors.append(
                f"Task {task.id}: Implementation does not satisfy {task.contract}: "
                f"{mismatch_details}"
            )
        elif result.status == VerificationStatus.ERROR:
            errors.append(
                f"Task {task.id}: Verification error: {result.error_message}"
            )

    return errors, results


def _find_implementation_file(task: "Task", workspace: Path) -> Path | None:
    """Find the implementation file for a task.

    Checks task.target_path and task.modifies for Python files.

    Args:
        task: Task to find implementation file for
        workspace: Workspace root directory

    Returns:
        Path to implementation file, or None if not found
    """
    # First check target_path
    if task.target_path:
        target = Path(task.target_path)
        if target.suffix == ".py":
            full_path = workspace / target if not target.is_absolute() else target
            if full_path.exists():
                return full_path

    # Check modifies for Python files
    for modified in task.modifies:
        modified_path = Path(modified)
        if modified_path.suffix == ".py":
            full_path = workspace / modified_path if not modified_path.is_absolute() else modified_path
            if full_path.exists():
                return full_path

    return None


def _find_contract_file(task: "Task", workspace: Path) -> Path | None:
    """Find the contract/Protocol file for a contract task.

    Checks task.target_path and task.modifies for Python files.

    Args:
        task: Contract task to find Protocol file for
        workspace: Workspace root directory

    Returns:
        Path to contract file, or None if not found
    """
    # Same logic as implementation file - contracts are also Python files
    return _find_implementation_file(task, workspace)


def format_execution_summary(tasks: list[Task]) -> str:
    """Format a summary of task execution with parallelization stats (RFC-034).

    Args:
        tasks: List of executed tasks

    Returns:
        Formatted summary string
    """
    from sunwell.planning.naaru.types import TaskStatus

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
