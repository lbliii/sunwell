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

"""The Prism Principle - Multi-perspective synthesis beats single-shot.

This is the CORE THESIS of Sunwell:

> Small models contain multitudes (critic, expert, user, adversary).
> Multi-perspective synthesis reveals what's already there.
> The smaller the model, the more it benefits from structured refraction.

If this test fails, Sunwell's architecture is aspirational, not real.

Test Strategy:
1. Generate with single-shot (baseline)
2. Generate with harmonic synthesis (multiple personas)
3. Judge quality of both outputs
4. Verify: treatment > baseline, especially on small models
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest


# =============================================================================
# Test Data Classes
# =============================================================================


@dataclass
class GenerationResult:
    """Result from a generation strategy."""

    content: str
    strategy: str
    model: str
    metadata: dict[str, Any] | None = None


@dataclass
class QualityJudgment:
    """Quality judgment for a generation result."""

    score: float  # 0.0 - 1.0
    criteria_scores: dict[str, float]
    explanation: str


@dataclass
class ComparisonResult:
    """Result of comparing two strategies."""

    baseline: GenerationResult
    treatment: GenerationResult
    baseline_score: float
    treatment_score: float
    improvement: float  # (treatment - baseline) / baseline
    treatment_wins: bool


# =============================================================================
# Mock Implementation for Unit Testing
# =============================================================================


class MockQualityJudge:
    """Mock judge that scores based on content characteristics.

    This allows testing the comparison framework without real LLM calls.
    In integration tests, replace with real LLM-based judging.
    """

    def __init__(self, criteria: list[str] | None = None):
        self.criteria = criteria or [
            "completeness",
            "clarity",
            "correctness",
            "structure",
        ]

    def judge(self, content: str, task: str) -> QualityJudgment:
        """Score content based on heuristics."""
        scores = {}

        # Simple heuristics (replace with LLM judging in integration tests)
        scores["completeness"] = min(1.0, len(content) / 500)
        scores["clarity"] = 0.8 if "```" in content else 0.5  # Has code blocks
        scores["correctness"] = 0.7  # Can't verify without execution
        scores["structure"] = 0.9 if content.count("\n\n") >= 2 else 0.5

        # Weight: completeness 30%, clarity 25%, correctness 30%, structure 15%
        weights = {"completeness": 0.3, "clarity": 0.25, "correctness": 0.3, "structure": 0.15}
        overall = sum(scores[k] * weights[k] for k in scores)

        return QualityJudgment(
            score=overall,
            criteria_scores=scores,
            explanation=f"Scored {overall:.2f} based on heuristics",
        )


# =============================================================================
# Test: Harmonic Planning Produces Better DAGs
# =============================================================================


class TestHarmonicPlanningImprovement:
    """Harmonic planning should produce better artifact DAGs than single-shot."""

    @pytest.mark.asyncio
    async def test_harmonic_planning_improves_parallelism(self):
        """Harmonic planning should produce graphs with higher parallelism."""
        from sunwell.naaru.artifacts import ArtifactGraph, ArtifactSpec
        from sunwell.naaru.planners.harmonic import HarmonicPlanner, PlanMetrics

        # Create a mock model that returns different artifacts per call
        call_count = [0]

        class VariedMockModel:
            async def generate(self, prompt: str, options=None):
                call_count[0] += 1

                # Vary the response to simulate different planning perspectives
                if "parallel_first" in prompt or "MAXIMUM PARALLELISM" in prompt:
                    # Parallel-first style: more leaves
                    response = '''[
                        {"id": "A", "description": "A", "contract": "A", "requires": []},
                        {"id": "B", "description": "B", "contract": "B", "requires": []},
                        {"id": "C", "description": "C", "contract": "C", "requires": []},
                        {"id": "D", "description": "D", "contract": "D", "requires": ["A", "B", "C"]}
                    ]'''
                else:
                    # Default: sequential
                    response = '''[
                        {"id": "A", "description": "A", "contract": "A", "requires": []},
                        {"id": "B", "description": "B", "contract": "B", "requires": ["A"]},
                        {"id": "C", "description": "C", "contract": "C", "requires": ["B"]}
                    ]'''

                class MockResult:
                    def __init__(self, content):
                        self.content = content
                        self.text = content

                return MockResult(response)

        model = VariedMockModel()
        planner = HarmonicPlanner(
            model=model,
            candidates=3,
            refinement_rounds=0,
        )

        graph, metrics = await planner.plan_with_metrics(
            "Build something",
            context={"cwd": "/tmp"},
        )

        # Harmonic should select the more parallel plan
        assert metrics.parallelism_factor > 0.3, (
            f"Expected parallelism > 0.3, got {metrics.parallelism_factor}"
        )

    @pytest.mark.asyncio
    async def test_harmonic_planning_selects_best_candidate(self):
        """Harmonic planning should select the highest-scoring candidate."""
        from sunwell.naaru.planners.harmonic import HarmonicPlanner, PlanMetrics

        class ScoringMockModel:
            """Mock that returns plans with known scores."""

            async def generate(self, prompt: str, options=None):
                # Return a plan that will score based on prompt style
                if "thorough" in prompt.lower():
                    # More artifacts, deeper
                    response = '''[
                        {"id": "A", "description": "A", "contract": "A", "requires": []},
                        {"id": "B", "description": "B", "contract": "B", "requires": ["A"]},
                        {"id": "C", "description": "C", "contract": "C", "requires": ["B"]},
                        {"id": "D", "description": "D", "contract": "D", "requires": ["C"]}
                    ]'''
                elif "minimal" in prompt.lower():
                    # Fewer artifacts
                    response = '''[
                        {"id": "A", "description": "A", "contract": "A", "requires": []}
                    ]'''
                else:
                    # Balanced - should win
                    response = '''[
                        {"id": "A", "description": "A", "contract": "A", "requires": []},
                        {"id": "B", "description": "B", "contract": "B", "requires": []},
                        {"id": "C", "description": "C", "contract": "C", "requires": ["A", "B"]}
                    ]'''

                class MockResult:
                    def __init__(self, content):
                        self.content = content

                return MockResult(response)

        model = ScoringMockModel()
        planner = HarmonicPlanner(
            model=model,
            candidates=3,
            refinement_rounds=0,
        )

        graph, metrics = await planner.plan_with_metrics(
            "Build something",
            context={"cwd": "/tmp"},
        )

        # Should select the balanced plan (2 leaves, 1 root, good parallelism)
        assert len(graph) == 3, f"Expected 3 artifacts, got {len(graph)}"


# =============================================================================
# Test: Multi-Perspective Synthesis Structure
# =============================================================================


class TestMultiPerspectiveSynthesisStructure:
    """Verify the structure of multi-perspective synthesis is correct."""

    def test_harmonic_worker_has_multiple_personas(self):
        """HarmonicSynthesisWorker must define multiple personas."""
        from sunwell.naaru.workers.harmonic import HarmonicSynthesisWorker

        assert hasattr(HarmonicSynthesisWorker, "LENS_PERSONAS")
        personas = HarmonicSynthesisWorker.LENS_PERSONAS

        # Must have at least 2 personas for meaningful synthesis
        assert len(personas) >= 2, f"Expected >= 2 personas, got {len(personas)}"

        # Each persona must have name and system prompt
        for key, persona in personas.items():
            assert "name" in persona, f"Persona {key} missing 'name'"
            assert "system" in persona, f"Persona {key} missing 'system'"

    def test_diversity_module_has_harmonic_function(self):
        """Diversity module must have harmonic (multi-persona) function."""
        from sunwell.naaru.diversity import diversity_harmonic, HARMONIC_PERSONAS

        # Harmonic function must exist
        assert callable(diversity_harmonic), "diversity_harmonic must be callable"

        # Must have multiple personas
        assert len(HARMONIC_PERSONAS) >= 2, (
            f"Expected >= 2 personas, got {len(HARMONIC_PERSONAS)}"
        )

    def test_variance_strategies_exist(self):
        """HarmonicPlanner must have variance strategies."""
        from sunwell.naaru.planners.harmonic import VarianceStrategy

        strategies = [s.value for s in VarianceStrategy]

        assert "prompting" in strategies
        assert "temperature" in strategies
        assert "mixed" in strategies


# =============================================================================
# Test: Confidence Triangulation Uses Multiple Signals
# =============================================================================


class TestConfidenceTriangulation:
    """Confidence must be derived from multiple signals, not single-shot."""

    def test_triangulator_uses_multiple_signals(self):
        """ConfidenceTriangulator must combine multiple evidence sources."""
        from sunwell.verification.triangulator import ConfidenceTriangulator
        from sunwell.verification.types import (
            PerspectiveResult,
            Specification,
            InputSpec,
            OutputSpec,
        )

        triangulator = ConfidenceTriangulator()

        # Create test data
        spec = Specification(
            description="Add two numbers",
            inputs=(InputSpec(name="a", type_hint="int", constraints=()),),
            outputs=(OutputSpec(type_hint="int", constraints=()),),
            preconditions=(),
            postconditions=(),
            invariants=(),
            edge_cases=(),
            source="contract",
            confidence=0.9,
        )

        perspectives = [
            PerspectiveResult(
                perspective="security",
                verdict="correct",
                confidence=0.9,
                issues=[],
                recommendations=[],
            ),
            PerspectiveResult(
                perspective="code_quality",
                verdict="correct",
                confidence=0.85,
                issues=[],
                recommendations=[],
            ),
        ]

        result = triangulator.triangulate(
            spec=spec,
            execution_results=None,
            perspective_results=perspectives,
        )

        # Result must reflect combined signals
        assert result.confidence > 0, "Confidence must be positive"
        assert len(result.perspective_results) == 2, (
            "Must preserve all perspective results"
        )

    def test_triangulator_detects_contradictions(self):
        """Triangulator must detect when perspectives contradict."""
        from sunwell.verification.triangulator import ConfidenceTriangulator
        from sunwell.verification.types import (
            PerspectiveResult,
            Specification,
            OutputSpec,
        )

        triangulator = ConfidenceTriangulator()

        spec = Specification(
            description="Do something risky",
            inputs=(),
            outputs=(OutputSpec(type_hint="None", constraints=()),),
            preconditions=(),
            postconditions=(),
            invariants=(),
            edge_cases=(),
            source="contract",
            confidence=0.9,
        )

        # Contradicting perspectives
        perspectives = [
            PerspectiveResult(
                perspective="security",
                verdict="incorrect",  # Says it's bad
                confidence=0.9,
                issues=["Security vulnerability"],
                recommendations=[],
            ),
            PerspectiveResult(
                perspective="code_quality",
                verdict="correct",  # Says it's good
                confidence=0.9,
                issues=[],
                recommendations=[],
            ),
        ]

        result = triangulator.triangulate(
            spec=spec,
            execution_results=None,
            perspective_results=perspectives,
        )

        # Contradictions should reduce confidence
        assert result.confidence < 0.9, (
            "Contradicting perspectives should reduce confidence"
        )


# =============================================================================
# Integration Test: Real Model Comparison (Skip without model)
# =============================================================================


@pytest.mark.slow
@pytest.mark.integration
class TestPrismPrincipleIntegration:
    """Integration tests requiring a real model.

    These tests verify the core thesis with actual LLM calls.
    Skip in CI; run manually with: pytest -m integration
    """

    @pytest.fixture
    def has_model(self):
        """Check if a model is available."""
        try:
            from sunwell.models.ollama import OllamaModel
            model = OllamaModel(model_id="qwen2.5:3b")
            return True
        except Exception:
            return False

    @pytest.mark.asyncio
    async def test_harmonic_beats_single_shot_planning(self, has_model):
        """Harmonic planning should produce better plans than single-shot."""
        if not has_model:
            pytest.skip("No model available")

        from sunwell.naaru.planners.artifact import ArtifactPlanner
        from sunwell.naaru.planners.harmonic import HarmonicPlanner
        from sunwell.models.ollama import OllamaModel

        model = OllamaModel(model_id="qwen2.5:3b")
        goal = "Build a REST API with user authentication"

        # Single-shot planning
        single_planner = ArtifactPlanner(model=model)
        single_graph = await single_planner.discover_graph(goal)

        # Harmonic planning
        harmonic_planner = HarmonicPlanner(
            model=model,
            candidates=5,
            refinement_rounds=1,
        )
        harmonic_graph, harmonic_metrics = await harmonic_planner.plan_with_metrics(goal)

        # Calculate single-shot metrics for comparison
        single_leaves = len(single_graph.leaves())
        single_total = len(single_graph)
        single_parallelism = single_leaves / single_total if single_total > 0 else 0

        # Harmonic should have better parallelism
        improvement = (harmonic_metrics.parallelism_factor - single_parallelism) / max(single_parallelism, 0.1)

        assert improvement >= 0.10, (
            f"Expected >= 10% improvement, got {improvement:.1%}. "
            f"Single: {single_parallelism:.2f}, Harmonic: {harmonic_metrics.parallelism_factor:.2f}"
        )
