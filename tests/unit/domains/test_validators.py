"""Tests for domain validators."""

import pytest

from sunwell.domains.code.validators import (
    LintValidator,
    SyntaxValidator,
    TestValidator,
    TypeValidator,
    _normalize_file_paths,
)
from sunwell.domains.protocol import ValidationResult
from sunwell.domains.research.validators import CoherenceValidator, SourceValidator


class TestNormalizeFilePaths:
    """Tests for _normalize_file_paths helper."""

    def test_string_input(self) -> None:
        result = _normalize_file_paths("path/to/file.py", "test")
        assert len(result) == 1
        assert str(result[0]) == "path/to/file.py"

    def test_list_input(self) -> None:
        result = _normalize_file_paths(["a.py", "b.py"], "test")
        assert len(result) == 2

    def test_invalid_input_returns_error(self) -> None:
        result = _normalize_file_paths(123, "test")
        assert isinstance(result, ValidationResult)
        assert result.passed is False
        assert "Invalid artifact type" in result.message


class TestCodeValidatorProperties:
    """Tests for code validator dataclass fields."""

    def test_syntax_validator_defaults(self) -> None:
        v = SyntaxValidator()
        assert v.name == "syntax"
        assert v.description == "Check Python syntax is valid"

    def test_lint_validator_defaults(self) -> None:
        v = LintValidator()
        assert v.name == "lint"
        assert v.description == "Check code style with ruff"
        assert v.auto_fix is True

    def test_lint_validator_custom(self) -> None:
        v = LintValidator(auto_fix=False)
        assert v.auto_fix is False

    def test_type_validator_defaults(self) -> None:
        v = TypeValidator()
        assert v.name == "type"
        assert v.description == "Check types with ty/mypy"

    def test_test_validator_defaults(self) -> None:
        v = TestValidator()
        assert v.name == "test"
        assert v.description == "Run tests with pytest"


class TestResearchValidatorProperties:
    """Tests for research validator dataclass fields."""

    def test_source_validator_defaults(self) -> None:
        v = SourceValidator()
        assert v.name == "sources"
        assert v.description == "Check claims are backed by sources"
        assert v.min_sources == 1

    def test_source_validator_custom(self) -> None:
        v = SourceValidator(min_sources=3)
        assert v.min_sources == 3

    def test_coherence_validator_defaults(self) -> None:
        v = CoherenceValidator()
        assert v.name == "coherence"
        assert v.description == "Check logical coherence and structure"
        assert v.min_paragraphs == 1


class TestSourceValidatorValidation:
    """Tests for SourceValidator.validate."""

    @pytest.mark.anyio
    async def test_passes_with_url(self) -> None:
        v = SourceValidator()
        result = await v.validate(
            "The study https://example.com/paper shows results.",
            {},
        )
        assert result.passed is True
        assert "1 source" in result.message

    @pytest.mark.anyio
    async def test_passes_with_citation(self) -> None:
        v = SourceValidator()
        result = await v.validate(
            "According to Smith (2023), this is true [1].",
            {},
        )
        assert result.passed is True

    @pytest.mark.anyio
    async def test_fails_without_sources(self) -> None:
        v = SourceValidator()
        result = await v.validate(
            "This is a claim without any sources.",
            {},
        )
        assert result.passed is False
        assert "need at least 1" in result.message

    @pytest.mark.anyio
    async def test_fails_with_invalid_artifact(self) -> None:
        v = SourceValidator()
        result = await v.validate(123, {})
        assert result.passed is False
        assert "Invalid artifact type" in result.message


class TestCoherenceValidatorValidation:
    """Tests for CoherenceValidator.validate."""

    @pytest.mark.anyio
    async def test_passes_with_structure(self) -> None:
        v = CoherenceValidator()
        result = await v.validate(
            "First paragraph here.\n\nSecond paragraph with transitions. However, there is more.",
            {},
        )
        assert result.passed is True

    @pytest.mark.anyio
    async def test_fails_with_insufficient_paragraphs(self) -> None:
        v = CoherenceValidator(min_paragraphs=2)
        result = await v.validate("Just one short paragraph.", {})
        assert result.passed is False
        # Check the error details contain paragraph info
        assert any("paragraph" in str(e) for e in result.errors)

    @pytest.mark.anyio
    async def test_warns_multi_paragraph_no_transitions(self) -> None:
        v = CoherenceValidator()
        # Multi-paragraph content without any transition words
        # (avoid "first", "second", "finally", etc. which are transition words)
        content = (
            "The initial paragraph about topic A with details\n\n"
            "Another paragraph about topic B with different points\n\n"
            "A third paragraph about topic C with more content"
        )
        result = await v.validate(content, {})
        assert result.passed is False
        assert any("transition" in str(e).lower() for e in result.errors)
