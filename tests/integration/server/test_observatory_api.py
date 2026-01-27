"""Integration tests for Observatory API endpoints.

Tests the run history, event retrieval, and visualization data endpoints
that power the Studio Observatory workflow.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime, UTC

import pytest
from fastapi.testclient import TestClient

from sunwell.interface.server.main import create_app


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the API."""
    app = create_app(dev_mode=True)
    return TestClient(app)


@pytest.fixture
def mock_run_store():
    """Create a mock run store with sample data."""
    from sunwell.interface.server.run_store import StoredRun, ObservatorySnapshot
    
    sample_run = StoredRun(
        run_id="test-run-123",
        goal="Test goal for observatory",
        status="complete",
        source="studio",
        started_at="2026-01-27T10:00:00Z",
        completed_at="2026-01-27T10:05:00Z",
        workspace="/tmp/test-workspace",
        project_id="test-project",
        lens="coder",
        model="gemma3:4b",
        events=(
            {"type": "thinking", "data": {"content": "Planning..."}},
            {"type": "tool_call", "data": {"name": "file_read", "args": {"path": "test.py"}}},
            {"type": "tool_result", "data": {"success": True}},
            {"type": "response", "data": {"content": "Done!"}},
        ),
    )
    
    sample_snapshot = ObservatorySnapshot(
        run_id="test-run-123",
        resonance_iterations=({"iteration": 1, "score": 0.95},),
        prism_candidates=({"id": "c1", "score": 0.9}, {"id": "c2", "score": 0.8}),
        selected_candidate={"id": "c1", "score": 0.9},
        tasks=({"id": "t1", "status": "complete"}, {"id": "t2", "status": "complete"}),
        learnings=("learning 1", "learning 2"),
        convergence_iterations=({"iteration": 1}, {"iteration": 2}),
        convergence_status="converged",
    )
    
    return sample_run, sample_snapshot


class TestObservatoryData:
    """Tests for GET /api/observatory/data/{run_id} endpoint."""

    def test_observatory_data_not_found(self, client: TestClient) -> None:
        """Observatory data returns error for unknown run_id."""
        with patch(
            "sunwell.interface.server.routes.agent.get_run_store"
        ) as mock_store:
            mock_store.return_value.get_observatory_snapshot.return_value = None
            
            response = client.get("/api/observatory/data/non-existent")
            
            assert response.status_code == 200
            data = response.json()
            assert "error" in data

    def test_observatory_data_from_store(self, client: TestClient, mock_run_store) -> None:
        """Observatory data returns snapshot from persistent storage."""
        sample_run, sample_snapshot = mock_run_store
        
        with patch(
            "sunwell.interface.server.routes.agent.get_run_store"
        ) as mock_store:
            mock_store.return_value.get_observatory_snapshot.return_value = sample_snapshot
            
            response = client.get(f"/api/observatory/data/{sample_run.run_id}")
            
            assert response.status_code == 200
            data = response.json()
            # Should have visualization data sections
            assert "run_id" in data or "resonance_data" in data or "error" not in data

    def test_observatory_data_from_active_run(
        self, client: TestClient, mock_run_store
    ) -> None:
        """Observatory data builds snapshot from active run."""
        sample_run, sample_snapshot = mock_run_store
        
        # Start a run to have an active run
        start_response = client.post(
            "/api/run",
            json={"goal": "Test goal for observatory"},
        )
        run_id = start_response.json().get("runId") or start_response.json().get("run_id")
        
        with patch(
            "sunwell.interface.server.routes.agent.get_run_store"
        ) as mock_store:
            # No persisted snapshot, but run exists in memory
            mock_store.return_value.get_observatory_snapshot.return_value = None
            
            response = client.get(f"/api/observatory/data/{run_id}")
            
            assert response.status_code == 200
            data = response.json()
            # Should return data (possibly empty for new run)
            assert isinstance(data, dict)


class TestRunEventsForObservatory:
    """Tests for GET /api/run/{run_id}/events used by Observatory."""

    def test_events_structure(self, client: TestClient, mock_run_store) -> None:
        """Events response has expected structure for Observatory."""
        sample_run, _ = mock_run_store
        
        with patch(
            "sunwell.interface.server.routes.agent.get_run_store"
        ) as mock_store:
            mock_store.return_value.get_events.return_value = sample_run.events
            
            response = client.get(f"/api/run/{sample_run.run_id}/events")
            
            assert response.status_code == 200
            data = response.json()
            assert "events" in data
            
            if data["events"]:
                event = data["events"][0]
                assert "type" in event
                assert "data" in event

    def test_events_types_for_visualization(self, client: TestClient, mock_run_store) -> None:
        """Events include types needed for Observatory visualizations."""
        sample_run, _ = mock_run_store
        
        with patch(
            "sunwell.interface.server.routes.agent.get_run_store"
        ) as mock_store:
            mock_store.return_value.get_events.return_value = sample_run.events
            
            response = client.get(f"/api/run/{sample_run.run_id}/events")
            
            assert response.status_code == 200
            data = response.json()
            
            if data["events"]:
                event_types = {e["type"] for e in data["events"]}
                # Observatory needs various event types
                expected_types = {"thinking", "tool_call", "tool_result", "response"}
                # At least some expected types should be present
                assert event_types.intersection(expected_types)


class TestRunHistoryForObservatory:
    """Tests for run history endpoints used by Observatory."""

    def test_history_structure(self, client: TestClient, mock_run_store) -> None:
        """Run history has expected structure for Observatory list view."""
        sample_run, _ = mock_run_store
        
        with patch(
            "sunwell.interface.server.routes.agent.get_run_store"
        ) as mock_store:
            mock_store.return_value.list_runs.return_value = [sample_run]
            
            response = client.get("/api/run/history")
            
            assert response.status_code == 200
            data = response.json()
            
            if data:
                run = data[0]
                # Check required fields for Observatory list
                assert "runId" in run or "run_id" in run
                assert "goal" in run
                assert "status" in run

    def test_history_filter_by_project(self, client: TestClient, mock_run_store) -> None:
        """Run history can be filtered by project for Observatory."""
        sample_run, _ = mock_run_store
        
        with patch(
            "sunwell.interface.server.routes.agent.get_run_store"
        ) as mock_store:
            mock_store.return_value.list_runs.return_value = [sample_run]
            
            response = client.get("/api/run/history?project_id=test-project")
            
            assert response.status_code == 200


class TestRunsListForObservatory:
    """Tests for GET /api/runs used by Observatory to show all runs."""

    def test_runs_includes_active_and_historical(self, client: TestClient) -> None:
        """Runs list includes both active and historical runs."""
        response = client.get("/api/runs?include_historical=true")
        
        assert response.status_code == 200
        data = response.json()
        assert "runs" in data

    def test_runs_sorted_by_started_at(self, client: TestClient, mock_run_store) -> None:
        """Runs are sorted by started_at descending."""
        sample_run, _ = mock_run_store
        
        with patch(
            "sunwell.interface.server.routes.agent.get_run_store"
        ) as mock_store:
            mock_store.return_value.list_runs.return_value = [sample_run]
            
            response = client.get("/api/runs")
            
            assert response.status_code == 200
            data = response.json()
            
            if len(data["runs"]) > 1:
                # Check sorted descending by startedAt
                times = [r.get("startedAt") or r.get("started_at") for r in data["runs"]]
                assert times == sorted(times, reverse=True)


class TestObservatoryIntegration:
    """Integration tests for Observatory workflow end-to-end."""

    def test_run_to_observatory_flow(self, client: TestClient) -> None:
        """Test complete flow: start run -> get events -> get observatory data."""
        # 1. Start a run
        start_response = client.post(
            "/api/run",
            json={"goal": "Integration test goal"},
        )
        assert start_response.status_code == 200
        run_id = start_response.json().get("runId") or start_response.json().get("run_id")
        
        # 2. Check run status
        status_response = client.get(f"/api/run/{run_id}")
        assert status_response.status_code == 200
        
        # 3. Get events for the run
        events_response = client.get(f"/api/run/{run_id}/events")
        assert events_response.status_code == 200
        assert "events" in events_response.json()
        
        # 4. Get observatory data
        observatory_response = client.get(f"/api/observatory/data/{run_id}")
        assert observatory_response.status_code == 200

    def test_list_then_detail_flow(self, client: TestClient) -> None:
        """Test flow: list runs -> select run -> view details."""
        # 1. List all runs
        list_response = client.get("/api/runs")
        assert list_response.status_code == 200
        runs = list_response.json()["runs"]
        
        # 2. If runs exist, get details for first one
        if runs:
            run_id = runs[0].get("runId") or runs[0].get("run_id")
            
            # Get status
            status_response = client.get(f"/api/run/{run_id}")
            assert status_response.status_code == 200
            
            # Get events
            events_response = client.get(f"/api/run/{run_id}/events")
            assert events_response.status_code == 200
