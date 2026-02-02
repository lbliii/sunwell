"""Tests for checkpoint utilities.

Tests the ensure_checkpoint_response helper function.
"""

import pytest

from sunwell.agent.chat.checkpoint import (
    CheckpointResponse,
    ensure_checkpoint_response,
)


class TestEnsureCheckpointResponse:
    """Tests for ensure_checkpoint_response helper."""

    def test_passthrough_checkpoint_response(self) -> None:
        """CheckpointResponse objects pass through unchanged."""
        original = CheckpointResponse(choice="y")
        result = ensure_checkpoint_response(original)

        assert result is original
        assert result.choice == "y"

    def test_none_becomes_empty_choice(self) -> None:
        """None becomes CheckpointResponse with empty choice."""
        result = ensure_checkpoint_response(None)

        assert isinstance(result, CheckpointResponse)
        assert result.choice == ""

    def test_string_becomes_checkpoint_response(self) -> None:
        """String becomes CheckpointResponse with that choice."""
        result = ensure_checkpoint_response("yes")

        assert isinstance(result, CheckpointResponse)
        assert result.choice == "yes"

    def test_string_y_is_proceed(self) -> None:
        """String 'y' creates a proceed response."""
        result = ensure_checkpoint_response("y")

        assert result.proceed is True
        assert result.abort is False

    def test_string_abort_is_abort(self) -> None:
        """String 'abort' creates an abort response."""
        result = ensure_checkpoint_response("abort")

        assert result.abort is True
        assert result.proceed is False

    def test_string_n_is_skip(self) -> None:
        """String 'n' creates a skip response."""
        result = ensure_checkpoint_response("n")

        assert result.skip is True
        assert result.proceed is False

    def test_empty_string_not_proceed(self) -> None:
        """Empty string is not proceed."""
        result = ensure_checkpoint_response("")

        assert result.proceed is False
        assert result.abort is False

    def test_preserves_checkpoint_response_properties(self) -> None:
        """Existing CheckpointResponse properties are preserved."""
        original = CheckpointResponse(
            choice="background",
            additional_input="some context",
        )
        result = ensure_checkpoint_response(original)

        assert result.run_background is True
        assert result.additional_input == "some context"
