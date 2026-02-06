"""MCP mirror/introspection tools for Sunwell.

Provides tools for self-introspection and team knowledge access:
learnings, patterns, dead ends, and team decisions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register_mirror_tools(mcp: FastMCP, workspace: str | None = None) -> None:
    """Register mirror/introspection-related tools.

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
    def sunwell_mirror(
        aspect: str = "all",
        project: str | None = None,
        limit: int = 10,
    ) -> str:
        """
        Self-introspection snapshot of Sunwell's accumulated knowledge.

        Returns learnings, dead ends, patterns, and proposals from Sunwell's
        mirror system. This is the agent's own self-model - what it has
        learned about itself, its patterns, and areas for improvement.

        Aspects:
        - "all": Everything (may be large)
        - "learnings": Extracted learnings and insights
        - "patterns": Detected behavior patterns (error patterns, latency, tool usage)
        - "deadends": Known dead ends and failed approaches
        - "errors": Recent errors and error patterns

        Args:
            aspect: What aspect of self-knowledge to retrieve (default: all)
            project: Optional project path
            limit: Max items per category (default: 10)

        Returns:
            JSON with self-introspection data for the requested aspect
        """
        try:
            from sunwell.memory.facade import PersistentMemory

            ws = _resolve_workspace(project)
            memory = PersistentMemory.load(ws)
            result: dict = {"aspect": aspect, "workspace": str(ws)}

            # Learnings from simulacrum
            if aspect in ("all", "learnings") and memory.simulacrum:
                try:
                    from sunwell.features.mirror.introspection import simulacrum_get_learnings

                    learnings = simulacrum_get_learnings(memory.simulacrum)
                    result["learnings"] = learnings[:limit]
                    result["total_learnings"] = len(learnings)
                except Exception as e:
                    result["learnings_error"] = str(e)
                    # Fallback: try direct access
                    try:
                        dag = memory.simulacrum.get_dag()
                        all_learnings = dag.get_learnings()
                        result["learnings"] = [
                            {
                                "fact": l.fact if hasattr(l, "fact") else str(l),
                                "category": getattr(l, "category", None),
                                "confidence": getattr(l, "confidence", None),
                                "use_count": getattr(l, "use_count", 0),
                            }
                            for l in all_learnings[:limit]
                        ]
                        result["total_learnings"] = len(all_learnings)
                    except Exception:
                        pass

            # Dead ends
            if aspect in ("all", "deadends") and memory.simulacrum:
                try:
                    from sunwell.features.mirror.introspection import simulacrum_get_dead_ends

                    dead_ends = simulacrum_get_dead_ends(memory.simulacrum)
                    result["dead_ends"] = dead_ends[:limit]
                    result["total_dead_ends"] = len(dead_ends)
                except Exception as e:
                    result["dead_ends_error"] = str(e)
                    # Fallback
                    try:
                        dead_ends = memory.simulacrum.get_dead_ends()
                        result["dead_ends"] = [str(de) for de in dead_ends[:limit]]
                        result["total_dead_ends"] = len(dead_ends)
                    except Exception:
                        pass

            # Patterns from pattern profile
            if aspect in ("all", "patterns") and memory.patterns:
                try:
                    result["patterns"] = {
                        "naming_conventions": getattr(memory.patterns, "naming_conventions", None),
                        "docstring_style": getattr(memory.patterns, "docstring_style", None),
                        "import_style": getattr(memory.patterns, "import_style", None),
                    }
                except Exception as e:
                    result["patterns_error"] = str(e)

            # Failure memory
            if aspect in ("all", "errors") and memory.failures:
                try:
                    result["failure_count"] = memory.failure_count
                except Exception as e:
                    result["errors_error"] = str(e)

            # Decision memory
            if aspect in ("all", "learnings") and memory.decisions:
                try:
                    result["decision_count"] = memory.decision_count
                except Exception as e:
                    result["decisions_error"] = str(e)

            # Summary counts
            result["counts"] = {
                "learnings": memory.learning_count,
                "decisions": memory.decision_count,
                "failures": memory.failure_count,
                "has_simulacrum": memory.simulacrum is not None,
                "has_patterns": memory.patterns is not None,
                "has_team": memory.team is not None,
            }

            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)}, indent=2)

    @mcp.tool()
    def sunwell_team(
        query: str,
        scope: str = "all",
        project: str | None = None,
        limit: int = 10,
    ) -> str:
        """
        Query the team knowledge store.

        Accesses accumulated team intelligence including architectural decisions,
        known failures, code ownership, and patterns. This is the shared
        knowledge that persists across team members and sessions.

        Scopes:
        - "all": Search across all team knowledge
        - "decisions": Architectural and design decisions
        - "failures": Known failures and things that didn't work
        - "ownership": File and module ownership information
        - "patterns": Team-level patterns and conventions

        Args:
            query: What to search for in team knowledge
            scope: Knowledge scope to search (default: all)
            project: Optional project path
            limit: Max results per category (default: 10)

        Returns:
            JSON with team knowledge organized by category
        """
        import asyncio

        try:
            from sunwell.memory.facade import PersistentMemory

            ws = _resolve_workspace(project)
            memory = PersistentMemory.load(ws)

            if not memory.team:
                return json.dumps(
                    {
                        "status": "no_team_store",
                        "message": "No team knowledge store available for this workspace.",
                        "hint": "Team knowledge is built up over time as Sunwell works in the project.",
                    },
                    indent=2,
                )

            result: dict = {"query": query, "scope": scope}

            # Get relevant context
            try:
                loop = asyncio.new_event_loop()
                try:
                    context = loop.run_until_complete(
                        memory.team.get_relevant_context(query)
                    )
                finally:
                    loop.close()

                if context:
                    result["context"] = str(context)[:2000]
            except Exception as e:
                result["context_error"] = str(e)

            # File-specific knowledge
            if scope in ("all", "ownership"):
                try:
                    if hasattr(memory.team, "get_file_context"):
                        loop = asyncio.new_event_loop()
                        try:
                            file_ctx = loop.run_until_complete(
                                memory.team.get_file_context(query)
                            )
                        finally:
                            loop.close()
                        if file_ctx:
                            result["file_context"] = str(file_ctx)[:1000]
                except Exception as e:
                    result["ownership_error"] = str(e)

            # Approach warnings
            try:
                if hasattr(memory.team, "check_approach"):
                    loop = asyncio.new_event_loop()
                    try:
                        warnings = loop.run_until_complete(
                            memory.team.check_approach(query)
                        )
                    finally:
                        loop.close()
                    if warnings:
                        result["warnings"] = [str(w) for w in warnings[:limit]]
            except Exception as e:
                result["warnings_error"] = str(e)

            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)}, indent=2)
