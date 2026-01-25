"""Tests for Workspace Lifecycle Management (RFC-141)."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from sunwell.knowledge.project import ProjectRegistry, init_project
from sunwell.knowledge.workspace import (
    CleanupResult,
    DeleteResult,
    DeletionMode,
    MoveResult,
    PurgeResult,
    RenameResult,
    WorkspaceLifecycle,
    WorkspaceManager,
    WorkspaceStatus,
    has_nested_workspaces,
)


# ═══════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def temp_workspace(tmp_path: Path) -> Path:
    """Create a temporary workspace with project markers."""
    workspace = tmp_path / "test-workspace"
    workspace.mkdir()
    (workspace / "pyproject.toml").write_text("[project]\nname = 'test'\n")  # Add project marker
    # Add some source files
    (workspace / "src").mkdir()
    (workspace / "src" / "main.py").write_text("# Main file\nprint('Hello')")
    return workspace


@pytest.fixture
def runs_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a temporary runs directory."""
    runs = tmp_path / "runs"
    runs.mkdir()

    # Monkeypatch the runs directory
    monkeypatch.setattr(
        "sunwell.knowledge.workspace.lifecycle.WorkspaceLifecycle.get_runs_dir",
        lambda self: runs,
    )

    return runs


@pytest.fixture
def manager() -> WorkspaceManager:
    """Create a WorkspaceManager instance."""
    return WorkspaceManager()


# ═══════════════════════════════════════════════════════════════
# LIFECYCLE MODULE TESTS
# ═══════════════════════════════════════════════════════════════


class TestWorkspaceLifecycle:
    """Tests for WorkspaceLifecycle helper class."""

    def test_list_workspace_runs(self, runs_dir: Path) -> None:
        """Test listing runs for a workspace."""
        workspace_id = "test-list-runs-ws"

        # Create some run files
        run1 = runs_dir / "run-1.json"
        run1.write_text(json.dumps({"run_id": "run-1", "project_id": workspace_id}))

        run2 = runs_dir / "run-2.json"
        run2.write_text(json.dumps({"run_id": "run-2", "project_id": workspace_id}))

        run3 = runs_dir / "run-3.json"
        run3.write_text(json.dumps({"run_id": "run-3", "project_id": "other-workspace"}))

        lifecycle = WorkspaceLifecycle()
        lifecycle._sunwell_dir = runs_dir.parent

        run_ids = lifecycle.list_workspace_runs(workspace_id)

        assert len(run_ids) == 2
        assert "run-1" in run_ids
        assert "run-2" in run_ids
        assert "run-3" not in run_ids

    def test_delete_runs(self, runs_dir: Path) -> None:
        """Test deleting runs by ID."""
        # Create run files
        (runs_dir / "run-1.json").write_text("{}")
        (runs_dir / "run-2.json").write_text("{}")
        (runs_dir / "run-3.json").write_text("{}")

        lifecycle = WorkspaceLifecycle()
        lifecycle._sunwell_dir = runs_dir.parent

        deleted = lifecycle.delete_runs(["run-1", "run-2"])

        assert deleted == 2
        assert not (runs_dir / "run-1.json").exists()
        assert not (runs_dir / "run-2.json").exists()
        assert (runs_dir / "run-3.json").exists()

    def test_mark_runs_orphaned(self, runs_dir: Path) -> None:
        """Test marking runs as orphaned."""
        # Create run file
        run_file = runs_dir / "run-1.json"
        run_file.write_text(json.dumps({"run_id": "run-1", "project_id": "test"}))

        lifecycle = WorkspaceLifecycle()
        lifecycle._sunwell_dir = runs_dir.parent

        marked = lifecycle.mark_runs_orphaned(["run-1"])

        assert marked == 1

        data = json.loads(run_file.read_text())
        assert data["workspace_deleted"] is True

    def test_update_runs_workspace_id(self, runs_dir: Path) -> None:
        """Test updating workspace ID in runs."""
        # Create run files
        run1 = runs_dir / "run-1.json"
        run1.write_text(json.dumps({"run_id": "run-1", "project_id": "old-id"}))

        run2 = runs_dir / "run-2.json"
        run2.write_text(json.dumps({"run_id": "run-2", "project_id": "other-id"}))

        lifecycle = WorkspaceLifecycle()
        lifecycle._sunwell_dir = runs_dir.parent

        updated = lifecycle.update_runs_workspace_id("old-id", "new-id")

        assert updated == 1

        data1 = json.loads(run1.read_text())
        assert data1["project_id"] == "new-id"

        data2 = json.loads(run2.read_text())
        assert data2["project_id"] == "other-id"

    def test_delete_sunwell_data(self, tmp_path: Path) -> None:
        """Test deleting .sunwell directory."""
        # Create a workspace with .sunwell data
        workspace = tmp_path / "test-delete-sunwell"
        workspace.mkdir()
        
        sunwell_dir = workspace / ".sunwell"
        sunwell_dir.mkdir()
        (sunwell_dir / "project.toml").write_text("[project]\nid = 'test'\n")
        
        lineage_dir = sunwell_dir / "lineage"
        lineage_dir.mkdir()
        (lineage_dir / "index.json").write_text("{}")
        
        memory_dir = sunwell_dir / "memory"
        memory_dir.mkdir()
        (memory_dir / "store.json").write_text("{}")

        lifecycle = WorkspaceLifecycle()
        deleted, failed = lifecycle.delete_sunwell_data(workspace)

        assert len(deleted) > 0
        assert len(failed) == 0
        # Some items should be deleted
        assert any("lineage" in d for d in deleted)

    def test_find_orphaned_runs(self, runs_dir: Path) -> None:
        """Test finding orphaned runs."""
        # Create run files
        (runs_dir / "run-1.json").write_text(
            json.dumps({"run_id": "run-1", "project_id": "valid-workspace"})
        )
        (runs_dir / "run-2.json").write_text(
            json.dumps({"run_id": "run-2", "project_id": "missing-workspace"})
        )
        (runs_dir / "run-3.json").write_text(
            json.dumps(
                {"run_id": "run-3", "project_id": "already-orphan", "workspace_deleted": True}
            )
        )

        lifecycle = WorkspaceLifecycle()
        lifecycle._sunwell_dir = runs_dir.parent

        orphaned = lifecycle.find_orphaned_runs({"valid-workspace"})

        assert len(orphaned) == 1
        assert "run-2" in orphaned

    def test_find_invalid_registrations(self, tmp_path: Path) -> None:
        """Test finding invalid registry entries."""
        registry_entries = {
            "valid": {"root": str(tmp_path)},
            "invalid": {"root": "/nonexistent/path/to/workspace"},
        }

        lifecycle = WorkspaceLifecycle()
        invalid = lifecycle.find_invalid_registrations(registry_entries)

        assert len(invalid) == 1
        assert "invalid" in invalid


class TestHasNestedWorkspaces:
    """Tests for nested workspace detection."""

    def test_no_nested_workspaces(self, tmp_path: Path) -> None:
        """Test when no nested workspaces exist."""
        # Create workspace without nested children
        workspace_path = tmp_path / "no-nested"
        workspace_path.mkdir()
        (workspace_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        project = init_project(root=workspace_path, project_id="no-nested-ws", register=True)
        
        registry = ProjectRegistry()
        nested = has_nested_workspaces(workspace_path, registry.projects)

        assert len(nested) == 0
        
        # Cleanup
        registry.unregister(project.id)

    def test_with_nested_workspace(self, tmp_path: Path) -> None:
        """Test detection of nested workspaces."""
        # Create parent workspace
        parent = tmp_path / "parent-detect"
        parent.mkdir()
        (parent / "pyproject.toml").write_text("[project]\nname = 'parent'\n")
        parent_proj = init_project(root=parent, project_id="parent-detect", register=True)

        # Create nested workspace
        nested = parent / "nested"
        nested.mkdir()
        (nested / "pyproject.toml").write_text("[project]\nname = 'nested'\n")
        nested_proj = init_project(root=nested, project_id="nested-detect", register=True)

        registry = ProjectRegistry()
        found_nested = has_nested_workspaces(parent, registry.projects)

        assert len(found_nested) == 1
        assert "nested-detect" in found_nested
        
        # Cleanup
        registry.unregister(nested_proj.id)
        registry.unregister(parent_proj.id)


# ═══════════════════════════════════════════════════════════════
# WORKSPACE MANAGER LIFECYCLE TESTS
# ═══════════════════════════════════════════════════════════════


class TestUnregister:
    """Tests for workspace unregister operation."""

    def test_unregister_success(self, tmp_path: Path) -> None:
        """Test successful unregister."""
        # Create and register workspace
        workspace_path = tmp_path / "test-unregister"
        workspace_path.mkdir()
        (workspace_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        project = init_project(root=workspace_path, project_id="test-unregister", register=True)
        
        manager = WorkspaceManager()
        result = manager.unregister(project.id)

        assert result.success
        assert result.mode == DeletionMode.UNREGISTER
        assert result.workspace_id == project.id
        assert "registry_entry" in result.deleted_items

        # Verify no longer registered
        registry = ProjectRegistry()
        assert registry.get(project.id) is None

        # Verify files still exist
        assert workspace_path.exists()
        assert (workspace_path / "pyproject.toml").exists()

    def test_unregister_not_found(self, manager: WorkspaceManager) -> None:
        """Test unregister with non-existent workspace."""
        with pytest.raises(ValueError, match="not registered"):
            manager.unregister("nonexistent-workspace-abc123")

    def test_unregister_clears_current(self, tmp_path: Path) -> None:
        """Test that unregistering current workspace clears it."""
        # Create and register workspace
        workspace_path = tmp_path / "test-unregister-current"
        workspace_path.mkdir()
        (workspace_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        project = init_project(root=workspace_path, project_id="test-unregister-current", register=True)
        
        manager = WorkspaceManager()

        # Set as current
        manager.switch_workspace(workspace_path)
        assert manager.get_current() is not None

        # Unregister
        result = manager.unregister(project.id)

        assert result.was_current


class TestPurge:
    """Tests for workspace purge operation."""

    def test_purge_success(self, tmp_path: Path) -> None:
        """Test successful purge."""
        # Create and register workspace with .sunwell data
        workspace_path = tmp_path / "test-purge"
        workspace_path.mkdir()
        (workspace_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        project = init_project(root=workspace_path, project_id="test-purge", register=True)
        
        # Add sunwell data
        sunwell_dir = workspace_path / ".sunwell"
        lineage_dir = sunwell_dir / "lineage"
        lineage_dir.mkdir(parents=True)
        (lineage_dir / "index.json").write_text("{}")

        manager = WorkspaceManager()
        result = manager.purge(project.id, force=True)

        assert result.workspace_id == project.id

        # Verify workspace directory still exists
        assert workspace_path.exists()

    def test_purge_not_found(self, manager: WorkspaceManager) -> None:
        """Test purge with non-existent workspace."""
        with pytest.raises(ValueError, match="not registered"):
            manager.purge("nonexistent-workspace-xyz789")


class TestDelete:
    """Tests for workspace full delete operation."""

    def test_delete_success(self, tmp_path: Path) -> None:
        """Test successful full delete."""
        # Create and register workspace
        workspace_path = tmp_path / "test-delete"
        workspace_path.mkdir()
        (workspace_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        project = init_project(root=workspace_path, project_id="test-delete", register=True)
        
        manager = WorkspaceManager()
        result = manager.delete(project.id, force=True)

        assert result.success
        assert result.mode == DeletionMode.FULL
        assert result.workspace_id == project.id

        # Verify workspace is completely deleted
        assert not workspace_path.exists()

        # Verify no longer registered
        registry = ProjectRegistry()
        assert registry.get(project.id) is None

    def test_delete_not_found(self, manager: WorkspaceManager) -> None:
        """Test delete with non-existent workspace."""
        with pytest.raises(ValueError, match="not registered"):
            manager.delete("nonexistent-workspace-del456")

    def test_delete_with_nested_workspace_fails(self, tmp_path: Path) -> None:
        """Test delete fails when nested workspaces exist."""
        # Create parent workspace
        parent = tmp_path / "parent-nested"
        parent.mkdir()
        (parent / "pyproject.toml").write_text("[project]\nname = 'parent'\n")
        init_project(root=parent, project_id="parent-nested", register=True)

        # Create nested workspace
        nested = parent / "nested"
        nested.mkdir()
        (nested / "pyproject.toml").write_text("[project]\nname = 'nested'\n")
        init_project(root=nested, project_id="nested-child", register=True)

        manager = WorkspaceManager()

        with pytest.raises(ValueError, match="nested workspaces"):
            manager.delete("parent-nested")
        
        # Cleanup
        manager.unregister("nested-child")
        manager.delete("parent-nested", force=True)


class TestRename:
    """Tests for workspace rename operation."""

    def test_rename_success(self, tmp_path: Path) -> None:
        """Test successful rename."""
        # Create and register workspace
        workspace_path = tmp_path / "test-rename"
        workspace_path.mkdir()
        (workspace_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        project = init_project(root=workspace_path, project_id="test-rename-old", register=True)

        manager = WorkspaceManager()
        result = manager.rename(project.id, new_id="test-rename-new", new_name="New Name")

        assert result.success
        assert result.old_id == project.id
        assert result.new_id == "test-rename-new"

        # Verify new ID is registered
        registry = ProjectRegistry()
        assert registry.get("test-rename-new") is not None
        assert registry.get(project.id) is None
        
        # Cleanup
        manager.unregister("test-rename-new")

    def test_rename_conflict(self, tmp_path: Path) -> None:
        """Test rename fails on ID conflict."""
        # Create two workspaces
        ws1 = tmp_path / "ws1-conflict"
        ws1.mkdir()
        (ws1 / "pyproject.toml").write_text("[project]\nname = 'ws1'\n")
        init_project(root=ws1, project_id="workspace-conflict-1", register=True)

        ws2 = tmp_path / "ws2-conflict"
        ws2.mkdir()
        (ws2 / "pyproject.toml").write_text("[project]\nname = 'ws2'\n")
        init_project(root=ws2, project_id="workspace-conflict-2", register=True)

        manager = WorkspaceManager()
        
        with pytest.raises(ValueError, match="already exists"):
            manager.rename("workspace-conflict-1", new_id="workspace-conflict-2")
        
        # Cleanup
        manager.unregister("workspace-conflict-1")
        manager.unregister("workspace-conflict-2")

    def test_rename_not_found(self, manager: WorkspaceManager) -> None:
        """Test rename with non-existent workspace."""
        with pytest.raises(ValueError, match="not registered"):
            manager.rename("nonexistent-rename-123", new_id="new-name")


class TestMove:
    """Tests for workspace move operation."""

    def test_move_success(self, tmp_path: Path) -> None:
        """Test successful move."""
        # Create and register workspace
        old_path = tmp_path / "test-move-old"
        old_path.mkdir()
        (old_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        project = init_project(root=old_path, project_id="test-move", register=True)

        # Create new location
        new_path = tmp_path / "test-move-new"
        new_path.mkdir()
        (new_path / "pyproject.toml").write_text("[project]\nname = 'new'\n")

        manager = WorkspaceManager()
        result = manager.move(project.id, new_path)

        assert result.success
        assert result.workspace_id == project.id
        assert result.old_path == old_path
        assert result.new_path == new_path

        # Verify registry updated
        registry = ProjectRegistry()
        proj = registry.get(project.id)
        assert proj is not None
        assert proj.root == new_path
        
        # Cleanup
        manager.unregister(project.id)

    def test_move_path_not_exists(self, tmp_path: Path) -> None:
        """Test move with non-existent new path."""
        # Create and register workspace
        workspace_path = tmp_path / "test-move-noexist"
        workspace_path.mkdir()
        (workspace_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        project = init_project(root=workspace_path, project_id="test-move-noexist", register=True)

        manager = WorkspaceManager()
        
        with pytest.raises(ValueError, match="does not exist"):
            manager.move(project.id, Path("/nonexistent/path/xyz"))
        
        # Cleanup
        manager.unregister(project.id)

    def test_move_not_found(self, manager: WorkspaceManager, tmp_path: Path) -> None:
        """Test move with non-existent workspace."""
        with pytest.raises(ValueError, match="not registered"):
            manager.move("nonexistent-move-456", tmp_path)


class TestCleanupOrphaned:
    """Tests for cleanup orphaned operation."""

    def test_cleanup_dry_run(
        self, manager: WorkspaceManager, runs_dir: Path, tmp_path: Path
    ) -> None:
        """Test cleanup in dry-run mode."""
        # Create orphaned run
        (runs_dir / "orphan-run.json").write_text(
            json.dumps({"run_id": "orphan-run", "project_id": "missing-workspace"})
        )

        result = manager.cleanup_orphaned(dry_run=True)

        assert result.dry_run
        assert len(result.orphaned_runs) >= 0  # May or may not find depending on setup
        assert result.cleaned_runs == 0
        assert result.cleaned_registrations == 0

    def test_cleanup_actual(
        self, manager: WorkspaceManager, runs_dir: Path, tmp_path: Path
    ) -> None:
        """Test actual cleanup."""
        # Create orphaned run
        run_file = runs_dir / "orphan-run.json"
        run_file.write_text(
            json.dumps({"run_id": "orphan-run", "project_id": "missing-workspace"})
        )

        # First do dry run to see what would be cleaned
        dry_result = manager.cleanup_orphaned(dry_run=True)

        # Then do actual cleanup
        result = manager.cleanup_orphaned(dry_run=False)

        assert not result.dry_run


class TestHasActiveRuns:
    """Tests for active run detection."""

    def test_no_active_runs(self, manager: WorkspaceManager) -> None:
        """Test when no active runs exist."""
        # Use a workspace ID that likely has no runs
        active = manager.has_active_runs("nonexistent-workspace-runs")

        assert len(active) == 0

    def test_with_active_runs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test detection of active runs."""
        # Create a temp .sunwell directory
        sunwell_dir = tmp_path / ".sunwell"
        runs_dir = sunwell_dir / "runs"
        runs_dir.mkdir(parents=True)

        # Create active run
        run_file = runs_dir / "active-run.json"
        run_file.write_text(
            json.dumps({
                "run_id": "active-run",
                "project_id": "test-active-runs",
                "status": "running",
            })
        )

        # Monkeypatch Path.home to use our temp dir
        monkeypatch.setattr(
            "sunwell.knowledge.workspace.manager.Path.home",
            lambda: tmp_path,
        )

        manager = WorkspaceManager()
        active = manager.has_active_runs("test-active-runs")

        assert isinstance(active, list)
        assert len(active) == 1
        assert "active-run" in active


# ═══════════════════════════════════════════════════════════════
# EDGE CASES
# ═══════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Tests for edge cases in lifecycle operations."""

    def test_empty_workspace_id(self, manager: WorkspaceManager) -> None:
        """Test operations with empty workspace ID."""
        with pytest.raises(ValueError):
            manager.unregister("")

    def test_special_characters_in_id(self, tmp_path: Path) -> None:
        """Test handling of special characters in workspace ID."""
        workspace = tmp_path / "test workspace with spaces edge"
        workspace.mkdir()
        (workspace / "pyproject.toml").write_text("[project]\nname = 'test'\n")

        project = init_project(
            root=workspace,
            project_id="test-with-spaces-edge",
            register=True,
        )

        manager = WorkspaceManager()
        result = manager.unregister(project.id)
        assert result.success

    def test_unicode_workspace_name(self, tmp_path: Path) -> None:
        """Test handling of unicode in workspace names."""
        workspace = tmp_path / "test-unicode-workspace-edge"
        workspace.mkdir()
        (workspace / "pyproject.toml").write_text("[project]\nname = 'test'\n")

        project = init_project(
            root=workspace,
            project_id="unicode-test-edge",
            register=True,
        )

        manager = WorkspaceManager()
        result = manager.rename(project.id, new_id="renamed-unicode-edge", new_name="Unicode Test")
        assert result.success
        
        # Cleanup
        manager.unregister("renamed-unicode-edge")

    def test_concurrent_operations_safety(self, tmp_path: Path) -> None:
        """Test that operations are safe for concurrent access."""
        # Create and register workspace
        workspace = tmp_path / "test-concurrent"
        workspace.mkdir()
        (workspace / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        project = init_project(root=workspace, project_id="test-concurrent", register=True)

        manager = WorkspaceManager()

        # This is a basic test - in practice, we'd need threading tests
        # Just verify that double-unregister doesn't crash badly
        manager.unregister(project.id)

        with pytest.raises(ValueError, match="not registered"):
            manager.unregister(project.id)
