"""Tests for lineage API endpoints (RFC-121 Phase 5).

Requires FastAPI and httpx to be installed. Skipped if not available.
"""

import json
from pathlib import Path

import pytest

# Skip all tests if FastAPI not installed
pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from sunwell.lineage import LineageStore


@pytest.fixture
def temp_project(tmp_path):
    """Create a temp project with lineage data."""
    # Initialize lineage store
    store = LineageStore(tmp_path)

    # Create some test files
    src_dir = tmp_path / "src"
    src_dir.mkdir()

    (src_dir / "base.py").write_text("class Base: pass")
    (src_dir / "auth.py").write_text("from .base import Base\nclass Auth(Base): pass")

    # Record lineage
    store.record_create(
        path="src/base.py",
        content="class Base: pass",
        goal_id="goal-001",
        task_id="task-001",
        reason="Base class",
        model="claude-sonnet",
    )

    store.record_create(
        path="src/auth.py",
        content="from .base import Base\nclass Auth(Base): pass",
        goal_id="goal-001",
        task_id="task-002",
        reason="Auth module",
        model="claude-sonnet",
    )

    # Set up dependencies
    store.update_imports("src/auth.py", ["src/base.py"])
    store.add_imported_by("src/base.py", "src/auth.py")

    return tmp_path


@pytest.fixture
def client(temp_project, monkeypatch):
    """Create test client with temp project."""
    # Monkeypatch cwd to temp project
    monkeypatch.chdir(temp_project)

    from sunwell.server.main import create_app

    app = create_app(dev_mode=True)
    return TestClient(app)


class TestLineageFileEndpoint:
    def test_get_file_lineage(self, client):
        response = client.get("/api/lineage/src/base.py")
        assert response.status_code == 200
        data = response.json()
        assert data["path"] == "src/base.py"
        assert data["created_by_goal"] == "goal-001"
        assert data["model"] == "claude-sonnet"

    def test_get_missing_file(self, client):
        response = client.get("/api/lineage/nonexistent.py")
        assert response.status_code == 200
        data = response.json()
        assert "error" in data


class TestLineageGoalEndpoint:
    def test_get_goal_artifacts(self, client):
        response = client.get("/api/lineage/goal/goal-001")
        assert response.status_code == 200
        data = response.json()
        assert data["goal_id"] == "goal-001"
        assert data["count"] == 2
        paths = [a["path"] for a in data["artifacts"]]
        assert "src/base.py" in paths
        assert "src/auth.py" in paths

    def test_get_missing_goal(self, client):
        response = client.get("/api/lineage/goal/nonexistent")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0


class TestLineageDepsEndpoint:
    def test_get_dependencies(self, client):
        response = client.get("/api/lineage/deps/src/auth.py")
        assert response.status_code == 200
        data = response.json()
        assert data["path"] == "src/auth.py"
        assert "src/base.py" in data["imports"]

    def test_get_imported_by(self, client):
        response = client.get("/api/lineage/deps/src/base.py")
        assert response.status_code == 200
        data = response.json()
        assert "src/auth.py" in data["imported_by"]


class TestLineageImpactEndpoint:
    def test_impact_analysis(self, client):
        response = client.get("/api/lineage/impact/src/base.py")
        assert response.status_code == 200
        data = response.json()
        assert data["path"] == "src/base.py"
        # base.py is imported by auth.py
        assert "src/auth.py" in data["affected_files"]

    def test_no_impact(self, client):
        response = client.get("/api/lineage/impact/src/auth.py")
        assert response.status_code == 200
        data = response.json()
        # auth.py is not imported by anything
        assert data["affected_files"] == []


class TestLineageStatsEndpoint:
    def test_get_stats(self, client):
        response = client.get("/api/lineage/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["tracked_files"] == 2
        assert data["sunwell_edits"] == 0  # Only creation, no edits yet
        assert data["dependency_edges"] == 1  # auth imports base


class TestLineageGraphEndpoint:
    def test_get_graph(self, client):
        response = client.get("/api/lineage/graph")
        assert response.status_code == 200
        data = response.json()
        assert data["node_count"] == 2
        assert data["edge_count"] == 1
        # Check nodes
        node_ids = [n["id"] for n in data["nodes"]]
        assert "src/base.py" in node_ids
        assert "src/auth.py" in node_ids


class TestLineageSyncEndpoint:
    def test_detect_untracked(self, client, temp_project):
        # Modify a file outside Sunwell
        (temp_project / "src" / "base.py").write_text("class Base:\n    pass  # modified")

        response = client.get("/api/lineage/sync")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= 1
        paths = [c["path"] for c in data["untracked"]]
        assert "src/base.py" in paths

    def test_sync_untracked(self, client, temp_project):
        # Modify a file
        (temp_project / "src" / "base.py").write_text("class Base:\n    modified = True")

        response = client.post("/api/lineage/sync", json={})
        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= 1
