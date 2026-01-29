"""Tool DAG for workflow-aware progressive disclosure.

This module implements a directed acyclic graph of tools where edges
represent natural workflow progressions. Tools are only presented to
models after their predecessors have been used, dramatically reducing
the tool count for small models.

Research backing:
- vLLM semantic router: 99.1% token reduction with 3.2x accuracy improvement
- ToolNet: Graph-based tool navigation outperforms flat lists
- Graph RAG-Tool Fusion: 71.7% improvement over naive RAG

Follows patterns from SkillGraph (src/sunwell/planning/skills/graph.py).
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.models import Tool


class ToolDAGError(Exception):
    """Base exception for tool DAG errors."""


@dataclass(frozen=True, slots=True)
class ToolNode:
    """Node in the tool dependency graph.

    Each node represents a tool and its successors - tools that become
    available after this tool has been used.

    Attributes:
        name: Tool name (must match tool definition name)
        successors: Tools unlocked after using this tool
        category: Logical grouping (file, git, search, env, etc.)
    """

    name: str
    successors: frozenset[str] = frozenset()
    category: str = "core"


@dataclass(slots=True)
class ToolDAG:
    """DAG of tools with workflow-aware progressive disclosure.

    Provides intelligent tool selection based on which tools have already
    been used in the current session. Entry points are always available,
    and using a tool unlocks its successors.

    Thread-safe for reads. The graph is immutable after construction.

    Example workflow encoded in DAG:
        list_files -> read_file -> edit_file -> git_add -> git_commit

    After calling list_files, read_file becomes available.
    After calling read_file, edit_file becomes available.
    And so on.
    """

    _nodes: dict[str, ToolNode] = field(default_factory=dict)
    """Mapping from tool name to ToolNode."""

    _entry_points: frozenset[str] = field(default_factory=frozenset)
    """Tools available from the start (no predecessors required)."""

    def get_available(self, used_tools: frozenset[str]) -> frozenset[str]:
        """Get tools available given which tools have been used.

        Args:
            used_tools: Set of tool names that have been called

        Returns:
            Set of tool names that are currently available
        """
        if not used_tools:
            return self._entry_points

        # Entry points are always available
        available = set(self._entry_points)

        # Add successors of used tools
        for tool_name in used_tools:
            if node := self._nodes.get(tool_name):
                available.update(node.successors)

        return frozenset(available)

    def get_all_tools(self) -> frozenset[str]:
        """Get all tools in the DAG."""
        return frozenset(self._nodes.keys())

    def is_entry_point(self, tool_name: str) -> bool:
        """Check if a tool is an entry point."""
        return tool_name in self._entry_points

    def get_successors(self, tool_name: str) -> frozenset[str]:
        """Get successors of a tool (tools unlocked by using it)."""
        if node := self._nodes.get(tool_name):
            return node.successors
        return frozenset()

    def get_category(self, tool_name: str) -> str:
        """Get the category of a tool."""
        if node := self._nodes.get(tool_name):
            return node.category
        return "unknown"

    def __contains__(self, tool_name: str) -> bool:
        return tool_name in self._nodes

    def __len__(self) -> int:
        return len(self._nodes)

    @classmethod
    def from_nodes(cls, nodes: tuple[ToolNode, ...]) -> "ToolDAG":
        """Create a ToolDAG from a collection of nodes.

        Entry points are automatically detected as nodes that are not
        successors of any other node.

        Args:
            nodes: ToolNode definitions

        Returns:
            New ToolDAG with computed entry points
        """
        nodes_dict = {node.name: node for node in nodes}

        # Find all successors
        all_successors: set[str] = set()
        for node in nodes:
            all_successors.update(node.successors)

        # Entry points are nodes that are not successors of any node
        entry_points = frozenset(
            name for name in nodes_dict.keys()
            if name not in all_successors
        )

        return cls(_nodes=nodes_dict, _entry_points=entry_points)


# =============================================================================
# DEFAULT TOOL DAG
# =============================================================================

# Define the default DAG structure encoding natural workflow progressions.
# This is based on common development patterns:
# - Discovery (list/search) -> Reading -> Editing -> Git staging -> Git commit
# - Each progression unlocks the next natural step

_DEFAULT_NODES: tuple[ToolNode, ...] = (
    # === ENTRY POINTS (always visible) ===
    # These are discovery/exploration tools that make sense as starting points

    ToolNode(
        name="list_files",
        successors=frozenset({"read_file", "find_files"}),
        category="file",
    ),
    ToolNode(
        name="search_files",
        successors=frozenset({"read_file"}),
        category="search",
    ),
    ToolNode(
        name="find_files",
        successors=frozenset({"read_file"}),
        category="search",
    ),
    ToolNode(
        name="git_status",
        successors=frozenset({"git_diff", "git_add", "git_restore", "read_file"}),
        category="git",
    ),
    ToolNode(
        name="run_command",
        successors=frozenset({"read_file"}),  # Often run tests then read results
        category="shell",
    ),
    ToolNode(
        name="list_env",
        successors=frozenset({"get_env"}),
        category="env",
    ),

    # === SECOND LEVEL (unlocked by entry points) ===

    ToolNode(
        name="read_file",
        successors=frozenset({"edit_file", "write_file", "patch_file", "copy_file"}),
        category="file",
    ),
    ToolNode(
        name="git_diff",
        successors=frozenset({"git_add", "edit_file", "read_file"}),
        category="git",
    ),
    ToolNode(
        name="git_restore",
        successors=frozenset({"read_file", "git_status"}),
        category="git",
    ),
    ToolNode(
        name="get_env",
        successors=frozenset(),  # Terminal node
        category="env",
    ),

    # === THIRD LEVEL (file modification) ===

    ToolNode(
        name="edit_file",
        successors=frozenset({"git_add", "undo_file", "run_command", "read_file"}),
        category="file",
    ),
    ToolNode(
        name="write_file",
        successors=frozenset({"git_add", "undo_file", "run_command", "read_file"}),
        category="file",
    ),
    ToolNode(
        name="patch_file",
        successors=frozenset({"git_add", "undo_file", "run_command", "read_file"}),
        category="file",
    ),
    ToolNode(
        name="mkdir",
        successors=frozenset({"write_file", "copy_file"}),
        category="file",
    ),
    ToolNode(
        name="copy_file",
        successors=frozenset({"read_file", "edit_file", "git_add"}),
        category="file",
    ),

    # === FOURTH LEVEL (file management and undo) ===

    ToolNode(
        name="delete_file",
        successors=frozenset({"git_add", "undo_file", "list_backups"}),
        category="file",
    ),
    ToolNode(
        name="rename_file",
        successors=frozenset({"git_add", "read_file"}),
        category="file",
    ),
    ToolNode(
        name="undo_file",
        successors=frozenset({"read_file", "list_backups"}),
        category="file",
    ),
    ToolNode(
        name="list_backups",
        successors=frozenset({"restore_file", "undo_file"}),
        category="file",
    ),
    ToolNode(
        name="restore_file",
        successors=frozenset({"read_file", "git_add"}),
        category="file",
    ),

    # === GIT WORKFLOW ===

    ToolNode(
        name="git_add",
        successors=frozenset({"git_commit", "git_restore", "git_diff", "git_status"}),
        category="git",
    ),
    ToolNode(
        name="git_commit",
        successors=frozenset({"git_branch", "git_stash", "git_log", "git_status"}),
        category="git",
    ),
    ToolNode(
        name="git_branch",
        successors=frozenset({"git_checkout", "git_merge", "git_status"}),
        category="git",
    ),
    ToolNode(
        name="git_checkout",
        successors=frozenset({"git_status", "read_file", "git_merge"}),
        category="git",
    ),
    ToolNode(
        name="git_stash",
        successors=frozenset({"git_checkout", "git_status"}),
        category="git",
    ),
    ToolNode(
        name="git_reset",
        successors=frozenset({"git_status", "git_diff", "read_file"}),
        category="git",
    ),
    ToolNode(
        name="git_merge",
        successors=frozenset({"git_status", "git_diff", "read_file"}),
        category="git",
    ),

    # === GIT READ-ONLY (accessible from git_status) ===

    ToolNode(
        name="git_log",
        successors=frozenset({"git_show", "git_diff"}),
        category="git",
    ),
    ToolNode(
        name="git_show",
        successors=frozenset({"read_file", "git_diff"}),
        category="git",
    ),
    ToolNode(
        name="git_blame",
        successors=frozenset({"read_file", "git_show"}),
        category="git",
    ),
    ToolNode(
        name="git_info",
        successors=frozenset({"git_status", "git_log"}),
        category="git",
    ),
    ToolNode(
        name="git_init",
        successors=frozenset({"git_status", "git_add"}),
        category="git",
    ),

    # === WEB TOOLS (entry points for research tasks) ===

    ToolNode(
        name="web_search",
        successors=frozenset({"web_fetch", "read_file"}),
        category="web",
    ),
    ToolNode(
        name="web_fetch",
        successors=frozenset({"write_file", "read_file"}),
        category="web",
    ),

    # === EXPERTISE TOOLS (entry points for guided tasks) ===

    ToolNode(
        name="list_expertise_areas",
        successors=frozenset({"get_expertise"}),
        category="expertise",
    ),
    ToolNode(
        name="get_expertise",
        successors=frozenset({"verify_against_expertise", "read_file", "edit_file"}),
        category="expertise",
    ),
    ToolNode(
        name="verify_against_expertise",
        successors=frozenset({"edit_file", "get_expertise"}),
        category="expertise",
    ),
)

# Create the default DAG
DEFAULT_TOOL_DAG = ToolDAG.from_nodes(_DEFAULT_NODES)
