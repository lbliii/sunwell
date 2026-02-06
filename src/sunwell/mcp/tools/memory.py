"""MCP memory tools for Sunwell.

Provides tools for accessing Sunwell's memory system:
briefings, persistent learnings, artifact lineage, and session tracking.
"""

from __future__ import annotations

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


def register_memory_tools(mcp: FastMCP, runtime: MCPRuntime | None = None) -> None:
    """Register memory-related tools.

    Args:
        mcp: FastMCP server instance
        runtime: Shared MCPRuntime for workspace resolution and subsystem access
    """

    @mcp.tool()
    def sunwell_briefing(
        project: str | None = None,
        format: str = DEFAULT_FORMAT,
    ) -> str:
        """
        Get the current rolling briefing for a project.

        The briefing is the single most useful context blob for understanding
        where a project stands.

        Formats:
        - "summary": mission, status, next_action, hazard count (~200 tokens)
        - "compact": all fields except prompt_text (~500 tokens, default)
        - "full": everything including injectable prompt_text (~2-5k tokens)

        Args:
            project: Optional project path. Defaults to current workspace.
            format: Output format — summary, compact, or full (default: compact)

        Returns:
            JSON with briefing data or error if no briefing exists
        """
        fmt = resolve_format(format)

        try:
            from sunwell.memory.briefing import Briefing

            ws = runtime.resolve_workspace(project) if runtime else Path.cwd()
            briefing = Briefing.load(ws)

            if not briefing:
                return mcp_json(
                    {"status": "no_briefing", "message": f"No briefing found for {ws}"},
                    fmt,
                )

            status_val = briefing.status.value if hasattr(briefing.status, "value") else str(briefing.status)

            if fmt == "summary":
                return mcp_json(omit_empty({
                    "mission": truncate(briefing.mission, 120),
                    "status": status_val,
                    "next_action": truncate(briefing.next_action, 120),
                    "hazards": len(briefing.hazards),
                    "blockers": len(briefing.blockers),
                    "suggested_lens": briefing.suggested_lens,
                    "complexity_estimate": briefing.complexity_estimate,
                }), fmt)

            # Compact: all fields, no prompt_text
            data = omit_empty({
                "mission": briefing.mission,
                "status": status_val,
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
            })

            if fmt == "full":
                data["prompt_text"] = briefing.to_prompt()

            return mcp_json(data, fmt)
        except Exception as e:
            return mcp_json({"error": str(e)}, fmt)

    @mcp.tool()
    def sunwell_recall(
        query: str,
        scope: str = "all",
        project: str | None = None,
        limit: int = 5,
        format: str = DEFAULT_FORMAT,
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

        Formats:
        - "summary": counts per category only (~100 tokens)
        - "compact": items with facts truncated to 200 chars (default)
        - "full": complete items with full text

        Args:
            query: What to search for in memory
            scope: Memory scope to search (default: all)
            project: Optional project path
            limit: Max results per category (default: 5)
            format: Output format — summary, compact, or full (default: compact)

        Returns:
            JSON with matching memory entries organized by category
        """
        fmt = resolve_format(format)

        try:
            ws = runtime.resolve_workspace(project) if runtime else Path.cwd()
            memory = runtime.memory if runtime else None

            if memory is None:
                from sunwell.memory.facade import PersistentMemory
                memory = PersistentMemory.load(ws)

            counts = {
                "learnings": memory.learning_count,
                "decisions": memory.decision_count,
                "failures": memory.failure_count,
            }

            # Summary: just counts
            if fmt == "summary":
                return mcp_json({"query": query, "scope": scope, "counts": counts}, fmt)

            result: dict = {"query": query, "scope": scope}
            trunc_len = 200 if fmt == "compact" else 0  # 0 = no truncation

            # Query simulacrum store for learnings/dead ends
            if memory.simulacrum and scope in ("all", "learnings", "deadends", "constraints"):
                try:
                    planning_ctx = runtime.run(
                        memory.simulacrum.retrieve_for_planning(query, limit_per_category=limit)
                    ) if runtime else None

                    if planning_ctx:
                        if scope in ("all", "learnings"):
                            learnings = planning_ctx.all_learnings if hasattr(planning_ctx, "all_learnings") else []
                            result["learnings"] = [
                                omit_empty({
                                    "fact": truncate(l.fact, trunc_len) if trunc_len else (l.fact if hasattr(l, "fact") else str(l)),
                                    "confidence": getattr(l, "confidence", None),
                                    "category": getattr(l, "category", None),
                                })
                                for l in learnings[:limit]
                            ]

                        if scope in ("all", "deadends"):
                            dead_ends = memory.simulacrum.get_dead_ends()
                            result["dead_ends"] = [
                                {"description": truncate(str(de), trunc_len) if trunc_len else str(de)}
                                for de in dead_ends[:limit]
                            ]

                        if scope in ("all", "constraints"):
                            all_learnings = planning_ctx.all_learnings if hasattr(planning_ctx, "all_learnings") else []
                            result["constraints"] = [
                                omit_empty({
                                    "fact": truncate(l.fact, trunc_len) if trunc_len else (l.fact if hasattr(l, "fact") else str(l)),
                                    "confidence": getattr(l, "confidence", None),
                                })
                                for l in all_learnings
                                if getattr(l, "category", None) == "constraint"
                            ][:limit]
                except Exception as e:
                    result["simulacrum_error"] = str(e)

            # Query decision memory
            if memory.decisions and scope in ("all", "decisions"):
                try:
                    decisions = runtime.run(
                        memory.decisions.find_relevant_decisions(query, top_k=limit)
                    ) if runtime else []
                    result["decisions"] = [
                        {"decision": truncate(str(d), trunc_len) if trunc_len else str(d)}
                        for d in decisions[:limit]
                    ]
                except Exception as e:
                    result["decisions_error"] = str(e)

            # Query failure memory
            if memory.failures and scope in ("all", "deadends"):
                try:
                    failures = runtime.run(
                        memory.failures.check_similar_failures(query, top_k=limit)
                    ) if runtime else []
                    result["failures"] = [
                        {"failure": truncate(str(f), trunc_len) if trunc_len else str(f)}
                        for f in failures[:limit]
                    ]
                except Exception as e:
                    result["failures_error"] = str(e)

            result["counts"] = counts

            return mcp_json(result, fmt)
        except Exception as e:
            return mcp_json({"error": str(e)}, fmt)

    @mcp.tool()
    def sunwell_lineage(
        file_path: str,
        project: str | None = None,
        format: str = DEFAULT_FORMAT,
    ) -> str:
        """
        Get artifact provenance for a file.

        Shows who created/modified a file, why, and its dependency relationships.
        Useful for understanding the history and impact of a file.

        Args:
            file_path: Path to the file (relative to project or absolute)
            project: Optional project path
            format: Output format — summary, compact, or full (default: compact)

        Returns:
            JSON with creation info, edit history, and dependency graph
        """
        fmt = resolve_format(format)

        try:
            from sunwell.memory.lineage.store import LineageStore

            ws = runtime.resolve_workspace(project) if runtime else Path.cwd()
            store = LineageStore(ws)

            lineage = store.get_by_path(file_path)
            if not lineage:
                return mcp_json(
                    {"status": "no_lineage", "file": file_path, "message": f"No lineage tracked for {file_path}"},
                    fmt,
                )

            dependents = store.get_dependents(file_path)
            dependencies = store.get_dependencies(file_path)

            if fmt == "summary":
                return mcp_json(omit_empty({
                    "file": lineage.path,
                    "created_at": str(lineage.created_at),
                    "human_edited": lineage.human_edited,
                    "edit_count": len(lineage.edits),
                    "import_count": len(lineage.imports),
                    "dependent_count": len(dependents),
                }), fmt)

            data = omit_empty({
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
                    omit_empty({
                        "lines_added": getattr(e, "lines_added", None),
                        "lines_removed": getattr(e, "lines_removed", None),
                        "source": getattr(e, "source", None),
                        "model": getattr(e, "model", None),
                    })
                    for e in lineage.edits
                ],
                "imports": list(lineage.imports),
                "imported_by": list(lineage.imported_by),
                "dependents": dependents,
                "dependencies": dependencies,
            })

            return mcp_json(data, fmt)
        except Exception as e:
            return mcp_json({"error": str(e)}, fmt)

    @mcp.tool()
    def sunwell_session(
        session_id: str | None = None,
        project: str | None = None,
        list_recent: bool = False,
        limit: int = 5,
        format: str = DEFAULT_FORMAT,
    ) -> str:
        """
        Get session context and history.

        Without session_id, returns the most recent session summary.
        With list_recent=True, lists recent session summaries.

        Formats:
        - "summary": session ID, duration, goal/file counts only
        - "compact": core fields without full goal details (default)
        - "full": everything including all goal details and top files

        Args:
            session_id: Specific session ID to retrieve (optional)
            project: Optional project path
            list_recent: If True, list recent sessions instead of getting one
            limit: Max sessions to list (default: 5)
            format: Output format — summary, compact, or full (default: compact)

        Returns:
            JSON with session summary including goals, files, and metrics
        """
        fmt = resolve_format(format)

        try:
            from sunwell.memory.session.tracker import SessionTracker

            ws = runtime.resolve_workspace(project) if runtime else Path.cwd()
            base_path = ws / ".sunwell" / "sessions"

            if list_recent:
                paths = SessionTracker.list_recent(base_path=base_path, limit=limit)
                sessions = []
                for path in paths:
                    try:
                        tracker = SessionTracker.load(path)
                        summary = tracker.get_summary()
                        if fmt == "summary":
                            sessions.append(omit_empty({
                                "session_id": summary.session_id,
                                "goals_completed": summary.goals_completed,
                                "files_modified": summary.files_modified,
                                "total_duration_seconds": summary.total_duration_seconds,
                            }))
                        else:
                            sessions.append(omit_empty({
                                "session_id": summary.session_id,
                                "started_at": str(summary.started_at),
                                "ended_at": str(summary.ended_at) if summary.ended_at else None,
                                "goals_completed": summary.goals_completed,
                                "goals_failed": summary.goals_failed,
                                "files_created": summary.files_created,
                                "files_modified": summary.files_modified,
                                "learnings_added": summary.learnings_added,
                                "total_duration_seconds": summary.total_duration_seconds,
                            }))
                    except Exception:
                        continue
                return mcp_json({"sessions": sessions, "total": len(sessions)}, fmt)

            # Load specific or most recent session
            if session_id:
                session_path = base_path / f"{session_id}.json"
                if not session_path.exists():
                    return mcp_json({"error": f"Session {session_id} not found"}, fmt)
                tracker = SessionTracker.load(session_path)
            else:
                paths = SessionTracker.list_recent(base_path=base_path, limit=1)
                if not paths:
                    return mcp_json({"status": "no_sessions", "message": "No sessions found"}, fmt)
                tracker = SessionTracker.load(paths[0])

            summary = tracker.get_summary()

            if fmt == "summary":
                return mcp_json(omit_empty({
                    "session_id": summary.session_id,
                    "goals_completed": summary.goals_completed,
                    "goals_failed": summary.goals_failed,
                    "files_modified": summary.files_modified,
                    "lines_added": summary.lines_added,
                    "total_duration_seconds": summary.total_duration_seconds,
                }), fmt)

            data = omit_empty({
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
            })

            if fmt == "full":
                data["top_files"] = summary.top_files
                data["goals"] = [
                    omit_empty({
                        "goal_id": g.goal_id if hasattr(g, "goal_id") else str(g),
                        "goal": getattr(g, "goal", None),
                        "status": getattr(g, "status", None),
                    })
                    for g in summary.goals
                ]

            return mcp_json(data, fmt)
        except Exception as e:
            return mcp_json({"error": str(e)}, fmt)
