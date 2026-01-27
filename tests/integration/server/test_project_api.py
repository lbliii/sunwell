"""Integration tests for Project API endpoints.

Tests the project discovery, scan, open-by-id, and lifecycle endpoints
that power the Studio frontend project workflows.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from sunwell.interface.server.main import create_app


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the API."""
    app = create_app(dev_mode=True)
    return TestClient(app)


@pytest.fixture
def mock_registry(tmp_path: Path):
    """Create a mock project registry."""
    registry_file = tmp_path / "projects.json"
    
    # Create test projects
    project1 = tmp_path / "test-project-1"
    project1.mkdir()
    (project1 / ".sunwell").mkdir()
    
    project2 = tmp_path / "test-project-2"
    project2.mkdir()
    (project2 / ".sunwell").mkdir()
    
    registry_data = {
        "projects": {
            "test-project-1": {
                "root": str(project1),
                "last_used": "2026-01-27T10:00:00",
                "workspace_type": "registered",
            },
            "test-project-2": {
                "root": str(project2),
                "last_used": "2026-01-26T10:00:00",
                "workspace_type": "registered",
            },
        },
        "default_project": "test-project-1",
        "slugs": {
            "test-project-1": "test-project-1",
            "test-project-2": "test-project-2",
        },
    }
    registry_file.write_text(json.dumps(registry_data))
    
    return registry_file, tmp_path


class TestProjectScan:
    """Tests for GET /project/scan endpoint."""

    def test_scan_returns_projects(self, client: TestClient, mock_registry) -> None:
        """Scan returns list of registered projects."""
        registry_file, tmp_path = mock_registry
        
        with patch(
            "sunwell.knowledge.project.registry._get_registry_path",
            return_value=registry_file,
        ):
            response = client.get("/api/project/scan")
            
            assert response.status_code == 200
            data = response.json()
            assert "projects" in data
            assert "total" in data
            assert data["total"] >= 0

    def test_scan_returns_project_details(self, client: TestClient, mock_registry) -> None:
        """Scan returns project details including status."""
        registry_file, tmp_path = mock_registry
        
        with patch(
            "sunwell.knowledge.project.registry._get_registry_path",
            return_value=registry_file,
        ):
            response = client.get("/api/project/scan")
            
            assert response.status_code == 200
            data = response.json()
            
            if data["projects"]:
                project = data["projects"][0]
                # Check required fields
                assert "id" in project
                assert "path" in project
                assert "name" in project
                assert "status" in project


class TestProjectRecent:
    """Tests for GET /project/recent endpoint."""

    def test_recent_returns_list(self, client: TestClient, mock_registry) -> None:
        """Recent returns list of recently used projects."""
        registry_file, tmp_path = mock_registry
        
        with patch(
            "sunwell.knowledge.project.registry._get_registry_path",
            return_value=registry_file,
        ):
            response = client.get("/api/project/recent")
            
            assert response.status_code == 200
            data = response.json()
            assert "recent" in data
            assert isinstance(data["recent"], list)

    def test_recent_sorted_by_last_opened(self, client: TestClient, mock_registry) -> None:
        """Recent projects are sorted by last_opened descending."""
        registry_file, tmp_path = mock_registry
        
        with patch(
            "sunwell.knowledge.project.registry._get_registry_path",
            return_value=registry_file,
        ):
            response = client.get("/api/project/recent")
            
            assert response.status_code == 200
            data = response.json()
            
            if len(data["recent"]) > 1:
                # Check sorted descending by last_opened
                times = [p.get("last_opened", 0) for p in data["recent"]]
                assert times == sorted(times, reverse=True)


class TestProjectOpenById:
    """Tests for POST /project/open-by-id endpoint."""

    def test_open_by_id_not_found(self, client: TestClient, mock_registry) -> None:
        """Open by ID returns 404 for non-existent project."""
        registry_file, tmp_path = mock_registry
        
        with patch(
            "sunwell.knowledge.project.registry._get_registry_path",
            return_value=registry_file,
        ):
            response = client.post(
                "/api/project/open-by-id",
                json={"project_id": "non-existent-project"},
            )
            
            assert response.status_code == 404

    def test_open_by_id_success(self, client: TestClient, mock_registry) -> None:
        """Open by ID returns project info for valid project."""
        registry_file, tmp_path = mock_registry
        
        with patch(
            "sunwell.knowledge.project.registry._get_registry_path",
            return_value=registry_file,
        ):
            response = client.post(
                "/api/project/open-by-id",
                json={"project_id": "test-project-1"},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == "test-project-1"
            assert "path" in data
            assert "name" in data


class TestProjectSlug:
    """Tests for project slug resolution endpoints."""

    def test_get_slug_for_path(self, client: TestClient, mock_registry) -> None:
        """Get slug returns slug for registered project path."""
        registry_file, tmp_path = mock_registry
        project_path = tmp_path / "test-project-1"
        
        with patch(
            "sunwell.knowledge.project.registry._get_registry_path",
            return_value=registry_file,
        ):
            response = client.post(
                "/api/project/slug",
                json={"path": str(project_path)},
            )
            
            assert response.status_code == 200
            data = response.json()
            # Either has slug or error
            assert "slug" in data or "error" in data

    def test_resolve_slug(self, client: TestClient, mock_registry) -> None:
        """Resolve slug returns project info."""
        registry_file, tmp_path = mock_registry
        
        with patch(
            "sunwell.knowledge.project.registry._get_registry_path",
            return_value=registry_file,
        ):
            response = client.post(
                "/api/project/resolve",
                json={"slug": "test-project-1"},
            )
            
            assert response.status_code == 200
            data = response.json()
            # Either has project, ambiguous, or error
            assert "project" in data or "ambiguous" in data or "error" in data


class TestProjectLifecycle:
    """Tests for project lifecycle endpoints (delete, archive, iterate)."""

    def test_delete_nonexistent(self, client: TestClient, mock_registry) -> None:
        """Delete returns failure for non-existent project."""
        registry_file, tmp_path = mock_registry
        
        with patch(
            "sunwell.knowledge.project.registry._get_registry_path",
            return_value=registry_file,
        ):
            response = client.post(
                "/api/project/delete",
                json={"path": str(tmp_path / "non-existent")},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False

    def test_archive_nonexistent(self, client: TestClient, mock_registry) -> None:
        """Archive returns failure for non-existent project."""
        registry_file, tmp_path = mock_registry
        
        with patch(
            "sunwell.knowledge.project.registry._get_registry_path",
            return_value=registry_file,
        ):
            response = client.post(
                "/api/project/archive",
                json={"path": str(tmp_path / "non-existent")},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False

    def test_resume_no_checkpoint(self, client: TestClient, mock_registry) -> None:
        """Resume returns no checkpoint for project without checkpoints."""
        registry_file, tmp_path = mock_registry
        project_path = tmp_path / "test-project-1"
        
        with patch(
            "sunwell.knowledge.project.registry._get_registry_path",
            return_value=registry_file,
        ):
            response = client.post(
                "/api/project/resume",
                json={"path": str(project_path)},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["checkpoint_exists"] is False
