"""MCP event stream and status tools for external observability.

Exposes read-only views of system state so MCP clients can observe
the multi-agent system's behavior: active goals, worker status,
error budget, and recent events.

This maps to the Cursor article's emphasis on observability being
critical for understanding multi-agent behavior.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.mcp.formatting import mcp_json, omit_empty

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from sunwell.mcp.runtime import MCPRuntime

logger = logging.getLogger(__name__)


def register_events_tools(mcp: FastMCP, runtime: MCPRuntime | None = None) -> None:
    """Register event and status tools for MCP observability.

    Args:
        mcp: FastMCP server instance
        runtime: Shared MCPRuntime for workspace resolution and subsystem access
    """

    @mcp.tool()
    def sunwell_status() -> str:
        """
        Get current system status and health indicators.

        Returns a comprehensive view of the self-driving system's state:
        - Active goals and their status
        - Worker claims and heartbeat status
        - Error budget (if convergence mode is active)
        - Dead letter queue (tasks that repeatedly failed)
        - File conflict warnings

        Use this for observability into the multi-agent system.

        Returns:
            JSON with system status including:
            - backlog: Goal counts by state
            - workers: Active claims and heartbeat info
            - error_budget: Current error rate and threshold
            - dead_letters: Tasks shelved after repeated failures
            - conflicts: File conflict warnings between workers
            - health: Overall system health assessment
        """
        try:
            workspace = runtime.resolve_workspace() if runtime else Path.cwd()

            # Use runtime-cached backlog or create fresh
            manager = runtime.backlog if runtime else None
            if manager is None:
                from sunwell.features.backlog.manager import BacklogManager
                manager = BacklogManager(root=workspace)

            # Gather backlog stats
            total_goals = len(manager.backlog.goals)
            completed = len(manager.backlog.completed)
            blocked = len(manager.backlog.blocked)
            in_progress = manager.backlog.in_progress

            # Count claimed goals
            claims = manager.get_claims()
            claimed_count = len(claims)
            pending_count = total_goals - completed - blocked

            # Check for stale claims (>5 min without heartbeat)
            stale_claims: list[dict] = []
            now = datetime.now()
            for goal_id, goal in manager.backlog.goals.items():
                if goal.claimed_by is not None and goal.claimed_at is not None:
                    elapsed = (now - goal.claimed_at).total_seconds()
                    if elapsed > 300:  # 5 minutes
                        stale_claims.append({
                            "goal_id": goal_id,
                            "worker_id": goal.claimed_by,
                            "elapsed_seconds": int(elapsed),
                        })

            # Get dead letter queue info
            dead_letter_info: dict = {"count": 0, "entries": []}
            try:
                from sunwell.agent.coordination.parallel_executor import (
                    get_dead_letter_queue,
                )
                dlq = get_dead_letter_queue()
                dead_letter_info = {
                    "count": dlq.count,
                    "entries": dlq.get_for_replanning()[:5],  # Last 5
                }
            except Exception:
                pass  # DLQ not initialized

            # Get convergence/error budget info
            error_budget_info: dict | None = None
            try:
                from sunwell.agent.convergence.reconciler import Reconciler
                # Check if a reconciler state file exists
                from sunwell.knowledge.project.state import resolve_state_dir
                reconciler_state = resolve_state_dir(workspace) / "convergence_state.json"
                if reconciler_state.exists():
                    import json as json_mod
                    state = json_mod.loads(reconciler_state.read_text())
                    error_budget_info = state.get("error_budget")
            except Exception:
                pass

            # Detect conflicts
            conflicts = manager.detect_conflicts()

            # Assess health
            health = "healthy"
            health_issues: list[str] = []

            if stale_claims:
                health = "degraded"
                health_issues.append(
                    f"{len(stale_claims)} stale claims (>5min without heartbeat)"
                )

            if dead_letter_info["count"] > 5:
                health = "degraded"
                health_issues.append(
                    f"{dead_letter_info['count']} tasks in dead letter queue"
                )

            if conflicts:
                health_issues.append(
                    f"{len(conflicts)} file conflicts between workers"
                )

            if error_budget_info and not error_budget_info.get("within_budget", True):
                health = "unhealthy"
                health_issues.append("Error rate exceeds threshold")

            # Read pending handoffs count
            handoff_count = 0
            from sunwell.knowledge.project.state import resolve_state_dir
            handoff_path = resolve_state_dir(workspace) / "backlog" / "handoffs.jsonl"
            if handoff_path.exists():
                try:
                    handoff_count = sum(1 for _ in handoff_path.open())
                except OSError:
                    pass

            return mcp_json(omit_empty({
                "backlog": {
                    "total_goals": total_goals,
                    "completed": completed,
                    "blocked": blocked,
                    "pending": pending_count,
                    "in_progress": in_progress,
                },
                "workers": omit_empty({
                    "active_claims": claimed_count,
                    "claims": {
                        goal_id: worker_id
                        for goal_id, worker_id in claims.items()
                    },
                    "stale_claims": stale_claims if stale_claims else None,
                }),
                "error_budget": error_budget_info,
                "dead_letters": dead_letter_info if dead_letter_info["count"] > 0 else None,
                "conflicts": conflicts if conflicts else None,
                "handoffs_pending": handoff_count if handoff_count > 0 else None,
                "health": health,
                "health_issues": health_issues if health_issues else None,
                "timestamp": datetime.now().isoformat(),
            }), "compact")

        except Exception as e:
            return mcp_json({
                "error": str(e),
                "health": "unknown",
            }, "compact")

    @mcp.tool()
    def sunwell_events(
        limit: int = 20,
        event_type: str = "",
    ) -> str:
        """
        Get recent events from the autonomous system.

        Returns recent events for observability: goal completions,
        handoff submissions, worker claims, validation results, etc.

        Args:
            limit: Maximum events to return (default: 20)
            event_type: Filter by event type (empty = all types).
                Types: "handoff", "completion", "claim", "release", "error"

        Returns:
            JSON with recent events list, each containing:
            - type: Event type
            - timestamp: When the event occurred
            - data: Event-specific data
        """
        try:
            workspace = runtime.resolve_workspace() if runtime else Path.cwd()
            events: list[dict] = []

            # Read handoff events
            if not event_type or event_type == "handoff":
                from sunwell.knowledge.project.state import resolve_state_dir
                handoff_path = resolve_state_dir(workspace) / "backlog" / "handoffs.jsonl"
                if handoff_path.exists():
                    try:
                        from sunwell.foundation.utils import safe_jsonl_load
                        for entry in safe_jsonl_load(handoff_path):
                            events.append({
                                "type": "handoff",
                                "timestamp": entry.get("timestamp", ""),
                                "data": {
                                    "task_id": entry.get("task_id"),
                                    "worker_id": entry.get("worker_id"),
                                    "success": entry.get("success"),
                                    "summary": entry.get("summary", "")[:200],
                                    "findings_count": len(entry.get("findings", [])),
                                    "concerns_count": len(entry.get("concerns", [])),
                                },
                            })
                    except Exception:
                        pass

            # Read completion events
            if not event_type or event_type == "completion":
                from sunwell.knowledge.project.state import resolve_state_dir
                completion_path = resolve_state_dir(workspace) / "backlog" / "completed.jsonl"
                if completion_path.exists():
                    try:
                        from sunwell.foundation.utils import safe_jsonl_load
                        for entry in safe_jsonl_load(completion_path):
                            events.append({
                                "type": "completion",
                                "timestamp": entry.get("timestamp", ""),
                                "data": {
                                    "goal_id": entry.get("goal_id"),
                                    "success": entry.get("success"),
                                    "duration_seconds": entry.get("duration_seconds"),
                                    "files_changed": entry.get("files_changed", [])[:5],
                                },
                            })
                    except Exception:
                        pass

            # Sort by timestamp (most recent first)
            events.sort(
                key=lambda e: e.get("timestamp", ""),
                reverse=True,
            )

            # Apply limit
            events = events[:limit]

            return mcp_json({
                "events": events,
                "total_returned": len(events),
            }, "compact")

        except Exception as e:
            return mcp_json({"error": str(e)}, "compact")
