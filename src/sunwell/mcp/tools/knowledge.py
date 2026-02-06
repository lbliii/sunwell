"""MCP knowledge tools for Sunwell.

Provides tools for semantic search, question answering,
codebase intelligence, and workspace discovery.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register_knowledge_tools(mcp: FastMCP, workspace: str | None = None) -> None:
    """Register knowledge-related tools.

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
    def sunwell_search(
        query: str,
        project: str | None = None,
        max_results: int = 10,
        scope: str = "all",
    ) -> str:
        """
        Semantic search across the indexed codebase.

        Uses Sunwell's indexing service for RAG-quality retrieval.
        Returns ranked code chunks with relevance scores.

        Scopes:
        - "all": Search everything
        - "code": Only source code files
        - "docs": Only documentation files

        Args:
            query: Natural language search query
            project: Optional project path
            max_results: Maximum results to return (default: 10)
            scope: Search scope (default: all)

        Returns:
            JSON with ranked search results including file paths, content, and scores
        """
        import asyncio

        try:
            from sunwell.knowledge.indexing import IndexingService

            ws = _resolve_workspace(project)
            indexer = IndexingService(workspace_root=ws)

            # Start indexer, wait for ready, then query
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(indexer.start())
                loop.run_until_complete(indexer.wait_ready(timeout=30.0))
                results = loop.run_until_complete(
                    indexer.query(query, top_k=max_results, threshold=0.3)
                )
            finally:
                loop.run_until_complete(indexer.stop())
                loop.close()

            # Filter by scope
            filtered = []
            for r in results:
                path_str = str(getattr(r, "path", getattr(r, "file_path", "")))
                if scope == "code" and any(
                    path_str.endswith(ext)
                    for ext in (".md", ".rst", ".txt", ".adoc")
                ):
                    continue
                if scope == "docs" and not any(
                    path_str.endswith(ext)
                    for ext in (".md", ".rst", ".txt", ".adoc")
                ):
                    continue
                filtered.append(r)

            return json.dumps(
                {
                    "query": query,
                    "scope": scope,
                    "total_results": len(filtered),
                    "results": [
                        {
                            "path": str(getattr(r, "path", getattr(r, "file_path", "unknown"))),
                            "content": getattr(r, "content", getattr(r, "text", ""))[:500],
                            "score": round(getattr(r, "score", 0.0), 3),
                            "start_line": getattr(r, "start_line", None),
                            "end_line": getattr(r, "end_line", None),
                            "signature": getattr(r, "signature", None),
                        }
                        for r in filtered[:max_results]
                    ],
                },
                indent=2,
                default=str,
            )
        except Exception as e:
            return json.dumps({"error": str(e), "query": query}, indent=2)

    @mcp.tool()
    def sunwell_ask(
        question: str,
        project: str | None = None,
        max_sources: int = 5,
    ) -> str:
        """
        Answer a question about the codebase using synthesized knowledge.

        Uses Sunwell's answer_question system (RFC-135) to provide a synthesized
        answer with source references. More comprehensive than raw search -
        it reads, understands, and composes an answer.

        Args:
            question: Natural language question about the codebase
            project: Optional project path
            max_sources: Maximum source files to consider (default: 5)

        Returns:
            JSON with synthesized answer, source references, and confidence
        """
        import asyncio

        try:
            from sunwell.knowledge.answering import answer_question
            from sunwell.models.registry.registry import resolve_model

            ws = _resolve_workspace(project)
            model = resolve_model("default")

            if not model:
                return json.dumps(
                    {
                        "error": "No model available for question answering",
                        "hint": "Configure a model in sunwell config",
                    },
                    indent=2,
                )

            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(
                    answer_question(
                        question=question,
                        workspace=ws,
                        model=model,
                        max_sources=max_sources,
                    )
                )
            finally:
                loop.close()

            if not result:
                return json.dumps(
                    {
                        "question": question,
                        "status": "no_answer",
                        "message": "Could not find enough context to answer this question.",
                    },
                    indent=2,
                )

            return json.dumps(
                {
                    "question": question,
                    "answer": result.answer,
                    "sources": list(result.sources),
                    "confidence": round(result.confidence, 3),
                    "context_used": result.context_used[:1000] if result.context_used else None,
                },
                indent=2,
            )
        except Exception as e:
            return json.dumps({"error": str(e), "question": question}, indent=2)

    @mcp.tool()
    def sunwell_codebase(
        project: str | None = None,
        aspect: str = "structure",
    ) -> str:
        """
        Get codebase intelligence for a project.

        Provides structural understanding of the codebase including
        call graphs, class hierarchies, hot paths, and error-prone areas.

        Aspects:
        - "structure": Overall project structure and key components
        - "hotpaths": Most frequently called/imported code paths
        - "errors": Error-prone locations and common failure patterns
        - "patterns": Detected code patterns and conventions

        Args:
            project: Optional project path
            aspect: What aspect of the codebase to analyze (default: structure)

        Returns:
            JSON with codebase intelligence for the requested aspect
        """
        try:
            from sunwell.knowledge.codebase import CodebaseGraph

            ws = _resolve_workspace(project)
            graph = CodebaseGraph.load(ws)

            if not graph:
                return json.dumps(
                    {
                        "status": "no_graph",
                        "workspace": str(ws),
                        "message": "No codebase graph found. Run `sunwell scan` first.",
                    },
                    indent=2,
                )

            result: dict = {"workspace": str(ws), "aspect": aspect}

            if aspect == "structure":
                result["nodes"] = getattr(graph, "node_count", None)
                result["edges"] = getattr(graph, "edge_count", None)

                # Get key entry points and modules
                if hasattr(graph, "get_entry_points"):
                    result["entry_points"] = graph.get_entry_points()
                if hasattr(graph, "get_modules"):
                    result["modules"] = graph.get_modules()[:20]
                if hasattr(graph, "get_classes"):
                    classes = graph.get_classes()
                    result["classes"] = [str(c) for c in classes[:20]]
                if hasattr(graph, "concept_clusters"):
                    result["concept_clusters"] = [
                        str(c) for c in graph.concept_clusters[:10]
                    ]

            elif aspect == "hotpaths":
                if hasattr(graph, "hot_paths"):
                    result["hot_paths"] = [str(p) for p in graph.hot_paths[:15]]
                if hasattr(graph, "get_most_imported"):
                    result["most_imported"] = graph.get_most_imported(limit=15)

            elif aspect == "errors":
                if hasattr(graph, "error_prone"):
                    result["error_prone"] = [str(e) for e in graph.error_prone[:15]]
                if hasattr(graph, "get_complex_functions"):
                    result["complex_functions"] = graph.get_complex_functions(limit=15)

            elif aspect == "patterns":
                if hasattr(graph, "patterns"):
                    result["patterns"] = [str(p) for p in graph.patterns[:15]]
                if hasattr(graph, "naming_conventions"):
                    result["naming_conventions"] = graph.naming_conventions

            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)}, indent=2)

    @mcp.tool()
    def sunwell_workspace(format: str = "compact") -> str:
        """
        List known projects and their metadata.

        Discovers projects in the workspace and returns their metadata
        including paths, roles, and project types.

        Formats:
        - "minimal": Just project names and paths
        - "compact": Full metadata (default)

        Args:
            format: Output format (default: compact)

        Returns:
            JSON with discovered projects and metadata
        """
        try:
            ws = _resolve_workspace()
            projects: list[dict] = []

            # Try workspace registry first
            try:
                from sunwell.knowledge.workspace import WorkspaceRegistry

                registry = WorkspaceRegistry()
                workspaces = registry.list_workspaces()
                for ws_entry in workspaces:
                    for proj in ws_entry.projects:
                        entry: dict = {
                            "id": proj.id,
                            "path": str(proj.path),
                        }
                        if format != "minimal":
                            entry["role"] = proj.role.value if hasattr(proj.role, "value") else str(proj.role)
                            entry["is_primary"] = proj.is_primary
                        projects.append(entry)
            except Exception:
                pass

            # Fallback: scan for common project markers
            if not projects:
                markers = [
                    "pyproject.toml", "package.json", "Cargo.toml",
                    "go.mod", "pom.xml", "build.gradle",
                ]
                for marker in markers:
                    if (ws / marker).exists():
                        projects.append({
                            "id": ws.name,
                            "path": str(ws),
                            "role": "primary",
                            "is_primary": True,
                            "detected_by": marker,
                        })
                        break

            return json.dumps(
                {
                    "projects": projects,
                    "total": len(projects),
                    "workspace_root": str(ws),
                    "format": format,
                },
                indent=2,
            )
        except Exception as e:
            return json.dumps({"error": str(e)}, indent=2)
