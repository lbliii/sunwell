"""MCP Tool definitions for Sunwell."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from sunwell.mcp.runtime import MCPRuntime

from sunwell.mcp.tools.backlog import register_backlog_tools
from sunwell.mcp.tools.context import register_context_tools
from sunwell.mcp.tools.delegation import register_delegation_tools
from sunwell.mcp.tools.events import register_events_tools
from sunwell.mcp.tools.execution import register_execution_tools
from sunwell.mcp.tools.knowledge import register_knowledge_tools
from sunwell.mcp.tools.lens import register_lens_tools
from sunwell.mcp.tools.memory import register_memory_tools
from sunwell.mcp.tools.mirror import register_mirror_tools
from sunwell.mcp.tools.planning import register_planning_tools
from sunwell.mcp.tools.routing import register_routing_tools


def register_tools(
    mcp: FastMCP,
    lenses_dir: str | None = None,
    runtime: MCPRuntime | None = None,
) -> None:
    """Register all Sunwell tools with the MCP server.

    Args:
        mcp: FastMCP server instance
        lenses_dir: Optional path to lenses directory
        runtime: Shared MCPRuntime for async bridging, workspace resolution,
                 and lazy subsystem access
    """
    # Lens system (no async, no subsystems — just lenses_dir)
    register_lens_tools(mcp, lenses_dir)
    register_routing_tools(mcp, lenses_dir)

    # Memory and context
    register_memory_tools(mcp, runtime)

    # Knowledge and search
    register_knowledge_tools(mcp, runtime)

    # Planning and routing intelligence
    register_planning_tools(mcp, runtime)

    # Backlog and goals
    register_backlog_tools(mcp, runtime)

    # Mirror and introspection
    register_mirror_tools(mcp, runtime)

    # Execution and completion
    register_execution_tools(mcp, runtime)

    # Model delegation (no workspace/async needed)
    register_delegation_tools(mcp)

    # Multi-agent coordination (self-driving)
    register_context_tools(mcp, runtime)
    register_events_tools(mcp, runtime)
