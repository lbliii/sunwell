"""Task graph for tracking execution state.

The TaskGraph manages task dependencies, completion status, and artifact tracking
for the Agent's execution pipeline.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.planning.naaru.types import Task

from sunwell.agent.validation.gates import ValidationGate


def sanitize_code_content(content: str | None) -> str:
    """Strip markdown fences, tool call syntax, and preamble from generated code.

    Defense-in-depth: Called before direct file writes to ensure
    clean code content even when models output tool calls in text.

    Handles multiple formats (in order of specificity):
    1. Python function call: write_file("path", '''content''') or write_file("path", \"\"\"content\"\"\")
    2. Tool call with markdown fence: write_file path ```language\\ncode\\n```
    3. Explanatory preamble: "Okay, I will create..." followed by tool call
    4. Standard markdown: ```language\\ncode\\n```
    5. Truncated output: ```language\\ncode (no closing ```)

    Args:
        content: Raw content that may contain markdown fences, tool syntax, or preamble

    Returns:
        Clean code content with all wrapping stripped, or empty string if None/empty
    """
    import re

    if not content:
        return ""

    text = content.strip()
    if not text:
        return ""

    # Pattern 1: Python function call syntax with triple quotes
    # Matches: write_file("path", """content""") or write_file("path", '''content''')
    # Also handles: write_file("path", """content
    python_call_pattern = re.compile(
        r'write_file\s*\(\s*["\'][^"\']+["\']\s*,\s*'  # write_file("path",
        r'(?:"""(.*?)"""|\'\'\'(.*?)\'\'\')',  # """content""" or '''content'''
        re.DOTALL
    )
    match = python_call_pattern.search(text)
    if match:
        extracted = match.group(1) or match.group(2)
        if extracted:
            return extracted.strip()

    # Pattern 1b: Unclosed Python triple quotes (truncated)
    # Matches: write_file("path", """content (no closing """)
    python_unclosed = re.compile(
        r'write_file\s*\(\s*["\'][^"\']+["\']\s*,\s*'  # write_file("path",
        r'(?:"""|\'\'\')\s*(.*)$',  # """content (to end)
        re.DOTALL
    )
    match = python_unclosed.search(text)
    if match:
        extracted = match.group(1)
        # Remove trailing """) if present
        extracted = re.sub(r'["\')]+\s*$', '', extracted)
        if extracted.strip():
            return extracted.strip()

    # Pattern 2: Tool call prefix with markdown fence
    # Matches: write_file path ```language\ncode\n``` or write_file("path") ```code```
    # Also catches preamble text before tool call
    tool_fence_pattern = re.compile(
        r'(?:^|\n)write_file\s+\S+\s*'  # write_file path
        r'```\w*\n?(.*?)```',  # ```language\ncode```
        re.DOTALL
    )
    match = tool_fence_pattern.search(text)
    if match:
        return match.group(1).strip()

    # Pattern 3: Any markdown fence anywhere (most flexible)
    # This handles preamble text + ```code``` cases
    fence_pattern = re.compile(r'```\w*\n(.*?)```', re.DOTALL)
    match = fence_pattern.search(text)
    if match:
        return match.group(1).strip()

    # Pattern 4: Unclosed markdown fence (truncated output)
    # Matches: ```language\ncode (no closing ```)
    open_fence = re.compile(r'```\w*\n(.*)$', re.DOTALL)
    match = open_fence.search(text)
    if match:
        return match.group(1).strip()

    # Pattern 5: Standard case - starts with markdown fence
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove opening fence
        lines = lines[1:]
        # Remove closing fence if present
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines)

    # Pattern 6: Just a tool call with no content (e.g., "write_file path")
    # This indicates the model failed to output actual content
    if re.match(r'^write_file\s+\S+\s*$', text):
        # Return empty - there's no actual code here
        return ""

    # Pattern 7: Remove common preamble patterns at the start
    # e.g., "Okay, I will create...", "I'll write..."
    preamble_patterns = [
        r'^(?:Okay|Ok|Sure|Alright|I\'ll|I will|Let me|Here\'s|Here is)[^`\n]*\n+',
    ]
    for pattern in preamble_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)

    # No fence found and not a tool call pattern, return cleaned text as-is
    return text.strip()




@dataclass(slots=True)
class TaskGraph:
    """A graph of tasks with execution state.

    Tracks which tasks are complete, which artifacts have been produced,
    and provides methods to determine which tasks are ready for execution.

    Attributes:
        tasks: All tasks in the graph
        gates: Validation gates to run at checkpoints
        completed_ids: IDs of completed tasks
        completed_artifacts: Artifacts that have been produced
    """

    tasks: list[Task] = field(default_factory=list)
    """All tasks in the graph."""

    gates: list[ValidationGate] = field(default_factory=list)
    """Validation gates."""

    completed_ids: set[str] = field(default_factory=set)
    """IDs of completed tasks."""

    completed_artifacts: set[str] = field(default_factory=set)
    """Artifacts that have been produced."""

    def has_pending_tasks(self) -> bool:
        """Check if there are pending tasks."""
        return len(self.completed_ids) < len(self.tasks)

    def get_ready_tasks(self) -> list[Task]:
        """Get tasks that are ready to execute.

        A task is ready when:
        - It hasn't been completed yet
        - All its dependencies are satisfied

        Returns:
            List of tasks ready for execution
        """
        return [
            t
            for t in self.tasks
            if t.id not in self.completed_ids
            and t.is_ready(self.completed_ids, self.completed_artifacts)
        ]

    def mark_complete(self, task: Task) -> None:
        """Mark a task as complete.

        Args:
            task: The completed task
        """
        self.completed_ids.add(task.id)
        if task.produces:
            self.completed_artifacts.update(task.produces)

    @property
    def completed_summary(self) -> str:
        """Summary of completed work."""
        return f"{len(self.completed_ids)}/{len(self.tasks)} tasks"

    # =========================================================================
    # Parallel Execution Support (Agentic Infrastructure Phase 2)
    # =========================================================================

    def get_parallel_groups(self) -> dict[str | None, list[Task]]:
        """Group ready tasks by parallel_group for subagent spawning.

        Returns a dict mapping parallel_group name to list of ready tasks.
        Tasks without a parallel_group are grouped under key None.

        Only returns tasks that are:
        - Not yet completed
        - Have all dependencies satisfied
        - Can potentially run in parallel

        Returns:
            Dict mapping parallel_group name (or None) to ready tasks
        """
        ready = self.get_ready_tasks()
        groups: dict[str | None, list[Task]] = {}

        for task in ready:
            group_key = task.parallel_group
            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append(task)

        return groups

    def can_parallelize(self, tasks: list[Task]) -> bool:
        """Check if tasks can safely execute in parallel.

        Tasks can be parallelized when they have non-overlapping `modifies` sets.
        Two tasks with overlapping modifies sets could conflict on the same file.

        Args:
            tasks: List of tasks to check

        Returns:
            True if tasks have no overlapping modifies sets
        """
        if len(tasks) <= 1:
            return True

        # Collect all modifies sets
        all_modifies: list[frozenset[str]] = []
        for task in tasks:
            if task.modifies:
                all_modifies.append(task.modifies)

        # Check for overlaps
        for i, mods_a in enumerate(all_modifies):
            for mods_b in all_modifies[i + 1:]:
                if mods_a & mods_b:  # Non-empty intersection
                    return False

        return True

    def get_parallelizable_groups(self) -> dict[str, list[Task]]:
        """Get parallel groups that are safe to execute concurrently.

        Filters get_parallel_groups() to only include groups where:
        - All tasks have non-overlapping modifies sets
        - Group has more than one task (worth parallelizing)

        Returns:
            Dict mapping group name to parallelizable tasks.
            Excludes None key and single-task groups.
        """
        groups = self.get_parallel_groups()
        result: dict[str, list[Task]] = {}

        for group_name, tasks in groups.items():
            # Skip ungrouped tasks and single-task groups
            if group_name is None or len(tasks) <= 1:
                continue

            # Check if tasks can actually be parallelized
            if self.can_parallelize(tasks):
                result[group_name] = tasks

        return result

    def get_sequential_tasks(self) -> list[Task]:
        """Get ready tasks that must execute sequentially.

        Returns tasks that are:
        - Not in a parallel group, OR
        - In a parallel group but can't be safely parallelized

        Returns:
            List of tasks to execute one at a time
        """
        groups = self.get_parallel_groups()
        parallelizable = self.get_parallelizable_groups()

        sequential: list[Task] = []

        for group_name, tasks in groups.items():
            if group_name is None:
                # Ungrouped tasks are sequential
                sequential.extend(tasks)
            elif group_name not in parallelizable:
                # Group exists but isn't parallelizable (conflicts)
                sequential.extend(tasks)

        return sequential
