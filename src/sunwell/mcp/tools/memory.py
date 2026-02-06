"""MCP memory tools for Sunwell.

Provides tools for accessing Sunwell's memory system:
briefings, persistent learnings, artifact lineage, and session tracking.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register_memory_tools(mcp: FastMCP, workspace: str | None = None) -> None:
    """Register memory-related tools.

    Args:
        mcp: FastMCP server instance
        workspace: Optional workspace root path
    """

    def _resolve_workspace(project: str | None = None) -> Path:
        if project:
            p = Path(project).expanduser().resolve()
            if p.exists():
                return p
        if workspace:
            return Path(workspace).expanduser().resolve()
        return Path.cwd()

    @mcp.tool()
    def sunwell_briefing(project: str | None = None) -> str:
        """
        Get the current rolling briefing for a project.

        The briefing is the single most useful context blob for understanding
        where a project stands. It contains:
        - mission: What we're trying to accomplish
        - status: not_started, in_progress, blocked, complete
        - progress: Where we are right now
        - hazards: Things to avoid (max 3)
        - hot_files: Files currently relevant (max 5)
        - predicted_skills: Skills predicted to need next
        - suggested_lens: Best lens for current work
        - complexity_estimate: trivial, moderate, complex, requires_human

        Args:
            project: Optional project path. Defaults to current workspace.

        Returns:
            JSON with briefing data or error if no briefing exists
        """
        try:
            from sunwell.memory.briefing import Briefing

            ws = _resolve_workspace(project)
            briefing = Briefing.load(ws)

            if not briefing:
                return json.dumps(
                    {
                        "status": "no_briefing",
                        "message": f"No briefing found for {ws}",
                        "hint": "A briefing is created after Sunwell runs a goal in this project.",
                    },
                    indent=2,
                )

            return json.dumps(
                {
                    "mission": briefing.mission,
                    "status": briefing.status.value if hasattr(briefing.status, "value") else str(briefing.status),
                    "progress": briefing.progress,
                    "last_action": briefing.last_action,
                    "next_action": briefing.next_action,
                    "hazards": list(briefing.hazards),
                    "blockers": list(briefing.blockers),
                    "hot_files": list(briefing.hot_files),
                    "related_learnings": list(briefing.related_learnings),
                    "predicted_skills": list(briefing.predicted_skills),
                    "suggested_lens": briefing.suggested_lens,
                    "complexity_estimate": briefing.complexity_estimate,
                    "estimated_files_touched": briefing.estimated_files_touched,
                    "updated_at": briefing.updated_at,
                    "session_id": briefing.session_id,
                    "prompt_text": briefing.to_prompt(),
                },
                indent=2,
            )
        except Exception as e:
            return json.dumps({"error": str(e)}, indent=2)

    @mcp.tool()
    def sunwell_recall(
        query: str,
        scope: str = "all",
        project: str | None = None,
        limit: int = 5,
    ) -> str:
        """
        Query persistent memory for learnings, dead ends, and constraints.

        Search through Sunwell's accumulated knowledge from past sessions.
        This helps avoid repeating mistakes and leverage past insights.

        Scopes:
        - "all": Search across all memory types
        - "learnings": Only factual learnings and patterns
        - "deadends": Only failed approaches and dead ends
        - "constraints": Only constraints and guardrails
        - "decisions": Only architectural decisions

        Args:
            query: What to search for in memory
            scope: Memory scope to search (default: all)
            project: Optional project path
            limit: Max results per category (default: 5)

        Returns:
            JSON with matching memory entries organized by category
        """
        import asyncio

        try:
            from sunwell.memory.facade import PersistentMemory

            ws = _resolve_workspace(project)
            memory = PersistentMemory.load(ws)

            result: dict = {"query": query, "scope": scope, "workspace": str(ws)}

            # Query simulacrum store for learnings/dead ends
            if memory.simulacrum and scope in ("all", "learnings", "deadends", "constraints"):
                try:
                    planning_ctx = asyncio.get_event_loop().run_until_complete(
                        memory.simulacrum.retrieve_for_planning(query, limit_per_category=limit)
                    )

                    if scope in ("all", "learnings"):
                        learnings = planning_ctx.all_learnings if hasattr(planning_ctx, "all_learnings") else []
                        result["learnings"] = [
                            {
                                "fact": l.fact if hasattr(l, "fact") else str(l),
                                "confidence": getattr(l, "confidence", None),
                                "category": getattr(l, "category", None),
                            }
                            for l in learnings[:limit]
                        ]

                    if scope in ("all", "deadends"):
                        dead_ends = memory.simulacrum.get_dead_ends()
                        result["dead_ends"] = [
                            {
                                "description": str(de),
                            }
                            for de in dead_ends[:limit]
                        ]

                    if scope in ("all", "constraints"):
                        # Constraints are learnings with category="constraint"
                        all_learnings = planning_ctx.all_learnings if hasattr(planning_ctx, "all_learnings") else []
                        result["constraints"] = [
                            {
                                "fact": l.fact if hasattr(l, "fact") else str(l),
                                "confidence": getattr(l, "confidence", None),
                            }
                            for l in all_learnings
                            if getattr(l, "category", None) == "constraint"
                        ][:limit]
                except Exception as e:
                    result["simulacrum_error"] = str(e)

            # Query decision memory
            if memory.decisions and scope in ("all", "decisions"):
                try:
                    decisions = asyncio.get_event_loop().run_until_complete(
                        memory.decisions.find_relevant_decisions(query, top_k=limit)
                    )
                    result["decisions"] = [
                        {
                            "decision": str(d),
                        }
                        for d in decisions[:limit]
                    ]
                except Exception as e:
                    result["decisions_error"] = str(e)

            # Query failure memory
            if memory.failures and scope in ("all", "deadends"):
                try:
                    failures = asyncio.get_event_loop().run_until_complete(
                        memory.failures.check_similar_failures(query, top_k=limit)
                    )
                    result["failures"] = [
                        {
                            "failure": str(f),
                        }
                        for f in failures[:limit]
                    ]
                except Exception as e:
                    result["failures_error"] = str(e)

            result["counts"] = {
                "learnings": memory.learning_count,
                "decisions": memory.decision_count,
                "failures": memory.failure_count,
            }

            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)}, indent=2)

    @mcp.tool()
    def sunwell_lineage(file_path: str, project: str | None = None) -> str:
        """
        Get artifact provenance for a file.

        Shows who created/modified a file, why, and its dependency relationships.
        Useful for understanding the history and impact of a file.

        Args:
            file_path: Path to the file (relative to project or absolute)
            project: Optional project path

        Returns:
            JSON with creation info, edit history, and dependency graph
        """
        try:
            from sunwell.memory.lineage.store import LineageStore

            ws = _resolve_workspace(project)
            store = LineageStore(ws)

            lineage = store.get_by_path(file_path)
            if not lineage:
                return json.dumps(
                    {
                        "status": "no_lineage",
                        "file": file_path,
                        "message": f"No lineage tracked for {file_path}",
                    },
                    indent=2,
                )

            # Get dependency info
            dependents = store.get_dependents(file_path)
            dependencies = store.get_dependencies(file_path)

            return json.dumps(
                {
                    "file": lineage.path,
                    "artifact_id": lineage.artifact_id,
                    "content_hash": lineage.content_hash,
                    "created_by_goal": lineage.created_by_goal,
                    "created_by_task": lineage.created_by_task,
                    "created_at": str(lineage.created_at),
                    "created_reason": lineage.created_reason,
                    "model": lineage.model,
                    "human_edited": lineage.human_edited,
                    "deleted_at": str(lineage.deleted_at) if lineage.deleted_at else None,
                    "edits": [
                        {
                            "lines_added": getattr(e, "lines_added", None),
                            "lines_removed": getattr(e, "lines_removed", None),
                            "source": getattr(e, "source", None),
                            "model": getattr(e, "model", None),
                        }
                        for e in lineage.edits
                    ],
                    "imports": list(lineage.imports),
                    "imported_by": list(lineage.imported_by),
                    "dependents": dependents,
                    "dependencies": dependencies,
                },
                indent=2,
                default=str,
            )
        except Exception as e:
            return json.dumps({"error": str(e)}, indent=2)

    @mcp.tool()
    def sunwell_session(
        session_id: str | None = None,
        project: str | None = None,
        list_recent: bool = False,
        limit: int = 5,
    ) -> str:
        """
        Get session context and history.

        Without session_id, returns the most recent session summary.
        With list_recent=True, lists recent session summaries.

        Args:
            session_id: Specific session ID to retrieve (optional)
            project: Optional project path
            list_recent: If True, list recent sessions instead of getting one
            limit: Max sessions to list (default: 5)

        Returns:
            JSON with session summary including goals, files, and metrics
        """
        try:
            from sunwell.memory.session.tracker import SessionTracker

            ws = _resolve_workspace(project)
            base_path = ws / ".sunwell" / "sessions"

            if list_recent:
                paths = SessionTracker.list_recent(base_path=base_path, limit=limit)
                sessions = []
                for path in paths:
                    try:
                        tracker = SessionTracker.load(path)
                        summary = tracker.get_summary()
                        sessions.append({
                            "session_id": summary.session_id,
                            "started_at": str(summary.started_at),
                            "ended_at": str(summary.ended_at) if summary.ended_at else None,
                            "goals_completed": summary.goals_completed,
                            "goals_failed": summary.goals_failed,
                            "files_created": summary.files_created,
                            "files_modified": summary.files_modified,
                            "learnings_added": summary.learnings_added,
                            "total_duration_seconds": summary.total_duration_seconds,
                        })
                    except Exception:
                        continue
                return json.dumps({"sessions": sessions, "total": len(sessions)}, indent=2, default=str)

            # Load specific or most recent session
            if session_id:
                session_path = base_path / f"{session_id}.json"
                if not session_path.exists():
                    return json.dumps({"error": f"Session {session_id} not found"}, indent=2)
                tracker = SessionTracker.load(session_path)
            else:
                paths = SessionTracker.list_recent(base_path=base_path, limit=1)
                if not paths:
                    return json.dumps(
                        {"status": "no_sessions", "message": "No sessions found"},
                        indent=2,
                    )
                tracker = SessionTracker.load(paths[0])

            summary = tracker.get_summary()
            return json.dumps(
                {
                    "session_id": summary.session_id,
                    "started_at": str(summary.started_at),
                    "ended_at": str(summary.ended_at) if summary.ended_at else None,
                    "source": summary.source,
                    "goals_started": summary.goals_started,
                    "goals_completed": summary.goals_completed,
                    "goals_failed": summary.goals_failed,
                    "files_created": summary.files_created,
                    "files_modified": summary.files_modified,
                    "files_deleted": summary.files_deleted,
                    "lines_added": summary.lines_added,
                    "lines_removed": summary.lines_removed,
                    "learnings_added": summary.learnings_added,
                    "dead_ends_recorded": summary.dead_ends_recorded,
                    "total_duration_seconds": summary.total_duration_seconds,
                    "planning_seconds": summary.planning_seconds,
                    "execution_seconds": summary.execution_seconds,
                    "top_files": summary.top_files,
                    "goals": [
                        {
                            "goal_id": g.goal_id if hasattr(g, "goal_id") else str(g),
                            "goal": getattr(g, "goal", None),
                            "status": getattr(g, "status", None),
                        }
                        for g in summary.goals
                    ],
                },
                indent=2,
                default=str,
            )
        except Exception as e:
            return json.dumps({"error": str(e)}, indent=2)
