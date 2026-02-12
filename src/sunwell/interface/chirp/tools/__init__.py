"""Chirp MCP tool registration for Sunwell.

Exposes Sunwell capabilities via Chirp's built-in MCP server (@app.tool decorator).
This module registers all Sunwell tools with the Chirp app, enabling:

1. AI agents to call tools via /mcp endpoint (JSON-RPC)
2. Web UI to call the same functions (unified interface)
3. Real-time activity monitoring via app.tool_events

Usage:
    from chirp import App
    from sunwell.interface.chirp.tools import register_all_tools

    app = App()
    register_all_tools(app)

Architecture:
    These are thin wrappers around Sunwell's existing service layer. They:
    - Adapt existing services to Chirp's @app.tool() decorator
    - Provide consistent naming (sunwell_* prefix)
    - Enable automatic JSON Schema generation
    - Support tool event emission for monitoring
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from chirp import App

logger = logging.getLogger(__name__)


def register_all_tools(app: App) -> None:
    """Register all Sunwell tools with the Chirp app.

    This registers tools from all categories:
    - Backlog (goals, tasks)
    - Knowledge (search, codebase)
    - Memory (recall, briefing)
    - Planning (plan, classify)
    - Execution (execute, validate)
    - Lens (expertise, routing)

    Args:
        app: Chirp application instance
    """
    from sunwell.interface.chirp.tools.backlog import register_backlog_tools
    from sunwell.interface.chirp.tools.knowledge import register_knowledge_tools
    from sunwell.interface.chirp.tools.lens import register_lens_tools
    from sunwell.interface.chirp.tools.memory import register_memory_tools

    logger.info("Registering Sunwell MCP tools with Chirp app")

    # Register tool categories
    register_backlog_tools(app)
    register_knowledge_tools(app)
    register_lens_tools(app)
    register_memory_tools(app)

    # TODO: Add when implemented
    # register_planning_tools(app)
    # register_execution_tools(app)

    logger.info("Sunwell MCP tools registered successfully")


__all__ = ["register_all_tools"]
