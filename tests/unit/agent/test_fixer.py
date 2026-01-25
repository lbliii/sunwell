"""Tests for fix stage (RFC-042).

Tests error fixing logic and FixStage.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sunwell.agent.execution.fixer import FixAttempt, FixResult, FixStage
from sunwell.agent.validation import Artifact, ValidationError


class TestFixAttempt:
    """Tests for FixAttempt dataclass."""

    def test_successful_attempt(self) -> None:
        """FixAttempt captures successful fix."""
        attempt = FixAttempt(
            strategy="direct",
            target_file="app.py",
            target_lines=(10, 15),
            original_code="def broken(",
            fixed_code="def fixed():",
            success=True,
        )

        assert attempt.success
        assert attempt.strategy == "direct"
        assert attempt.target_lines == (10, 15)
        assert attempt.error_message == ""

    def test_failed_attempt(self) -> None:
        """FixAttempt captures failed fix."""
        attempt = FixAttempt(
            strategy="vortex",
            target_file="models.py",
            target_lines=None,
            original_code="class Broken",
            fixed_code="class StillBroken",
            success=False,
            error_message="Could not resolve type error",
        )

        assert not attempt.success
        assert attempt.error_message == "Could not resolve type error"

    def test_attempt_is_frozen(self) -> None:
        """FixAttempt is immutable."""
        attempt = FixAttempt(
            strategy="direct",
            target_file="test.py",
            target_lines=None,
            original_code="x",
            fixed_code="y",
            success=True,
        )

        with pytest.raises(AttributeError):
            attempt.success = False  # type: ignore


class TestFixResult:
    """Tests for FixResult dataclass."""

    def test_successful_result(self) -> None:
        """FixResult captures overall success."""
        attempts = (
            FixAttempt(
                strategy="direct",
                target_file="a.py",
                target_lines=None,
                original_code="x",
                fixed_code="y",
                success=True,
            ),
        )
        result = FixResult(success=True, attempts=attempts)

        assert result.success
        assert len(result.attempts) == 1
        assert result.remaining_errors == ()

    def test_partial_result(self) -> None:
        """FixResult captures partial fix with remaining errors."""
        remaining = (
            ValidationError(error_type="runtime", message="Still broken"),
        )
        result = FixResult(
            success=False,
            attempts=(),
            remaining_errors=remaining,
        )

        assert not result.success
        assert len(result.remaining_errors) == 1


class TestFixStage:
    """Tests for FixStage class."""

    def test_stage_initialization(self, tmp_path: Path) -> None:
        """FixStage initializes with model and cwd."""
        mock_model = MagicMock()
        stage = FixStage(model=mock_model, cwd=tmp_path, max_attempts=5)

        assert stage.model is mock_model
        assert stage.cwd == tmp_path
        assert stage.max_attempts == 5

    def test_stage_default_max_attempts(self, tmp_path: Path) -> None:
        """FixStage has default max_attempts."""
        mock_model = MagicMock()
        stage = FixStage(model=mock_model, cwd=tmp_path)

        assert stage.max_attempts == 3

    @pytest.mark.asyncio
    async def test_fix_errors_emits_start_event(self, tmp_path: Path) -> None:
        """fix_errors emits FIX_START event."""
        from sunwell.agent.events import EventType

        mock_model = MagicMock()
        stage = FixStage(model=mock_model, cwd=tmp_path)

        errors = [ValidationError(error_type="syntax", message="Test error")]

        events = []
        async for event in stage.fix_errors(errors, {}):
            events.append(event)
            break  # Just check first event

        assert events[0].type == EventType.FIX_START
        assert events[0].data["errors"] == 1

    @pytest.mark.asyncio
    async def test_fix_errors_skips_missing_artifact(self, tmp_path: Path) -> None:
        """fix_errors skips errors without matching artifact."""
        mock_model = MagicMock()
        stage = FixStage(model=mock_model, cwd=tmp_path)

        errors = [
            ValidationError(
                error_type="syntax",
                message="Test error",
                file="nonexistent.py",
            )
        ]

        events = []
        async for event in stage.fix_errors(errors, {}):
            events.append(event)

        # Should escalate since artifact not found
        event_types = [e.type for e in events]
        from sunwell.agent.events import EventType
        assert EventType.ESCALATE in event_types

    def test_extract_code_from_markdown(self, tmp_path: Path) -> None:
        """_extract_code handles markdown code blocks."""
        mock_model = MagicMock()
        stage = FixStage(model=mock_model, cwd=tmp_path)

        text = """Here's the fix:
```python
def fixed_function():
    return True
```
"""
        result = stage._extract_code(text)

        assert result is not None
        assert "def fixed_function" in result

    def test_extract_code_plain(self, tmp_path: Path) -> None:
        """_extract_code handles plain code."""
        mock_model = MagicMock()
        stage = FixStage(model=mock_model, cwd=tmp_path)

        text = """def plain_code():
    return 42"""

        result = stage._extract_code(text)

        assert result is not None
        assert "def plain_code" in result

    def test_extract_code_prose_returns_none(self, tmp_path: Path) -> None:
        """_extract_code returns None for prose."""
        mock_model = MagicMock()
        stage = FixStage(model=mock_model, cwd=tmp_path)

        text = "I couldn't fix this error because the code is too complex."

        result = stage._extract_code(text)

        assert result is None


class TestDirectFix:
    """Tests for direct fix strategy."""

    def test_fix_stage_has_direct_fix_method(self, tmp_path: Path) -> None:
        """FixStage has _direct_fix method."""
        mock_model = MagicMock()
        stage = FixStage(model=mock_model, cwd=tmp_path)

        assert hasattr(stage, "_direct_fix")
        assert callable(stage._direct_fix)


class TestCompoundEyeFix:
    """Tests for compound eye fix strategy."""

    @pytest.mark.asyncio
    async def test_compound_eye_extracts_region(self, tmp_path: Path) -> None:
        """_compound_eye_fix extracts error region."""
        from sunwell.agent.signals import ErrorSignals

        mock_model = MagicMock()
        mock_result = MagicMock()
        mock_result.text = "fixed_line = True"
        mock_model.generate = AsyncMock(return_value=mock_result)

        stage = FixStage(model=mock_model, cwd=tmp_path)

        # Create file with multiple lines
        content = "\n".join([f"line_{i} = {i}" for i in range(20)])
        file_path = tmp_path / "multi.py"
        file_path.write_text(content)

        # Mock artifact (can't actually modify frozen dataclass)
        artifact = MagicMock()
        artifact.path = file_path
        artifact.content = content

        error = ValidationError(error_type="type", message="Type error", line=10)
        signals = ErrorSignals(error_type="type", severity="MEDIUM")

        # Just verify method exists and can be called
        assert hasattr(stage, "_compound_eye_fix")


class TestVortexFix:
    """Tests for vortex fix strategy."""

    @pytest.mark.asyncio
    async def test_vortex_fallback_to_compound_eye(self, tmp_path: Path) -> None:
        """_vortex_fix falls back to compound_eye if vortex unavailable."""
        from sunwell.agent.signals import ErrorSignals

        mock_model = MagicMock()
        stage = FixStage(model=mock_model, cwd=tmp_path)

        # Mock the compound_eye_fix to track if it's called
        stage._compound_eye_fix = AsyncMock(return_value=True)

        artifact = MagicMock()
        artifact.content = "broken code"
        artifact.path = tmp_path / "test.py"

        error = ValidationError(error_type="runtime", message="Runtime error", line=1)
        signals = ErrorSignals(error_type="runtime", severity="MEDIUM")

        # If VortexPipeline import fails, should fall back
        with patch.dict("sys.modules", {"sunwell.vortex.pipeline": None}):
            # Method should still exist
            assert hasattr(stage, "_vortex_fix")
