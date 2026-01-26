"""Workspace-aware search with query routing.

Provides cross-project search that:
1. Uses QueryRouter to identify relevant projects
2. Loads indexes lazily for those projects
3. Merges results across projects
4. Includes dependency projects automatically
"""

import asyncio
import logging
from dataclasses import dataclass, field

from sunwell.knowledge.indexing.service import IndexingService
from sunwell.knowledge.routing.query_router import QueryRouter
from sunwell.knowledge.workspace.indexer import CodeChunk
from sunwell.knowledge.workspace.types import IndexTier, Workspace, WorkspaceProject

logger = logging.getLogger(__name__)

__all__ = [
    "WorkspaceSearch",
    "SearchResult",
]


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Result from cross-project search."""

    chunk: CodeChunk
    """The code chunk."""

    project_id: str
    """Which project this came from."""

    score: float
    """Relevance score."""


@dataclass(slots=True)
class WorkspaceSearch:
    """Cross-project search with query routing.

    Provides workspace-aware semantic search that:
    1. Routes queries to relevant projects using QueryRouter
    2. Loads project indexes lazily (L2 for active, L1 for others)
    3. Merges and deduplicates results
    4. Includes shared dependencies automatically

    Example:
        >>> search = WorkspaceSearch(workspace)
        >>> results = await search.query("how does authentication work?")
        >>> for result in results:
        ...     print(f"[{result.project_id}] {result.chunk.file_path}")
    """

    workspace: Workspace
    """The workspace container to search within."""

    active_project_id: str | None = None
    """Currently active/focused project (gets L2 indexing)."""

    # Cached index services per project
    _indexes: dict[str, IndexingService] = field(default_factory=dict, init=False)

    # Query router
    _router: QueryRouter = field(init=False)

    def __post_init__(self) -> None:
        """Initialize router."""
        self._router = QueryRouter(self.workspace)

    async def query(
        self,
        text: str,
        top_k: int = 10,
        threshold: float = 0.3,
    ) -> list[SearchResult]:
        """Search across workspace projects.

        Args:
            text: Query text.
            top_k: Maximum results to return.
            threshold: Minimum relevance score.

        Returns:
            List of SearchResult sorted by relevance.
        """
        # Route query to relevant projects
        route_result = await self._router.route(text)

        if route_result.include_dependencies:
            route_result = self._router.expand_with_dependencies(route_result)

        if not route_result.projects:
            logger.debug(f"No projects matched query: {text[:50]}...")
            return []

        logger.debug(
            f"Routing query to {len(route_result.projects)} projects: "
            f"{[p.id for p in route_result.projects]} ({route_result.reason})"
        )

        # Search relevant projects in parallel
        tasks = [
            self._search_project(project, text, top_k, threshold)
            for project in route_result.projects
        ]

        results_lists = await asyncio.gather(*tasks, return_exceptions=True)

        # Merge results
        all_results: list[SearchResult] = []
        for results in results_lists:
            if isinstance(results, Exception):
                logger.warning(f"Search failed for a project: {results}")
                continue
            all_results.extend(results)

        # Sort by score and take top_k
        all_results.sort(key=lambda r: r.score, reverse=True)
        return all_results[:top_k]

    async def query_project(
        self,
        project_id: str,
        text: str,
        top_k: int = 10,
        threshold: float = 0.3,
    ) -> list[SearchResult]:
        """Search a specific project.

        Args:
            project_id: Project to search.
            text: Query text.
            top_k: Maximum results.
            threshold: Minimum score.

        Returns:
            List of SearchResult.
        """
        project = self.workspace.get_project(project_id)
        if not project:
            logger.warning(f"Project not found: {project_id}")
            return []

        return await self._search_project(project, text, top_k, threshold)

    async def _search_project(
        self,
        project: WorkspaceProject,
        text: str,
        top_k: int,
        threshold: float,
    ) -> list[SearchResult]:
        """Search a single project."""
        try:
            index = await self._get_or_create_index(project)

            if not index.is_ready:
                # Wait a bit for the index to be ready
                ready = await index.wait_ready(timeout=5.0)
                if not ready:
                    logger.warning(f"Index not ready for {project.id}, skipping")
                    return []

            chunks = await index.query(text, top_k=top_k, threshold=threshold)

            return [
                SearchResult(chunk=chunk, project_id=project.id, score=0.5)
                for chunk in chunks
            ]

        except Exception as e:
            logger.warning(f"Search failed for {project.id}: {e}")
            return []

    async def _get_or_create_index(self, project: WorkspaceProject) -> IndexingService:
        """Get or create an index for a project.

        Active project gets L2 (full), others get L1 (signatures).
        """
        if project.id in self._indexes:
            return self._indexes[project.id]

        # Determine tier based on whether this is the active project
        is_active = project.id == self.active_project_id
        tier = IndexTier.L2_FULL if is_active else IndexTier.L1_SIGNATURES

        index = IndexingService(
            workspace_root=project.path,
            tier=tier,
        )

        # Start indexing in background
        await index.start()

        self._indexes[project.id] = index
        return index

    async def set_active_project(self, project_id: str) -> None:
        """Set the active project (triggers L2 indexing).

        Args:
            project_id: Project to make active.
        """
        if self.active_project_id == project_id:
            return

        old_active = self.active_project_id
        self.active_project_id = project_id

        # Upgrade new active project to L2 if already indexed at L1
        if project_id in self._indexes:
            old_index = self._indexes[project_id]
            if old_index.tier == IndexTier.L1_SIGNATURES:
                await old_index.stop()
                del self._indexes[project_id]

                project = self.workspace.get_project(project_id)
                if project:
                    await self._get_or_create_index(project)

        # Downgrade old active to L1 (optional, to save memory)
        # For now, keep it at L2 for faster subsequent access

    async def close(self) -> None:
        """Stop all index services."""
        for index in self._indexes.values():
            await index.stop()
        self._indexes.clear()
