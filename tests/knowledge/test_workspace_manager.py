"""Tests for WorkspaceManager (RFC-140)."""

import tempfile
from pathlib import Path

import pytest

from sunwell.knowledge.project import ProjectRegistry
from sunwell.knowledge.workspace import WorkspaceManager, WorkspaceStatus


@pytest.fixture
def temp_workspace(tmp_path: Path) -> Path:
    """Create a temporary workspace with project markers."""
    workspace = tmp_path / "test-workspace"
    workspace.mkdir()
    (workspace / ".git").mkdir()  # Add git marker
    return workspace


@pytest.fixture
def manager() -> WorkspaceManager:
    """Create a WorkspaceManager instance."""
    return WorkspaceManager()


def test_discover_workspaces(manager: WorkspaceManager, temp_workspace: Path) -> None:
    """Test workspace discovery."""
    workspaces = manager.discover_workspaces(temp_workspace.parent)

    # Should find our temp workspace
    found = [w for w in workspaces if w.path == temp_workspace]
    assert len(found) > 0

    workspace_info = found[0]
    assert workspace_info.path == temp_workspace
    assert workspace_info.status == WorkspaceStatus.VALID
    assert not workspace_info.is_registered  # Not registered yet


def test_get_current_no_current(manager: WorkspaceManager) -> None:
    """Test get_current when no current workspace is set."""
    current = manager.get_current()
    # May be None or fallback to default project
    assert current is None or current.is_current


def test_switch_workspace(manager: WorkspaceManager, temp_workspace: Path) -> None:
    """Test switching to a workspace."""
    workspace_info = manager.switch_workspace(temp_workspace)

    assert workspace_info.path == temp_workspace
    assert workspace_info.is_current

    # Verify current is set
    current = manager.get_current()
    assert current is not None
    assert current.path == temp_workspace


def test_get_status_valid(manager: WorkspaceManager, temp_workspace: Path) -> None:
    """Test getting status for valid workspace."""
    status = manager.get_status(temp_workspace)
    assert status == WorkspaceStatus.VALID


def test_get_status_not_found(manager: WorkspaceManager) -> None:
    """Test getting status for non-existent workspace."""
    status = manager.get_status(Path("/nonexistent/path"))
    assert status == WorkspaceStatus.NOT_FOUND


def test_register_discovered(manager: WorkspaceManager, temp_workspace: Path) -> None:
    """Test registering a discovered workspace."""
    project = manager.register_discovered(temp_workspace)

    assert project.root == temp_workspace
    assert project.id == "test-workspace"

    # Verify it's now registered
    registry = ProjectRegistry()
    found = registry.find_by_root(temp_workspace)
    assert found is not None
    assert found.id == project.id
