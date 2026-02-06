"""MCP backlog tools for multi-agent coordination.

Exposes Sunwell's backlog/goal system to external MCP agents (Cursor,
Claude Desktop, etc.), enabling them to participate as workers in the
self-driving system.

External agents can:
- Browse available goals (unclaimed, by priority)
- Claim a goal for exclusive work
- Submit handoffs when done (with findings, concerns, suggestions)
- Release claims when giving up
- Get context needed to execute a goal independently

This makes Sunwell the "planner" and any MCP-capable agent a "worker"
in the recursive planner/subplanner/worker hierarchy.

Inspired by: "Workers pick up tasks and are solely responsible for
driving them to completion. They're unaware of the larger system."
(Cursor self-driving codebases research, Feb 2026)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)


def register_backlog_tools(mcp: FastMCP, workspace_dir: str | None = None) -> None:
    """Register backlog-related MCP tools.

    Args:
        mcp: FastMCP server instance
        workspace_dir: Optional workspace directory for backlog operations
    """

    def _get_workspace() -> Path:
        """Resolve workspace directory."""
        if workspace_dir:
            return Path(workspace_dir)
        return Path.cwd()

    def _get_manager():
        """Get or create BacklogManager for the workspace."""
        from sunwell.features.backlog.manager import BacklogManager

        workspace = _get_workspace()
        return BacklogManager(root=workspace)

    @mcp.tool()
    def sunwell_get_goals(
        state: str = "pending",
        max_results: int = 20,
    ) -> str:
        """
        List available goals from Sunwell's autonomous backlog.

        Browse goals that external agents can claim and work on.
        Goals are returned in priority order with dependency info.

        Args:
            state: Filter by state - "pending" (default), "all", "claimed", "completed", "blocked"
            max_results: Maximum number of goals to return (default: 20)

        Returns:
            JSON with goals list, each containing:
            - id, title, description, priority, category
            - estimated_complexity, scope limits
            - claimed_by (null if unclaimed)
            - requires (dependency goal IDs)
        """
        import asyncio

        try:
            manager = _get_manager()

            goals_list = []
            for goal_id, goal in manager.backlog.goals.items():
                # Filter by state
                is_completed = goal_id in manager.backlog.completed
                is_blocked = goal_id in manager.backlog.blocked
                is_claimed = goal.claimed_by is not None
                is_pending = not is_completed and not is_blocked

                if state == "pending" and not is_pending:
                    continue
                if state == "claimed" and not is_claimed:
                    continue
                if state == "completed" and not is_completed:
                    continue
                if state == "blocked" and not is_blocked:
                    continue

                goals_list.append({
                    "id": goal.id,
                    "title": goal.title,
                    "description": goal.description[:500],
                    "priority": goal.priority,
                    "category": goal.category,
                    "estimated_complexity": goal.estimated_complexity,
                    "auto_approvable": goal.auto_approvable,
                    "claimed_by": goal.claimed_by,
                    "claimed_at": (
                        goal.claimed_at.isoformat() if goal.claimed_at else None
                    ),
                    "requires": list(goal.requires),
                    "produces": list(goal.produces),
                    "scope": {
                        "max_files": goal.scope.max_files,
                        "max_lines_changed": goal.scope.max_lines_changed,
                    },
                    "state": (
                        "completed" if is_completed
                        else "blocked" if is_blocked
                        else "claimed" if is_claimed
                        else "pending"
                    ),
                })

            # Sort by priority (highest first)
            goals_list.sort(key=lambda g: g["priority"], reverse=True)
            goals_list = goals_list[:max_results]

            return json.dumps({
                "goals": goals_list,
                "total": len(goals_list),
                "workspace": str(_get_workspace()),
                "backlog_stats": {
                    "total_goals": len(manager.backlog.goals),
                    "completed": len(manager.backlog.completed),
                    "blocked": len(manager.backlog.blocked),
                    "in_progress": manager.backlog.in_progress,
                },
            }, indent=2)

        except Exception as e:
            return json.dumps({
                "error": str(e),
                "hint": "Ensure the workspace has a .sunwell/backlog directory",
            }, indent=2)

    @mcp.tool()
    def sunwell_claim_goal(goal_id: str, worker_name: str = "mcp-agent") -> str:
        """
        Claim a goal for exclusive work.

        Claims a goal so no other agent works on it simultaneously.
        Returns the full goal context needed to execute independently.

        Args:
            goal_id: ID of the goal to claim
            worker_name: Name of the claiming agent (for tracking)

        Returns:
            JSON with claim result and goal context if successful
        """
        import asyncio

        try:
            manager = _get_manager()

            # Use worker hash as ID
            worker_id = hash(worker_name) % 10000

            # Run claim in event loop
            loop = asyncio.new_event_loop()
            try:
                claimed = loop.run_until_complete(
                    manager.claim_goal(goal_id, worker_id=worker_id)
                )
            finally:
                loop.close()

            if not claimed:
                goal = manager.backlog.goals.get(goal_id)
                if goal is None:
                    return json.dumps({
                        "claimed": False,
                        "reason": f"Goal '{goal_id}' not found",
                    }, indent=2)
                if goal.claimed_by is not None:
                    return json.dumps({
                        "claimed": False,
                        "reason": f"Goal already claimed by worker {goal.claimed_by}",
                    }, indent=2)
                return json.dumps({
                    "claimed": False,
                    "reason": "Claim failed (unknown reason)",
                }, indent=2)

            # Return full goal context for the claiming agent
            goal = manager.backlog.goals[goal_id]
            return json.dumps({
                "claimed": True,
                "goal": {
                    "id": goal.id,
                    "title": goal.title,
                    "description": goal.description,
                    "category": goal.category,
                    "estimated_complexity": goal.estimated_complexity,
                    "requires": list(goal.requires),
                    "produces": list(goal.produces),
                    "scope": {
                        "max_files": goal.scope.max_files,
                        "max_lines_changed": goal.scope.max_lines_changed,
                    },
                },
                "worker_id": worker_id,
                "worker_name": worker_name,
                "instructions": (
                    "You have claimed this goal. Execute it within the scope limits. "
                    "When done, call sunwell_submit_handoff() with your results, "
                    "findings, and any concerns. If you cannot complete it, call "
                    "sunwell_release_goal() to release the claim."
                ),
            }, indent=2)

        except Exception as e:
            return json.dumps({"error": str(e)}, indent=2)

    @mcp.tool()
    def sunwell_submit_handoff(
        goal_id: str,
        success: bool,
        summary: str,
        files_changed: str = "",
        findings: str = "",
        concerns: str = "",
        suggestions: str = "",
    ) -> str:
        """
        Submit a handoff after completing (or failing) a claimed goal.

        Handoffs carry not just the outcome but what was LEARNED:
        findings, concerns, deviations, and suggestions. This enables
        the planner to make informed replanning decisions.

        Args:
            goal_id: ID of the goal this handoff is for
            success: Whether the goal was completed successfully
            summary: Brief summary of what was accomplished
            files_changed: Comma-separated list of files changed
            findings: Comma-separated list of things discovered during execution
            concerns: Comma-separated list of risks or issues to flag
            suggestions: Comma-separated list of ideas for follow-up work

        Returns:
            JSON confirming handoff was received and goal status updated
        """
        import asyncio

        from sunwell.agent.coordination.handoff import Finding, Handoff

        try:
            manager = _get_manager()

            # Verify goal exists and is claimed
            goal = manager.backlog.goals.get(goal_id)
            if goal is None:
                return json.dumps({
                    "accepted": False,
                    "reason": f"Goal '{goal_id}' not found",
                }, indent=2)

            if goal.claimed_by is None:
                return json.dumps({
                    "accepted": False,
                    "reason": "Goal is not claimed. Claim it first with sunwell_claim_goal().",
                }, indent=2)

            # Parse comma-separated fields
            files_list = [f.strip() for f in files_changed.split(",") if f.strip()] if files_changed else []
            findings_list = [f.strip() for f in findings.split(",") if f.strip()] if findings else []
            concerns_list = [c.strip() for c in concerns.split(",") if c.strip()] if concerns else []
            suggestions_list = [s.strip() for s in suggestions.split(",") if s.strip()] if suggestions else []

            # Create handoff
            handoff = Handoff(
                task_id=goal_id,
                worker_id=f"mcp-worker-{goal.claimed_by}",
                success=success,
                summary=summary,
                artifacts=tuple(files_list),
                findings=tuple(
                    Finding(description=f) for f in findings_list
                ),
                concerns=tuple(concerns_list),
                suggestions=tuple(suggestions_list),
            )

            # Update goal status
            loop = asyncio.new_event_loop()
            try:
                if success:
                    from sunwell.features.backlog.goals import GoalResult
                    result = GoalResult(
                        success=True,
                        summary=summary,
                        files_changed=tuple(files_list),
                    )
                    loop.run_until_complete(
                        manager.complete_goal(goal_id, result)
                    )
                else:
                    loop.run_until_complete(
                        manager.mark_failed(goal_id, summary)
                    )
            finally:
                loop.close()

            # Store handoff for planner consumption
            _store_handoff(manager.backlog_path, handoff)

            return json.dumps({
                "accepted": True,
                "goal_id": goal_id,
                "new_status": "completed" if success else "failed",
                "handoff_summary": {
                    "findings_count": len(findings_list),
                    "concerns_count": len(concerns_list),
                    "suggestions_count": len(suggestions_list),
                    "files_changed": len(files_list),
                },
                "message": (
                    "Handoff received. The planner will incorporate your "
                    "findings into the next planning cycle."
                ),
            }, indent=2)

        except Exception as e:
            return json.dumps({"error": str(e)}, indent=2)

    @mcp.tool()
    def sunwell_release_goal(goal_id: str) -> str:
        """
        Release a claimed goal back to the pool.

        Call this when you cannot complete a claimed goal. The goal
        becomes available for other agents to claim.

        Args:
            goal_id: ID of the goal to release

        Returns:
            JSON confirming the release
        """
        import asyncio

        try:
            manager = _get_manager()

            goal = manager.backlog.goals.get(goal_id)
            if goal is None:
                return json.dumps({
                    "released": False,
                    "reason": f"Goal '{goal_id}' not found",
                }, indent=2)

            if goal.claimed_by is None:
                return json.dumps({
                    "released": False,
                    "reason": "Goal is not claimed",
                }, indent=2)

            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(manager.unclaim_goal(goal_id))
            finally:
                loop.close()

            return json.dumps({
                "released": True,
                "goal_id": goal_id,
                "message": "Goal released and available for other agents.",
            }, indent=2)

        except Exception as e:
            return json.dumps({"error": str(e)}, indent=2)


def _store_handoff(backlog_path: Path, handoff) -> None:
    """Store a handoff for planner consumption.

    Handoffs are stored as JSONL in the backlog directory
    so the planner can read them during the next planning cycle.

    Args:
        backlog_path: Path to the backlog directory
        handoff: The Handoff to store
    """
    from sunwell.foundation.utils import safe_jsonl_append

    handoff_path = backlog_path / "handoffs.jsonl"
    safe_jsonl_append(handoff.to_dict(), handoff_path)
