"""Tool Invocation Tracker - Central tracking for all tool calls.

Provides:
1. Recording of all tool invocations (name, args, result, success)
2. Verification against expected tool calls
3. Self-correction strategies when tools weren't called

This enables Sunwell to detect when models output text instead of
calling tools, and self-correct by performing the intended action.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ToolCategory(Enum):
    """Categories of tools for different self-correction strategies."""

    OUTPUT = "output"  # Creates/modifies state (write_file, edit_file, run_command)
    INPUT = "input"  # Reads state (read_file, search, grep)
    QUERY = "query"  # External queries (web_search, api_call)


# Tool categorization for self-correction routing
TOOL_CATEGORIES: dict[str, ToolCategory] = {
    # Output tools - can self-correct by performing the action
    "write_file": ToolCategory.OUTPUT,
    "edit_file": ToolCategory.OUTPUT,
    "run_command": ToolCategory.OUTPUT,
    "delete_file": ToolCategory.OUTPUT,
    "create_directory": ToolCategory.OUTPUT,
    # Input tools - self-correction is different (need to actually read)
    "read_file": ToolCategory.INPUT,
    "list_directory": ToolCategory.INPUT,
    "search": ToolCategory.INPUT,
    "grep": ToolCategory.INPUT,
    "find_files": ToolCategory.INPUT,
    # Query tools - external dependencies
    "web_search": ToolCategory.QUERY,
}


@dataclass(slots=True)
class ToolInvocation:
    """Record of a single tool invocation."""

    tool_name: str
    arguments: dict[str, Any]
    result: Any
    success: bool
    timestamp: datetime = field(default_factory=datetime.now)
    duration_ms: int | None = None
    error: str | None = None
    self_corrected: bool = False  # Was this a self-correction?


@dataclass
class InvocationTracker:
    """Tracks tool invocations for a task or session.

    Usage:
        tracker = InvocationTracker()

        # Record invocations as they happen
        tracker.record("write_file", {"path": "x.py", "content": "..."}, success=True)

        # Check what was expected vs actual
        expected = {"write_file": [{"path": "x.py"}]}
        missing = tracker.get_missing_invocations(expected)

        # Self-correct if needed
        if missing:
            for tool, args_list in missing.items():
                for args in args_list:
                    self_correct(tool, args, model_output)
    """

    invocations: list[ToolInvocation] = field(default_factory=list)
    task_id: str | None = None

    def record(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        result: Any = None,
        success: bool = True,
        duration_ms: int | None = None,
        error: str | None = None,
        self_corrected: bool = False,
    ) -> ToolInvocation:
        """Record a tool invocation."""
        invocation = ToolInvocation(
            tool_name=tool_name,
            arguments=arguments,
            result=result,
            success=success,
            duration_ms=duration_ms,
            error=error,
            self_corrected=self_corrected,
        )
        self.invocations.append(invocation)
        return invocation

    def was_called(self, tool_name: str) -> bool:
        """Check if a tool was called at all."""
        return any(inv.tool_name == tool_name for inv in self.invocations)

    def was_called_with(self, tool_name: str, **expected_args: Any) -> bool:
        """Check if a tool was called with specific arguments."""
        for inv in self.invocations:
            if inv.tool_name != tool_name:
                continue
            # Check if expected args are subset of actual args
            if all(inv.arguments.get(k) == v for k, v in expected_args.items()):
                return True
        return False

    def get_calls(self, tool_name: str) -> list[ToolInvocation]:
        """Get all invocations of a specific tool."""
        return [inv for inv in self.invocations if inv.tool_name == tool_name]

    def get_successful_calls(self, tool_name: str) -> list[ToolInvocation]:
        """Get successful invocations of a specific tool."""
        return [
            inv for inv in self.invocations
            if inv.tool_name == tool_name and inv.success
        ]

    def get_output_tool_calls(self) -> list[ToolInvocation]:
        """Get all OUTPUT category tool calls (write_file, edit_file, etc.)."""
        return [
            inv for inv in self.invocations
            if TOOL_CATEGORIES.get(inv.tool_name) == ToolCategory.OUTPUT
        ]

    def get_missing_invocations(
        self,
        expected: dict[str, list[dict[str, Any]]],
    ) -> dict[str, list[dict[str, Any]]]:
        """Compare expected tool calls against actual.

        Args:
            expected: Dict of tool_name -> list of expected argument dicts
                      e.g., {"write_file": [{"path": "x.py"}]}

        Returns:
            Dict of missing tool calls (same format as expected)
        """
        missing: dict[str, list[dict[str, Any]]] = {}

        for tool_name, expected_calls in expected.items():
            missing_for_tool = []
            for expected_args in expected_calls:
                # Check if this specific call was made
                if not self.was_called_with(tool_name, **expected_args):
                    missing_for_tool.append(expected_args)

            if missing_for_tool:
                missing[tool_name] = missing_for_tool

        return missing

    def summary(self) -> dict[str, Any]:
        """Get a summary of all invocations."""
        by_tool: dict[str, int] = {}
        successful = 0
        failed = 0
        self_corrected = 0

        for inv in self.invocations:
            by_tool[inv.tool_name] = by_tool.get(inv.tool_name, 0) + 1
            if inv.success:
                successful += 1
            else:
                failed += 1
            if inv.self_corrected:
                self_corrected += 1

        return {
            "total": len(self.invocations),
            "successful": successful,
            "failed": failed,
            "self_corrected": self_corrected,
            "by_tool": by_tool,
        }

    def clear(self) -> None:
        """Clear all invocations (for reuse)."""
        self.invocations.clear()


def can_self_correct(tool_name: str) -> bool:
    """Check if a tool can be self-corrected from model output."""
    category = TOOL_CATEGORIES.get(tool_name)
    # OUTPUT tools can potentially be self-corrected
    return category == ToolCategory.OUTPUT


def get_self_correction_strategy(tool_name: str) -> str | None:
    """Get the self-correction strategy for a tool.

    Returns:
        Strategy name or None if tool can't be self-corrected
    """
    strategies = {
        "write_file": "write_model_output",  # Write model's text output to file
        "edit_file": "apply_model_diff",  # Apply diff from model output (harder)
        "run_command": "execute_suggested_command",  # Run command from model output
        "delete_file": "delete_mentioned_file",  # Delete file model mentioned
        "create_directory": "create_mentioned_dir",  # Create dir model mentioned
    }
    return strategies.get(tool_name)
