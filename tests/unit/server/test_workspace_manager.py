"""Tests for WorkspaceManager (RFC: Architecture Proposal).

Tests server-side memory caching.
"""

import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from sunwell.interface.server.workspace_manager import (
    CachedWorkspace,
    WorkspaceManager,
    get_workspace_manager,
)


class TestCachedWorkspace:
    """Tests for CachedWorkspace dataclass."""

    def test_create(self, tmp_path: Path) -> None:
        """CachedWorkspace should create with required fields."""
        mock_memory = MagicMock()

        cached = CachedWorkspace(
            workspace=tmp_path,
            memory=mock_memory,
            last_accessed=time.monotonic(),
        )

        assert cached.workspace == tmp_path
        assert cached.memory is mock_memory
        assert cached.access_count == 0

    def test_touch_updates_access(self, tmp_path: Path) -> None:
        """touch() should update last_accessed and increment count."""
        mock_memory = MagicMock()
        initial_time = time.monotonic()

        cached = CachedWorkspace(
            workspace=tmp_path,
            memory=mock_memory,
            last_accessed=initial_time,
        )

        time.sleep(0.01)  # Small delay
        cached.touch()

        assert cached.last_accessed > initial_time
        assert cached.access_count == 1

        cached.touch()
        assert cached.access_count == 2


class TestWorkspaceManagerBasics:
    """Tests for WorkspaceManager basic operations."""

    def test_create_with_defaults(self) -> None:
        """WorkspaceManager should create with default settings."""
        manager = WorkspaceManager()

        assert manager.max_size == 10
        assert manager.ttl_seconds == 3600.0

    def test_stats_empty_cache(self) -> None:
        """stats() should return correct values for empty cache."""
        manager = WorkspaceManager()

        stats = manager.stats()

        assert stats["cached_workspaces"] == 0
        assert stats["max_size"] == 10
        assert stats["ttl_seconds"] == 3600.0
        assert stats["total_accesses"] == 0


class TestWorkspaceManagerGetMemory:
    """Tests for WorkspaceManager.get_memory()."""

    def test_get_memory_returns_memory(self, tmp_path: Path) -> None:
        """get_memory() should return a PersistentMemory instance."""
        manager = WorkspaceManager()

        memory = manager.get_memory(tmp_path)

        assert memory is not None
        assert memory.workspace == tmp_path

    def test_get_memory_caches(self, tmp_path: Path) -> None:
        """get_memory() should cache and return same instance."""
        manager = WorkspaceManager()

        memory1 = manager.get_memory(tmp_path)
        memory2 = manager.get_memory(tmp_path)

        assert memory1 is memory2
        assert manager.stats()["cached_workspaces"] == 1

    def test_get_memory_different_workspaces(self, tmp_path: Path) -> None:
        """get_memory() should cache different workspaces separately."""
        manager = WorkspaceManager()

        ws1 = tmp_path / "ws1"
        ws2 = tmp_path / "ws2"
        ws1.mkdir()
        ws2.mkdir()

        memory1 = manager.get_memory(ws1)
        memory2 = manager.get_memory(ws2)

        assert memory1.workspace != memory2.workspace
        assert manager.stats()["cached_workspaces"] == 2


class TestWorkspaceManagerInvalidate:
    """Tests for WorkspaceManager invalidation."""

    def test_invalidate_removes_cached(self, tmp_path: Path) -> None:
        """invalidate() should remove workspace from cache."""
        manager = WorkspaceManager()

        manager.get_memory(tmp_path)
        assert manager.stats()["cached_workspaces"] == 1

        result = manager.invalidate(tmp_path)

        assert result is True
        assert manager.stats()["cached_workspaces"] == 0

    def test_invalidate_returns_false_if_not_cached(self, tmp_path: Path) -> None:
        """invalidate() should return False if workspace not cached."""
        manager = WorkspaceManager()

        result = manager.invalidate(tmp_path)

        assert result is False

    def test_invalidate_all_clears_cache(self, tmp_path: Path) -> None:
        """invalidate_all() should clear entire cache."""
        manager = WorkspaceManager()

        ws1 = tmp_path / "ws1"
        ws2 = tmp_path / "ws2"
        ws1.mkdir()
        ws2.mkdir()

        manager.get_memory(ws1)
        manager.get_memory(ws2)

        count = manager.invalidate_all()

        assert count == 2
        assert manager.stats()["cached_workspaces"] == 0


class TestWorkspaceManagerBuildSession:
    """Tests for WorkspaceManager session building."""

    def test_build_session_returns_session(self, tmp_path: Path) -> None:
        """build_session() should return SessionContext."""
        manager = WorkspaceManager()

        session = manager.build_session(tmp_path, "test goal")

        assert session is not None
        assert session.goal == "test goal"
        assert session.cwd == tmp_path


class TestGetWorkspaceManager:
    """Tests for get_workspace_manager() singleton."""

    def test_returns_instance(self) -> None:
        """get_workspace_manager() should return a WorkspaceManager."""
        manager = get_workspace_manager()
        assert isinstance(manager, WorkspaceManager)

    def test_returns_singleton(self) -> None:
        """get_workspace_manager() should return same instance."""
        manager1 = get_workspace_manager()
        manager2 = get_workspace_manager()

        assert manager1 is manager2
