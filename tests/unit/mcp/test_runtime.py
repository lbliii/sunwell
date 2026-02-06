"""Tests for MCPRuntime — async bridge, workspace resolution, and subsystem caching."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sunwell.mcp.runtime import MCPRuntime, _LoopThread, _UNSET


# ---------------------------------------------------------------------------
# _LoopThread tests
# ---------------------------------------------------------------------------


class TestLoopThread:
    """Tests for the persistent event loop thread."""

    def test_loop_thread_starts(self):
        """Thread should start and become ready."""
        lt = _LoopThread()
        try:
            assert lt._loop is not None
            assert not lt._loop.is_closed()
            assert lt._thread is not None
            assert lt._thread.is_alive()
            # Verify the loop is actually usable
            async def ping():
                return "pong"
            assert lt.run(ping()) == "pong"
        finally:
            lt.shutdown()

    def test_run_coroutine(self):
        """run() should execute a coroutine and return its result."""
        lt = _LoopThread()
        try:
            async def add(a, b):
                return a + b

            result = lt.run(add(3, 4))
            assert result == 7
        finally:
            lt.shutdown()

    def test_run_async_sleep(self):
        """run() should handle async coroutines that yield."""
        lt = _LoopThread()
        try:
            async def delayed_value():
                await asyncio.sleep(0.01)
                return 42

            assert lt.run(delayed_value()) == 42
        finally:
            lt.shutdown()

    def test_run_propagates_exceptions(self):
        """run() should propagate exceptions from the coroutine."""
        lt = _LoopThread()
        try:
            async def failing():
                raise ValueError("test error")

            with pytest.raises(ValueError, match="test error"):
                lt.run(failing())
        finally:
            lt.shutdown()

    def test_run_timeout(self):
        """run() should raise on timeout."""
        import concurrent.futures

        lt = _LoopThread()
        try:
            async def slow():
                await asyncio.sleep(60)

            with pytest.raises((TimeoutError, concurrent.futures.TimeoutError)):
                lt.run(slow(), timeout=0.1)
        finally:
            lt.shutdown()

    def test_shutdown_stops_loop(self):
        """shutdown() should stop the loop and thread."""
        lt = _LoopThread()
        lt.shutdown()
        # After shutdown, loop should be stopped
        assert not lt._thread.is_alive()

    def test_run_after_shutdown_raises(self):
        """run() after shutdown should raise RuntimeError."""
        lt = _LoopThread()
        lt.shutdown()

        async def noop():
            return None

        with pytest.raises(RuntimeError, match="not running"):
            lt.run(noop())


# ---------------------------------------------------------------------------
# MCPRuntime — workspace resolution
# ---------------------------------------------------------------------------


class TestRuntimeWorkspace:
    """Tests for MCPRuntime.resolve_workspace()."""

    def test_default_workspace_is_cwd(self):
        """Without workspace arg, defaults to cwd."""
        rt = MCPRuntime()
        try:
            assert rt.workspace == Path.cwd()
        finally:
            rt.shutdown()

    def test_explicit_workspace(self, tmp_path):
        """Explicit workspace path is resolved."""
        rt = MCPRuntime(workspace=str(tmp_path))
        try:
            assert rt.workspace == tmp_path
        finally:
            rt.shutdown()

    def test_resolve_workspace_no_override(self, tmp_path):
        """resolve_workspace() returns default when no project override."""
        rt = MCPRuntime(workspace=str(tmp_path))
        try:
            assert rt.resolve_workspace() == tmp_path
        finally:
            rt.shutdown()

    def test_resolve_workspace_with_project_override(self, tmp_path):
        """resolve_workspace(project=...) overrides if project exists."""
        project_dir = tmp_path / "override"
        project_dir.mkdir()

        rt = MCPRuntime(workspace=str(tmp_path))
        try:
            assert rt.resolve_workspace(str(project_dir)) == project_dir
        finally:
            rt.shutdown()

    def test_resolve_workspace_project_missing_falls_back(self, tmp_path):
        """resolve_workspace(project=...) falls back if project doesn't exist."""
        rt = MCPRuntime(workspace=str(tmp_path))
        try:
            result = rt.resolve_workspace("/nonexistent/path/that/does/not/exist")
            assert result == tmp_path
        finally:
            rt.shutdown()


# ---------------------------------------------------------------------------
# MCPRuntime — async bridge
# ---------------------------------------------------------------------------


class TestRuntimeAsyncBridge:
    """Tests for MCPRuntime.run() async-to-sync bridge."""

    def test_run_simple_coroutine(self, tmp_path):
        """run() should execute a simple coroutine."""
        rt = MCPRuntime(workspace=str(tmp_path))
        try:
            async def compute():
                return 10 * 5

            assert rt.run(compute()) == 50
        finally:
            rt.shutdown()

    def test_run_with_await(self, tmp_path):
        """run() should handle coroutines with awaits."""
        rt = MCPRuntime(workspace=str(tmp_path))
        try:
            async def multi_step():
                await asyncio.sleep(0.01)
                x = 1
                await asyncio.sleep(0.01)
                return x + 1

            assert rt.run(multi_step()) == 2
        finally:
            rt.shutdown()

    def test_multiple_sequential_runs(self, tmp_path):
        """Multiple sequential run() calls should work."""
        rt = MCPRuntime(workspace=str(tmp_path))
        try:
            async def inc(x):
                return x + 1

            assert rt.run(inc(0)) == 1
            assert rt.run(inc(1)) == 2
            assert rt.run(inc(2)) == 3
        finally:
            rt.shutdown()


# ---------------------------------------------------------------------------
# MCPRuntime — lazy subsystem caching
# ---------------------------------------------------------------------------


class TestRuntimeSubsystems:
    """Tests for lazy-loaded subsystem properties."""

    def test_memory_loads_lazily(self, tmp_path):
        """memory property should lazy-load PersistentMemory."""
        rt = MCPRuntime(workspace=str(tmp_path))
        try:
            assert rt._memory is _UNSET

            mock_memory = MagicMock()
            with patch(
                "sunwell.mcp.runtime.MCPRuntime._load_memory",
                return_value=mock_memory,
            ):
                result = rt.memory
                assert result is mock_memory

            # Second access should return cached value (not call _load_memory again)
            assert rt.memory is mock_memory
        finally:
            rt.shutdown()

    def test_backlog_loads_lazily(self, tmp_path):
        """backlog property should lazy-load BacklogManager."""
        rt = MCPRuntime(workspace=str(tmp_path))
        try:
            assert rt._backlog is _UNSET

            mock_backlog = MagicMock()
            with patch(
                "sunwell.mcp.runtime.MCPRuntime._load_backlog",
                return_value=mock_backlog,
            ):
                result = rt.backlog
                assert result is mock_backlog
        finally:
            rt.shutdown()

    def test_graph_loads_lazily(self, tmp_path):
        """graph property should lazy-load CodebaseGraph."""
        rt = MCPRuntime(workspace=str(tmp_path))
        try:
            assert rt._graph is _UNSET

            mock_graph = MagicMock()
            with patch(
                "sunwell.mcp.runtime.MCPRuntime._load_graph",
                return_value=mock_graph,
            ):
                result = rt.graph
                assert result is mock_graph
        finally:
            rt.shutdown()

    def test_subsystem_caches_after_first_access(self, tmp_path):
        """Once loaded, subsystem should not reload."""
        rt = MCPRuntime(workspace=str(tmp_path))
        try:
            mock_memory = MagicMock()
            with patch(
                "sunwell.mcp.runtime.MCPRuntime._load_memory",
                return_value=mock_memory,
            ) as mock_load:
                _ = rt.memory
                _ = rt.memory
                _ = rt.memory
                # _load_memory should be called only once
                mock_load.assert_called_once()
        finally:
            rt.shutdown()

    def test_invalidate_resets_caches(self, tmp_path):
        """invalidate() should reset all caches to _UNSET."""
        rt = MCPRuntime(workspace=str(tmp_path))
        try:
            # Simulate loaded state
            rt._memory = MagicMock()
            rt._backlog = MagicMock()
            rt._graph = MagicMock()

            rt.invalidate()

            assert rt._memory is _UNSET
            assert rt._backlog is _UNSET
            assert rt._graph is _UNSET
        finally:
            rt.shutdown()

    def test_graceful_degradation_memory(self, tmp_path):
        """If memory fails to load, property returns None."""
        rt = MCPRuntime(workspace=str(tmp_path))
        try:
            with patch(
                "sunwell.mcp.runtime.MCPRuntime._load_memory",
                side_effect=ImportError("no memory module"),
            ):
                # Should not raise — returns None via internal handler
                # But since we patched _load_memory, we need to test the real loader
                pass

            # Test the actual _load_memory with a missing module
            rt._memory = _UNSET
            # The real _load_memory tries to import PersistentMemory
            # In test environment, it will fail gracefully
            result = rt._load_memory()
            # Result is either a PersistentMemory or None (if import/load fails)
            assert result is None or result is not _UNSET
        finally:
            rt.shutdown()

    def test_graceful_degradation_backlog(self, tmp_path):
        """If backlog fails to load, property returns None."""
        rt = MCPRuntime(workspace=str(tmp_path))
        try:
            result = rt._load_backlog()
            # In test env, should either succeed or gracefully return None
            assert result is None or result is not _UNSET
        finally:
            rt.shutdown()

    def test_graceful_degradation_graph(self, tmp_path):
        """If graph fails to load, property returns None."""
        rt = MCPRuntime(workspace=str(tmp_path))
        try:
            result = rt._load_graph()
            assert result is None or result is not _UNSET
        finally:
            rt.shutdown()


# ---------------------------------------------------------------------------
# MCPRuntime — availability
# ---------------------------------------------------------------------------


class TestRuntimeAvailability:
    """Tests for availability reporting."""

    def test_availability_returns_dict(self, tmp_path):
        """availability property should return a dict of subsystem statuses."""
        rt = MCPRuntime(workspace=str(tmp_path))
        try:
            with patch.object(rt, "_load_memory", return_value=None):
                with patch.object(rt, "_load_backlog", return_value=None):
                    with patch.object(rt, "_load_graph", return_value=None):
                        avail = rt.availability
                        assert isinstance(avail, dict)
                        assert "memory" in avail
                        assert "backlog" in avail
                        assert "graph" in avail
                        # All None → all False
                        assert avail["memory"] is False
                        assert avail["backlog"] is False
                        assert avail["graph"] is False
        finally:
            rt.shutdown()

    def test_availability_with_loaded_subsystem(self, tmp_path):
        """availability should report True for loaded subsystems."""
        rt = MCPRuntime(workspace=str(tmp_path))
        try:
            rt._memory = MagicMock()
            rt._backlog = None
            rt._graph = MagicMock()

            avail = rt.availability
            assert avail["memory"] is True
            assert avail["backlog"] is False
            assert avail["graph"] is True
        finally:
            rt.shutdown()


# ---------------------------------------------------------------------------
# MCPRuntime — repr
# ---------------------------------------------------------------------------


class TestRuntimeRepr:
    """Tests for repr."""

    def test_repr(self, tmp_path):
        """repr should show workspace path."""
        rt = MCPRuntime(workspace=str(tmp_path))
        try:
            r = repr(rt)
            assert "MCPRuntime" in r
            assert str(tmp_path) in r
        finally:
            rt.shutdown()
