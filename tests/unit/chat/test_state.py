"""Tests for chat state utilities.

Tests the append_to_history helper function and MAX_HISTORY_SIZE constant.
"""

import pytest

from sunwell.agent.chat.state import (
    MAX_HISTORY_SIZE,
    LoopState,
    append_to_history,
)


class TestLoopState:
    """Tests for LoopState enum."""

    def test_all_states_exist(self) -> None:
        """All expected loop states are defined."""
        expected = {
            "IDLE",
            "CLASSIFYING",
            "CONVERSING",
            "PLANNING",
            "CONFIRMING",
            "EXECUTING",
            "INTERRUPTED",
            "COMPLETED",
            "ERROR",
        }

        actual = {state.name for state in LoopState}

        assert actual == expected


class TestMaxHistorySize:
    """Tests for MAX_HISTORY_SIZE constant."""

    def test_max_history_size_is_reasonable(self) -> None:
        """MAX_HISTORY_SIZE is a reasonable value."""
        assert MAX_HISTORY_SIZE > 0
        assert MAX_HISTORY_SIZE <= 100  # Don't want unbounded growth
        assert MAX_HISTORY_SIZE == 50  # Current expected value


class TestAppendToHistory:
    """Tests for append_to_history helper."""

    def test_appends_message(self) -> None:
        """append_to_history adds a message to the history."""
        history: list[dict[str, str]] = []

        append_to_history(history, "user", "hello")

        assert len(history) == 1
        assert history[0] == {"role": "user", "content": "hello"}

    def test_appends_multiple_messages(self) -> None:
        """append_to_history appends messages in order."""
        history: list[dict[str, str]] = []

        append_to_history(history, "user", "hello")
        append_to_history(history, "assistant", "hi there")
        append_to_history(history, "user", "how are you?")

        assert len(history) == 3
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"
        assert history[2]["role"] == "user"

    def test_trims_when_exceeds_max(self) -> None:
        """append_to_history trims oldest messages when exceeding MAX_HISTORY_SIZE."""
        history: list[dict[str, str]] = []

        # Fill past the limit
        for i in range(MAX_HISTORY_SIZE + 10):
            append_to_history(history, "user", f"message {i}")

        # Should be trimmed to MAX_HISTORY_SIZE
        assert len(history) == MAX_HISTORY_SIZE
        # Oldest messages should be removed
        assert history[0]["content"] == "message 10"
        assert history[-1]["content"] == f"message {MAX_HISTORY_SIZE + 9}"

    def test_trims_to_exactly_max(self) -> None:
        """append_to_history trims to exactly MAX_HISTORY_SIZE."""
        history: list[dict[str, str]] = []

        # Fill to exactly max
        for i in range(MAX_HISTORY_SIZE):
            append_to_history(history, "user", f"msg{i}")

        assert len(history) == MAX_HISTORY_SIZE

        # Add one more - should still be at max
        append_to_history(history, "user", "overflow")

        assert len(history) == MAX_HISTORY_SIZE
        assert history[-1]["content"] == "overflow"
        assert history[0]["content"] == "msg1"  # First one was trimmed

    def test_modifies_list_in_place(self) -> None:
        """append_to_history modifies the list in place."""
        history: list[dict[str, str]] = []
        original_id = id(history)

        append_to_history(history, "user", "test")

        # Same list object
        assert id(history) == original_id

    def test_handles_empty_content(self) -> None:
        """append_to_history handles empty content."""
        history: list[dict[str, str]] = []

        append_to_history(history, "assistant", "")

        assert len(history) == 1
        assert history[0]["content"] == ""

    def test_handles_special_characters(self) -> None:
        """append_to_history handles special characters in content."""
        history: list[dict[str, str]] = []

        content = "Hello! 🎉 <script>alert('xss')</script> \n\t test"
        append_to_history(history, "user", content)

        assert history[0]["content"] == content
