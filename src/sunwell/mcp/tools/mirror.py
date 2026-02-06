"""MCP mirror/introspection tools for Sunwell.

Provides tools for self-introspection and team knowledge access:
learnings, patterns, dead ends, and team decisions.
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


def register_mirror_tools(mcp: FastMCP, runtime: MCPRuntime | None = None) -> None:
    """Register mirror/introspection-related tools.

    Args:
        mcp: FastMCP server instance
        runtime: Shared MCPRuntime for workspace resolution and subsystem access
    """

    @mcp.tool()
    def sunwell_mirror(
        aspect: str = "all",
        project: str | None = None,
        limit: int = 10,
        format: str = DEFAULT_FORMAT,
    ) -> str:
        """
        Self-introspection snapshot of Sunwell's accumulated knowledge.

        Returns learnings, dead ends, patterns, and proposals from Sunwell's
        mirror system. This is the agent's own self-model.

        Aspects:
        - "all": Everything (may be large)
        - "learnings": Extracted learnings and insights
        - "patterns": Detected behavior patterns
        - "deadends": Known dead ends and failed approaches
        - "errors": Recent errors and error patterns

        Formats:
        - "summary": just counts per category (~100 tokens)
        - "compact": limited items with truncated text (~1k tokens, default)
        - "full": everything untruncated (~5-10k tokens)

        Args:
            aspect: What aspect of self-knowledge to retrieve (default: all)
            project: Optional project path
            limit: Max items per category (default: 10)
            format: Output format — summary, compact, or full (default: compact)

        Returns:
            JSON with self-introspection data for the requested aspect
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
                "has_simulacrum": memory.simulacrum is not None,
                "has_patterns": memory.patterns is not None,
                "has_team": memory.team is not None,
            }

            # Summary: just counts
            if fmt == "summary":
                return mcp_json({"aspect": aspect, "counts": counts}, fmt)

            result: dict = {"aspect": aspect}
            trunc_len = 200 if fmt == "compact" else 0

            # Learnings from simulacrum
            if aspect in ("all", "learnings") and memory.simulacrum:
                try:
                    from sunwell.features.mirror.introspection import simulacrum_get_learnings

                    learnings_raw = simulacrum_get_learnings(memory.simulacrum)
                    result["total_learnings"] = len(learnings_raw)
                    result["learnings"] = learnings_raw[:limit]
                except Exception:
                    # Fallback: direct access
                    try:
                        dag = memory.simulacrum.get_dag()
                        all_learnings = dag.get_learnings()
                        result["total_learnings"] = len(all_learnings)
                        result["learnings"] = [
                            omit_empty({
                                "fact": truncate(l.fact, trunc_len) if trunc_len else (l.fact if hasattr(l, "fact") else str(l)),
                                "category": getattr(l, "category", None),
                                "confidence": getattr(l, "confidence", None),
                                "use_count": getattr(l, "use_count", 0),
                            })
                            for l in all_learnings[:limit]
                        ]
                    except Exception:
                        pass

            # Dead ends
            if aspect in ("all", "deadends") and memory.simulacrum:
                try:
                    from sunwell.features.mirror.introspection import simulacrum_get_dead_ends

                    dead_ends_raw = simulacrum_get_dead_ends(memory.simulacrum)
                    result["total_dead_ends"] = len(dead_ends_raw)
                    result["dead_ends"] = dead_ends_raw[:limit]
                except Exception:
                    try:
                        dead_ends = memory.simulacrum.get_dead_ends()
                        result["total_dead_ends"] = len(dead_ends)
                        result["dead_ends"] = [
                            truncate(str(de), trunc_len) if trunc_len else str(de)
                            for de in dead_ends[:limit]
                        ]
                    except Exception:
                        pass

            # Patterns from pattern profile
            if aspect in ("all", "patterns") and memory.patterns:
                try:
                    result["patterns"] = omit_empty({
                        "naming_conventions": getattr(memory.patterns, "naming_conventions", None),
                        "docstring_style": getattr(memory.patterns, "docstring_style", None),
                        "import_style": getattr(memory.patterns, "import_style", None),
                    })
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

            result["counts"] = counts

            return mcp_json(result, fmt)
        except Exception as e:
            return mcp_json({"error": str(e)}, fmt)

    @mcp.tool()
    def sunwell_team(
        query: str,
        scope: str = "all",
        project: str | None = None,
        limit: int = 10,
        format: str = DEFAULT_FORMAT,
    ) -> str:
        """
        Query the team knowledge store.

        Accesses accumulated team intelligence including architectural decisions,
        known failures, code ownership, and patterns.

        Scopes:
        - "all": Search across all team knowledge
        - "decisions": Architectural and design decisions
        - "failures": Known failures and things that didn't work
        - "ownership": File and module ownership information
        - "patterns": Team-level patterns and conventions

        Formats:
        - "summary": warnings only (~200 tokens)
        - "compact": context truncated to 500 chars (default)
        - "full": context up to 5000 chars

        Args:
            query: What to search for in team knowledge
            scope: Knowledge scope to search (default: all)
            project: Optional project path
            limit: Max results per category (default: 10)
            format: Output format — summary, compact, or full (default: compact)

        Returns:
            JSON with team knowledge organized by category
        """
        fmt = resolve_format(format)

        try:
            ws = runtime.resolve_workspace(project) if runtime else Path.cwd()
            memory = runtime.memory if runtime else None

            if memory is None:
                from sunwell.memory.facade import PersistentMemory
                memory = PersistentMemory.load(ws)

            if not memory.team:
                return mcp_json(
                    {"status": "no_team_store", "message": "No team knowledge store available."},
                    fmt,
                )

            result: dict = {"query": query, "scope": scope}
            ctx_limit = 500 if fmt == "compact" else (5000 if fmt == "full" else 0)

            # Approach warnings (always included, cheapest)
            try:
                if hasattr(memory.team, "check_approach") and runtime:
                    warnings = runtime.run(memory.team.check_approach(query))
                    if warnings:
                        result["warnings"] = [
                            truncate(str(w), 200) for w in warnings[:limit]
                        ]
            except Exception as e:
                result["warnings_error"] = str(e)

            # Summary: just warnings
            if fmt == "summary":
                return mcp_json(result, fmt)

            # Get relevant context
            if ctx_limit > 0 and runtime:
                try:
                    context = runtime.run(memory.team.get_relevant_context(query))
                    if context:
                        result["context"] = str(context)[:ctx_limit]
                except Exception as e:
                    result["context_error"] = str(e)

            # File-specific knowledge
            if scope in ("all", "ownership") and ctx_limit > 0 and runtime:
                try:
                    if hasattr(memory.team, "get_file_context"):
                        file_ctx = runtime.run(memory.team.get_file_context(query))
                        if file_ctx:
                            result["file_context"] = str(file_ctx)[:ctx_limit]
                except Exception as e:
                    result["ownership_error"] = str(e)

            return mcp_json(result, fmt)
        except Exception as e:
            return mcp_json({"error": str(e)}, fmt)
