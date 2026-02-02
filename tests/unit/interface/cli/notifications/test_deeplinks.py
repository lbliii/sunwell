"""Tests for deep link generation."""

from pathlib import Path

import pytest

from sunwell.interface.cli.notifications.deeplinks import (
    DeepLink,
    DeepLinkTarget,
    create_deep_link,
    create_file_context,
    create_session_context,
    get_deep_link_from_context,
)


class TestDeepLinkTarget:
    """Test DeepLinkTarget enum."""

    def test_all_targets_exist(self) -> None:
        """All expected targets exist."""
        targets = ["vscode", "cursor", "iterm", "terminal"]
        for t in targets:
            assert DeepLinkTarget(t) is not None

    def test_values(self) -> None:
        """Enum values are correct."""
        assert DeepLinkTarget.VSCODE.value == "vscode"
        assert DeepLinkTarget.CURSOR.value == "cursor"


class TestDeepLink:
    """Test DeepLink dataclass."""

    def test_create_deep_link(self) -> None:
        """Create a deep link."""
        link = DeepLink(
            url="vscode://file/test.py:10",
            target=DeepLinkTarget.VSCODE,
            fallback_path="/path/to/test.py",
        )

        assert link.url == "vscode://file/test.py:10"
        assert link.target == DeepLinkTarget.VSCODE


class TestCreateDeepLink:
    """Test deep link creation."""

    def test_vscode_link(self) -> None:
        """Create VS Code deep link."""
        link = create_deep_link(
            file_path="/Users/test/project/main.py",
            target=DeepLinkTarget.VSCODE,
        )

        assert link.url.startswith("vscode://file/")
        assert "main.py" in link.url
        assert link.target == DeepLinkTarget.VSCODE

    def test_vscode_link_with_line(self) -> None:
        """VS Code link with line number."""
        link = create_deep_link(
            file_path="/Users/test/project/main.py",
            line=42,
            target=DeepLinkTarget.VSCODE,
        )

        assert ":42" in link.url

    def test_vscode_link_with_line_and_column(self) -> None:
        """VS Code link with line and column."""
        link = create_deep_link(
            file_path="/Users/test/project/main.py",
            line=42,
            column=10,
            target=DeepLinkTarget.VSCODE,
        )

        assert ":42:10" in link.url

    def test_cursor_link(self) -> None:
        """Create Cursor deep link."""
        link = create_deep_link(
            file_path="/Users/test/project/main.py",
            target=DeepLinkTarget.CURSOR,
        )

        assert link.url.startswith("cursor://file/")
        assert link.target == DeepLinkTarget.CURSOR

    def test_iterm_link(self) -> None:
        """Create iTerm deep link."""
        link = create_deep_link(
            file_path="/Users/test/project/main.py",
            target=DeepLinkTarget.ITERM,
        )

        # iTerm uses a different format
        assert link.target == DeepLinkTarget.ITERM
        assert link.fallback_path == "/Users/test/project/main.py"

    def test_default_target_vscode(self) -> None:
        """Default target is VS Code."""
        link = create_deep_link(file_path="/test/file.py")

        assert link.target == DeepLinkTarget.VSCODE


class TestCreateFileContext:
    """Test file context creation."""

    def test_basic_context(self) -> None:
        """Create basic file context."""
        context = create_file_context(
            file_path="/Users/test/project/src/main.py",
            workspace="/Users/test/project",
        )

        assert context["file"] == "/Users/test/project/src/main.py"
        assert context["relative_path"] == "src/main.py"
        assert "deep_link" in context

    def test_context_with_line(self) -> None:
        """File context with line number."""
        context = create_file_context(
            file_path="/test/file.py",
            line=100,
        )

        assert context["line"] == 100
        assert ":100" in context["deep_link"]

    def test_context_with_column(self) -> None:
        """File context with line and column."""
        context = create_file_context(
            file_path="/test/file.py",
            line=50,
            column=15,
        )

        assert context["line"] == 50
        assert context["column"] == 15

    def test_context_generates_deep_link(self) -> None:
        """File context always generates a deep link."""
        context = create_file_context(
            file_path="/test/file.py",
        )

        # Deep link is auto-generated with default target (vscode)
        assert "vscode://" in context["deep_link"]


class TestCreateSessionContext:
    """Test session context creation."""

    def test_basic_session_context(self) -> None:
        """Create session context."""
        context = create_session_context(session_id="abc-123")

        assert context["session_id"] == "abc-123"

    def test_session_context_with_workspace(self) -> None:
        """Session context with workspace."""
        context = create_session_context(
            session_id="def-456",
            workspace="/Users/test/project",
        )

        assert context["session_id"] == "def-456"
        assert context["workspace"] == "/Users/test/project"


class TestGetDeepLinkFromContext:
    """Test extracting deep link from context."""

    def test_get_from_context(self) -> None:
        """Get deep link from context dict."""
        context = {"deep_link": "vscode://file/test.py:10"}

        link = get_deep_link_from_context(context)

        assert link == "vscode://file/test.py:10"

    def test_generates_link_from_file(self) -> None:
        """Generates deep link from file context if no deep_link key."""
        context = {"file": "/test/file.py"}

        link = get_deep_link_from_context(context)

        # Should generate a link from the file
        assert link is not None
        assert "vscode://file/" in link

    def test_empty_context_returns_none(self) -> None:
        """Empty context (no file, no deep_link) returns None."""
        context = {"other_key": "value"}

        link = get_deep_link_from_context(context)

        assert link is None

    def test_none_context_returns_none(self) -> None:
        """None context returns None."""
        link = get_deep_link_from_context(None)

        assert link is None
