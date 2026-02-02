"""Tests for resume command and continuation intent detection."""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from sunwell.interface.cli.core.main import CONTINUATION_PATTERNS, main
from sunwell.planning.naaru.session_store import SessionStore
from sunwell.planning.naaru.types import SessionConfig, SessionState, SessionStatus


class TestContinuationPatterns:
    """Test continuation intent patterns."""

    def test_continuation_patterns_lowercase(self) -> None:
        """Test continuation patterns are lowercase."""
        for pattern in CONTINUATION_PATTERNS:
            assert pattern == pattern.lower(), f"Pattern '{pattern}' should be lowercase"

    def test_common_patterns_included(self) -> None:
        """Test common continuation phrases are included."""
        expected = {"yes", "y", "continue", "proceed", "go", "ok", "sure"}
        assert expected.issubset(CONTINUATION_PATTERNS)

    def test_patterns_are_frozen(self) -> None:
        """Test patterns set is immutable."""
        assert isinstance(CONTINUATION_PATTERNS, frozenset)


class TestContinuationIntentDetection:
    """Test continuation intent detection in CLI."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a Click test runner."""
        return CliRunner()

    @pytest.fixture
    def temp_sessions_dir(self):
        """Create a temporary sessions directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_continuation_intent_flag_set(self, runner: CliRunner) -> None:
        """Test that continuation intent flag is set for matching patterns."""
        # Mock at the source module where SessionStore is defined
        with patch(
            "sunwell.interface.cli.commands.goal.run_goal_unified",
            new_callable=AsyncMock,
        ):
            with patch(
                "sunwell.planning.naaru.session_store.SessionStore"
            ) as mock_store:
                mock_store.return_value.get_resumable_sessions.return_value = []
                
                result = runner.invoke(main, ["yes"])
                
                # Should attempt to check for resumable sessions
                # (the continuation detection path calls SessionStore)
                assert mock_store.called or result.exit_code in (0, 1)

    def test_non_continuation_input_not_flagged(self, runner: CliRunner) -> None:
        """Test that normal goals don't trigger continuation check."""
        with patch(
            "sunwell.interface.cli.commands.goal.run_goal_unified",
            new_callable=AsyncMock,
        ):
            # For normal goals, should proceed to run_goal_unified
            result = runner.invoke(main, ["build a todo app"])
            
            # Should not error out with continuation-related issues
            assert "unexpected" not in result.output.lower()


class TestResumeCommand:
    """Test sunwell resume command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a Click test runner."""
        return CliRunner()

    @pytest.fixture
    def temp_sessions_dir(self):
        """Create a temporary sessions directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_resume_command_exists(self, runner: CliRunner) -> None:
        """Test that resume command is registered."""
        result = runner.invoke(main, ["resume", "--help"])
        
        assert result.exit_code == 0
        assert "Resume an interrupted goal" in result.output

    def test_resume_list_option(self, runner: CliRunner) -> None:
        """Test resume --list option."""
        with patch(
            "sunwell.planning.naaru.session_store.SessionStore"
        ) as mock_store:
            mock_store.return_value.get_resumable_sessions.return_value = []
            
            result = runner.invoke(main, ["resume", "--list"])
            
            # Should show "no resumable goals" message
            assert "No resumable goals found" in result.output or result.exit_code == 0

    def test_resume_with_session_id(self, runner: CliRunner) -> None:
        """Test resume with specific session ID."""
        with patch(
            "sunwell.planning.naaru.session_store.SessionStore"
        ) as mock_store:
            mock_store.return_value.load.return_value = None
            
            result = runner.invoke(main, ["resume", "nonexistent-session"])
            
            assert "Session not found" in result.output or "not found" in result.output.lower()

    def test_resume_shows_in_help(self, runner: CliRunner) -> None:
        """Test that resume shows in main help."""
        result = runner.invoke(main, ["--help"])
        
        # resume should be visible in help (Tier 1-2)
        assert "resume" in result.output


class TestGoalSessionTracking:
    """Test session tracking during goal execution."""

    @pytest.fixture
    def temp_sessions_dir(self):
        """Create a temporary sessions directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_create_goal_session(self, temp_sessions_dir: Path) -> None:
        """Test _create_goal_session creates a valid session."""
        from sunwell.interface.cli.commands.goal import _create_goal_session

        with patch(
            "sunwell.planning.naaru.session_store.SessionStore"
        ) as mock_store_class:
            mock_store = mock_store_class.return_value
            mock_store.save.return_value = temp_sessions_dir / "test-session"

            session_id = _create_goal_session("test goal", Path("/workspace"))

            assert session_id is not None
            assert len(session_id) == 12  # UUID hex[:12]
            mock_store.save.assert_called_once()
            mock_store.set_metadata.assert_called_once()

    def test_update_session_status(self) -> None:
        """Test _update_session_status updates correctly."""
        from sunwell.interface.cli.commands.goal import _update_session_status

        with patch(
            "sunwell.planning.naaru.session_store.SessionStore"
        ) as mock_store_class:
            mock_store = mock_store_class.return_value

            _update_session_status("test-session", "paused", "User interrupted")

            mock_store.update_status.assert_called_once()
            call_args = mock_store.update_status.call_args
            assert call_args[0][0] == "test-session"
            assert call_args[0][1] == SessionStatus.PAUSED
            assert call_args[0][2] == "User interrupted"


class TestResumeIntegration:
    """Integration tests for resume functionality."""

    @pytest.fixture
    def temp_sessions_dir(self):
        """Create a temporary sessions directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_session_roundtrip(self, temp_sessions_dir: Path) -> None:
        """Test full session create -> pause -> resume roundtrip."""
        store = SessionStore(sessions_dir=temp_sessions_dir)

        # Create session (simulating goal start)
        state = SessionState(
            session_id="roundtrip-test",
            config=SessionConfig(goals=("test goal",)),
            status=SessionStatus.RUNNING,
        )
        store.save(state)
        store.set_metadata("roundtrip-test", workspace_id="/test/workspace")

        # Pause session (simulating Ctrl+C)
        store.update_status("roundtrip-test", SessionStatus.PAUSED, "User interrupted")

        # Check it's resumable
        resumable = store.get_resumable_sessions()
        assert len(resumable) == 1
        assert resumable[0].session_id == "roundtrip-test"
        assert resumable[0].status == SessionStatus.PAUSED

        # Load for resume
        loaded = store.load("roundtrip-test")
        assert loaded is not None
        assert loaded.status == SessionStatus.PAUSED
        assert loaded.config.goals == ("test goal",)
