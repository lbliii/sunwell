"""MCP Runtime — shared async bridge and subsystem cache.

Created once at server startup, passed to all tool registration functions.
Eliminates per-call event loop creation, workspace resolution duplication,
and repeated subsystem initialization across 25+ MCP tools.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Sentinel to distinguish "not yet loaded" from "loaded but None"
_UNSET: Any = object()


class _LoopThread:
    """Daemon thread owning a persistent asyncio event loop.

    Created once per MCPRuntime. Provides a safe sync-to-async bridge
    via run(), which uses run_coroutine_threadsafe + Future.result().
    """

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._start()

    def _start(self) -> None:
        """Start the daemon thread with a fresh event loop."""
        self._thread = threading.Thread(
            target=self._run_loop,
            name="sunwell-mcp-loop",
            daemon=True,
        )
        self._thread.start()
        # Block until the loop is running
        self._ready.wait(timeout=5.0)

    def _run_loop(self) -> None:
        """Thread target: create loop, signal ready, run forever."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._ready.set()
        self._loop.run_forever()

    def run(self, coro: Any, timeout: float | None = 120.0) -> Any:
        """Submit a coroutine and block until it completes.

        Args:
            coro: An awaitable coroutine
            timeout: Max seconds to wait (default: 120s, None=forever)

        Returns:
            The coroutine's return value

        Raises:
            RuntimeError: If the loop thread is not running
            TimeoutError: If the coroutine exceeds the timeout
            Exception: Any exception raised by the coroutine
        """
        if self._loop is None or self._loop.is_closed():
            raise RuntimeError("MCP async loop is not running")

        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)

    def shutdown(self) -> None:
        """Stop the event loop and join the thread."""
        if self._loop and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._loop.stop)
            # Wait for the thread to finish (loop.stop makes run_forever return)
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=5.0)
            # Close the loop so subsequent run() calls get a clear error
            if not self._loop.is_closed():
                self._loop.close()


class MCPRuntime:
    """Shared runtime for all MCP tools and resources.

    Owns:
    - A persistent event loop thread for async-to-sync bridging
    - Workspace resolution (one implementation for all tools)
    - Lazy-cached subsystem instances (memory, backlog, codebase graph)

    Usage:
        runtime = MCPRuntime(workspace="/path/to/project")
        ws = runtime.resolve_workspace()
        memory = runtime.memory        # lazy, cached
        result = runtime.run(some_async_call())  # safe sync-to-async
    """

    def __init__(self, workspace: str | None = None) -> None:
        self._workspace = (
            Path(workspace).expanduser().resolve() if workspace else Path.cwd()
        )
        self._loop_thread = _LoopThread()

        # Lazy subsystem caches (UNSET = not attempted yet)
        self._memory: Any = _UNSET
        self._backlog: Any = _UNSET
        self._graph: Any = _UNSET

    # ------------------------------------------------------------------
    # Async bridge
    # ------------------------------------------------------------------

    def run(self, coro: Any, timeout: float | None = 120.0) -> Any:
        """Run an async coroutine from sync code.

        Submits the coroutine to the persistent event loop thread
        and blocks until the result is available.

        Args:
            coro: An awaitable coroutine
            timeout: Max seconds to wait (default: 120s)

        Returns:
            The coroutine's return value
        """
        return self._loop_thread.run(coro, timeout=timeout)

    # ------------------------------------------------------------------
    # Workspace resolution
    # ------------------------------------------------------------------

    def resolve_workspace(self, project: str | None = None) -> Path:
        """Resolve workspace path, optionally overridden by project.

        Args:
            project: Optional project path override. If it exists on disk,
                     it takes priority over the default workspace.

        Returns:
            Resolved absolute Path to the workspace directory
        """
        if project:
            p = Path(project).expanduser().resolve()
            if p.exists():
                return p
        return self._workspace

    @property
    def workspace(self) -> Path:
        """The default workspace path."""
        return self._workspace

    # ------------------------------------------------------------------
    # Lazy subsystems
    # ------------------------------------------------------------------

    @property
    def memory(self) -> Any:
        """PersistentMemory, lazy-loaded and cached.

        Returns None if the subsystem cannot be loaded (missing data, import error, etc.).
        """
        if self._memory is _UNSET:
            self._memory = self._load_memory()
        return self._memory

    @property
    def backlog(self) -> Any:
        """BacklogManager, lazy-loaded and cached.

        Returns None if the subsystem cannot be loaded.
        """
        if self._backlog is _UNSET:
            self._backlog = self._load_backlog()
        return self._backlog

    @property
    def graph(self) -> Any:
        """CodebaseGraph, lazy-loaded and cached.

        Returns None if no graph is available for this workspace.
        """
        if self._graph is _UNSET:
            self._graph = self._load_graph()
        return self._graph

    def invalidate(self) -> None:
        """Reset all cached subsystems so they reload on next access.

        Call this if the workspace state has changed significantly
        (e.g., after sunwell_complete or sunwell_execute).
        """
        self._memory = _UNSET
        self._backlog = _UNSET
        self._graph = _UNSET

    @property
    def availability(self) -> dict[str, bool]:
        """Check which subsystems are available.

        Triggers lazy loading for all subsystems and reports status.
        """
        return {
            "memory": self.memory is not None,
            "backlog": self.backlog is not None,
            "graph": self.graph is not None,
        }

    # ------------------------------------------------------------------
    # Private loaders
    # ------------------------------------------------------------------

    def _load_memory(self) -> Any:
        """Load PersistentMemory for the workspace."""
        try:
            from sunwell.memory.facade import PersistentMemory

            return PersistentMemory.load(self._workspace)
        except Exception as e:
            logger.debug("Failed to load PersistentMemory: %s", e)
            return None

    def _load_backlog(self) -> Any:
        """Load BacklogManager for the workspace."""
        try:
            from sunwell.features.backlog.manager import BacklogManager

            return BacklogManager(root=self._workspace)
        except Exception as e:
            logger.debug("Failed to load BacklogManager: %s", e)
            return None

    def _load_graph(self) -> Any:
        """Load CodebaseGraph for the workspace."""
        try:
            from sunwell.knowledge.codebase import CodebaseGraph

            return CodebaseGraph.load(self._workspace)
        except Exception as e:
            logger.debug("Failed to load CodebaseGraph: %s", e)
            return None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def shutdown(self) -> None:
        """Clean up the runtime (stop event loop thread)."""
        self._loop_thread.shutdown()

    def __repr__(self) -> str:
        return f"MCPRuntime(workspace={self._workspace})"
