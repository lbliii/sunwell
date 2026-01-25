"""Tests for Project Lifecycle Management (RFC-141 Extension).

These tests verify that project CLI commands and API endpoints correctly
delegate to WorkspaceManager, which handles the actual lifecycle operations.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from sunwell.knowledge.project import ProjectRegistry, init_project
from sunwell.knowledge.workspace import (
    CleanupResult,
    PurgeResult,
    RenameResult,
    WorkspaceManager,
)


# ═══════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create a CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    """Create a temporary project directory."""
    project_path = tmp_path / "test-project"
    project_path.mkdir()
    (project_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
    (project_path / "src").mkdir()
    (project_path / "src" / "main.py").write_text("# Test file")
    return project_path


# ═══════════════════════════════════════════════════════════════
# CLI COMMAND TESTS
# ═══════════════════════════════════════════════════════════════


class TestProjectCLIPurge:
    """Tests for 'sunwell project purge' command."""

    def test_purge_not_registered(self, cli_runner: CliRunner) -> None:
        """Purge fails for unregistered project."""
        from sunwell.interface.cli.commands.project_cmd import project

        result = cli_runner.invoke(project, ["purge", "nonexistent-project"])
        assert result.exit_code == 1
        assert "not registered" in result.output.lower()

    def test_purge_requires_confirm(
        self, cli_runner: CliRunner, temp_project: Path
    ) -> None:
        """Purge requires --confirm flag."""
        from sunwell.interface.cli.commands.project_cmd import project

        # Register a project
        proj = init_project(root=temp_project, project_id="test-purge-confirm", register=True)

        try:
            result = cli_runner.invoke(project, ["purge", proj.id])
            assert result.exit_code == 1
            assert "--confirm" in result.output
        finally:
            # Cleanup
            ProjectRegistry().unregister(proj.id)

    def test_purge_success(self, cli_runner: CliRunner, temp_project: Path) -> None:
        """Purge succeeds with --confirm."""
        from sunwell.interface.cli.commands.project_cmd import project

        proj = init_project(root=temp_project, project_id="test-purge-success", register=True)

        try:
            result = cli_runner.invoke(
                project, ["purge", proj.id, "--confirm"], catch_exceptions=False
            )
            assert result.exit_code == 0
            assert "purged" in result.output.lower()

            # Verify unregistered
            registry = ProjectRegistry()
            assert registry.get(proj.id) is None
        finally:
            # Cleanup in case of failure
            registry = ProjectRegistry()
            if registry.get(proj.id):
                registry.unregister(proj.id)


class TestProjectCLIDelete:
    """Tests for 'sunwell project delete' command."""

    def test_delete_not_registered(self, cli_runner: CliRunner) -> None:
        """Delete fails for unregistered project."""
        from sunwell.interface.cli.commands.project_cmd import project

        result = cli_runner.invoke(project, ["delete", "nonexistent-project"])
        assert result.exit_code == 1
        assert "not registered" in result.output.lower()

    def test_delete_requires_confirm(
        self, cli_runner: CliRunner, temp_project: Path
    ) -> None:
        """Delete requires --confirm-full-delete flag."""
        from sunwell.interface.cli.commands.project_cmd import project

        proj = init_project(root=temp_project, project_id="test-delete-confirm", register=True)

        try:
            result = cli_runner.invoke(project, ["delete", proj.id])
            assert result.exit_code == 1
            assert "--confirm-full-delete" in result.output
        finally:
            # Cleanup
            ProjectRegistry().unregister(proj.id)


class TestProjectCLIRename:
    """Tests for 'sunwell project rename' command."""

    def test_rename_not_registered(self, cli_runner: CliRunner) -> None:
        """Rename fails for unregistered project."""
        from sunwell.interface.cli.commands.project_cmd import project

        result = cli_runner.invoke(project, ["rename", "nonexistent", "new-name"])
        assert result.exit_code == 1
        assert "not registered" in result.output.lower() or "error" in result.output.lower()

    def test_rename_success(self, cli_runner: CliRunner, temp_project: Path) -> None:
        """Rename succeeds for registered project."""
        from sunwell.interface.cli.commands.project_cmd import project

        proj = init_project(root=temp_project, project_id="test-rename-old", register=True)

        try:
            result = cli_runner.invoke(
                project, ["rename", proj.id, "test-rename-new"], catch_exceptions=False
            )
            assert result.exit_code == 0
            assert "renamed" in result.output.lower()

            # Verify renamed
            registry = ProjectRegistry()
            assert registry.get("test-rename-old") is None
            assert registry.get("test-rename-new") is not None
        finally:
            # Cleanup
            registry = ProjectRegistry()
            for proj_id in ["test-rename-old", "test-rename-new"]:
                if registry.get(proj_id):
                    registry.unregister(proj_id)


class TestProjectCLIMove:
    """Tests for 'sunwell project move' command."""

    def test_move_nonexistent_project(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """Move fails for unregistered project."""
        from sunwell.interface.cli.commands.project_cmd import project

        new_path = tmp_path / "new-location"
        new_path.mkdir()

        result = cli_runner.invoke(project, ["move", "nonexistent", str(new_path)])
        assert result.exit_code == 1

    def test_move_success(
        self, cli_runner: CliRunner, temp_project: Path, tmp_path: Path
    ) -> None:
        """Move updates registry path after manual move."""
        from sunwell.interface.cli.commands.project_cmd import project

        proj = init_project(root=temp_project, project_id="test-move-proj", register=True)

        # Simulate manual move
        new_location = tmp_path / "new-location"
        temp_project.rename(new_location)

        try:
            result = cli_runner.invoke(
                project, ["move", proj.id, str(new_location)], catch_exceptions=False
            )
            assert result.exit_code == 0
            assert "updated" in result.output.lower()

            # Verify path updated
            registry = ProjectRegistry()
            updated = registry.get(proj.id)
            assert updated is not None
            assert updated.root == new_location
        finally:
            # Cleanup
            ProjectRegistry().unregister(proj.id)


class TestProjectCLICleanup:
    """Tests for 'sunwell project cleanup' command."""

    def test_cleanup_dry_run(self, cli_runner: CliRunner) -> None:
        """Cleanup runs in dry-run mode by default."""
        from sunwell.interface.cli.commands.project_cmd import project

        result = cli_runner.invoke(project, ["cleanup"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "dry run" in result.output.lower()

    def test_cleanup_with_confirm(self, cli_runner: CliRunner) -> None:
        """Cleanup with --confirm actually cleans."""
        from sunwell.interface.cli.commands.project_cmd import project

        result = cli_runner.invoke(project, ["cleanup", "--confirm"], catch_exceptions=False)
        assert result.exit_code == 0
        # Should show cleaned counts
        assert "cleaned" in result.output.lower() or "registrations" in result.output.lower()


# ═══════════════════════════════════════════════════════════════
# API ENDPOINT TESTS
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def api_client() -> TestClient:
    """Create a test client for API endpoints."""
    from sunwell.interface.server.main import create_app

    app = create_app(dev_mode=True)
    return TestClient(app)


class TestProjectAPILifecycleDelete:
    """Tests for DELETE /api/project/lifecycle/{id} endpoint."""

    def test_delete_nonexistent(self, api_client: TestClient) -> None:
        """Delete returns 404 for nonexistent project."""
        response = api_client.delete("/api/project/lifecycle/nonexistent-project-12345")
        assert response.status_code == 404

    def test_delete_invalid_mode(self, api_client: TestClient, temp_project: Path) -> None:
        """Delete rejects invalid mode."""
        proj = init_project(root=temp_project, project_id="test-api-invalid-mode", register=True)
        try:
            response = api_client.delete(
                f"/api/project/lifecycle/{proj.id}?mode=invalid"
            )
            assert response.status_code == 400
            assert "Invalid mode" in response.json()["detail"]
        finally:
            ProjectRegistry().unregister(proj.id)

    def test_delete_purge_requires_confirm(
        self, api_client: TestClient, temp_project: Path
    ) -> None:
        """Purge mode requires confirm."""
        proj = init_project(root=temp_project, project_id="test-api-purge-confirm", register=True)

        try:
            response = api_client.delete(
                f"/api/project/lifecycle/{proj.id}?mode=purge"
            )
            assert response.status_code == 400
            assert "confirm" in response.json()["detail"].lower()
        finally:
            ProjectRegistry().unregister(proj.id)

    def test_delete_unregister_success(
        self, api_client: TestClient, temp_project: Path
    ) -> None:
        """Unregister mode succeeds without confirm."""
        proj = init_project(root=temp_project, project_id="test-api-unregister", register=True)

        response = api_client.delete(f"/api/project/lifecycle/{proj.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "deleted"
        assert data["mode"] == "unregister"

        # Verify unregistered
        registry = ProjectRegistry()
        assert registry.get(proj.id) is None


class TestProjectAPILifecycleUpdate:
    """Tests for PATCH /api/project/lifecycle/{id} endpoint."""

    def test_update_nonexistent(self, api_client: TestClient) -> None:
        """Update returns error for nonexistent project."""
        response = api_client.patch(
            "/api/project/lifecycle/nonexistent-12345",
            json={"id": "new-name"},
        )
        # Could be 400 or 404 depending on validation order
        assert response.status_code in (400, 404)

    def test_update_no_fields(self, api_client: TestClient, temp_project: Path) -> None:
        """Update requires at least one field."""
        proj = init_project(root=temp_project, project_id="test-api-update-empty", register=True)

        try:
            response = api_client.patch(f"/api/project/lifecycle/{proj.id}", json={})
            assert response.status_code == 400
        finally:
            ProjectRegistry().unregister(proj.id)

    def test_rename_success(self, api_client: TestClient, temp_project: Path) -> None:
        """Rename via PATCH succeeds."""
        proj = init_project(root=temp_project, project_id="test-api-rename-old", register=True)

        try:
            response = api_client.patch(
                f"/api/project/lifecycle/{proj.id}",
                json={"id": "test-api-rename-new"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "updated"

            # Verify renamed
            registry = ProjectRegistry()
            assert registry.get("test-api-rename-old") is None
            assert registry.get("test-api-rename-new") is not None
        finally:
            # Cleanup
            registry = ProjectRegistry()
            for proj_id in ["test-api-rename-old", "test-api-rename-new"]:
                if registry.get(proj_id):
                    registry.unregister(proj_id)


class TestProjectAPILifecycleCleanup:
    """Tests for POST /api/project/lifecycle/cleanup endpoint."""

    def test_cleanup_dry_run(self, api_client: TestClient) -> None:
        """Cleanup with dry_run returns findings."""
        response = api_client.post(
            "/api/project/lifecycle/cleanup",
            json={"dryRun": True},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["dryRun"] is True
        assert "orphanedRuns" in data
        assert "invalidRegistrations" in data

    def test_cleanup_execute(self, api_client: TestClient) -> None:
        """Cleanup with dry_run=false executes."""
        response = api_client.post(
            "/api/project/lifecycle/cleanup",
            json={"dryRun": False},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["dryRun"] is False
        assert "cleanedRuns" in data
        assert "cleanedRegistrations" in data


class TestProjectAPILifecycleActiveRuns:
    """Tests for GET /api/project/lifecycle/{id}/active-runs endpoint."""

    def test_active_runs_nonexistent(self, api_client: TestClient) -> None:
        """Active runs check works even for nonexistent project."""
        # This should not fail, just return empty
        response = api_client.get("/api/project/lifecycle/nonexistent-12345/active-runs")
        assert response.status_code == 200
        data = response.json()
        assert data["projectId"] == "nonexistent-12345"
        assert data["activeRuns"] == []
        assert data["hasActiveRuns"] is False

    def test_active_runs_existing(
        self, api_client: TestClient, temp_project: Path
    ) -> None:
        """Active runs check for existing project."""
        proj = init_project(root=temp_project, project_id="test-api-active-runs", register=True)

        try:
            response = api_client.get(f"/api/project/lifecycle/{proj.id}/active-runs")
            assert response.status_code == 200
            data = response.json()
            assert data["projectId"] == proj.id
            assert "activeRuns" in data
            assert "hasActiveRuns" in data
        finally:
            ProjectRegistry().unregister(proj.id)


# ═══════════════════════════════════════════════════════════════
# DELEGATION TESTS
# ═══════════════════════════════════════════════════════════════


class TestDelegationToWorkspaceManager:
    """Verify project operations delegate to WorkspaceManager."""

    def test_purge_delegates_to_manager(
        self, cli_runner: CliRunner, temp_project: Path
    ) -> None:
        """Project purge calls WorkspaceManager.purge()."""
        from sunwell.interface.cli.commands.project_cmd import project

        proj = init_project(root=temp_project, project_id="test-delegate-purge", register=True)

        with patch.object(WorkspaceManager, "purge") as mock_purge:
            mock_purge.return_value = PurgeResult(
                success=True,
                workspace_id=proj.id,
                workspace_path=temp_project,
                deleted_dirs=(),
                deleted_files=(),
                failed_items=(),
                runs_deleted=0,
                was_current=False,
                error=None,
            )

            cli_runner.invoke(
                project, ["purge", proj.id, "--confirm"], catch_exceptions=False
            )

            mock_purge.assert_called_once()
            call_args = mock_purge.call_args
            assert call_args[0][0] == proj.id  # workspace_id

        # Cleanup
        registry = ProjectRegistry()
        if registry.get(proj.id):
            registry.unregister(proj.id)

    def test_rename_delegates_to_manager(
        self, cli_runner: CliRunner, temp_project: Path
    ) -> None:
        """Project rename calls WorkspaceManager.rename()."""
        from sunwell.interface.cli.commands.project_cmd import project

        proj = init_project(root=temp_project, project_id="test-delegate-rename", register=True)

        with patch.object(WorkspaceManager, "rename") as mock_rename:
            mock_rename.return_value = RenameResult(
                success=True,
                old_id=proj.id,
                new_id="new-name",
                runs_updated=0,
                error=None,
            )

            cli_runner.invoke(
                project, ["rename", proj.id, "new-name"], catch_exceptions=False
            )

            mock_rename.assert_called_once()
            call_args = mock_rename.call_args
            assert call_args[0][0] == proj.id  # workspace_id
            assert call_args[1]["new_id"] == "new-name"

        # Cleanup
        registry = ProjectRegistry()
        for proj_id in [proj.id, "new-name"]:
            if registry.get(proj_id):
                registry.unregister(proj_id)

    def test_cleanup_delegates_to_manager(self, cli_runner: CliRunner) -> None:
        """Project cleanup calls WorkspaceManager.cleanup_orphaned()."""
        from sunwell.interface.cli.commands.project_cmd import project

        with patch.object(WorkspaceManager, "cleanup_orphaned") as mock_cleanup:
            mock_cleanup.return_value = CleanupResult(
                dry_run=True,
                orphaned_runs=(),
                invalid_registrations=(),
                cleaned_runs=0,
                cleaned_registrations=0,
            )

            cli_runner.invoke(project, ["cleanup"], catch_exceptions=False)

            mock_cleanup.assert_called_once()
            assert mock_cleanup.call_args[1]["dry_run"] is True
