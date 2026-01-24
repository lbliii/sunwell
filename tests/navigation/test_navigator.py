"""Tests for TocNavigator (RFC-124)."""

from __future__ import annotations

import pytest

from sunwell.models.mock import MockModel
from sunwell.navigation.navigator import (
    NavigationResult,
    NavigatorConfig,
    TocNavigator,
)
from sunwell.navigation.toc import ProjectToc, TocNode


class TestNavigationResult:
    """Tests for NavigationResult dataclass."""

    def test_create_result(self) -> None:
        """Test basic result creation."""
        result = NavigationResult(
            path="sunwell/auth/token.py",
            reasoning="This file handles token validation",
            confidence=0.85,
        )

        assert result.path == "sunwell/auth/token.py"
        assert result.reasoning == "This file handles token validation"
        assert result.confidence == 0.85
        assert result.content is None
        assert result.follow_up == ()

    def test_result_with_content(self) -> None:
        """Test result with content and follow-up."""
        result = NavigationResult(
            path="auth/token.py",
            reasoning="Found token validation",
            confidence=0.9,
            content="class TokenValidator:\n    pass",
            follow_up=("auth/session.py", "auth/refresh.py"),
        )

        assert result.content is not None
        assert len(result.follow_up) == 2

    def test_result_immutable(self) -> None:
        """Test that NavigationResult is frozen."""
        result = NavigationResult(
            path="test.py",
            reasoning="Test",
            confidence=0.5,
        )

        with pytest.raises(AttributeError):
            result.path = "changed.py"  # type: ignore


class TestNavigatorConfig:
    """Tests for NavigatorConfig."""

    def test_default_config(self) -> None:
        """Test default configuration."""
        config = NavigatorConfig()

        assert config.max_depth == 3
        assert config.max_iterations == 3
        assert config.cache_size == 100
        assert config.max_content_lines == 200
        assert config.subtree_budget == 500

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = NavigatorConfig(
            max_depth=2,
            max_iterations=5,
            cache_size=50,
        )

        assert config.max_depth == 2
        assert config.max_iterations == 5
        assert config.cache_size == 50


class TestTocNavigator:
    """Tests for TocNavigator."""

    @pytest.fixture
    def sample_toc(self) -> ProjectToc:
        """Create a sample ToC for testing."""
        toc = ProjectToc(root_id="project")

        root = TocNode(
            node_id="project",
            title="Project",
            node_type="directory",
            summary="Root directory",
            path=".",
            children=("project.auth", "project.api", "project.utils"),
        )
        toc.add_node(root)

        auth = TocNode(
            node_id="project.auth",
            title="auth",
            node_type="module",
            summary="Authentication and authorization",
            path="auth",
            children=("project.auth.token", "project.auth.session"),
            concepts=("auth",),
        )
        toc.add_node(auth)

        token = TocNode(
            node_id="project.auth.token",
            title="token",
            node_type="module",
            summary="Token validation and refresh",
            path="auth/token.py",
            concepts=("auth",),
        )
        toc.add_node(token)

        session = TocNode(
            node_id="project.auth.session",
            title="session",
            node_type="module",
            summary="Session management",
            path="auth/session.py",
            concepts=("auth",),
        )
        toc.add_node(session)

        api = TocNode(
            node_id="project.api",
            title="api",
            node_type="module",
            summary="REST API endpoints",
            path="api",
            concepts=("api",),
        )
        toc.add_node(api)

        utils = TocNode(
            node_id="project.utils",
            title="utils",
            node_type="module",
            summary="Utility functions",
            path="utils",
            concepts=("util",),
        )
        toc.add_node(utils)

        return toc

    @pytest.fixture
    def navigator(self, sample_toc: ProjectToc, tmp_path) -> TocNavigator:
        """Create a navigator with mock model."""
        # Create some test files
        (tmp_path / "auth").mkdir()
        (tmp_path / "auth" / "__init__.py").write_text('"""Auth module."""\n')
        (tmp_path / "auth" / "token.py").write_text('''"""Token validation."""

class TokenValidator:
    """Validates authentication tokens."""

    def validate(self, token: str) -> bool:
        """Validate a token."""
        return True
''')

        return TocNavigator(
            toc=sample_toc,
            model=MockModel(),
            workspace_root=tmp_path,
            config=NavigatorConfig(max_iterations=2),
        )

    def test_fallback_navigate(self, navigator: TocNavigator) -> None:
        """Test fallback navigation with keyword matching."""
        result = navigator._fallback_navigate("authentication token validation")

        assert result.path != ""
        assert result.confidence == 0.3  # Fallback confidence
        assert "keyword" in result.reasoning.lower() or "fallback" in result.reasoning.lower()

    def test_fallback_navigate_no_match(self, navigator: TocNavigator) -> None:
        """Test fallback navigation with no matching keywords."""
        result = navigator._fallback_navigate("xyz abc 123")

        assert result.path == "."  # Falls back to root
        assert result.confidence == 0.1

    def test_cache_key_generation(self, navigator: TocNavigator) -> None:
        """Test cache key generation."""
        key1 = navigator._cache_key("query", None)
        key2 = navigator._cache_key("query", ["step1"])
        key3 = navigator._cache_key("query", ["step1", "step2"])

        assert key1 != key2
        assert key2 != key3
        assert "query" in key1

    def test_format_history(self, navigator: TocNavigator) -> None:
        """Test history formatting."""
        history = ["Explored auth/", "Found token.py"]
        formatted = navigator._format_history(history)

        assert "- Explored auth/" in formatted
        assert "- Found token.py" in formatted

    def test_format_history_empty(self, navigator: TocNavigator) -> None:
        """Test empty history formatting."""
        formatted = navigator._format_history([])
        assert formatted == "None"

    def test_normalize_path(self, navigator: TocNavigator) -> None:
        """Test path normalization."""
        # Leading slashes
        assert navigator._normalize_path("/path/to/file") == "path/to/file"
        assert navigator._normalize_path("./path/to/file") == "path/to/file"

        # Quotes
        assert navigator._normalize_path('"path/to/file"') == "path/to/file"
        assert navigator._normalize_path("'path/to/file'") == "path/to/file"

        # Backslashes
        assert navigator._normalize_path("path\\to\\file") == "path/to/file"

    def test_parse_json_response(self, navigator: TocNavigator) -> None:
        """Test JSON response parsing."""
        # Valid JSON
        valid = '{"selected_path": "auth/token.py", "reasoning": "test", "confidence": 0.9}'
        parsed = navigator._parse_json_response(valid)
        assert parsed["selected_path"] == "auth/token.py"

        # With markdown code block
        markdown = '```json\n{"selected_path": "auth.py", "confidence": 0.8}\n```'
        parsed2 = navigator._parse_json_response(markdown)
        assert parsed2["selected_path"] == "auth.py"

        # Invalid JSON
        invalid = "not json at all"
        parsed3 = navigator._parse_json_response(invalid)
        assert parsed3 == {}

    def test_parse_navigation_response(self, navigator: TocNavigator) -> None:
        """Test navigation response parsing."""
        response = (
            '{"selected_path": "auth/token.py", "reasoning": "Contains auth logic", '
            '"confidence": 0.85, "follow_up": ["auth/session.py"]}'
        )

        result = navigator._parse_navigation_response(response)

        assert result.path == "auth/token.py"
        assert "auth" in result.reasoning.lower()
        assert result.confidence == 0.85
        assert "auth/session.py" in result.follow_up

    def test_parse_navigation_response_confidence_clamped(self, navigator: TocNavigator) -> None:
        """Test that confidence is clamped to 0-1."""
        response = '{"selected_path": "test.py", "reasoning": "test", "confidence": 1.5}'
        result = navigator._parse_navigation_response(response)
        assert result.confidence == 1.0

        response2 = '{"selected_path": "test.py", "reasoning": "test", "confidence": -0.5}'
        result2 = navigator._parse_navigation_response(response2)
        assert result2.confidence == 0.0

    def test_cache_operations(self, navigator: TocNavigator) -> None:
        """Test cache operations."""
        assert len(navigator._cache) == 0

        # Add to cache manually
        result = NavigationResult(path="test.py", reasoning="test", confidence=0.5)
        navigator._cache["test_key"] = result

        assert len(navigator._cache) == 1

        # Clear cache
        navigator.clear_cache()
        assert len(navigator._cache) == 0

    @pytest.mark.asyncio
    async def test_read_path_file(self, navigator: TocNavigator) -> None:
        """Test reading file content."""
        content = await navigator._read_path("auth/token.py")

        assert content is not None
        assert "TokenValidator" in content

    @pytest.mark.asyncio
    async def test_read_path_directory(self, navigator: TocNavigator) -> None:
        """Test reading directory (should read __init__.py)."""
        content = await navigator._read_path("auth")

        assert content is not None
        assert "Auth module" in content

    @pytest.mark.asyncio
    async def test_read_path_nonexistent(self, navigator: TocNavigator) -> None:
        """Test reading nonexistent path."""
        content = await navigator._read_path("nonexistent/path.py")
        assert content is None

    @pytest.mark.asyncio
    async def test_navigate_to_concept(self, navigator: TocNavigator) -> None:
        """Test concept-based navigation."""
        results = await navigator.navigate_to_concept("auth")

        assert len(results) > 0
        for result in results:
            assert result.confidence == 0.9
            assert "auth" in result.reasoning.lower()

    @pytest.mark.asyncio
    async def test_navigate_to_concept_not_found(self, navigator: TocNavigator) -> None:
        """Test concept navigation with unknown concept."""
        results = await navigator.navigate_to_concept("nonexistent")
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_expand_subtree(self, navigator: TocNavigator) -> None:
        """Test subtree expansion."""
        subtree = await navigator.expand_subtree("project.auth", depth=1)

        assert isinstance(subtree, str)
        # Should be valid JSON
        import json
        data = json.loads(subtree)
        assert isinstance(data, list)
