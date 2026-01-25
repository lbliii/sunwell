"""Tests for parallel execution planning."""

import pytest

from sunwell.models.capability.parallel import (
    ParallelExecutionPlan,
    ToolCategory,
    can_parallelize,
    classify_tool,
    plan_parallel_execution,
)
from sunwell.models.capability.registry import ModelCapability
from sunwell.models.protocol import Tool, ToolCall


class TestClassifyTool:
    """Test tool classification."""

    def test_read_tool(self):
        """Read tools should be classified as READ_ONLY."""
        tool = Tool(name="read_file", description="Read a file", parameters={})
        assert classify_tool(tool) == ToolCategory.READ_ONLY

    def test_write_tool(self):
        """Write tools should be classified as WRITE."""
        tool = Tool(name="write_file", description="Write to a file", parameters={})
        assert classify_tool(tool) == ToolCategory.WRITE

    def test_list_tool(self):
        """List tools should be READ_ONLY."""
        tool = Tool(name="list_files", description="List files", parameters={})
        assert classify_tool(tool) == ToolCategory.READ_ONLY

    def test_execute_tool(self):
        """Execute tools should be SIDE_EFFECT."""
        tool = Tool(name="execute_command", description="Run a command", parameters={})
        assert classify_tool(tool) == ToolCategory.SIDE_EFFECT

    def test_unknown_defaults_to_side_effect(self):
        """Unknown tools default to SIDE_EFFECT (safest)."""
        tool = Tool(name="do_something", description="Does something", parameters={})
        assert classify_tool(tool) == ToolCategory.SIDE_EFFECT


class TestPlanParallelExecution:
    """Test parallel execution planning."""

    def test_parallel_read_operations(self):
        """Read operations should be grouped for parallel execution."""
        tools = {
            "read_file": Tool(name="read_file", description="Read a file", parameters={}),
            "list_files": Tool(name="list_files", description="List files", parameters={}),
        }
        tool_calls = (
            ToolCall(id="1", name="read_file", arguments={"path": "a.py"}),
            ToolCall(id="2", name="list_files", arguments={"path": "."}),
        )
        capability = ModelCapability(parallel_tools=True)

        plan = plan_parallel_execution(tool_calls, tools, capability)

        assert len(plan.parallel_groups) == 1
        assert len(plan.parallel_groups[0]) == 2
        assert len(plan.sequential_calls) == 0

    def test_write_operations_sequential(self):
        """Write operations should be sequential."""
        tools = {
            "write_file": Tool(name="write_file", description="Write to file", parameters={})
        }
        tool_calls = (
            ToolCall(id="1", name="write_file", arguments={"path": "a.py"}),
            ToolCall(id="2", name="write_file", arguments={"path": "b.py"}),
        )
        capability = ModelCapability(parallel_tools=True)

        plan = plan_parallel_execution(tool_calls, tools, capability)

        assert len(plan.parallel_groups) == 0
        assert len(plan.sequential_calls) == 2

    def test_no_parallel_support(self):
        """Models without parallel support get sequential plan."""
        tools = {
            "read_file": Tool(name="read_file", description="Read a file", parameters={}),
        }
        tool_calls = (
            ToolCall(id="1", name="read_file", arguments={"path": "a.py"}),
            ToolCall(id="2", name="read_file", arguments={"path": "b.py"}),
        )
        capability = ModelCapability(parallel_tools=False)

        plan = plan_parallel_execution(tool_calls, tools, capability)

        assert len(plan.parallel_groups) == 0
        assert len(plan.sequential_calls) == 2


class TestCanParallelize:
    """Test parallelization check."""

    def test_multiple_reads(self):
        """Multiple read calls can be parallelized."""
        tools = {
            "read_file": Tool(name="read_file", description="Read", parameters={}),
        }
        calls = (
            ToolCall(id="1", name="read_file", arguments={}),
            ToolCall(id="2", name="read_file", arguments={}),
        )
        assert can_parallelize(calls, tools) is True

    def test_single_read(self):
        """Single read cannot be parallelized."""
        tools = {
            "read_file": Tool(name="read_file", description="Read", parameters={}),
        }
        calls = (ToolCall(id="1", name="read_file", arguments={}),)
        assert can_parallelize(calls, tools) is False
