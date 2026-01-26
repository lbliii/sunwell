"""Server-side workspace and memory management (RFC: Architecture Proposal).

Caches PersistentMemory instances per workspace to avoid repeated loading.
Provides unified workspace resolution for all server routes.
"""

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.agent.context.session import SessionContext
    from sunwell.memory import PersistentMemory

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CachedWorkspace:
    """Cached workspace state."""

    workspace: Path
    memory: PersistentMemory
    last_accessed: float
    access_count: int = 0

    def touch(self) -> None:
        """Update access time."""
        self.last_accessed = time.monotonic()
        self.access_count += 1


@dataclass(slots=True)
class WorkspaceManager:
    """Server-side cache for PersistentMemory instances.

    Key features:
    - LRU eviction when cache exceeds max_size
    - TTL-based expiration for stale entries
    - Thread-safe access for parallel requests
    - Lazy loading on first access

    Usage:
        manager = WorkspaceManager()
        memory = await manager.get_memory(workspace_path)
        # memory is cached and reused for subsequent requests
    """

    max_size: int = 10
    """Maximum number of workspaces to cache."""

    ttl_seconds: float = 3600.0
    """Time-to-live for cached entries (1 hour default)."""

    _cache: dict[Path, CachedWorkspace] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def _resolve_workspace_id(self, project_path: Path) -> str | None:
        """Find workspace container for a project.

        Looks up the project in the workspace registry to find
        if it belongs to a multi-project workspace container.

        Args:
            project_path: Path to the project.

        Returns:
            Workspace container ID if found, None otherwise.
        """
        try:
            from sunwell.knowledge.workspace import WorkspaceRegistry

            registry = WorkspaceRegistry()
            ws = registry.find_workspace_for_project(project_path.name)
            return ws.id if ws else None
        except Exception as e:
            logger.debug(f"Could not resolve workspace for {project_path}: {e}")
            return None

    def get_memory(self, workspace: Path) -> PersistentMemory:
        """Get or load PersistentMemory for workspace (sync version)."""
        from sunwell.memory import PersistentMemory

        workspace = workspace.resolve()

        with self._lock:
            # Check cache
            if workspace in self._cache:
                cached = self._cache[workspace]
                # Check TTL
                if time.monotonic() - cached.last_accessed < self.ttl_seconds:
                    cached.touch()
                    logger.debug(f"Cache hit for {workspace}")
                    return cached.memory
                # Expired, remove
                del self._cache[workspace]
                logger.debug(f"Cache expired for {workspace}")

            # Resolve workspace container for workspace-scoped memory
            workspace_id = self._resolve_workspace_id(workspace)

            # Load fresh
            logger.info(f"Loading memory for {workspace} (workspace_id={workspace_id})")
            memory = PersistentMemory.load(workspace, workspace_id=workspace_id)

            # Evict if at capacity
            self._evict_if_needed()

            # Cache
            self._cache[workspace] = CachedWorkspace(
                workspace=workspace,
                memory=memory,
                last_accessed=time.monotonic(),
            )

            return memory

    async def get_memory_async(self, workspace: Path) -> PersistentMemory:
        """Get or load PersistentMemory for workspace (async version)."""
        from sunwell.memory import PersistentMemory

        workspace = workspace.resolve()

        with self._lock:
            # Check cache
            if workspace in self._cache:
                cached = self._cache[workspace]
                if time.monotonic() - cached.last_accessed < self.ttl_seconds:
                    cached.touch()
                    logger.debug(f"Cache hit for {workspace}")
                    return cached.memory
                del self._cache[workspace]
                logger.debug(f"Cache expired for {workspace}")

        # Resolve workspace container for workspace-scoped memory
        workspace_id = self._resolve_workspace_id(workspace)

        # Load outside lock (async)
        logger.info(f"Loading memory async for {workspace} (workspace_id={workspace_id})")
        memory = await PersistentMemory.load_async(workspace, workspace_id=workspace_id)

        # Trigger L1 indexing in background for multi-project workspaces
        if workspace_id:
            self._trigger_l1_indexing(workspace_id)

        with self._lock:
            # Double-check (another request may have loaded)
            if workspace in self._cache:
                # Use the existing one, discard ours
                cached = self._cache[workspace]
                cached.touch()
                return cached.memory

            self._evict_if_needed()

            self._cache[workspace] = CachedWorkspace(
                workspace=workspace,
                memory=memory,
                last_accessed=time.monotonic(),
            )

            return memory

    def _trigger_l1_indexing(self, workspace_id: str) -> None:
        """Trigger L1 signature indexing in the background.

        Non-blocking call that starts L1 indexing for all projects
        in the workspace without waiting for completion.
        """
        try:
            from sunwell.knowledge.workspace import WorkspaceRegistry

            registry = WorkspaceRegistry()
            registry.trigger_l1_indexing_background(workspace_id)
            logger.debug(f"Triggered L1 indexing for workspace {workspace_id}")
        except Exception as e:
            # Don't fail memory loading if indexing fails
            logger.warning(f"Failed to trigger L1 indexing for {workspace_id}: {e}")

    def build_session(
        self,
        workspace: Path,
        goal: str,
        *,
        trust: str = "workspace",
        timeout: int = 300,
        model: str | None = None,
    ) -> SessionContext:
        """Build SessionContext for workspace.

        Convenience method that combines memory loading with session building.
        Automatically resolves workspace container context.
        """
        from sunwell.agent.context.session import SessionContext
        from sunwell.agent.utils.request import RunOptions

        workspace = workspace.resolve()

        # Resolve workspace container for multi-project context
        workspace_id = self._resolve_workspace_id(workspace)

        # Build options
        options = RunOptions(
            trust=trust,
            timeout_seconds=timeout,
            model=model,
        )

        # Build session (this also loads briefing)
        session = SessionContext.build(
            workspace,
            goal,
            options,
            workspace_id=workspace_id,
            project_id=workspace.name,
        )

        return session

    async def build_session_async(
        self,
        workspace: Path,
        goal: str,
        *,
        trust: str = "workspace",
        timeout: int = 300,
        model: str | None = None,
    ) -> tuple[SessionContext, PersistentMemory]:
        """Build SessionContext and load PersistentMemory in parallel.

        Returns both objects ready for Agent.run().
        Automatically resolves workspace container context.
        """
        from sunwell.agent.context.session import SessionContext
        from sunwell.agent.utils.request import RunOptions

        workspace = workspace.resolve()

        # Resolve workspace container for multi-project context
        workspace_id = self._resolve_workspace_id(workspace)

        options = RunOptions(
            trust=trust,
            timeout_seconds=timeout,
            model=model,
        )

        # Load memory and build session in parallel
        memory_task = asyncio.create_task(self.get_memory_async(workspace))

        # Session build is sync but fast, run in executor if needed
        loop = asyncio.get_running_loop()
        session_task = loop.run_in_executor(
            None,
            lambda: SessionContext.build(
                workspace,
                goal,
                options,
                workspace_id=workspace_id,
                project_id=workspace.name,
            ),
        )

        memory, session = await asyncio.gather(memory_task, session_task)

        return session, memory

    def invalidate(self, workspace: Path) -> bool:
        """Invalidate cached memory for workspace.

        Call after external changes to .sunwell/ directory.
        Returns True if entry was cached.
        """
        workspace = workspace.resolve()
        with self._lock:
            if workspace in self._cache:
                del self._cache[workspace]
                logger.info(f"Invalidated cache for {workspace}")
                return True
            return False

    def invalidate_all(self) -> int:
        """Invalidate all cached entries.

        Returns count of invalidated entries.
        """
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"Invalidated {count} cached workspaces")
            return count

    def sync_memory(self, workspace: Path) -> bool:
        """Sync cached memory to disk.

        Returns True if workspace was cached and synced.
        """
        workspace = workspace.resolve()
        with self._lock:
            if workspace not in self._cache:
                return False
            cached = self._cache[workspace]

        # Sync outside lock
        result = cached.memory.sync()
        if not result.success:
            logger.warning(f"Sync failed for {workspace}: {result.results}")
        return result.success

    def stats(self) -> dict[str, int | float]:
        """Get cache statistics."""
        with self._lock:
            total_accesses = sum(c.access_count for c in self._cache.values())
            return {
                "cached_workspaces": len(self._cache),
                "max_size": self.max_size,
                "ttl_seconds": self.ttl_seconds,
                "total_accesses": total_accesses,
            }

    def _evict_if_needed(self) -> None:
        """Evict least recently used entry if at capacity.

        Must be called with lock held.
        """
        if len(self._cache) < self.max_size:
            return

        # Find LRU
        lru_workspace = min(
            self._cache.keys(),
            key=lambda w: self._cache[w].last_accessed,
        )

        # Sync before evicting
        cached = self._cache[lru_workspace]
        try:
            cached.memory.sync()
        except Exception as e:
            logger.error(f"Failed to sync before eviction: {e}")

        del self._cache[lru_workspace]
        logger.info(f"Evicted LRU workspace: {lru_workspace}")


# Global singleton for server use
_workspace_manager: WorkspaceManager | None = None
_manager_lock = threading.Lock()


def get_workspace_manager() -> WorkspaceManager:
    """Get or create the global WorkspaceManager singleton."""
    global _workspace_manager
    if _workspace_manager is None:
        with _manager_lock:
            if _workspace_manager is None:
                _workspace_manager = WorkspaceManager()
    return _workspace_manager
