"""Tests for SessionContext (RFC: Architecture Proposal).

Tests the consolidated session state object.
"""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from sunwell.agent.context.session import SessionContext


class TestSessionContextProperties:
    """Tests for SessionContext properties and methods."""

    @pytest.fixture
    def session(self, tmp_path: Path) -> SessionContext:
        """Create a sample session for testing."""
        return SessionContext(
            session_id="test-session-123",
            cwd=tmp_path,
            goal="build an API",
            project_name="test-project",
            project_type="python",
            framework="fastapi",
            key_files=[("pyproject.toml", "[project]")],
            entry_points=["src/main.py"],
            directory_tree="├── src/",
            briefing=None,
            trust="workspace",
            timeout=300,
            model_name="gpt-4o",
            lens=None,
        )

    def test_session_id_is_set(self, session: SessionContext) -> None:
        """Session should have a unique session ID."""
        assert session.session_id == "test-session-123"

    def test_goal_is_set(self, session: SessionContext) -> None:
        """Session should have the goal."""
        assert session.goal == "build an API"

    def test_project_info_is_set(self, session: SessionContext) -> None:
        """Session should have project info."""
        assert session.project_type == "python"
        assert session.framework == "fastapi"
        assert session.project_name == "test-project"

    def test_to_planning_prompt_returns_string(self, session: SessionContext) -> None:
        """to_planning_prompt() should return a string."""
        prompt = session.to_planning_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_to_task_prompt_returns_string(self, session: SessionContext) -> None:
        """to_task_prompt() should return a string."""
        mock_task = MagicMock()
        mock_task.description = "Create API endpoint"

        prompt = session.to_task_prompt(mock_task)

        assert isinstance(prompt, str)

    def test_summary_returns_dict(self, session: SessionContext) -> None:
        """summary() should return session info dict."""
        summary = session.summary()

        assert isinstance(summary, dict)
        assert "session_id" in summary
        assert "goal" in summary


class TestSessionContextMutation:
    """Tests for SessionContext mutation during execution."""

    @pytest.fixture
    def session(self, tmp_path: Path) -> SessionContext:
        """Create a sample session for testing."""
        return SessionContext(
            session_id="test-session",
            cwd=tmp_path,
            goal="test goal",
            project_name="test",
            project_type="python",
            framework=None,
            key_files=[],
            entry_points=[],
            directory_tree="",
            briefing=None,
            trust="workspace",
            timeout=300,
            model_name="gpt-4o",
            lens=None,
        )

    def test_add_task(self, session: SessionContext) -> None:
        """Tasks can be added to session."""
        mock_task = MagicMock()
        session.tasks.append(mock_task)

        assert len(session.tasks) == 1
        assert session.tasks[0] is mock_task

    def test_update_current_task(self, session: SessionContext) -> None:
        """Current task can be updated."""
        mock_task = MagicMock()
        session.current_task = mock_task

        assert session.current_task is mock_task

    def test_track_files_modified(self, session: SessionContext) -> None:
        """Files modified can be tracked."""
        session.files_modified.append("src/api.py")
        session.files_modified.append("src/models.py")

        assert len(session.files_modified) == 2
        assert "src/api.py" in session.files_modified

    def test_track_artifacts_created(self, session: SessionContext) -> None:
        """Artifacts created can be tracked."""
        session.artifacts_created.append("test.db")

        assert len(session.artifacts_created) == 1
        assert "test.db" in session.artifacts_created


class TestSessionContextBuild:
    """Tests for SessionContext.build() factory method."""

    def test_build_exists(self) -> None:
        """SessionContext.build() class method should exist."""
        assert hasattr(SessionContext, "build")
        assert callable(SessionContext.build)

    def test_build_auto_corrects_sunwell_directory(self, tmp_path: Path) -> None:
        """build() auto-corrects .sunwell directory to parent."""
        # Create a .sunwell directory inside the project
        project_dir = tmp_path / "my-project"
        project_dir.mkdir()
        sunwell_dir = project_dir / ".sunwell"
        sunwell_dir.mkdir()

        # Build session from .sunwell directory
        session = SessionContext.build(
            cwd=sunwell_dir,
            goal="test goal",
        )

        # Should have auto-corrected to parent
        assert session.cwd == project_dir
        assert session.project_name == "my-project"

    def test_build_uses_regular_directory_as_is(self, tmp_path: Path) -> None:
        """build() uses regular directories without modification."""
        project_dir = tmp_path / "my-project"
        project_dir.mkdir()

        session = SessionContext.build(
            cwd=project_dir,
            goal="test goal",
        )

        assert session.cwd == project_dir
        assert session.project_name == "my-project"
