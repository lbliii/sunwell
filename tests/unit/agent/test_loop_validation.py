"""Tests for loop validation utilities.

Tests the helper functions in sunwell.agent.loop.validation.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sunwell.agent.loop.validation import (
    create_artifacts_from_paths,
    emit_gate_failure,
)


class TestCreateArtifactsFromPaths:
    """Tests for create_artifacts_from_paths helper."""

    def test_creates_artifacts_from_paths(self) -> None:
        """create_artifacts_from_paths creates Artifact objects."""
        paths = ["foo.py", "bar.py", "baz/qux.py"]

        artifacts = create_artifacts_from_paths(paths)

        assert len(artifacts) == 3
        assert artifacts[0].path == Path("foo.py")
        assert artifacts[1].path == Path("bar.py")
        assert artifacts[2].path == Path("baz/qux.py")

    def test_empty_paths_returns_empty_list(self) -> None:
        """create_artifacts_from_paths returns empty list for empty input."""
        artifacts = create_artifacts_from_paths([])

        assert artifacts == []

    def test_content_is_empty(self) -> None:
        """create_artifacts_from_paths creates artifacts with empty content."""
        artifacts = create_artifacts_from_paths(["test.py"])

        assert artifacts[0].content == ""

    def test_handles_absolute_paths(self) -> None:
        """create_artifacts_from_paths handles absolute paths."""
        paths = ["/Users/test/project/main.py"]

        artifacts = create_artifacts_from_paths(paths)

        assert artifacts[0].path == Path("/Users/test/project/main.py")

    def test_returns_list_of_artifacts(self) -> None:
        """create_artifacts_from_paths returns a list."""
        result = create_artifacts_from_paths(["a.py"])

        assert isinstance(result, list)


class TestEmitGateFailure:
    """Tests for emit_gate_failure helper."""

    @patch("sunwell.agent.loop.validation.emit_hook_sync")
    def test_emits_gate_fail_hook(self, mock_emit: MagicMock) -> None:
        """emit_gate_failure calls emit_hook_sync with GATE_FAIL event."""
        from sunwell.agent.hooks import HookEvent

        emit_gate_failure(
            gate_id="test_gate",
            gate_type="syntax",
            file_paths=["foo.py", "bar.py"],
            errors=["Error 1", "Error 2"],
        )

        mock_emit.assert_called_once_with(
            HookEvent.GATE_FAIL,
            gate_id="test_gate",
            gate_type="syntax",
            files=["foo.py", "bar.py"],
            errors=["Error 1", "Error 2"],
        )

    @patch("sunwell.agent.loop.validation.emit_hook_sync")
    def test_handles_empty_errors(self, mock_emit: MagicMock) -> None:
        """emit_gate_failure handles empty error list."""
        from sunwell.agent.hooks import HookEvent

        emit_gate_failure(
            gate_id="gate_1",
            gate_type="lint",
            file_paths=["test.py"],
            errors=[],
        )

        mock_emit.assert_called_once()
        call_kwargs = mock_emit.call_args[1]
        assert call_kwargs["errors"] == []

    @patch("sunwell.agent.loop.validation.emit_hook_sync")
    def test_handles_contract_gate_type(self, mock_emit: MagicMock) -> None:
        """emit_gate_failure handles contract gate type."""
        from sunwell.agent.hooks import HookEvent

        emit_gate_failure(
            gate_id="contract_MyProtocol",
            gate_type="contract",
            file_paths=["impl.py"],
            errors=["Missing method: foo"],
        )

        call_kwargs = mock_emit.call_args[1]
        assert call_kwargs["gate_type"] == "contract"
