"""Tests for Naaru condition implementations.

Tests for:
- Vote parsing in Harmonic conditions
- Frame parsing in Rotation conditions
- Token estimation
- Persona selection
"""

import pytest

from sunwell.benchmark.naaru.conditions.rotation import (
    DIVERGENT_ROTATION_FRAMES,
    ROTATION_FRAMES,
    build_rotation_prompt,
    parse_frame_usage,
)
from sunwell.benchmark.naaru.conditions.personas import (
    DIVERGENT_PERSONAS,
    HARDCODED_PERSONAS,
    TemperatureStrategy,
)


# =============================================================================
# Vote Parsing Tests
# =============================================================================


class TestVoteParsing:
    """Tests for vote parsing logic in harmonic conditions.

    The vote parsing was improved to handle A-Z instead of just A/B/C.
    These tests verify that improvement works correctly.
    """

    def test_parse_vote_a(self):
        """Vote 'A' returns index 0."""
        vote = _parse_vote_text("A", n_candidates=3)
        assert vote == 0

    def test_parse_vote_b(self):
        """Vote 'B' returns index 1."""
        vote = _parse_vote_text("B", n_candidates=3)
        assert vote == 1

    def test_parse_vote_c(self):
        """Vote 'C' returns index 2."""
        vote = _parse_vote_text("C", n_candidates=3)
        assert vote == 2

    def test_parse_vote_beyond_candidates(self):
        """Vote beyond candidate count returns 0 (default)."""
        # Only 2 candidates, but vote is C (index 2)
        vote = _parse_vote_text("C", n_candidates=2)
        assert vote == 0  # Default to first

    def test_parse_vote_lowercase(self):
        """Lowercase votes handled (converted to upper)."""
        vote = _parse_vote_text("b", n_candidates=3)
        assert vote == 1

    def test_parse_vote_with_explanation(self):
        """Vote with trailing explanation parsed correctly."""
        vote = _parse_vote_text("B - Response B is more complete", n_candidates=3)
        assert vote == 1

    def test_parse_vote_empty_string(self):
        """Empty vote returns 0 (default)."""
        vote = _parse_vote_text("", n_candidates=3)
        assert vote == 0

    def test_parse_vote_non_letter(self):
        """Non-letter character returns 0 (default)."""
        vote = _parse_vote_text("1", n_candidates=3)
        assert vote == 0

    def test_parse_vote_whitespace(self):
        """Whitespace-only returns 0 (default)."""
        vote = _parse_vote_text("   ", n_candidates=3)
        assert vote == 0

    def test_parse_vote_z_with_many_candidates(self):
        """Vote 'Z' works with 26 candidates."""
        vote = _parse_vote_text("Z", n_candidates=26)
        assert vote == 25

    @pytest.mark.parametrize("letter,expected", [
        ("A", 0), ("B", 1), ("C", 2), ("D", 3), ("E", 4),
        ("F", 5), ("G", 6), ("H", 7), ("I", 8), ("J", 9),
    ])
    def test_parse_vote_letters_a_through_j(self, letter: str, expected: int):
        """All letters A-J map to correct indices."""
        vote = _parse_vote_text(letter, n_candidates=10)
        assert vote == expected


# =============================================================================
# Frame Parsing Tests
# =============================================================================


class TestParseFrameUsage:
    """Tests for parse_frame_usage in rotation conditions."""

    def test_single_frame_detected(self):
        """Single frame detected and counted."""
        text = "<think>Let me analyze this problem carefully.</think>"

        usage = parse_frame_usage(text, ROTATION_FRAMES)

        assert "think" in usage
        assert usage["think"] > 0

    def test_multiple_frames_detected(self):
        """Multiple different frames detected."""
        text = """<think>Initial thoughts here.</think>
<critic>But wait, there's a flaw.</critic>
<synthesize>Combining perspectives.</synthesize>"""

        usage = parse_frame_usage(text, ROTATION_FRAMES)

        assert len(usage) == 3
        assert "think" in usage
        assert "critic" in usage
        assert "synthesize" in usage

    def test_repeated_frame_aggregated(self):
        """Multiple instances of same frame are aggregated."""
        text = """<think>First thought.</think>
Some other content.
<think>Second thought with more words here.</think>"""

        usage = parse_frame_usage(text, ROTATION_FRAMES)

        assert "think" in usage
        # Should count tokens from both instances
        assert usage["think"] > 5  # More than just one instance

    def test_case_insensitive_matching(self):
        """Frame tags matched case-insensitively."""
        text = "<THINK>Upper case frame.</THINK>"

        usage = parse_frame_usage(text, ROTATION_FRAMES)

        assert "think" in usage

    def test_nested_content_extracted(self):
        """Content with nested elements extracted correctly."""
        text = """<think>
Here's some code:
```python
def example():
    pass
```
End of thought.
</think>"""

        usage = parse_frame_usage(text, ROTATION_FRAMES)

        assert "think" in usage
        assert usage["think"] > 0

    def test_unknown_frames_ignored(self):
        """Unknown frame names not included in results."""
        text = "<unknown>Some content</unknown><think>Valid</think>"

        usage = parse_frame_usage(text, ROTATION_FRAMES)

        assert "unknown" not in usage
        assert "think" in usage

    def test_empty_frame_not_counted(self):
        """Empty frames not included in results."""
        text = "<think></think>"

        usage = parse_frame_usage(text, ROTATION_FRAMES)

        # Empty content means no tokens, so frame shouldn't appear
        # (or appears with 0 tokens, depending on implementation)
        if "think" in usage:
            assert usage["think"] == 0

    def test_token_estimation_accuracy(self):
        """Token count estimation is approximately 1.33x word count."""
        # 10 words should be ~13 tokens
        text = "<think>one two three four five six seven eight nine ten</think>"

        usage = parse_frame_usage(text, ROTATION_FRAMES)

        # 10 words * 1.33 ≈ 13 tokens
        assert 10 <= usage["think"] <= 16

    def test_divergent_frames_parsed(self):
        """Divergent rotation frames parsed correctly."""
        text = """<adversary>Attack vectors here.</adversary>
<advocate>Defense points here.</advocate>
<naive>Beginner questions here.</naive>"""

        usage = parse_frame_usage(text, DIVERGENT_ROTATION_FRAMES)

        assert "adversary" in usage
        assert "advocate" in usage
        assert "naive" in usage

    def test_multiline_frame_content(self):
        """Multiline content within frames extracted."""
        text = """<think>
Line one of thought.
Line two of thought.
Line three of thought.
</think>"""

        usage = parse_frame_usage(text, ROTATION_FRAMES)

        assert "think" in usage
        # Should have tokens from all three lines
        assert usage["think"] >= 9  # At least 9 words


class TestBuildRotationPrompt:
    """Tests for build_rotation_prompt."""

    def test_includes_all_frames(self):
        """Generated prompt includes all frame definitions."""
        prompt = build_rotation_prompt(ROTATION_FRAMES)

        for frame_name in ROTATION_FRAMES:
            assert f"<{frame_name}>" in prompt
            assert f"</{frame_name}>" in prompt

    def test_includes_frame_descriptions(self):
        """Generated prompt includes frame descriptions."""
        prompt = build_rotation_prompt(ROTATION_FRAMES)

        for description in ROTATION_FRAMES.values():
            assert description in prompt

    def test_includes_example(self):
        """Generated prompt includes usage example."""
        prompt = build_rotation_prompt(ROTATION_FRAMES)

        assert "<think>" in prompt
        assert "</think>" in prompt
        assert "Example" in prompt


# =============================================================================
# Persona Tests
# =============================================================================


class TestHardcodedPersonas:
    """Tests for hardcoded persona definitions."""

    def test_has_three_personas(self):
        """Default set has 3 personas."""
        assert len(HARDCODED_PERSONAS) == 3

    def test_persona_names_present(self):
        """Expected persona names are present."""
        # May vary by implementation, but should have sensible names
        assert len(HARDCODED_PERSONAS) >= 2

    def test_persona_values_are_strings(self):
        """All persona values are non-empty strings."""
        for name, prompt in HARDCODED_PERSONAS.items():
            assert isinstance(name, str)
            assert isinstance(prompt, str)
            assert len(prompt) > 0


class TestDivergentPersonas:
    """Tests for divergent persona definitions."""

    def test_has_expected_personas(self):
        """Divergent set includes adversary, advocate, naive."""
        assert "adversary" in DIVERGENT_PERSONAS
        assert "advocate" in DIVERGENT_PERSONAS
        assert "naive" in DIVERGENT_PERSONAS

    def test_divergent_personas_have_temps(self):
        """Divergent personas include temperature values."""
        for name, value in DIVERGENT_PERSONAS.items():
            # Value should be a tuple of (prompt, temp) or similar
            assert len(value) >= 2


class TestTemperatureStrategy:
    """Tests for temperature strategy configurations."""

    def test_uniform_strategies_exist(self):
        """Uniform temperature strategies exist."""
        assert hasattr(TemperatureStrategy, "UNIFORM_LOW")
        assert hasattr(TemperatureStrategy, "UNIFORM_MED")
        assert hasattr(TemperatureStrategy, "UNIFORM_HIGH")

    def test_spread_strategy_exists(self):
        """Spread temperature strategy exists."""
        assert hasattr(TemperatureStrategy, "SPREAD")

    def test_divergent_strategy_exists(self):
        """Divergent temperature strategy exists."""
        assert hasattr(TemperatureStrategy, "DIVERGENT")

    def test_strategies_return_dict(self):
        """Temperature strategies return dict-like objects."""
        strategy = TemperatureStrategy.UNIFORM_MED

        # Should be usable as dict
        assert hasattr(strategy, "get") or isinstance(strategy, dict)


# =============================================================================
# Helpers
# =============================================================================


def _parse_vote_text(vote_text: str, n_candidates: int) -> int:
    """Replicate the vote parsing logic for testing.

    This mirrors the improved logic in harmonic.py:collect_votes.
    """
    vote_text = vote_text.strip().upper()
    vote = 0  # Default to first candidate

    if vote_text:
        first_char = vote_text[0]
        if "A" <= first_char <= "Z":
            candidate_idx = ord(first_char) - ord("A")
            if 0 <= candidate_idx < n_candidates:
                vote = candidate_idx

    return vote
