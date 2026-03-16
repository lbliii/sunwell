"""Memory tools for Chirp MCP integration.

Exposes Sunwell's memory system (briefing, learnings, session history) via Chirp's @app.tool() decorator.
Wired to PersistentMemory when project path is provided.
"""

import asyncio
import logging
from pathlib import Path

from chirp import App

logger = logging.getLogger(__name__)


def _fact(x: object) -> str:
    """Extract fact string from Learning or similar."""
    return getattr(x, "fact", str(x))


def _get_memory(project: str | None):
    """Load PersistentMemory for project, or None if unavailable."""
    if not project:
        return None
    try:
        from sunwell.memory import PersistentMemory

        return PersistentMemory.load(Path(project).expanduser().resolve())
    except Exception as e:
        logger.debug("Failed to load PersistentMemory for %s: %s", project, e)
        return None


def register_memory_tools(app: App) -> None:
    """Register memory-related tools with Chirp app.

    Registers:
    - sunwell_briefing: Get rolling briefing
    - sunwell_recall: Query learnings and insights
    - sunwell_lineage: Get artifact provenance
    - sunwell_session: Get session history

    Args:
        app: Chirp application instance
    """

    @app.tool(
        "sunwell_briefing",
        description="Get Sunwell's rolling briefing with mission status and context"
    )
    def sunwell_briefing(project: str | None = None) -> dict:
        """Get the rolling briefing.

        The briefing provides:
        - Current mission/goal
        - Progress status
        - Key learnings
        - Active constraints/hazards

        Args:
            project: Optional project path

        Returns:
            Dict with briefing content
        """
        try:
            memory = _get_memory(project)
            if not memory:
                return {
                    "mission": "No active mission",
                    "status": "idle",
                    "learnings": [],
                    "constraints": [],
                    "message": "Provide project path to load memory",
                }
            ctx = asyncio.run(
                memory.get_relevant("current mission and context", top_k=5)
            )
            return {
                "mission": "No active mission",
                "status": "idle",
                "learnings": [_fact(l) for l in ctx.learnings[:5]],
                "constraints": list(ctx.constraints[:5]),
                "dead_ends": list(ctx.dead_ends[:3]),
            }
        except Exception as e:
            logger.error(f"Error fetching briefing: {e}")
            return {"error": str(e)}

    @app.tool(
        "sunwell_recall",
        description="Query learnings, dead ends, and insights from memory"
    )
    def sunwell_recall(
        query: str,
        scope: str = "all",
        limit: int = 10,
        project: str | None = None,
    ) -> dict:
        """Recall learnings from memory.

        Args:
            query: Query string (semantic search)
            scope: Scope - "all", "learnings", "dead_ends", "constraints"
            limit: Maximum results (default: 10)
            project: Optional project path

        Returns:
            Dict with recalled memories
        """
        try:
            memory = _get_memory(project)
            if not memory:
                return {
                    "query": query,
                    "scope": scope,
                    "memories": [],
                    "count": 0,
                    "message": "Provide project path to load memory",
                }
            ctx = asyncio.run(memory.get_relevant(query, top_k=limit))
            memories: list[str] = []
            if scope in ("all", "learnings"):
                memories.extend(_fact(l) for l in ctx.learnings[:limit])
            if scope in ("all", "dead_ends"):
                memories.extend(ctx.dead_ends[:limit])
            if scope in ("all", "constraints"):
                memories.extend(ctx.constraints[:limit])
            return {
                "query": query,
                "scope": scope,
                "memories": memories[:limit],
                "count": len(memories),
            }
        except Exception as e:
            logger.error(f"Error recalling memories: {e}")
            return {"error": str(e), "memories": []}

    @app.tool(
        "sunwell_lineage",
        description="Get the creation lineage and provenance of an artifact"
    )
    def sunwell_lineage(
        file_path: str,
        project: str | None = None,
    ) -> dict:
        """Get artifact lineage/provenance.

        Args:
            file_path: Path to artifact (relative to project root)
            project: Optional project path

        Returns:
            Dict with lineage information
        """
        try:
            ws = Path(project).expanduser().resolve() if project else Path.cwd()
            full_path = ws / file_path

            # Basic lineage info
            info = {
                "file": file_path,
                "exists": full_path.exists(),
            }

            if full_path.exists():
                stat = full_path.stat()
                info.update({
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                    "created": stat.st_ctime,
                })

            return info

        except Exception as e:
            logger.error(f"Error getting lineage: {e}")
            return {"error": str(e)}

    @app.tool(
        "sunwell_session",
        description="Get current session history and metrics"
    )
    def sunwell_session(project: str | None = None) -> dict:
        """Get session history.

        Returns:
            Dict with session information
        """
        try:
            memory = _get_memory(project)
            if memory:
                return {
                    "session_id": "unknown",
                    "learning_count": memory.learning_count,
                    "decision_count": memory.decision_count,
                    "failure_count": memory.failure_count,
                }
            return {
                "session_id": "unknown",
                "message": "Provide project path to load memory",
            }
        except Exception as e:
            logger.error(f"Error fetching session: {e}")
            return {"error": str(e)}

    logger.debug("Registered memory tools: sunwell_briefing, sunwell_recall, sunwell_lineage, sunwell_session")
