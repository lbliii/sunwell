"""Backlog tools for Chirp MCP integration.

Exposes Sunwell's autonomous backlog system via Chirp's @app.tool() decorator.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from chirp import App

logger = logging.getLogger(__name__)


def register_backlog_tools(app: App) -> None:
    """Register backlog-related tools with Chirp app.

    Registers:
    - sunwell_goals: List goals by status
    - sunwell_goal: Get goal details
    - sunwell_add_goal: Add new goal
    - sunwell_suggest_goal: Generate goal from observation

    Args:
        app: Chirp application instance
    """

    def _get_manager(project: str | None = None):
        """Get BacklogManager instance."""
        from sunwell.features.backlog.manager import BacklogManager

        ws = Path(project).expanduser().resolve() if project else Path.cwd()
        return BacklogManager(root=ws)

    @app.tool(
        "sunwell_goals",
        description="List goals from Sunwell's autonomous backlog with flexible filtering"
    )
    def sunwell_goals(
        status: str = "all",
        max_results: int = 20,
        project: str | None = None,
    ) -> dict:
        """List goals from Sunwell's autonomous backlog.

        Args:
            status: Filter - "all", "pending", "claimed", "completed", "blocked"
            max_results: Maximum goals to return (default: 20)
            project: Optional project path (default: current directory)

        Returns:
            Dict with goals list and statistics
        """
        try:
            manager = _get_manager(project)
            goals = manager.list_goals(status=status if status != "all" else None, limit=max_results)

            # Get statistics
            all_goals = manager.list_goals()
            stats = {
                "total": len(all_goals),
                "pending": len([g for g in all_goals if g.status == "pending"]),
                "in_progress": len([g for g in all_goals if g.status == "in_progress"]),
                "completed": len([g for g in all_goals if g.status == "completed"]),
                "blocked": len([g for g in all_goals if g.blocked_by]),
            }

            # Format goals
            formatted_goals = []
            for goal in goals[:max_results]:
                formatted_goals.append({
                    "id": goal.id,
                    "title": goal.title,
                    "description": goal.description[:200] if goal.description else None,
                    "status": goal.status,
                    "priority": goal.priority,
                    "blocked_by": goal.blocked_by or [],
                    "depends_on": goal.depends_on or [],
                    "created_at": goal.created_at.isoformat() if hasattr(goal, "created_at") else None,
                })

            return {
                "goals": formatted_goals,
                "stats": stats,
                "filter": status,
                "showing": len(formatted_goals),
            }

        except Exception as e:
            logger.error(f"Error listing goals: {e}")
            return {"error": str(e), "goals": [], "stats": {}}

    @app.tool(
        "sunwell_goal",
        description="Get detailed information about a specific goal"
    )
    def sunwell_goal(goal_id: str, project: str | None = None) -> dict:
        """Get goal details including dependencies and scope.

        Args:
            goal_id: Goal identifier
            project: Optional project path

        Returns:
            Dict with goal details
        """
        try:
            manager = _get_manager(project)
            goal = manager.get_goal(goal_id)

            if not goal:
                return {"error": f"Goal not found: {goal_id}"}

            return {
                "id": goal.id,
                "title": goal.title,
                "description": goal.description,
                "status": goal.status,
                "priority": goal.priority,
                "blocked_by": goal.blocked_by or [],
                "depends_on": goal.depends_on or [],
                "scope": {
                    "max_files": goal.scope.max_files if hasattr(goal, "scope") else None,
                    "allowed_paths": goal.scope.allowed_paths if hasattr(goal, "scope") else [],
                    "forbidden_paths": goal.scope.forbidden_paths if hasattr(goal, "scope") else [],
                },
                "created_at": goal.created_at.isoformat() if hasattr(goal, "created_at") else None,
                "updated_at": goal.updated_at.isoformat() if hasattr(goal, "updated_at") else None,
            }

        except Exception as e:
            logger.error(f"Error fetching goal {goal_id}: {e}")
            return {"error": str(e)}

    @app.tool(
        "sunwell_add_goal",
        description="Add a new goal to Sunwell's backlog"
    )
    def sunwell_add_goal(
        title: str,
        description: str,
        priority: str = "medium",
        project: str | None = None,
    ) -> dict:
        """Add a new goal to the backlog.

        Args:
            title: Goal title (concise, actionable)
            description: Detailed description of what needs to be done
            priority: Priority level - "low", "medium", "high", "critical"
            project: Optional project path

        Returns:
            Dict with created goal details
        """
        try:
            manager = _get_manager(project)

            # Create goal
            goal = manager.create_goal(
                title=title,
                description=description,
                priority=priority,
            )

            return {
                "id": goal.id,
                "title": goal.title,
                "description": goal.description,
                "status": goal.status,
                "priority": goal.priority,
                "created_at": goal.created_at.isoformat() if hasattr(goal, "created_at") else None,
                "success": True,
            }

        except Exception as e:
            logger.error(f"Error creating goal: {e}")
            return {"error": str(e), "success": False}

    @app.tool(
        "sunwell_suggest_goal",
        description="Generate goal suggestions from observations or signals"
    )
    def sunwell_suggest_goal(
        signal: str,
        context: str | None = None,
        project: str | None = None,
    ) -> dict:
        """Generate goal suggestions based on observation signal.

        Args:
            signal: Observation or signal (e.g., "high test failure rate")
            context: Optional additional context
            project: Optional project path

        Returns:
            Dict with suggested goals
        """
        try:
            manager = _get_manager(project)

            # Generate suggestions (this would use AI in real impl)
            suggestions = []

            # TODO: Implement actual signal-based goal generation
            # For now, return placeholder
            suggestions.append({
                "title": f"Address: {signal}",
                "description": f"Investigate and resolve: {signal}\n\nContext: {context or 'None provided'}",
                "priority": "medium",
                "reasoning": "Generated from observation signal",
            })

            return {
                "suggestions": suggestions,
                "signal": signal,
                "count": len(suggestions),
            }

        except Exception as e:
            logger.error(f"Error generating goal suggestions: {e}")
            return {"error": str(e), "suggestions": []}

    logger.debug("Registered backlog tools: sunwell_goals, sunwell_goal, sunwell_add_goal, sunwell_suggest_goal")
