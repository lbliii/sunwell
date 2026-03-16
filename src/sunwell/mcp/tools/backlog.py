"""MCP backlog tools for Sunwell.

Provides two complementary tool surfaces for Sunwell's autonomous backlog:

1. **Read-only exploration** — Browse goals, inspect detail, generate suggestions.
   Used by any agent that needs to understand what Sunwell is working on.

2. **Multi-agent coordination** — Claim goals, submit handoffs, release claims.
   Used by external worker agents participating in Sunwell's self-driving system.

Together these expose the full backlog intelligence: the goal DAG, dependency
tracking, priority ordering, claim management, and signal-based goal generation.

Inspired by: "Workers pick up tasks and are solely responsible for driving them
to completion. They're unaware of the larger system."
(Cursor self-driving codebases research, Feb 2026)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.mcp.formatting import (
    DEFAULT_FORMAT,
    mcp_json,
    omit_empty,
    resolve_format,
    truncate,
)

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from sunwell.mcp.runtime import MCPRuntime

logger = logging.getLogger(__name__)


def register_backlog_tools(mcp: FastMCP, runtime: MCPRuntime | None = None) -> None:
    """Register backlog-related MCP tools.

    Registers both read-only exploration tools and multi-agent coordination
    tools for the autonomous backlog.

    Args:
        mcp: FastMCP server instance
        runtime: Shared MCPRuntime for workspace resolution and subsystem access
    """

    def _get_manager(project: str | None = None):
        """Get BacklogManager — prefer runtime cache, else create fresh."""
        if runtime:
            # For project overrides, create a new manager if project differs
            if project:
                ws = runtime.resolve_workspace(project)
                if ws != runtime.workspace:
                    from sunwell.features.backlog.manager import BacklogManager
                    return BacklogManager(root=ws)
            return runtime.backlog
        # Fallback: no runtime
        from sunwell.features.backlog.manager import BacklogManager
        ws = Path(project).expanduser().resolve() if project else Path.cwd()
        return BacklogManager(root=ws)

    # ------------------------------------------------------------------
    # Read-only exploration tools (MCP surface design)
    # ------------------------------------------------------------------

    @mcp.tool()
    def sunwell_goals(
        status: str = "all",
        max_results: int = 20,
        project: str | None = None,
        format: str = DEFAULT_FORMAT,
    ) -> str:
        """
        List goals from Sunwell's autonomous backlog.

        Browse the goal DAG with flexible filtering. Goals are returned in
        priority order with dependency info, claim status, and scope limits.

        Formats:
        - "summary": counts by status only, no goal list (~150 tokens)
        - "compact": goals with truncated descriptions (default)
        - "full": goals with full descriptions and scope details

        Args:
            status: Filter - "all" (default), "pending", "claimed", "completed", "blocked"
            max_results: Maximum goals to return (default: 20)
            project: Optional project path
            format: Output format — summary, compact, or full (default: compact)

        Returns:
            JSON with goals list and backlog statistics.
        """
        fmt = resolve_format(format)

        try:
            manager = _get_manager(project)

            blocked = getattr(manager.backlog, "blocked", {})
            stats = {
                "total_goals": len(manager.backlog.goals),
                "completed": len(manager.backlog.completed),
                "blocked": len(blocked),
                "in_progress": manager.backlog.in_progress,
            }

            # Summary: just stats
            if fmt == "summary":
                return mcp_json({"status_filter": status, "backlog_stats": stats}, fmt)

            goals_list = []
            for goal_id, goal in manager.backlog.goals.items():
                # Derive state (stub has no claimed_by/claimed_at; use in_progress)
                is_completed = goal_id in manager.backlog.completed
                is_blocked = goal_id in blocked
                is_claimed = goal_id == manager.backlog.in_progress

                goal_state = (
                    "completed" if is_completed
                    else "blocked" if is_blocked
                    else "claimed" if is_claimed
                    else "pending"
                )

                # Apply filter
                if status != "all" and goal_state != status:
                    continue

                desc_limit = 500 if fmt == "compact" else 0
                produces = getattr(goal, "produces", ())
                entry = omit_empty({
                    "id": goal.id,
                    "title": goal.title,
                    "description": truncate(goal.description, desc_limit) if desc_limit else goal.description,
                    "priority": goal.priority,
                    "category": goal.category,
                    "estimated_complexity": goal.estimated_complexity,
                    "auto_approvable": goal.auto_approvable,
                    "claimed_by": None,  # Stub has no claim tracking
                    "claimed_at": None,
                    "requires": list(goal.requires),
                    "produces": list(produces),
                    "state": goal_state,
                })

                if fmt == "full":
                    entry["scope"] = {
                        "max_files": goal.scope.max_files,
                        "max_lines_changed": goal.scope.max_lines_changed,
                    }

                goals_list.append(entry)

            # Sort by priority (highest first)
            goals_list.sort(key=lambda g: g["priority"], reverse=True)
            goals_list = goals_list[:max_results]

            return mcp_json({
                "goals": goals_list,
                "total": len(goals_list),
                "backlog_stats": stats,
            }, fmt)

        except Exception as e:
            return mcp_json({
                "error": str(e),
                "hint": "Ensure the workspace has a .sunwell/backlog directory",
            }, fmt)

    @mcp.tool()
    def sunwell_goal(
        goal_id: str,
        project: str | None = None,
        format: str = DEFAULT_FORMAT,
    ) -> str:
        """
        Get detailed information about a specific goal.

        Returns the full goal including description (untruncated), dependency
        chain, hierarchy position, progress signals, and claim status.

        Args:
            goal_id: ID of the goal to inspect
            project: Optional project path

        Returns:
            JSON with complete goal detail, dependency tree, and progress info
        """
        fmt = resolve_format(format)

        try:
            manager = _get_manager(project)

            goal = manager.backlog.goals.get(goal_id)
            if goal is None:
                return mcp_json({
                    "error": f"Goal '{goal_id}' not found",
                    "available_goals": list(manager.backlog.goals.keys())[:20],
                }, fmt)

            blocked = getattr(manager.backlog, "blocked", {})
            is_completed = goal_id in manager.backlog.completed
            is_blocked = goal_id in blocked
            is_claimed = goal_id == manager.backlog.in_progress

            goal_state = (
                "completed" if is_completed
                else "blocked" if is_blocked
                else "claimed" if is_claimed
                else "pending"
            )

            # Resolve dependency details
            dependencies = []
            for dep_id in goal.requires:
                dep = manager.backlog.goals.get(dep_id)
                if dep:
                    dep_completed = dep_id in manager.backlog.completed
                    dependencies.append({
                        "id": dep_id,
                        "title": dep.title,
                        "completed": dep_completed,
                    })
                else:
                    dependencies.append({
                        "id": dep_id,
                        "title": "(unknown)",
                        "completed": False,
                    })

            # Find dependents (goals that require this one)
            dependents = []
            for other_id, other in manager.backlog.goals.items():
                if goal_id in other.requires:
                    dependents.append({
                        "id": other_id,
                        "title": other.title,
                    })

            produces = getattr(goal, "produces", ())
            result = {
                "id": goal.id,
                "title": goal.title,
                "description": goal.description,
                "priority": goal.priority,
                "category": goal.category,
                "estimated_complexity": goal.estimated_complexity,
                "auto_approvable": goal.auto_approvable,
                "state": goal_state,
                "claimed_by": None,  # Stub has no claim tracking
                "claimed_at": None,
                "requires": list(goal.requires),
                "produces": list(produces),
                "scope": {
                    "max_files": goal.scope.max_files,
                    "max_lines_changed": goal.scope.max_lines_changed,
                },
                "dependencies": dependencies,
                "dependents": dependents,
                "all_deps_met": all(
                    d["completed"] for d in dependencies
                ),
            }

            return mcp_json(result, fmt)

        except Exception as e:
            return mcp_json({"error": str(e), "goal_id": goal_id}, fmt)

    @mcp.tool()
    def sunwell_suggest_goal(
        signal: str,
        project: str | None = None,
        max_suggestions: int = 5,
    ) -> str:
        """
        Generate goal suggestions from a free-text observation or signal.

        Feed in something you noticed ("tests are flaky", "auth module needs
        refactoring", "documentation is outdated") and Sunwell will decompose
        it into actionable goals using its backlog decomposer.

        Args:
            signal: Free-text observation, idea, or signal
            project: Optional project path
            max_suggestions: Maximum suggestions to return (default: 5)

        Returns:
            JSON with suggested goals including titles, descriptions,
            estimated complexity, and recommended priority
        """
        try:
            # Decomposer removed; return placeholder until feature restored
            return mcp_json({
                "signal": signal,
                "suggestions": [],
                "total": 0,
                "hint": (
                    "Signal decomposition is not available. Add goals explicitly "
                    "with 'sunwell backlog add <goal>' or use sunwell_goals to browse."
                ),
            }, "compact")

        except Exception as e:
            return mcp_json({
                "error": str(e),
                "signal": signal,
                "hint": "Signal decomposition requires an indexed workspace",
            }, "compact")

    # ------------------------------------------------------------------
    # Multi-agent coordination tools (self-driving architecture)
    # ------------------------------------------------------------------

    @mcp.tool()
    def sunwell_claim_goal(goal_id: str, worker_name: str = "mcp-agent") -> str:
        """
        Claim a goal for exclusive work.

        Claims a goal so no other agent works on it simultaneously.
        Returns the full goal context needed to execute independently.

        After claiming, use sunwell_get_goal_context() for rich execution
        context, or work directly from the goal details returned here.

        Args:
            goal_id: ID of the goal to claim
            worker_name: Name of the claiming agent (for tracking)

        Returns:
            JSON with claim result and goal context if successful
        """
        try:
            manager = _get_manager()

            # Use worker hash as ID (stub expects str)
            worker_id = str(hash(worker_name) % 10000)

            if not runtime:
                return mcp_json({"error": "Runtime not available for async claim"}, "compact")

            # Stub: already claimed if in_progress
            if manager.backlog.in_progress and manager.backlog.in_progress != goal_id:
                return mcp_json({
                    "claimed": False,
                    "reason": f"Another goal already in progress",
                }, "compact")

            claimed = runtime.run(manager.claim_goal(goal_id, worker_id=worker_id))

            if not claimed:
                goal = manager.backlog.goals.get(goal_id)
                if goal is None:
                    return mcp_json({
                        "claimed": False,
                        "reason": f"Goal '{goal_id}' not found",
                    }, "compact")
                return mcp_json({
                    "claimed": False,
                    "reason": "Claim failed (unknown reason)",
                }, "compact")

            # Return full goal context for the claiming agent
            goal = manager.backlog.goals[goal_id]
            return mcp_json({
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
            }, "full")

        except Exception as e:
            return mcp_json({"error": str(e)}, "compact")

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
        from sunwell.agent.coordination.handoff import Finding, Handoff

        try:
            manager = _get_manager()

            # Verify goal exists and is claimed (stub: in_progress tracks claim)
            goal = manager.backlog.goals.get(goal_id)
            if goal is None:
                return mcp_json({
                    "accepted": False,
                    "reason": f"Goal '{goal_id}' not found",
                }, "compact")

            if manager.backlog.in_progress != goal_id:
                return mcp_json({
                    "accepted": False,
                    "reason": "Goal is not claimed. Claim it first with sunwell_claim_goal().",
                }, "compact")

            # Parse comma-separated fields
            files_list = [f.strip() for f in files_changed.split(",") if f.strip()] if files_changed else []
            findings_list = [f.strip() for f in findings.split(",") if f.strip()] if findings else []
            concerns_list = [c.strip() for c in concerns.split(",") if c.strip()] if concerns else []
            suggestions_list = [s.strip() for s in suggestions.split(",") if s.strip()] if suggestions else []

            # Create handoff (stub has no claimed_by; use in_progress as worker hint)
            handoff = Handoff(
                task_id=goal_id,
                worker_id="mcp-worker",
                success=success,
                summary=summary,
                artifacts=tuple(files_list),
                findings=tuple(
                    Finding(description=f) for f in findings_list
                ),
                concerns=tuple(concerns_list),
                suggestions=tuple(suggestions_list),
            )

            if not runtime:
                return mcp_json({"error": "Runtime not available for async handoff"}, "compact")

            # Update goal status (stub: complete_goal takes artifacts, not GoalResult)
            if success:
                runtime.run(manager.complete_goal(goal_id, artifacts=tuple(files_list)))
            else:
                runtime.run(manager.mark_failed(goal_id, summary))

            # Store handoff for planner consumption (stub: use root, not backlog_path)
            handoff_dir = manager.root / ".sunwell" / "backlog"
            _store_handoff(handoff_dir, handoff)

            return mcp_json({
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
            }, "compact")

        except Exception as e:
            return mcp_json({"error": str(e)}, "compact")

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
        try:
            manager = _get_manager()

            goal = manager.backlog.goals.get(goal_id)
            if goal is None:
                return mcp_json({
                    "released": False,
                    "reason": f"Goal '{goal_id}' not found",
                }, "compact")

            if manager.backlog.in_progress != goal_id:
                return mcp_json({
                    "released": False,
                    "reason": "Goal is not claimed",
                }, "compact")

            if not runtime:
                return mcp_json({"error": "Runtime not available for async release"}, "compact")

            runtime.run(manager.unclaim_goal(goal_id))

            return mcp_json({
                "released": True,
                "goal_id": goal_id,
                "message": "Goal released and available for other agents.",
            }, "compact")

        except Exception as e:
            return mcp_json({"error": str(e)}, "compact")


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
