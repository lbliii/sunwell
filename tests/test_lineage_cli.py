"""Tests for lineage CLI commands (RFC-121 Phase 4)."""

import json
from pathlib import Path
from click.testing import CliRunner
import pytest

from sunwell.interface.cli.lineage_cmd import lineage


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def temp_project(tmp_path):
    """Create a temp project with lineage data."""
    from sunwell.lineage import LineageStore
    
    # Initialize lineage store
    store = LineageStore(tmp_path)
    
    # Create some test files
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    
    (src_dir / "base.py").write_text("class Base: pass")
    (src_dir / "auth.py").write_text("from .base import Base\nclass Auth(Base): pass")
    (src_dir / "api.py").write_text("from .auth import Auth\nclass Api: pass")
    
    # Record lineage
    store.record_create(
        path="src/base.py",
        content="class Base: pass",
        goal_id="goal-001",
        task_id="task-001",
        reason="Base class for inheritance",
        model="claude-sonnet",
    )
    
    store.record_create(
        path="src/auth.py",
        content="from .base import Base\nclass Auth(Base): pass",
        goal_id="goal-001",
        task_id="task-002",
        reason="Auth module extending Base",
        model="claude-sonnet",
    )
    
    store.record_create(
        path="src/api.py",
        content="from .auth import Auth\nclass Api: pass",
        goal_id="goal-002",
        task_id="task-003",
        reason="API module using Auth",
        model="claude-sonnet",
    )
    
    # Set up dependencies
    store.update_imports("src/auth.py", ["src/base.py"])
    store.add_imported_by("src/base.py", "src/auth.py")
    
    store.update_imports("src/api.py", ["src/auth.py"])
    store.add_imported_by("src/auth.py", "src/api.py")
    
    return tmp_path


class TestLineageShow:
    def test_show_existing_file(self, runner, temp_project):
        result = runner.invoke(lineage, ["show", "src/auth.py", "-w", str(temp_project)])
        assert result.exit_code == 0
        assert "src/auth.py" in result.output
        assert "goal-001" in result.output
        assert "Auth module extending Base" in result.output

    def test_show_json_output(self, runner, temp_project):
        result = runner.invoke(lineage, ["show", "src/auth.py", "--json", "-w", str(temp_project)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["path"] == "src/auth.py"
        assert data["created_by_goal"] == "goal-001"

    def test_show_missing_file(self, runner, temp_project):
        result = runner.invoke(lineage, ["show", "nonexistent.py", "-w", str(temp_project)])
        assert result.exit_code == 0
        assert "No lineage found" in result.output


class TestLineageGoal:
    def test_goal_artifacts(self, runner, temp_project):
        result = runner.invoke(lineage, ["goal", "goal-001", "-w", str(temp_project)])
        assert result.exit_code == 0
        assert "src/base.py" in result.output
        assert "src/auth.py" in result.output
        # goal-002 created api.py
        assert "src/api.py" not in result.output

    def test_goal_json_output(self, runner, temp_project):
        result = runner.invoke(lineage, ["goal", "goal-001", "--json", "-w", str(temp_project)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["goal_id"] == "goal-001"
        assert len(data["artifacts"]) == 2


class TestLineageDeps:
    def test_deps_both_directions(self, runner, temp_project):
        result = runner.invoke(lineage, ["deps", "src/auth.py", "-w", str(temp_project)])
        assert result.exit_code == 0
        assert "imports" in result.output
        assert "imported by" in result.output

    def test_deps_imports_only(self, runner, temp_project):
        result = runner.invoke(lineage, ["deps", "src/auth.py", "--direction", "imports", "-w", str(temp_project)])
        assert result.exit_code == 0
        assert "imports" in result.output or "src/base.py" in result.output

    def test_deps_json_output(self, runner, temp_project):
        result = runner.invoke(lineage, ["deps", "src/auth.py", "--json", "-w", str(temp_project)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["path"] == "src/auth.py"
        assert "imports" in data
        assert "imported_by" in data


class TestLineageImpact:
    def test_impact_analysis(self, runner, temp_project):
        result = runner.invoke(lineage, ["impact", "src/base.py", "-w", str(temp_project)])
        assert result.exit_code == 0
        # base.py is imported by auth.py
        assert "src/auth.py" in result.output or "affected" in result.output.lower()

    def test_impact_json_output(self, runner, temp_project):
        result = runner.invoke(lineage, ["impact", "src/base.py", "--json", "-w", str(temp_project)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "affected_files" in data
        assert "affected_goals" in data

    def test_impact_safe_file(self, runner, temp_project):
        # api.py is not imported by anything
        result = runner.invoke(lineage, ["impact", "src/api.py", "-w", str(temp_project)])
        assert result.exit_code == 0
        assert "No files depend" in result.output or "Safe" in result.output


class TestLineageInit:
    def test_init_creates_directory(self, runner, tmp_path):
        result = runner.invoke(lineage, ["init", "-w", str(tmp_path)])
        assert result.exit_code == 0
        assert "initialized" in result.output.lower()
        assert (tmp_path / ".sunwell" / "lineage").exists()


class TestLineageStats:
    def test_stats_output(self, runner, temp_project):
        result = runner.invoke(lineage, ["stats", "-w", str(temp_project)])
        assert result.exit_code == 0
        assert "Tracked files" in result.output or "tracked" in result.output.lower()

    def test_stats_json_output(self, runner, temp_project):
        result = runner.invoke(lineage, ["stats", "--json", "-w", str(temp_project)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "tracked_files" in data
        assert data["tracked_files"] == 3


class TestLineageSync:
    def test_sync_no_changes(self, runner, temp_project):
        result = runner.invoke(lineage, ["sync", "-w", str(temp_project)])
        # All files were just created, should be in sync
        assert result.exit_code == 0

    def test_sync_json_output(self, runner, temp_project):
        result = runner.invoke(lineage, ["sync", "--json", "-w", str(temp_project)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "untracked" in data
