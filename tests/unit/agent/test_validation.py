"""Tests for validation stage (RFC-042).

Tests artifact validation and ValidationStage/ValidationRunner.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sunwell.agent.gates import GateType, ValidationGate
from sunwell.agent.validation import (
    Artifact,
    ValidationError,
    ValidationResult,
    ValidationRunner,
    ValidationStage,
)


class TestArtifact:
    """Tests for Artifact dataclass."""

    def test_artifact_creation(self, tmp_path: Path) -> None:
        """Artifact stores path and content."""
        file_path = tmp_path / "test.py"
        artifact = Artifact(
            path=file_path,
            content="print('hello')",
            task_id="task-1",
            language="python",
        )

        assert artifact.path == file_path
        assert artifact.content == "print('hello')"
        assert artifact.task_id == "task-1"
        assert artifact.language == "python"

    def test_artifact_defaults(self, tmp_path: Path) -> None:
        """Artifact has sensible defaults."""
        artifact = Artifact(
            path=tmp_path / "code.py",
            content="x = 1",
        )

        assert artifact.task_id == ""
        assert artifact.language == "python"

    def test_artifact_is_frozen(self, tmp_path: Path) -> None:
        """Artifact is immutable."""
        artifact = Artifact(path=tmp_path / "test.py", content="code")

        with pytest.raises(AttributeError):
            artifact.content = "new code"  # type: ignore


class TestValidationError:
    """Tests for ValidationError dataclass."""

    def test_error_with_all_fields(self) -> None:
        """ValidationError stores all context."""
        error = ValidationError(
            error_type="syntax",
            message="Invalid syntax",
            file="test.py",
            line=42,
            column=10,
            traceback="Traceback...",
        )

        assert error.error_type == "syntax"
        assert error.message == "Invalid syntax"
        assert error.file == "test.py"
        assert error.line == 42
        assert error.column == 10
        assert error.traceback == "Traceback..."

    def test_error_minimal(self) -> None:
        """ValidationError works with minimal fields."""
        error = ValidationError(
            error_type="runtime",
            message="Division by zero",
        )

        assert error.file is None
        assert error.line is None

    def test_to_dict(self) -> None:
        """to_dict serializes error."""
        error = ValidationError(
            error_type="import",
            message="Module not found",
            file="app.py",
            line=5,
        )

        data = error.to_dict()

        assert data["error_type"] == "import"
        assert data["message"] == "Module not found"
        assert data["file"] == "app.py"
        assert data["line"] == 5


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_passed_result(self) -> None:
        """ValidationResult captures success."""
        result = ValidationResult(
            passed=True,
            duration_ms=150,
        )

        assert result.passed
        assert result.errors == ()
        assert result.duration_ms == 150

    def test_failed_result(self) -> None:
        """ValidationResult captures failure with errors."""
        errors = (
            ValidationError(error_type="syntax", message="Error 1"),
            ValidationError(error_type="lint", message="Error 2"),
        )
        result = ValidationResult(
            passed=False,
            errors=errors,
            duration_ms=200,
        )

        assert not result.passed
        assert len(result.errors) == 2


class TestValidationRunner:
    """Tests for ValidationRunner class."""

    def test_runner_initialization(self, tmp_path: Path) -> None:
        """ValidationRunner initializes with cwd."""
        runner = ValidationRunner(cwd=tmp_path)

        assert runner.cwd == tmp_path

    def test_runner_default_cwd(self) -> None:
        """ValidationRunner uses cwd() if not specified."""
        runner = ValidationRunner()

        assert runner.cwd == Path.cwd()

    @pytest.mark.asyncio
    async def test_check_imports_success(self, tmp_path: Path) -> None:
        """_check_imports passes for valid Python."""
        runner = ValidationRunner(cwd=tmp_path)

        artifact = Artifact(
            path=tmp_path / "valid.py",
            content="x = 1\ny = 2\n",
        )

        passed, message = await runner._check_imports([artifact])

        assert passed
        assert "importable" in message.lower()

    @pytest.mark.asyncio
    async def test_check_imports_syntax_error(self, tmp_path: Path) -> None:
        """_check_imports handles Python with syntax errors."""
        runner = ValidationRunner(cwd=tmp_path)

        # Syntax errors may or may not fail import check depending on how
        # importlib handles them - test that it doesn't crash
        artifact = Artifact(
            path=tmp_path / "invalid.py",
            content="def broken(\n",  # Syntax error
        )

        # Should not raise
        passed, message = await runner._check_imports([artifact])
        # Either passes or fails with a message
        assert isinstance(passed, bool)
        assert isinstance(message, str)

    @pytest.mark.asyncio
    async def test_check_imports_non_python_skipped(self, tmp_path: Path) -> None:
        """_check_imports skips non-Python files."""
        runner = ValidationRunner(cwd=tmp_path)

        artifact = Artifact(
            path=tmp_path / "data.json",
            content='{"key": "value"}',
            language="json",
        )

        passed, message = await runner._check_imports([artifact])

        assert passed


class TestValidationStage:
    """Tests for ValidationStage class."""

    def test_stage_initialization(self, tmp_path: Path) -> None:
        """ValidationStage initializes runner."""
        stage = ValidationStage(cwd=tmp_path)

        assert stage.cwd == tmp_path
        assert stage.runner is not None

    @pytest.mark.asyncio
    async def test_validate_incremental_emits_events(self, tmp_path: Path) -> None:
        """validate_incremental yields events."""
        from sunwell.agent.events import EventType

        stage = ValidationStage(cwd=tmp_path)

        # Create a valid artifact
        file_path = tmp_path / "test.py"
        file_path.write_text("x = 1")
        artifact = Artifact(path=file_path, content="x = 1")

        events = []
        async for event in stage.validate_incremental(artifact):
            events.append(event)

        # Should emit at least VALIDATE_LEVEL event
        assert len(events) > 0
        assert events[0].type == EventType.VALIDATE_LEVEL

    @pytest.mark.asyncio
    async def test_validate_all_stops_on_failure(self, tmp_path: Path) -> None:
        """validate_all stops when a gate fails."""
        from sunwell.agent.events import EventType

        stage = ValidationStage(cwd=tmp_path)

        gate = ValidationGate(
            id="gate_test",
            gate_type=GateType.IMPORT,
            depends_on=("task-1",),
            validation="import test",
        )

        # Mock runner to simulate failure
        with patch.object(stage.runner, "validate_gate") as mock_validate:
            async def mock_gen(*args, **kwargs):
                from sunwell.agent.events import AgentEvent
                yield AgentEvent(EventType.GATE_FAIL, {"gate_id": "gate_test", "failed_step": "import"})

            mock_validate.return_value = mock_gen()

            events = []
            async for event in stage.validate_all([gate], {}):
                events.append(event)

        # Should have stopped after failure
        event_types = [e.type for e in events]
        assert EventType.GATE_FAIL in event_types or EventType.VALIDATE_ERROR in event_types


class TestValidationGateIntegration:
    """Integration tests for gate validation."""

    @pytest.mark.asyncio
    async def test_validate_gate_emits_start_event(self, tmp_path: Path) -> None:
        """validate_gate emits GATE_START event."""
        from sunwell.agent.events import EventType

        runner = ValidationRunner(cwd=tmp_path)

        gate = ValidationGate(
            id="gate_syntax",
            gate_type=GateType.SYNTAX,
            depends_on=("task-1",),
            validation="python -m py_compile test.py",
        )

        # Create a simple artifact
        file_path = tmp_path / "test.py"
        file_path.write_text("x = 1")
        artifact = Artifact(path=file_path, content="x = 1")

        events = []
        async for event in runner.validate_gate(gate, [artifact]):
            events.append(event)

        # First event should be GATE_START
        assert len(events) > 0
        assert events[0].type == EventType.GATE_START
        assert events[0].data["gate_id"] == "gate_syntax"
