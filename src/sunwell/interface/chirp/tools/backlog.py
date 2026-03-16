"""Backlog tools for Chirp MCP integration.

Backlog feature removed in Sunwell reboot. Tools return stub responses.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from chirp import App

logger = logging.getLogger(__name__)

_FEATURE_REMOVED = "Backlog feature removed in Sunwell reboot"


def register_backlog_tools(app: App) -> None:
    """Register backlog-related tools (stubs - feature removed)."""

    @app.tool(
        "sunwell_goals",
        description="List goals from Sunwell's autonomous backlog (stub - feature removed)",
    )
    def sunwell_goals(
        status: str = "all",
        max_results: int = 20,
        project: str | None = None,
    ) -> dict:
        """List goals (stub)."""
        return {"error": _FEATURE_REMOVED, "goals": [], "stats": {}}

    @app.tool(
        "sunwell_goal",
        description="Get goal details (stub - feature removed)",
    )
    def sunwell_goal(goal_id: str, project: str | None = None) -> dict:
        """Get goal details (stub)."""
        return {"error": _FEATURE_REMOVED}

    @app.tool(
        "sunwell_add_goal",
        description="Add goal to backlog (stub - feature removed)",
    )
    def sunwell_add_goal(
        title: str,
        description: str,
        priority: str = "medium",
        project: str | None = None,
    ) -> dict:
        """Add goal (stub)."""
        return {"error": _FEATURE_REMOVED, "success": False}

    @app.tool(
        "sunwell_suggest_goal",
        description="Suggest goals from signals (stub - feature removed)",
    )
    def sunwell_suggest_goal(
        signal: str,
        context: str | None = None,
        project: str | None = None,
    ) -> dict:
        """Suggest goals (stub)."""
        return {"error": _FEATURE_REMOVED, "suggestions": []}

    logger.debug("Registered backlog tool stubs (feature removed)")
