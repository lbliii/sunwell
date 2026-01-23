"""Tests for preview functionality (RFC: Universal Project Readiness)."""

from pathlib import Path

import pytest

from sunwell.project.intent_types import (
    DevCommand,
    Prerequisite,
    PreviewType,
    ProjectAnalysis,
    ProjectType,
)
from sunwell.project.prereq_check import (
    can_preview,
    check_prerequisites,
    get_preview_status,
    missing_prerequisites,
)


class TestPreviewType:
    """Tests for PreviewType enum."""

    def test_preview_type_values(self) -> None:
        """Test all PreviewType values exist."""
        assert PreviewType.WEB_VIEW.value == "web_view"
        assert PreviewType.TERMINAL.value == "terminal"
        assert PreviewType.PROSE.value == "prose"
        assert PreviewType.SCREENPLAY.value == "screenplay"
        assert PreviewType.DIALOGUE.value == "dialogue"
        assert PreviewType.NOTEBOOK.value == "notebook"
        assert PreviewType.STATIC.value == "static"
        assert PreviewType.NONE.value == "none"

    def test_preview_type_from_string(self) -> None:
        """Test creating PreviewType from string value."""
        assert PreviewType("web_view") == PreviewType.WEB_VIEW
        assert PreviewType("prose") == PreviewType.PROSE
        assert PreviewType("none") == PreviewType.NONE


class TestProjectAnalysisPreviewFields:
    """Tests for preview fields in ProjectAnalysis."""

    def test_default_preview_type_is_none(self) -> None:
        """Test that default preview_type is NONE."""
        analysis = ProjectAnalysis(
            name="test",
            path=Path("/tmp/test"),
            project_type=ProjectType.CODE,
        )
        assert analysis.preview_type == PreviewType.NONE
        assert analysis.preview_url is None
        assert analysis.preview_file is None

    def test_preview_fields_set_correctly(self) -> None:
        """Test setting preview fields."""
        analysis = ProjectAnalysis(
            name="novel",
            path=Path("/tmp/novel"),
            project_type=ProjectType.CREATIVE,
            preview_type=PreviewType.PROSE,
            preview_url=None,
            preview_file="chapters/ch-01.md",
        )
        assert analysis.preview_type == PreviewType.PROSE
        assert analysis.preview_url is None
        assert analysis.preview_file == "chapters/ch-01.md"

    def test_web_view_preview_with_url(self) -> None:
        """Test WEB_VIEW preview with URL."""
        analysis = ProjectAnalysis(
            name="webapp",
            path=Path("/tmp/webapp"),
            project_type=ProjectType.CODE,
            preview_type=PreviewType.WEB_VIEW,
            preview_url="http://localhost:5000",
        )
        assert analysis.preview_type == PreviewType.WEB_VIEW
        assert analysis.preview_url == "http://localhost:5000"


class TestProjectAnalysisPreviewCache:
    """Tests for preview field serialization."""

    def test_cache_includes_preview_fields(self) -> None:
        """Test that to_cache_dict includes preview fields."""
        analysis = ProjectAnalysis(
            name="screenplay",
            path=Path("/tmp/screenplay"),
            project_type=ProjectType.CREATIVE,
            preview_type=PreviewType.SCREENPLAY,
            preview_file="script.fountain",
        )
        cache_dict = analysis.to_cache_dict()

        assert cache_dict["preview_type"] == "screenplay"
        assert cache_dict["preview_file"] == "script.fountain"
        assert cache_dict["preview_url"] is None

    def test_from_cache_parses_preview_fields(self) -> None:
        """Test that from_cache parses preview fields correctly."""
        analysis = ProjectAnalysis(
            name="webapp",
            path=Path("/tmp/webapp"),
            project_type=ProjectType.CODE,
            preview_type=PreviewType.WEB_VIEW,
            preview_url="http://localhost:3000",
        )
        cache_dict = analysis.to_cache_dict()
        loaded = ProjectAnalysis.from_cache(cache_dict)

        assert loaded.preview_type == PreviewType.WEB_VIEW
        assert loaded.preview_url == "http://localhost:3000"
        assert loaded.preview_file is None

    def test_from_cache_handles_missing_preview_fields(self) -> None:
        """Test that from_cache handles missing preview fields (old cache)."""
        # Simulate old cache format without preview fields
        old_cache = {
            "version": 1,
            "analyzed_at": "2026-01-22T12:00:00",
            "name": "old-project",
            "path": "/tmp/old-project",
            "project_type": "code",
            # No preview fields
        }
        loaded = ProjectAnalysis.from_cache(old_cache)

        assert loaded.preview_type == PreviewType.NONE
        assert loaded.preview_url is None
        assert loaded.preview_file is None


class TestPrerequisiteFields:
    """Tests for extended Prerequisite fields."""

    def test_prerequisite_defaults(self) -> None:
        """Test Prerequisite default values."""
        prereq = Prerequisite(
            command="npm install",
            description="Install dependencies",
        )
        assert prereq.satisfied is False
        assert prereq.required is True

    def test_prerequisite_with_all_fields(self) -> None:
        """Test Prerequisite with all fields."""
        prereq = Prerequisite(
            command="npm install",
            description="Install dependencies",
            check_command="test -d node_modules",
            satisfied=True,
            required=True,
        )
        assert prereq.satisfied is True
        assert prereq.required is True
        assert prereq.check_command == "test -d node_modules"


class TestCanPreview:
    """Tests for can_preview function."""

    def test_content_types_always_previewable(self) -> None:
        """Test that content preview types (PROSE, SCREENPLAY, DIALOGUE, STATIC) are always previewable."""
        content_types = [
            PreviewType.PROSE,
            PreviewType.SCREENPLAY,
            PreviewType.DIALOGUE,
            PreviewType.STATIC,
        ]

        for preview_type in content_types:
            analysis = ProjectAnalysis(
                name="content",
                path=Path("/tmp/content"),
                project_type=ProjectType.CREATIVE,
                preview_type=preview_type,
            )
            assert can_preview(analysis) is True, f"{preview_type} should be previewable"

    def test_none_not_previewable(self) -> None:
        """Test that NONE preview type is not previewable."""
        analysis = ProjectAnalysis(
            name="library",
            path=Path("/tmp/library"),
            project_type=ProjectType.CODE,
            preview_type=PreviewType.NONE,
        )
        assert can_preview(analysis) is False

    def test_web_view_without_dev_command_previewable(self) -> None:
        """Test WEB_VIEW without dev_command is still previewable."""
        analysis = ProjectAnalysis(
            name="docs",
            path=Path("/tmp/docs"),
            project_type=ProjectType.DOCUMENTATION,
            preview_type=PreviewType.WEB_VIEW,
            preview_url="http://localhost:8000",
        )
        assert can_preview(analysis) is True


class TestCheckPrerequisites:
    """Tests for check_prerequisites function."""

    def test_no_prerequisites_returns_empty(self) -> None:
        """Test that projects without prerequisites return empty list."""
        analysis = ProjectAnalysis(
            name="prose",
            path=Path("/tmp/prose"),
            project_type=ProjectType.CREATIVE,
            preview_type=PreviewType.PROSE,
        )
        assert check_prerequisites(analysis) == []

    def test_no_dev_command_returns_empty(self) -> None:
        """Test that projects without dev_command return empty list."""
        analysis = ProjectAnalysis(
            name="library",
            path=Path("/tmp/library"),
            project_type=ProjectType.CODE,
            preview_type=PreviewType.NONE,
        )
        assert check_prerequisites(analysis) == []


class TestMissingPrerequisites:
    """Tests for missing_prerequisites function."""

    def test_no_missing_when_no_prerequisites(self) -> None:
        """Test no missing prerequisites for prose project."""
        analysis = ProjectAnalysis(
            name="novel",
            path=Path("/tmp/novel"),
            project_type=ProjectType.CREATIVE,
            preview_type=PreviewType.PROSE,
        )
        assert missing_prerequisites(analysis) == []


class TestGetPreviewStatus:
    """Tests for get_preview_status function."""

    def test_prose_preview_status(self) -> None:
        """Test preview status for prose project."""
        analysis = ProjectAnalysis(
            name="novel",
            path=Path("/tmp/novel"),
            project_type=ProjectType.CREATIVE,
            preview_type=PreviewType.PROSE,
            preview_file="chapters/ch-01.md",
        )
        status = get_preview_status(analysis)

        assert status["ready"] is True
        assert status["preview_type"] == "prose"
        assert status["preview_file"] == "chapters/ch-01.md"
        assert status["preview_url"] is None
        assert status["missing"] == []

    def test_web_view_preview_status(self) -> None:
        """Test preview status for web app."""
        analysis = ProjectAnalysis(
            name="webapp",
            path=Path("/tmp/webapp"),
            project_type=ProjectType.CODE,
            preview_type=PreviewType.WEB_VIEW,
            preview_url="http://localhost:5000",
        )
        status = get_preview_status(analysis)

        assert status["preview_type"] == "web_view"
        assert status["preview_url"] == "http://localhost:5000"
