"""Integration tests for Agent API endpoints.

Tests the run lifecycle, event streaming, and run history endpoints
that power the Studio agent execution workflows.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from sunwell.interface.server.main import create_app


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the API."""
    app = create_app(dev_mode=True)
    return TestClient(app)


@pytest.fixture
def mock_workspace(tmp_path: Path) -> Path:
    """Create a mock workspace directory."""
    workspace = tmp_path / "test-workspace"
    workspace.mkdir()
    (workspace / ".sunwell").mkdir()
    return workspace


class TestRunStart:
    """Tests for POST /api/run endpoint."""

    def test_start_run_returns_run_id(self, client: TestClient, mock_workspace: Path) -> None:
        """Start run returns a run_id for tracking."""
        response = client.post(
            "/api/run",
            json={
                "goal": "Test goal",
                "workspace": str(mock_workspace),
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "runId" in data or "run_id" in data
        assert "status" in data

    def test_start_run_with_options(self, client: TestClient, mock_workspace: Path) -> None:
        """Start run accepts optional parameters."""
        response = client.post(
            "/api/run",
            json={
                "goal": "Test goal with options",
                "workspace": str(mock_workspace),
                "provider": "ollama",
                "model": "gemma3:4b",
                "trust": "workspace",
                "timeout": 600,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "runId" in data or "run_id" in data

    def test_start_run_minimal(self, client: TestClient) -> None:
        """Start run with minimal parameters."""
        response = client.post(
            "/api/run",
            json={"goal": "Minimal test"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "runId" in data or "run_id" in data


class TestRunStatus:
    """Tests for GET /api/run/{run_id} endpoint."""

    def test_get_run_not_found(self, client: TestClient) -> None:
        """Get run returns not_found for unknown run_id."""
        response = client.get("/api/run/non-existent-run-id")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "not_found"
        assert "error" in data

    def test_get_run_after_start(self, client: TestClient, mock_workspace: Path) -> None:
        """Get run returns status after starting a run."""
        # Start a run first
        start_response = client.post(
            "/api/run",
            json={
                "goal": "Test goal",
                "workspace": str(mock_workspace),
            },
        )
        run_id = start_response.json().get("runId") or start_response.json().get("run_id")
        
        # Get its status
        response = client.get(f"/api/run/{run_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["runId"] == run_id or data["run_id"] == run_id
        assert data["status"] in ("pending", "running", "complete", "error", "cancelled")


class TestRunCancel:
    """Tests for DELETE /api/run/{run_id} endpoint."""

    def test_cancel_not_found(self, client: TestClient) -> None:
        """Cancel returns error for unknown run_id."""
        response = client.delete("/api/run/non-existent-run-id")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"

    def test_cancel_after_start(self, client: TestClient, mock_workspace: Path) -> None:
        """Cancel run returns cancelled status."""
        # Start a run first
        start_response = client.post(
            "/api/run",
            json={
                "goal": "Test goal to cancel",
                "workspace": str(mock_workspace),
            },
        )
        run_id = start_response.json().get("runId") or start_response.json().get("run_id")
        
        # Cancel it
        response = client.delete(f"/api/run/{run_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("cancelled", "error")


class TestRunsList:
    """Tests for GET /api/runs endpoint."""

    def test_list_runs_empty(self, client: TestClient) -> None:
        """List runs returns empty list when no runs exist."""
        # Mock the run store to return empty
        with patch(
            "sunwell.interface.server.routes.agent.get_run_store"
        ) as mock_store:
            mock_store.return_value.list_runs.return_value = []
            
            response = client.get("/api/runs")
            
            assert response.status_code == 200
            data = response.json()
            assert "runs" in data
            assert isinstance(data["runs"], list)

    def test_list_runs_with_project_filter(self, client: TestClient) -> None:
        """List runs accepts project_id filter."""
        response = client.get("/api/runs?project_id=test-project")
        
        assert response.status_code == 200
        data = response.json()
        assert "runs" in data

    def test_list_runs_with_limit(self, client: TestClient) -> None:
        """List runs accepts limit parameter."""
        response = client.get("/api/runs?limit=5")
        
        assert response.status_code == 200
        data = response.json()
        assert "runs" in data
        assert len(data["runs"]) <= 5


class TestActiveRuns:
    """Tests for GET /api/run/active endpoint."""

    def test_get_active_runs(self, client: TestClient) -> None:
        """Get active runs returns list of running/pending runs."""
        response = client.get("/api/run/active")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestRunHistory:
    """Tests for GET /api/run/history endpoint."""

    def test_get_run_history(self, client: TestClient) -> None:
        """Get run history returns historical runs."""
        with patch(
            "sunwell.interface.server.routes.agent.get_run_store"
        ) as mock_store:
            mock_store.return_value.list_runs.return_value = []
            
            response = client.get("/api/run/history")
            
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)

    def test_get_run_history_with_limit(self, client: TestClient) -> None:
        """Get run history accepts limit parameter."""
        response = client.get("/api/run/history?limit=10")
        
        assert response.status_code == 200


class TestRunEvents:
    """Tests for GET /api/run/{run_id}/events endpoint."""

    def test_get_events_not_found(self, client: TestClient) -> None:
        """Get events returns error for unknown run_id."""
        with patch(
            "sunwell.interface.server.routes.agent.get_run_store"
        ) as mock_store:
            mock_store.return_value.get_events.return_value = None
            
            response = client.get("/api/run/non-existent/events")
            
            assert response.status_code == 200
            data = response.json()
            assert "error" in data or data.get("events") == []

    def test_get_events_after_start(self, client: TestClient, mock_workspace: Path) -> None:
        """Get events returns events for existing run."""
        # Start a run first
        start_response = client.post(
            "/api/run",
            json={
                "goal": "Test goal",
                "workspace": str(mock_workspace),
            },
        )
        run_id = start_response.json().get("runId") or start_response.json().get("run_id")
        
        # Get its events
        response = client.get(f"/api/run/{run_id}/events")
        
        assert response.status_code == 200
        data = response.json()
        assert "runId" in data or "run_id" in data
        assert "events" in data
        assert isinstance(data["events"], list)


class TestStopRun:
    """Tests for POST /api/run/stop endpoint."""

    def test_stop_run(self, client: TestClient) -> None:
        """Stop run endpoint exists and responds."""
        response = client.post(
            "/api/run/stop",
            json={"session_id": "test-session"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
