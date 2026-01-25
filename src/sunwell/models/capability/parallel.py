"""Parallel execution planning for tool calls.

Classifies tools as read-only or write operations to enable
safe parallel execution of independent operations.

Research Insight: Parallel tool calling can reduce latency by 4x
for independent read operations.
"""

from dataclasses import dataclass
from enum import Enum

from sunwell.models.capability.registry import ModelCapability
from sunwell.models.protocol import Tool, ToolCall


class ToolCategory(Enum):
    """Tool operation category for parallelization decisions."""

    READ_ONLY = "read_only"
    """Tool only reads data, no side effects."""

    WRITE = "write"
    """Tool modifies data/files."""

    SIDE_EFFECT = "side_effect"
    """Tool has external side effects (API calls, etc.)."""


# Tool name patterns for classification
_READ_PATTERNS = frozenset({
    "read",
    "get",
    "list",
    "find",
    "search",
    "check",
    "view",
    "show",
    "query",
    "fetch",
    "describe",
    "inspect",
})

_WRITE_PATTERNS = frozenset({
    "write",
    "create",
    "update",
    "delete",
    "remove",
    "modify",
    "set",
    "put",
    "patch",
    "append",
    "insert",
    "move",
    "rename",
    "copy",
})

_SIDE_EFFECT_PATTERNS = frozenset({
    "run",
    "execute",
    "send",
    "post",
    "submit",
    "trigger",
    "deploy",
    "publish",
    "notify",
})


def classify_tool(tool: Tool) -> ToolCategory:
    """Classify a tool based on its name and description.

    Args:
        tool: Tool to classify

    Returns:
        ToolCategory indicating operation type
    """
    name_lower = tool.name.lower()
    desc_lower = tool.description.lower()

    # Check name first (most reliable)
    for pattern in _READ_PATTERNS:
        if pattern in name_lower:
            return ToolCategory.READ_ONLY

    for pattern in _WRITE_PATTERNS:
        if pattern in name_lower:
            return ToolCategory.WRITE

    for pattern in _SIDE_EFFECT_PATTERNS:
        if pattern in name_lower:
            return ToolCategory.SIDE_EFFECT

    # Check description
    if "read" in desc_lower and "write" not in desc_lower:
        return ToolCategory.READ_ONLY

    if any(w in desc_lower for w in ["modify", "change", "update", "create", "delete"]):
        return ToolCategory.WRITE

    # Default to side effect (safest)
    return ToolCategory.SIDE_EFFECT


@dataclass(frozen=True, slots=True)
class ParallelExecutionPlan:
    """Plan for parallel execution of tool calls.

    Attributes:
        parallel_groups: Groups of tool calls that can run in parallel.
        sequential_calls: Tool calls that must run sequentially.
    """

    parallel_groups: tuple[tuple[ToolCall, ...], ...]
    """Groups of tool calls that can safely run in parallel."""

    sequential_calls: tuple[ToolCall, ...]
    """Tool calls that must run sequentially (writes, side effects)."""


def plan_parallel_execution(
    tool_calls: tuple[ToolCall, ...],
    tools: dict[str, Tool],
    capability: ModelCapability,
) -> ParallelExecutionPlan:
    """Plan parallel execution of tool calls.

    Groups read-only operations for parallel execution while
    ensuring writes and side effects run sequentially.

    Args:
        tool_calls: Tool calls to plan
        tools: Dict of tool name to Tool definition
        capability: Model capabilities (for parallel support check)

    Returns:
        ParallelExecutionPlan with grouped operations
    """
    # If model doesn't support parallel, everything is sequential
    if not capability.parallel_tools:
        return ParallelExecutionPlan(
            parallel_groups=(),
            sequential_calls=tool_calls,
        )

    read_only: list[ToolCall] = []
    sequential: list[ToolCall] = []

    for tc in tool_calls:
        tool = tools.get(tc.name)
        if tool is None:
            # Unknown tool, treat as side effect
            sequential.append(tc)
            continue

        category = classify_tool(tool)
        if category == ToolCategory.READ_ONLY:
            read_only.append(tc)
        else:
            sequential.append(tc)

    # Group read-only operations
    parallel_groups: tuple[tuple[ToolCall, ...], ...] = ()
    if read_only:
        # All read-only operations can run together
        parallel_groups = (tuple(read_only),)

    return ParallelExecutionPlan(
        parallel_groups=parallel_groups,
        sequential_calls=tuple(sequential),
    )


def can_parallelize(tool_calls: tuple[ToolCall, ...], tools: dict[str, Tool]) -> bool:
    """Check if any tool calls can be parallelized.

    Args:
        tool_calls: Tool calls to check
        tools: Dict of tool name to Tool definition

    Returns:
        True if parallelization is possible
    """
    read_only_count = 0
    for tc in tool_calls:
        tool = tools.get(tc.name)
        if tool and classify_tool(tool) == ToolCategory.READ_ONLY:
            read_only_count += 1

    # Need at least 2 read-only calls for parallelization to help
    return read_only_count >= 2
