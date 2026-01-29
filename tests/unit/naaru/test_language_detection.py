"""Tests for language detection (RFC: Language-Aware Sunwell).

Tests the centralized language detection module that replaces scattered
detection functions across the codebase.
"""

import tempfile
from pathlib import Path

import pytest

from sunwell.planning.naaru.expertise.language import (
    Language,
    LanguageClassification,
    LanguageClassifier,
    detect_language,
    get_language_lens,
    language_from_extension,
)


class TestLanguageClassifier:
    """Test the LanguageClassifier class."""

    @pytest.fixture
    def classifier(self) -> LanguageClassifier:
        return LanguageClassifier()

    # =========================================================================
    # Goal keyword detection
    # =========================================================================

    def test_detect_svelte_from_goal(self, classifier: LanguageClassifier) -> None:
        """Detect TypeScript from svelte keyword."""
        result = classifier.classify_goal("build a todo app in svelte")
        assert result.language == Language.TYPESCRIPT
        assert result.confidence >= 0.8
        assert "svelte" in result.signals

    def test_detect_react_from_goal(self, classifier: LanguageClassifier) -> None:
        """Detect TypeScript from react keyword."""
        result = classifier.classify_goal("create a react component")
        assert result.language == Language.TYPESCRIPT
        assert "react" in result.signals

    def test_detect_python_from_goal(self, classifier: LanguageClassifier) -> None:
        """Detect Python from python keyword."""
        result = classifier.classify_goal("write a python script for data analysis")
        assert result.language == Language.PYTHON
        assert "python" in result.signals

    def test_detect_django_from_goal(self, classifier: LanguageClassifier) -> None:
        """Detect Python from django keyword."""
        result = classifier.classify_goal("create a django api endpoint")
        assert result.language == Language.PYTHON
        assert "django" in result.signals

    def test_detect_rust_from_goal(self, classifier: LanguageClassifier) -> None:
        """Detect Rust from rust keyword."""
        result = classifier.classify_goal("implement a rust cli tool")
        assert result.language == Language.RUST
        assert "rust" in result.signals

    def test_detect_go_from_goal(self, classifier: LanguageClassifier) -> None:
        """Detect Go from golang keyword."""
        result = classifier.classify_goal("build a golang microservice")
        assert result.language == Language.GO
        assert "golang" in result.signals

    def test_unknown_language_from_goal(self, classifier: LanguageClassifier) -> None:
        """Return UNKNOWN for goals with no language signals."""
        result = classifier.classify_goal("fix the bug in the auth module")
        assert result.language == Language.UNKNOWN
        assert result.confidence == 0.0

    # =========================================================================
    # Project marker detection
    # =========================================================================

    def test_detect_python_project(self, classifier: LanguageClassifier) -> None:
        """Detect Python from pyproject.toml marker."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)
            (project / "pyproject.toml").write_text("[project]\nname = 'test'")

            result = classifier.classify_project(project)
            assert result.language == Language.PYTHON
            assert "pyproject.toml" in result.signals

    def test_detect_typescript_project(self, classifier: LanguageClassifier) -> None:
        """Detect TypeScript from tsconfig.json marker."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)
            (project / "tsconfig.json").write_text("{}")

            result = classifier.classify_project(project)
            assert result.language == Language.TYPESCRIPT
            assert "tsconfig.json" in result.signals

    def test_detect_rust_project(self, classifier: LanguageClassifier) -> None:
        """Detect Rust from Cargo.toml marker."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)
            (project / "Cargo.toml").write_text("[package]\nname = 'test'")

            result = classifier.classify_project(project)
            assert result.language == Language.RUST
            assert "Cargo.toml" in result.signals

    def test_detect_go_project(self, classifier: LanguageClassifier) -> None:
        """Detect Go from go.mod marker."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)
            (project / "go.mod").write_text("module test")

            result = classifier.classify_project(project)
            assert result.language == Language.GO
            assert "go.mod" in result.signals

    def test_unknown_project(self, classifier: LanguageClassifier) -> None:
        """Return UNKNOWN for projects with no recognized markers."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)
            # Empty directory

            result = classifier.classify_project(project)
            assert result.language == Language.UNKNOWN

    # =========================================================================
    # Combined detection
    # =========================================================================

    def test_goal_takes_priority_with_high_confidence(
        self, classifier: LanguageClassifier
    ) -> None:
        """Goal keyword with high confidence overrides project markers."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)
            (project / "pyproject.toml").write_text("[project]\nname = 'test'")

            # Explicit svelte request in a Python project
            result = classifier.classify("build a svelte app", project)
            assert result.language == Language.TYPESCRIPT
            assert result.source == "goal"

    def test_combined_boosts_confidence(self, classifier: LanguageClassifier) -> None:
        """Agreement between goal and project boosts confidence."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)
            (project / "pyproject.toml").write_text("[project]\nname = 'test'")

            # Use a moderate-confidence Python keyword (pip=0.6) to trigger combined logic
            result = classifier.classify("install with pip", project)
            assert result.language == Language.PYTHON
            assert result.source == "combined"
            assert result.confidence > 0.6


class TestDetectLanguageFunction:
    """Test the convenience function."""

    def test_detect_language_simple(self) -> None:
        """Simple goal detection."""
        result = detect_language("build a nextjs app")
        assert result.language == Language.TYPESCRIPT
        assert "nextjs" in result.signals

    def test_detect_language_with_project(self) -> None:
        """Detection with project path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)
            (project / "Cargo.toml").write_text("[package]\nname = 'test'")

            result = detect_language("add a new function", project)
            assert result.language == Language.RUST


class TestGetLanguageLens:
    """Test language-to-lens mapping."""

    def test_python_lens(self) -> None:
        assert get_language_lens(Language.PYTHON) == "python-expert-v2"

    def test_typescript_lens(self) -> None:
        assert get_language_lens(Language.TYPESCRIPT) == "typescript-expert-v2"

    def test_javascript_uses_typescript_lens(self) -> None:
        """JavaScript uses TypeScript lens (superset)."""
        assert get_language_lens(Language.JAVASCRIPT) == "typescript-expert-v2"

    def test_rust_lens(self) -> None:
        assert get_language_lens(Language.RUST) == "rust-expert-v2"

    def test_go_lens(self) -> None:
        assert get_language_lens(Language.GO) == "go-expert-v2"

    def test_unknown_has_no_lens(self) -> None:
        assert get_language_lens(Language.UNKNOWN) is None


class TestLanguageFromExtension:
    """Test file extension-based detection."""

    def test_python_extensions(self) -> None:
        assert language_from_extension(".py") == Language.PYTHON
        assert language_from_extension(".pyi") == Language.PYTHON
        assert language_from_extension("py") == Language.PYTHON  # Without dot

    def test_typescript_extensions(self) -> None:
        assert language_from_extension(".ts") == Language.TYPESCRIPT
        assert language_from_extension(".tsx") == Language.TYPESCRIPT

    def test_javascript_extensions(self) -> None:
        assert language_from_extension(".js") == Language.JAVASCRIPT
        assert language_from_extension(".jsx") == Language.JAVASCRIPT

    def test_svelte_uses_typescript(self) -> None:
        """Svelte files use TypeScript tooling."""
        assert language_from_extension(".svelte") == Language.TYPESCRIPT

    def test_rust_extensions(self) -> None:
        assert language_from_extension(".rs") == Language.RUST

    def test_go_extensions(self) -> None:
        assert language_from_extension(".go") == Language.GO

    def test_unknown_extension(self) -> None:
        assert language_from_extension(".xyz") == Language.UNKNOWN


class TestLanguageClassificationProperties:
    """Test LanguageClassification dataclass properties."""

    def test_is_confident_threshold(self) -> None:
        """Test confidence threshold for lens selection."""
        high = LanguageClassification(
            language=Language.PYTHON,
            confidence=0.8,
            signals=("python",),
            source="goal",
        )
        assert high.is_confident is True

        low = LanguageClassification(
            language=Language.PYTHON,
            confidence=0.4,
            signals=(),
            source="goal",
        )
        assert low.is_confident is False

        threshold = LanguageClassification(
            language=Language.PYTHON,
            confidence=0.5,
            signals=(),
            source="goal",
        )
        assert threshold.is_confident is True  # Exactly at threshold
