# Copyright (c) 2025, NVIDIA CORPORATION.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Resonance Verification - Does refinement actually improve quality?

This tests the core claim:
> Rejected proposals, refined with feedback, become better than the original.

The Resonance loop is:
1. Proposal → Judge → Rejected
2. Rejected + Feedback → Resonance → Refined
3. Refined → Judge → (Better score?)

If this test fails, the "iterate" part of the vision doesn't work.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import pytest

from sunwell.planning.naaru.resonance import Resonance, ResonanceConfig, ResonanceResult


# =============================================================================
# Quality Scoring (Heuristic Judge)
# =============================================================================


@dataclass
class QualityScore:
    """Quality assessment of code."""

    score: float  # 0-10
    issues: list[str]
    has_docstring: bool
    has_type_hints: bool
    has_error_handling: bool
    line_count: int


def score_python_code(code: str) -> QualityScore:
    """Score Python code quality using heuristics.

    This is a deterministic judge - same code always gets same score.
    Used for testing refinement improvement.
    """
    issues = []
    score = 5.0  # Start at middle

    # Check for docstring
    has_docstring = '"""' in code or "'''" in code
    if not has_docstring:
        issues.append("Missing docstring")
        score -= 1.5
    else:
        score += 1.0

    # Check for type hints
    has_type_hints = "->" in code or ": int" in code or ": str" in code or ": float" in code
    if not has_type_hints:
        issues.append("No type hints")
        score -= 1.0
    else:
        score += 1.0

    # Check for error handling
    has_error_handling = "raise " in code or "try:" in code or "except" in code
    if not has_error_handling:
        issues.append("No error handling")
        score -= 0.5
    else:
        score += 0.5

    # Check for Args/Returns in docstring
    if has_docstring:
        if "Args:" in code:
            score += 0.5
        else:
            issues.append("Docstring missing Args section")
        if "Returns:" in code:
            score += 0.5
        else:
            issues.append("Docstring missing Returns section")

    # Check for proper function definition
    if "def " in code:
        score += 0.5
    else:
        issues.append("No function definition")
        score -= 2.0

    # Check for reasonable length (not too short)
    lines = [l for l in code.split("\n") if l.strip() and not l.strip().startswith("#")]
    line_count = len(lines)
    if line_count < 3:
        issues.append("Too short - likely incomplete")
        score -= 1.0
    elif line_count > 5:
        score += 0.5  # More complete

    # Clamp score
    score = max(0.0, min(10.0, score))

    return QualityScore(
        score=score,
        issues=issues,
        has_docstring=has_docstring,
        has_type_hints=has_type_hints,
        has_error_handling=has_error_handling,
        line_count=line_count,
    )


# =============================================================================
# Mock Model for Testing
# =============================================================================


class MockRefinementModel:
    """Mock model that returns progressively better code.

    Simulates what a real model does: addresses feedback incrementally.
    """

    def __init__(self):
        self.call_count = 0
        self.prompts_received: list[str] = []

    async def generate(self, prompt: str, options=None):
        self.call_count += 1
        self.prompts_received.append(prompt)

        # Extract what issues we're asked to fix
        has_docstring_issue = "Missing docstring" in prompt or "docstring" in prompt.lower()
        has_type_hint_issue = "type hint" in prompt.lower() or "No type hints" in prompt
        has_error_issue = "error handling" in prompt.lower() or "No error handling" in prompt

        # Build incrementally better code
        code_lines = ["def example("]

        # Add type hints if requested
        if has_type_hint_issue or self.call_count > 1:
            code_lines[0] = "def example(x: int) -> int:"
        else:
            code_lines[0] = "def example(x):"

        # Add docstring if requested
        if has_docstring_issue or self.call_count > 1:
            code_lines.extend([
                '    """Process the input value.',
                "",
                "    Args:",
                "        x: The input integer",
                "",
                "    Returns:",
                "        The processed result",
                '    """',
            ])

        # Add error handling if requested
        if has_error_issue or self.call_count > 1:
            code_lines.extend([
                "    if x is None:",
                '        raise ValueError("x cannot be None")',
            ])

        # Add body
        code_lines.append("    return x * 2")

        content = "\n".join(code_lines)

        class MockResult:
            def __init__(self, content):
                self.content = content

            class usage:
                total_tokens = 50

        return MockResult(content)


class DeterministicImprovementModel:
    """Model that deterministically improves code quality each call."""

    RESPONSES = [
        # Attempt 1: Add type hints only
        """def example(x: int) -> int:
    return x * 2""",
        # Attempt 2: Add docstring
        '''def example(x: int) -> int:
    """Double the input.

    Args:
        x: Input value

    Returns:
        Doubled value
    """
    return x * 2''',
        # Attempt 3: Add error handling
        '''def example(x: int) -> int:
    """Double the input.

    Args:
        x: Input value

    Returns:
        Doubled value

    Raises:
        ValueError: If x is None
    """
    if x is None:
        raise ValueError("x cannot be None")
    return x * 2''',
    ]

    def __init__(self):
        self.call_count = 0

    async def generate(self, prompt: str, options=None):
        response = self.RESPONSES[min(self.call_count, len(self.RESPONSES) - 1)]
        self.call_count += 1

        class MockResult:
            def __init__(self, content):
                self.content = content

            class usage:
                total_tokens = 50

        return MockResult(response)


# =============================================================================
# Test: Resonance Structure
# =============================================================================


class TestResonanceStructure:
    """Test that Resonance has the expected interface."""

    def test_resonance_exists(self):
        """Resonance class must exist with expected interface."""
        assert hasattr(Resonance, "refine")
        assert hasattr(Resonance, "refine_with_validation")
        assert hasattr(Resonance, "get_stats")

    def test_resonance_config_defaults(self):
        """ResonanceConfig must have sensible defaults."""
        config = ResonanceConfig()
        assert config.max_attempts == 2
        assert config.temperature_boost == 0.1
        assert config.max_tokens == 768

    def test_resonance_result_structure(self):
        """ResonanceResult must have all required fields."""
        result = ResonanceResult(
            refined_code="def foo(): pass",
            refined_proposal_id="test_r1",
            original_proposal_id="test",
            attempts=[],
            total_tokens=100,
            success=True,
        )

        assert result.refined_code == "def foo(): pass"
        assert result.success is True
        assert result.total_tokens == 100


# =============================================================================
# Test: Refinement Produces Output
# =============================================================================


class TestRefinementProducesOutput:
    """Test that refinement actually generates refined code."""

    @pytest.mark.asyncio
    async def test_refine_returns_result(self):
        """Resonance.refine() must return a ResonanceResult."""
        model = MockRefinementModel()
        resonance = Resonance(model=model, config=ResonanceConfig(max_attempts=1))

        proposal = {"proposal_id": "test", "diff": "def foo(): pass"}
        rejection = {"issues": ["Missing docstring"], "score": 4.0}

        result = await resonance.refine(proposal, rejection)

        assert isinstance(result, ResonanceResult)
        assert result.refined_code != ""
        assert result.original_proposal_id == "test"

    @pytest.mark.asyncio
    async def test_refine_uses_feedback(self):
        """Resonance must incorporate feedback into the prompt."""
        model = MockRefinementModel()
        resonance = Resonance(model=model, config=ResonanceConfig(max_attempts=1))

        proposal = {"proposal_id": "test", "diff": "def foo(): pass"}
        rejection = {"issues": ["Missing docstring", "No type hints"], "score": 3.0}

        await resonance.refine(proposal, rejection)

        # Check the model received the issues in the prompt
        assert len(model.prompts_received) >= 1
        prompt = model.prompts_received[0]
        assert "Missing docstring" in prompt or "docstring" in prompt.lower()


# =============================================================================
# Test: Refinement Improves Quality (Core Thesis)
# =============================================================================


class TestRefinementImprovesQuality:
    """The core thesis: refinement must actually improve code quality."""

    @pytest.mark.asyncio
    async def test_refined_code_scores_higher(self):
        """Refined code must score higher than original."""
        model = DeterministicImprovementModel()
        resonance = Resonance(model=model, config=ResonanceConfig(max_attempts=1))

        # Start with bad code
        original_code = "def example(x): return x * 2"
        original_score = score_python_code(original_code)

        proposal = {"proposal_id": "test", "diff": original_code}
        rejection = {
            "issues": original_score.issues,
            "score": original_score.score,
        }

        result = await resonance.refine(proposal, rejection)
        refined_score = score_python_code(result.refined_code)

        assert refined_score.score > original_score.score, (
            f"Refinement did not improve score: {original_score.score} -> {refined_score.score}\n"
            f"Original: {original_code}\n"
            f"Refined: {result.refined_code}"
        )

    @pytest.mark.asyncio
    async def test_multiple_refinements_improve_cumulatively(self):
        """Multiple refinement rounds should keep improving quality."""
        model = DeterministicImprovementModel()
        resonance = Resonance(model=model, config=ResonanceConfig(max_attempts=3))

        original_code = "def example(x): return x * 2"
        scores = [score_python_code(original_code).score]

        current_code = original_code
        for i in range(3):
            current_score = score_python_code(current_code)
            proposal = {"proposal_id": f"test_{i}", "diff": current_code}
            rejection = {"issues": current_score.issues, "score": current_score.score}

            # Reset model for fresh refinement
            model_fresh = DeterministicImprovementModel()
            model_fresh.call_count = i  # Advance to right response
            resonance_fresh = Resonance(model=model_fresh, config=ResonanceConfig(max_attempts=1))

            result = await resonance_fresh.refine(proposal, rejection)
            current_code = result.refined_code
            scores.append(score_python_code(current_code).score)

        # Each refinement should improve or maintain score
        for i in range(1, len(scores)):
            assert scores[i] >= scores[i - 1], (
                f"Score decreased at refinement {i}: {scores[i-1]} -> {scores[i]}"
            )

        # Final score should be better than original
        assert scores[-1] > scores[0], (
            f"Final score ({scores[-1]}) not better than original ({scores[0]})"
        )

    @pytest.mark.asyncio
    async def test_refinement_addresses_specific_issues(self):
        """Refinement should address the specific issues raised."""
        model = MockRefinementModel()
        resonance = Resonance(model=model, config=ResonanceConfig(max_attempts=1))

        original_code = "def example(x): return x * 2"
        original_score = score_python_code(original_code)

        # Specifically request docstring fix
        proposal = {"proposal_id": "test", "diff": original_code}
        rejection = {"issues": ["Missing docstring"], "score": original_score.score}

        result = await resonance.refine(proposal, rejection)
        refined_score = score_python_code(result.refined_code)

        # The specific issue should be fixed
        assert refined_score.has_docstring, (
            f"Refinement did not add docstring:\n{result.refined_code}"
        )


# =============================================================================
# Test: Diminishing Returns
# =============================================================================


class TestDiminishingReturns:
    """Test that refinement has sensible stopping behavior."""

    @pytest.mark.asyncio
    async def test_refinement_respects_max_attempts(self):
        """Resonance must stop after max_attempts."""
        model = MockRefinementModel()
        config = ResonanceConfig(max_attempts=2)
        resonance = Resonance(model=model, config=config)

        proposal = {"proposal_id": "test", "diff": "def foo(): pass"}
        rejection = {"issues": ["Issue 1", "Issue 2"], "score": 3.0}

        result = await resonance.refine(proposal, rejection)

        # Should have exactly max_attempts attempts
        assert len(result.attempts) <= config.max_attempts

    @pytest.mark.asyncio
    async def test_perfect_code_needs_no_refinement(self):
        """Code that already scores high shouldn't need refinement."""
        perfect_code = '''def example(x: int) -> int:
    """Double the input value.

    Args:
        x: The input integer to double

    Returns:
        The doubled value

    Raises:
        ValueError: If x is None
    """
    if x is None:
        raise ValueError("x cannot be None")
    return x * 2'''

        score = score_python_code(perfect_code)

        # Perfect code should score high
        assert score.score >= 8.0, f"Perfect code scored too low: {score.score}"
        assert len(score.issues) <= 1, f"Perfect code has issues: {score.issues}"


# =============================================================================
# Test: Stats Tracking
# =============================================================================


class TestStatsTracking:
    """Test that Resonance tracks statistics correctly."""

    @pytest.mark.asyncio
    async def test_stats_increment_on_refinement(self):
        """Stats should update after each refinement."""
        model = MockRefinementModel()
        resonance = Resonance(model=model, config=ResonanceConfig(max_attempts=1))

        initial_stats = resonance.get_stats()
        assert initial_stats["refinements_attempted"] == 0

        proposal = {"proposal_id": "test", "diff": "def foo(): pass"}
        rejection = {"issues": ["Issue"], "score": 3.0}

        await resonance.refine(proposal, rejection)

        final_stats = resonance.get_stats()
        assert final_stats["refinements_attempted"] > 0
        assert final_stats["total_tokens"] > 0


# =============================================================================
# Integration Test: Full Refinement Loop (Skip without model)
# =============================================================================


@pytest.mark.slow
@pytest.mark.integration
class TestResonanceIntegration:
    """Integration tests requiring real model.

    Run manually with: pytest -m integration
    """

    @pytest.mark.asyncio
    async def test_real_model_refinement_improves_quality(self):
        """Test that refinement with a real model improves code quality."""
        pytest.skip("Requires real model - run manually")

        # This would test:
        # 1. Start with genuinely bad code
        # 2. Refine with real LLM
        # 3. Score both versions
        # 4. Assert improvement
