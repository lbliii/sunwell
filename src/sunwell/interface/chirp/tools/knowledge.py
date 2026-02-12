"""Knowledge tools for Chirp MCP integration.

Exposes Sunwell's knowledge base and semantic search via Chirp's @app.tool() decorator.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from chirp import App

logger = logging.getLogger(__name__)


def register_knowledge_tools(app: App) -> None:
    """Register knowledge-related tools with Chirp app.

    Registers:
    - sunwell_search: Semantic search across codebase
    - sunwell_ask: Ask a question about the codebase
    - sunwell_codebase: Get codebase structure and intelligence
    - sunwell_workspace: List known projects

    Args:
        app: Chirp application instance
    """

    @app.tool(
        "sunwell_search",
        description="Semantic search across the codebase using vector embeddings"
    )
    def sunwell_search(
        query: str,
        scope: str = "all",
        limit: int = 10,
        project: str | None = None,
    ) -> dict:
        """Search the codebase semantically.

        Args:
            query: Search query (natural language or keywords)
            scope: Search scope - "all", "code", "docs", "tests"
            limit: Maximum results to return (default: 10)
            project: Optional project path

        Returns:
            Dict with search results
        """
        try:
            # TODO: Integrate with actual KnowledgeService
            # For now, return placeholder
            results = []

            return {
                "query": query,
                "scope": scope,
                "results": results,
                "count": len(results),
                "message": "Knowledge search not yet implemented in Chirp integration",
            }

        except Exception as e:
            logger.error(f"Error searching codebase: {e}")
            return {"error": str(e), "results": []}

    @app.tool(
        "sunwell_ask",
        description="Ask a question about the codebase and get a synthesized answer"
    )
    def sunwell_ask(
        question: str,
        project: str | None = None,
    ) -> dict:
        """Ask a question and get a synthesized answer with sources.

        Args:
            question: Question to ask about the codebase
            project: Optional project path

        Returns:
            Dict with answer and source references
        """
        try:
            # TODO: Integrate with actual KnowledgeService
            return {
                "question": question,
                "answer": "Knowledge Q&A not yet implemented in Chirp integration",
                "sources": [],
                "confidence": 0.0,
            }

        except Exception as e:
            logger.error(f"Error answering question: {e}")
            return {"error": str(e), "answer": None}

    @app.tool(
        "sunwell_codebase",
        description="Get structural intelligence about the codebase"
    )
    def sunwell_codebase(
        aspect: str = "structure",
        project: str | None = None,
    ) -> dict:
        """Get codebase structural intelligence.

        Args:
            aspect: Aspect to query - "structure", "languages", "frameworks", "entry_points"
            project: Optional project path

        Returns:
            Dict with codebase intelligence
        """
        try:
            ws = Path(project).expanduser().resolve() if project else Path.cwd()

            # Basic structure detection
            info = {
                "root": str(ws),
                "aspect": aspect,
            }

            if aspect == "structure":
                # Count basic file types
                python_files = list(ws.rglob("*.py"))
                info.update({
                    "python_files": len(python_files),
                    "has_tests": any("test" in str(p) for p in python_files),
                    "has_src": (ws / "src").exists(),
                    "has_docs": (ws / "docs").exists(),
                })

            elif aspect == "frameworks":
                # Detect common frameworks
                frameworks = []
                if (ws / "pyproject.toml").exists():
                    frameworks.append("poetry/uv")
                if (ws / "setup.py").exists():
                    frameworks.append("setuptools")

                info["frameworks"] = frameworks

            return info

        except Exception as e:
            logger.error(f"Error getting codebase info: {e}")
            return {"error": str(e)}

    @app.tool(
        "sunwell_workspace",
        description="List known projects in Sunwell workspace"
    )
    def sunwell_workspace() -> dict:
        """List all known projects.

        Returns:
            Dict with project list
        """
        try:
            from sunwell.knowledge.project.registry import ProjectRegistry

            registry = ProjectRegistry()
            projects = registry.list_projects()

            formatted = []
            for project in projects:
                formatted.append({
                    "id": project.id,
                    "name": project.name,
                    "root": str(project.root),
                    "active": project.active if hasattr(project, "active") else True,
                })

            return {
                "projects": formatted,
                "count": len(formatted),
            }

        except Exception as e:
            logger.error(f"Error listing workspace projects: {e}")
            return {"error": str(e), "projects": []}

    logger.debug("Registered knowledge tools: sunwell_search, sunwell_ask, sunwell_codebase, sunwell_workspace")
