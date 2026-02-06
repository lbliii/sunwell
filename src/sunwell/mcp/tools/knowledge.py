"""MCP knowledge tools for Sunwell.

Provides tools for semantic search, question answering,
codebase intelligence, and workspace discovery.
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


def register_knowledge_tools(mcp: FastMCP, runtime: MCPRuntime | None = None) -> None:
    """Register knowledge-related tools.

    Args:
        mcp: FastMCP server instance
        runtime: Shared MCPRuntime for workspace resolution and async bridging
    """

    @mcp.tool()
    def sunwell_search(
        query: str,
        project: str | None = None,
        max_results: int = 10,
        scope: str = "all",
        format: str = DEFAULT_FORMAT,
    ) -> str:
        """
        Semantic search across the indexed codebase.

        Uses Sunwell's indexing service for RAG-quality retrieval.
        Returns ranked code chunks with relevance scores.

        Scopes:
        - "all": Search everything
        - "code": Only source code files
        - "docs": Only documentation files

        Formats:
        - "summary": file paths and scores only, no content (~200 tokens)
        - "compact": content truncated to 300 chars (default)
        - "full": content up to 1000 chars

        Args:
            query: Natural language search query
            project: Optional project path
            max_results: Maximum results to return (default: 10)
            scope: Search scope (default: all)
            format: Output format — summary, compact, or full (default: compact)

        Returns:
            JSON with ranked search results including file paths, content, and scores
        """
        fmt = resolve_format(format)

        try:
            from sunwell.knowledge.indexing import IndexingService

            ws = runtime.resolve_workspace(project) if runtime else Path.cwd()
            indexer = IndexingService(workspace_root=ws)

            if not runtime:
                return mcp_json({"error": "Runtime not available for async search"}, fmt)

            # Start indexer, wait for ready, then query
            async def _search():
                await indexer.start()
                await indexer.wait_ready(timeout=30.0)
                try:
                    return await indexer.query(query, top_k=max_results, threshold=0.3)
                finally:
                    await indexer.stop()

            results = runtime.run(_search())

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

            content_limit = 0 if fmt == "summary" else (300 if fmt == "compact" else 1000)

            result_items = []
            for r in filtered[:max_results]:
                item: dict = {
                    "path": str(getattr(r, "path", getattr(r, "file_path", "unknown"))),
                    "score": round(getattr(r, "score", 0.0), 3),
                }
                if content_limit > 0:
                    content = getattr(r, "content", getattr(r, "text", ""))
                    item["content"] = content[:content_limit]
                    item["start_line"] = getattr(r, "start_line", None)
                    item["end_line"] = getattr(r, "end_line", None)
                if fmt == "full":
                    item["signature"] = getattr(r, "signature", None)
                result_items.append(omit_empty(item))

            return mcp_json(
                {"query": query, "scope": scope, "total_results": len(filtered), "results": result_items},
                fmt,
            )
        except Exception as e:
            return mcp_json({"error": str(e), "query": query}, fmt)

    @mcp.tool()
    def sunwell_ask(
        question: str,
        project: str | None = None,
        max_sources: int = 5,
        format: str = DEFAULT_FORMAT,
    ) -> str:
        """
        Answer a question about the codebase using synthesized knowledge.

        Uses Sunwell's answer_question system (RFC-135) to provide a synthesized
        answer with source references.

        Formats:
        - "summary": answer text only (~200 tokens)
        - "compact": answer + sources + confidence (default)
        - "full": answer + sources + confidence + context used

        Args:
            question: Natural language question about the codebase
            project: Optional project path
            max_sources: Maximum source files to consider (default: 5)
            format: Output format — summary, compact, or full (default: compact)

        Returns:
            JSON with synthesized answer, source references, and confidence
        """
        fmt = resolve_format(format)

        try:
            from sunwell.knowledge.answering import answer_question
            from sunwell.models.registry.registry import resolve_model

            ws = runtime.resolve_workspace(project) if runtime else Path.cwd()
            model = resolve_model("default")

            if not model:
                return mcp_json(
                    {"error": "No model available for question answering"},
                    fmt,
                )

            if not runtime:
                return mcp_json({"error": "Runtime not available for async answering"}, fmt)

            result = runtime.run(
                answer_question(
                    question=question,
                    workspace=ws,
                    model=model,
                    max_sources=max_sources,
                )
            )

            if not result:
                return mcp_json(
                    {"question": question, "status": "no_answer", "message": "Could not find enough context."},
                    fmt,
                )

            if fmt == "summary":
                return mcp_json({"answer": result.answer}, fmt)

            data: dict = {
                "question": question,
                "answer": result.answer,
                "sources": list(result.sources),
                "confidence": round(result.confidence, 3),
            }

            if fmt == "full" and result.context_used:
                data["context_used"] = result.context_used[:2000]

            return mcp_json(data, fmt)
        except Exception as e:
            return mcp_json({"error": str(e), "question": question}, fmt)

    @mcp.tool()
    def sunwell_codebase(
        project: str | None = None,
        aspect: str = "structure",
        format: str = DEFAULT_FORMAT,
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

        Formats:
        - "summary": node/edge counts and top-3 lists (~150 tokens)
        - "compact": standard lists capped at 20 items (default)
        - "full": extended lists up to 50 items

        Args:
            project: Optional project path
            aspect: What aspect of the codebase to analyze (default: structure)
            format: Output format — summary, compact, or full (default: compact)

        Returns:
            JSON with codebase intelligence for the requested aspect
        """
        fmt = resolve_format(format)
        list_limit = 3 if fmt == "summary" else (20 if fmt == "compact" else 50)

        try:
            ws = runtime.resolve_workspace(project) if runtime else Path.cwd()

            # Try runtime cache first, then direct load
            graph = runtime.graph if runtime else None
            if graph is None:
                from sunwell.knowledge.codebase import CodebaseGraph
                graph = CodebaseGraph.load(ws)

            if not graph:
                return mcp_json(
                    {"status": "no_graph", "message": "No codebase graph found. Run `sunwell scan` first."},
                    fmt,
                )

            result: dict = {"aspect": aspect}

            if fmt != "summary":
                result["workspace"] = str(ws)

            if aspect == "structure":
                result["nodes"] = getattr(graph, "node_count", None)
                result["edges"] = getattr(graph, "edge_count", None)

                if hasattr(graph, "get_entry_points"):
                    result["entry_points"] = graph.get_entry_points()[:list_limit]
                if hasattr(graph, "get_modules"):
                    result["modules"] = graph.get_modules()[:list_limit]
                if hasattr(graph, "get_classes"):
                    classes = graph.get_classes()
                    result["classes"] = [str(c) for c in classes[:list_limit]]
                if fmt != "summary" and hasattr(graph, "concept_clusters"):
                    result["concept_clusters"] = [
                        str(c) for c in graph.concept_clusters[:list_limit]
                    ]

            elif aspect == "hotpaths":
                if hasattr(graph, "hot_paths"):
                    result["hot_paths"] = [str(p) for p in graph.hot_paths[:list_limit]]
                if hasattr(graph, "get_most_imported"):
                    result["most_imported"] = graph.get_most_imported(limit=list_limit)

            elif aspect == "errors":
                if hasattr(graph, "error_prone"):
                    result["error_prone"] = [str(e) for e in graph.error_prone[:list_limit]]
                if hasattr(graph, "get_complex_functions"):
                    result["complex_functions"] = graph.get_complex_functions(limit=list_limit)

            elif aspect == "patterns":
                if hasattr(graph, "patterns"):
                    result["patterns"] = [str(p) for p in graph.patterns[:list_limit]]
                if hasattr(graph, "naming_conventions"):
                    result["naming_conventions"] = graph.naming_conventions

            return mcp_json(omit_empty(result), fmt)
        except Exception as e:
            return mcp_json({"error": str(e)}, fmt)

    @mcp.tool()
    def sunwell_workspace(format: str = "compact") -> str:
        """
        List known projects and their metadata.

        Formats:
        - "minimal" / "summary": Just project names and paths
        - "compact": Full metadata (default)

        Args:
            format: Output format (default: compact)

        Returns:
            JSON with discovered projects and metadata
        """
        fmt = format.lower() if format else "compact"
        if fmt == "summary":
            fmt = "minimal"

        try:
            ws = runtime.resolve_workspace() if runtime else Path.cwd()
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
                        if fmt != "minimal":
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
                        projects.append(omit_empty({
                            "id": ws.name,
                            "path": str(ws),
                            "role": "primary" if fmt != "minimal" else None,
                            "is_primary": True if fmt != "minimal" else None,
                            "detected_by": marker if fmt != "minimal" else None,
                        }))
                        break

            return mcp_json(
                {"projects": projects, "total": len(projects)},
                fmt if fmt == "minimal" else "compact",
            )
        except Exception as e:
            return mcp_json({"error": str(e)}, "compact")
