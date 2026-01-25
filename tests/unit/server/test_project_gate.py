"""Tests for Project Gate endpoints (RFC-132).

Tests the validation, list, create, and default project endpoints.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from sunwell.server.routes.project import (
    CreateProjectRequest,
    ProjectPathRequest,
    SetDefaultRequest,
    create_project,
    get_default_project,
    list_projects,
    set_default_project,
    validate_project_path,
)


class TestValidateProjectPath:
    """Tests for /api/project/validate endpoint."""

    @pytest.mark.asyncio
    async def test_validate_nonexistent_path(self, tmp_path: Path) -> None:
        """Validation returns not_found for non-existent paths."""
        request = ProjectPathRequest(path=str(tmp_path / "does-not-exist"))

        result = await validate_project_path(request)

        assert result.valid is False
        assert result.error_code == "not_found"
        assert "does not exist" in (result.error_message or "")

    @pytest.mark.asyncio
    async def test_validate_valid_workspace(self, tmp_path: Path) -> None:
        """Validation passes for valid workspace."""
        # Create a simple project directory
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()

        request = ProjectPathRequest(path=str(project_dir))

        result = await validate_project_path(request)

        assert result.valid is True
        assert result.error_code is None

    @pytest.mark.asyncio
    async def test_validate_sunwell_repo_error(self, tmp_path: Path) -> None:
        """Validation returns sunwell_repo error for Sunwell's own repo."""
        from sunwell.project.validation import ProjectValidationError

        project_dir = tmp_path / "sunwell"
        project_dir.mkdir()

        with patch(
            "sunwell.project.validation.validate_workspace",
            side_effect=ProjectValidationError(
                "Cannot use Sunwell's own repository as workspace"
            ),
        ):
            request = ProjectPathRequest(path=str(project_dir))

            result = await validate_project_path(request)

            assert result.valid is False
            assert result.error_code == "sunwell_repo"
            assert result.suggestion is not None


class TestListProjects:
    """Tests for /api/project/list endpoint."""

    @pytest.mark.asyncio
    async def test_list_empty_registry(self, tmp_path: Path) -> None:
        """List returns empty when no projects registered."""
        # Use a temp registry file
        registry_file = tmp_path / "projects.json"
        registry_file.write_text('{"projects": {}, "default_project": null}')

        with patch(
            "sunwell.project.registry._get_registry_path", return_value=registry_file
        ):
            result = await list_projects()

            assert "projects" in result
            assert result["projects"] == []

    @pytest.mark.asyncio
    async def test_list_returns_projects_with_validity(self, tmp_path: Path) -> None:
        """List returns projects with validity status."""
        # Create a valid project directory
        valid_project = tmp_path / "valid-project"
        valid_project.mkdir()
        (valid_project / ".sunwell").mkdir()

        # Set up registry with project
        registry_file = tmp_path / "projects.json"
        import json

        registry_data = {
            "projects": {
                "valid-project": {
                    "root": str(valid_project),
                    "last_used": "2026-01-24T10:00:00",
                    "workspace_type": "registered",
                }
            },
            "default_project": "valid-project",
        }
        registry_file.write_text(json.dumps(registry_data))

        with patch(
            "sunwell.project.registry._get_registry_path", return_value=registry_file
        ):
            result = await list_projects()

            assert len(result["projects"]) == 1
            proj = result["projects"][0]
            assert proj.id == "valid-project"
            assert proj.valid is True
            assert proj.is_default is True


class TestCreateProject:
    """Tests for /api/project/create endpoint."""

    @pytest.mark.asyncio
    async def test_create_invalid_empty_name(self) -> None:
        """Create returns error for empty name."""
        request = CreateProjectRequest(name="  ")

        result = await create_project(request)

        assert result.error == "invalid_name"
        assert "empty" in (result.message or "").lower()

    @pytest.mark.asyncio
    async def test_create_invalid_long_name(self) -> None:
        """Create returns error for too long name."""
        request = CreateProjectRequest(name="a" * 100)

        result = await create_project(request)

        assert result.error == "invalid_name"
        assert "too long" in (result.message or "").lower()

    @pytest.mark.asyncio
    async def test_create_invalid_path_separator(self) -> None:
        """Create returns error for name with path separators."""
        request = CreateProjectRequest(name="my/project")

        result = await create_project(request)

        assert result.error == "invalid_name"
        assert "path separator" in (result.message or "").lower()

    @pytest.mark.asyncio
    async def test_create_project_success(self, tmp_path: Path) -> None:
        """Create project successfully."""
        import json

        # Set up registry file
        registry_file = tmp_path / "registry" / "projects.json"
        registry_file.parent.mkdir(parents=True)
        registry_file.write_text('{"projects": {}, "default_project": null}')

        projects_dir = tmp_path / "projects"
        projects_dir.mkdir()

        with (
            patch(
                "sunwell.workspace.resolver.default_workspace_root",
                return_value=projects_dir,
            ),
            patch(
                "sunwell.project.registry._get_registry_path",
                return_value=registry_file,
            ),
        ):
            request = CreateProjectRequest(name="My App")

            result = await create_project(request)

            assert result.error is None
            assert result.project["id"] == "my-app"
            assert result.project["name"] == "My App"
            assert result.is_new is True
            # Should auto-set as default since no default exists
            assert result.is_default is True

            # Verify registry was updated
            registry = json.loads(registry_file.read_text())
            assert "my-app" in registry["projects"]
            assert registry["default_project"] == "my-app"


class TestGetDefaultProject:
    """Tests for GET /api/project/default endpoint."""

    @pytest.mark.asyncio
    async def test_get_default_none(self, tmp_path: Path) -> None:
        """Get default returns null when no default set."""
        registry_file = tmp_path / "projects.json"
        registry_file.write_text('{"projects": {}, "default_project": null}')

        with patch(
            "sunwell.project.registry._get_registry_path", return_value=registry_file
        ):
            result = await get_default_project()

            assert result["project"] is None

    @pytest.mark.asyncio
    async def test_get_default_valid_project(self, tmp_path: Path) -> None:
        """Get default returns project info when valid."""
        import json

        project_dir = tmp_path / "default-project"
        project_dir.mkdir()
        (project_dir / ".sunwell").mkdir()

        registry_file = tmp_path / "projects.json"
        registry_data = {
            "projects": {
                "default-project": {
                    "root": str(project_dir),
                    "workspace_type": "registered",
                }
            },
            "default_project": "default-project",
        }
        registry_file.write_text(json.dumps(registry_data))

        with patch(
            "sunwell.project.registry._get_registry_path", return_value=registry_file
        ):
            result = await get_default_project()

            assert result["project"] is not None
            assert result["project"]["id"] == "default-project"


class TestSetDefaultProject:
    """Tests for PUT /api/project/default endpoint."""

    @pytest.mark.asyncio
    async def test_set_default_not_found(self, tmp_path: Path) -> None:
        """Set default returns error for non-existent project."""
        registry_file = tmp_path / "projects.json"
        registry_file.write_text('{"projects": {}, "default_project": null}')

        with patch(
            "sunwell.project.registry._get_registry_path", return_value=registry_file
        ):
            request = SetDefaultRequest(project_id="not-exist")

            result = await set_default_project(request)

            assert result["error"] == "not_found"
            assert "not found" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_set_default_success(self, tmp_path: Path) -> None:
        """Set default successfully."""
        import json

        project_dir = tmp_path / "my-project"
        project_dir.mkdir()

        registry_file = tmp_path / "projects.json"
        registry_data = {
            "projects": {
                "my-project": {
                    "root": str(project_dir),
                    "workspace_type": "registered",
                }
            },
            "default_project": None,
        }
        registry_file.write_text(json.dumps(registry_data))

        with patch(
            "sunwell.project.registry._get_registry_path", return_value=registry_file
        ):
            request = SetDefaultRequest(project_id="my-project")

            result = await set_default_project(request)

            assert result["success"] is True
            assert result["default_project"] == "my-project"

            # Verify registry was updated
            registry = json.loads(registry_file.read_text())
            assert registry["default_project"] == "my-project"
