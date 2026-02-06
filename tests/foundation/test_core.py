"""Tests for core data classes."""

import pytest

from sunwell.core.types.types import SemanticVersion, LensReference, Confidence, Tier
from sunwell.core.models.heuristic import Heuristic, Example
from sunwell.core.models.persona import Persona
from sunwell.foundation.core.lens import Lens, LensMetadata


class TestSemanticVersion:
    def test_parse_simple(self):
        v = SemanticVersion.parse("1.2.3")
        assert v.major == 1
        assert v.minor == 2
        assert v.patch == 3
        assert v.prerelease is None

    def test_parse_with_prerelease(self):
        v = SemanticVersion.parse("1.0.0-beta")
        assert v.major == 1
        assert v.prerelease == "beta"

    def test_str(self):
        v = SemanticVersion(1, 2, 3)
        assert str(v) == "1.2.3"

        v_pre = SemanticVersion(1, 0, 0, "rc1")
        assert str(v_pre) == "1.0.0-rc1"

    def test_comparison(self):
        v1 = SemanticVersion(1, 0, 0)
        v2 = SemanticVersion(2, 0, 0)
        assert v1 < v2
        assert v1 <= v2
        assert not v1 > v2


class TestLensReference:
    def test_local_reference(self):
        ref = LensReference(source="./my-lens.lens")
        assert ref.is_local
        assert not ref.is_fount

    def test_fount_reference(self):
        ref = LensReference(source="sunwell/tech-writer", version="^1.0")
        assert ref.is_fount
        assert not ref.is_local


class TestConfidence:
    def test_valid_score(self):
        c = Confidence(score=0.85, explanation="Good coverage")
        assert c.score == 0.85
        assert c.level == "🟡 Moderate"

    def test_high_confidence(self):
        c = Confidence(score=0.95)
        assert c.level == "🟢 High"

    def test_low_confidence(self):
        c = Confidence(score=0.55)
        assert c.level == "🟠 Low"

    def test_uncertain(self):
        c = Confidence(score=0.3)
        assert c.level == "🔴 Uncertain"

    def test_invalid_score_raises(self):
        with pytest.raises(ValueError):
            Confidence(score=1.5)

        with pytest.raises(ValueError):
            Confidence(score=-0.1)


class TestHeuristic:
    def test_to_prompt_fragment(self, sample_heuristic: Heuristic):
        fragment = sample_heuristic.to_prompt_fragment()
        assert "Test Heuristic" in fragment
        assert "Always test your code" in fragment
        assert "Write unit tests" in fragment

    def test_to_embedding_text(self, sample_heuristic: Heuristic):
        text = sample_heuristic.to_embedding_text()
        assert "Test Heuristic" in text
        assert "Always test your code" in text

    def test_embedding_parts(self, sample_heuristic: Heuristic):
        """Test Embeddable protocol implementation."""
        parts = sample_heuristic.embedding_parts()
        assert "Test Heuristic" in parts
        assert "Always test your code" in parts
        assert "Write unit tests" in parts
        assert "Skip tests" in parts


class TestPersona:
    def test_to_evaluation_prompt(self, sample_persona: Persona):
        prompt = sample_persona.to_evaluation_prompt("Sample content to review")
        assert "test_user" in prompt
        assert "Sample content to review" in prompt
        assert "What does this mean?" in prompt


class TestLens:
    def test_summary(self, sample_lens: Lens):
        summary = sample_lens.summary()
        assert "Test Lens" in summary
        assert "1.0.0" in summary

    def test_get_persona(self, sample_lens: Lens):
        persona = sample_lens.get_persona("test_user")
        assert persona is not None
        assert persona.name == "test_user"

        assert sample_lens.get_persona("nonexistent") is None

    def test_get_heuristic(self, sample_lens: Lens):
        heuristic = sample_lens.get_heuristic("Test Heuristic")
        assert heuristic is not None

    def test_to_context(self, sample_lens: Lens):
        context = sample_lens.to_context()
        assert "Test Lens" in context
        assert "Test Heuristic" in context
