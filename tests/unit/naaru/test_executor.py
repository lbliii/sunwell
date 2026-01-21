"""Unit tests for Naaru executor."""

from unittest.mock import AsyncMock, Mock

import pytest

from sunwell.naaru.executor import (
    ArtifactExecutor,
    ArtifactResult,
    ExecutionEvent,
    ExecutionResult,
)


class TestArtifactResult:
    """Test ArtifactResult type."""

    def test_artifact_result_creation(self) -> None:
        """Test ArtifactResult can be created."""
        result = ArtifactResult(
            artifact_id="test-1",
            content="test content",
            verified=True,
        )
        assert result.artifact_id == "test-1"
        assert result.content == "test content"
        assert result.verified is True
        assert result.success is True

    def test_artifact_result_with_error(self) -> None:
        """Test ArtifactResult with error."""
        result = ArtifactResult(
            artifact_id="test-2",
            error="Test error",
        )
        assert result.error == "Test error"
        assert result.success is False

    def test_artifact_result_success_property(self) -> None:
        """Test ArtifactResult success property."""
        # Success case
        success_result = ArtifactResult(
            artifact_id="test-3",
            content="content",
        )
        assert success_result.success is True

        # Failure case - has error
        fail_result = ArtifactResult(
            artifact_id="test-4",
            error="error",
        )
        assert fail_result.success is False

        # Failure case - no content
        no_content_result = ArtifactResult(
            artifact_id="test-5",
            content=None,
        )
        assert no_content_result.success is False


class TestExecutionResult:
    """Test ExecutionResult type."""

    def test_execution_result_creation(self) -> None:
        """Test ExecutionResult can be created."""
        result = ExecutionResult()
        assert len(result.completed) == 0
        assert len(result.failed) == 0
        assert len(result.waves) == 0

    def test_execution_result_success_rate(self) -> None:
        """Test ExecutionResult success_rate calculation."""
        result = ExecutionResult()
        
        # Empty result
        assert result.success_rate == 1.0

        # All successful
        result.completed["a1"] = ArtifactResult(artifact_id="a1", content="content")
        result.completed["a2"] = ArtifactResult(artifact_id="a2", content="content")
        assert result.success_rate == 1.0

        # Mixed results
        result.failed["a3"] = "Error message"
        # 2 successful out of 3 total = 0.666...
        assert result.success_rate == pytest.approx(2.0 / 3.0, rel=1e-2)

    def test_execution_result_verification_rate(self) -> None:
        """Test ExecutionResult verification_rate calculation."""
        result = ExecutionResult()
        
        # Empty result
        assert result.verification_rate == 1.0

        # All verified
        result.completed["a1"] = ArtifactResult(
            artifact_id="a1", content="content", verified=True
        )
        result.completed["a2"] = ArtifactResult(
            artifact_id="a2", content="content", verified=True
        )
        assert result.verification_rate == 1.0

        # Mixed verification
        result.completed["a3"] = ArtifactResult(
            artifact_id="a3", content="content", verified=False
        )
        # 2 verified out of 3 = 0.666...
        assert result.verification_rate == pytest.approx(2.0 / 3.0, rel=1e-2)

    def test_execution_result_to_dict(self) -> None:
        """Test ExecutionResult to_dict conversion."""
        result = ExecutionResult()
        result.completed["a1"] = ArtifactResult(
            artifact_id="a1",
            content="test content",
            verified=True,
            model_tier="medium",
            duration_ms=100,
        )
        result.failed["a2"] = "Test error"
        result.waves = [["a1"], ["a2"]]
        result.total_duration_ms = 200

        data = result.to_dict()
        
        assert "completed" in data
        assert "failed" in data
        assert "waves" in data
        assert "success_rate" in data
        assert "verification_rate" in data
        assert data["total_duration_ms"] == 200


class TestExecutionEvent:
    """Test ExecutionEvent type."""

    def test_execution_event_creation(self) -> None:
        """Test ExecutionEvent can be created."""
        event = ExecutionEvent(
            event_type="wave_start",
            wave_number=1,
            message="Starting wave 1",
        )
        assert event.event_type == "wave_start"
        assert event.wave_number == 1
        assert event.message == "Starting wave 1"
        assert event.artifact_id is None

    def test_execution_event_with_artifact(self) -> None:
        """Test ExecutionEvent with artifact."""
        event = ExecutionEvent(
            event_type="artifact_complete",
            artifact_id="test-1",
            message="Completed artifact",
        )
        assert event.artifact_id == "test-1"
        assert event.event_type == "artifact_complete"


class TestArtifactExecutor:
    """Test ArtifactExecutor."""

    def test_artifact_executor_creation(self) -> None:
        """Test ArtifactExecutor can be created."""
        executor = ArtifactExecutor()
        assert executor.planner is None
        assert executor.verify is True
        assert executor.dynamic_discovery is True
        assert executor.on_event is None

    def test_artifact_executor_with_options(self) -> None:
        """Test ArtifactExecutor with custom options."""
        mock_planner = Mock()
        mock_callback = Mock()
        
        executor = ArtifactExecutor(
            planner=mock_planner,
            verify=False,
            dynamic_discovery=False,
            on_event=mock_callback,
        )
        
        assert executor.planner == mock_planner
        assert executor.verify is False
        assert executor.dynamic_discovery is False
        assert executor.on_event == mock_callback

    @pytest.mark.asyncio
    async def test_artifact_executor_has_execute_method(self) -> None:
        """Test ArtifactExecutor has execute method."""
        executor = ArtifactExecutor()
        
        assert hasattr(executor, "execute")
        assert callable(executor.execute)
        
        # Verify it's async
        import inspect
        assert inspect.iscoroutinefunction(executor.execute)
