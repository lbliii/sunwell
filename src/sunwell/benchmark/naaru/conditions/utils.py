"""Utility functions for condition implementations."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.benchmark.types import BenchmarkTask


def lightweight_validate(
    task: BenchmarkTask,
    output: str,
) -> tuple[bool, list[str]]:
    """Lightweight structural validation (no LLM).

    Returns:
        Tuple of (is_ok, issues)
    """
    issues: list[str] = []

    # Check for empty output
    if not output or len(output.strip()) < 10:
        issues.append("Output is empty or too short")

    # Check deterministic criteria from task
    if task.evaluation:
        for must in task.evaluation.must_contain:
            if must.lower() not in output.lower():
                issues.append(f"Missing required element: {must}")

        for must_not in task.evaluation.must_not_contain:
            if must_not.lower() in output.lower():
                issues.append(f"Contains forbidden element: {must_not}")

    # Check for code blocks in code tasks
    from sunwell.benchmark.types import TaskCategory
    if task.category == TaskCategory.CODE_GENERATION:
        if "```" not in output and "def " not in output and "class " not in output:
            issues.append("Missing code block or function/class definition")
        if output.count("pass") > 3:
            issues.append("Too many placeholder 'pass' statements")

    return len(issues) == 0, issues
