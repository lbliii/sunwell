"""Tests for Phase 3: Reflection System.

Tests constraint causality analysis, pattern detection, and mental model synthesis.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sunwell.foundation.types.memory import Learning
from sunwell.memory.core.reflection.causality import CausalityAnalyzer
from sunwell.memory.core.reflection.patterns import PatternDetector
from sunwell.memory.core.reflection.reflector import Reflector
from sunwell.memory.core.reflection.types import MentalModel, PatternCluster, Reflection


class TestPatternDetector:
    """Test pattern detection and clustering."""

    def test_cluster_similar_learnings(self):
        """Test clustering similar learnings together."""
        detector = PatternDetector()

        learnings = [
            Learning(id="l1", fact="Don't use global state in components", category="constraint"),
            Learning(id="l2", fact="Avoid side effects in render", category="constraint"),
            Learning(id="l3", fact="Use hooks for state management", category="pattern"),
            Learning(id="l4", fact="Implement pagination for large datasets", category="pattern"),
        ]

        # Cluster learnings (semantic or keyword-based)
        clusters = detector.cluster_learnings(learnings, threshold=0.7)

        # Should create clusters based on similarity
        assert len(clusters) > 0

        # React/state management learnings should cluster together
        state_cluster = None
        for cluster in clusters:
            learning_ids = {l.id for l in cluster.learnings}
            if "l1" in learning_ids or "l2" in learning_ids or "l3" in learning_ids:
                state_cluster = cluster
                break

        assert state_cluster is not None
        assert len(state_cluster.learnings) >= 2

    def test_keyword_based_clustering(self):
        """Test keyword-based clustering fallback."""
        detector = PatternDetector()

        learnings = [
            Learning(id="l1", fact="React hooks are useful", category="pattern"),
            Learning(id="l2", fact="React components should be pure", category="constraint"),
            Learning(id="l3", fact="PostgreSQL indexes improve performance", category="pattern"),
        ]

        # Use keyword-based clustering
        clusters = detector.cluster_by_keywords(learnings)

        # Should create separate clusters for React and PostgreSQL
        assert len(clusters) >= 2

        # Verify React learnings clustered together
        react_cluster = next((c for c in clusters if "React" in c.theme), None)
        assert react_cluster is not None
        assert len(react_cluster.learnings) >= 2

    def test_empty_learnings(self):
        """Test clustering with no learnings."""
        detector = PatternDetector()
        clusters = detector.cluster_learnings([], threshold=0.7)
        assert len(clusters) == 0

    def test_single_learning(self):
        """Test clustering with single learning."""
        detector = PatternDetector()
        learnings = [Learning(id="l1", fact="Single fact", category="pattern")]
        clusters = detector.cluster_learnings(learnings, threshold=0.7)

        # Should create one cluster
        assert len(clusters) == 1
        assert len(clusters[0].learnings) == 1


class TestCausalityAnalyzer:
    """Test causality analysis."""

    @pytest.mark.asyncio
    async def test_analyze_constraint_causality(self):
        """Test analyzing WHY constraints exist."""
        analyzer = CausalityAnalyzer()

        constraints = [
            Learning(id="l1", fact="Don't use global state", category="constraint"),
            Learning(id="l2", fact="Avoid side effects in render", category="constraint"),
            Learning(id="l3", fact="Use functional components", category="constraint"),
        ]

        # Mock LLM response
        with patch.object(analyzer, "_llm_analyze", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = {
                "theme": "React functional programming",
                "causality": "These stem from React's declarative rendering model",
                "summary": "Functional purity enables predictable re-renders",
            }

            result = await analyzer.analyze_causality(constraints)

            assert result["theme"] == "React functional programming"
            assert "declarative" in result["causality"]
            assert "purity" in result["summary"]

    def test_heuristic_causality_analysis(self):
        """Test fallback heuristic analysis."""
        analyzer = CausalityAnalyzer()

        constraints = [
            Learning(id="l1", fact="Use bcrypt for passwords", category="constraint"),
            Learning(id="l2", fact="Never store passwords in plain text", category="constraint"),
            Learning(id="l3", fact="Require strong password policies", category="constraint"),
        ]

        # Use heuristic analysis (no LLM)
        result = analyzer.heuristic_analyze(constraints)

        assert result["theme"] is not None
        assert len(result["theme"]) > 0
        # Should extract common keywords like "password"


class TestReflector:
    """Test main reflection engine."""

    @pytest.mark.asyncio
    async def test_reflect_on_constraints(self):
        """Test reflection on constraint learnings."""
        reflector = Reflector()

        constraints = [
            Learning(id="l1", fact="Don't use global state", category="constraint"),
            Learning(id="l2", fact="Avoid side effects", category="constraint"),
            Learning(id="l3", fact="Use hooks for state", category="constraint"),
        ]

        # Mock the causality analyzer
        with patch.object(reflector.causality_analyzer, "analyze_causality", new_callable=AsyncMock) as mock_analyze:
            mock_analyze.return_value = {
                "theme": "React state management",
                "causality": "React's rendering model requires pure components",
                "summary": "Functional programming principles enable predictable UI",
            }

            reflection = await reflector.reflect_on_constraints(constraints)

            assert isinstance(reflection, Reflection)
            assert reflection.theme == "React state management"
            assert "React" in reflection.causality
            assert len(reflection.source_learning_ids) == 3

    @pytest.mark.asyncio
    async def test_build_mental_model(self):
        """Test building a mental model from learnings."""
        reflector = Reflector()

        learnings = [
            Learning(id="l1", fact="Use useState for local state", category="pattern"),
            Learning(id="l2", fact="Use useEffect for side effects", category="pattern"),
            Learning(id="l3", fact="Don't call hooks conditionally", category="constraint"),
            Learning(id="l4", fact="Extract custom hooks for reuse", category="pattern"),
            Learning(id="l5", fact="Avoid infinite render loops", category="dead_end"),
        ]

        # Mock clustering and analysis
        with patch.object(reflector.pattern_detector, "cluster_learnings") as mock_cluster:
            mock_cluster.return_value = [
                PatternCluster(
                    theme="React hooks",
                    learnings=learnings,
                    coherence_score=0.85,
                )
            ]

            with patch.object(reflector.causality_analyzer, "analyze_causality", new_callable=AsyncMock) as mock_analyze:
                mock_analyze.return_value = {
                    "theme": "React hooks",
                    "causality": "Hooks enable state and lifecycle in functional components",
                    "summary": "Follow rules of hooks for correctness",
                }

                mental_model = await reflector.build_mental_model("React hooks", learnings)

                assert isinstance(mental_model, MentalModel)
                assert mental_model.topic == "React hooks"
                assert len(mental_model.core_principles) > 0
                assert len(mental_model.key_patterns) > 0
                assert len(mental_model.anti_patterns) > 0  # From dead_end
                assert mental_model.source_learning_count == 5

    def test_estimate_token_savings(self):
        """Test token savings estimation."""
        reflector = Reflector()

        # Create mental model
        mental_model = MentalModel(
            topic="React hooks",
            core_principles=["Use hooks in functional components", "Follow rules of hooks"],
            key_patterns=["useState for state", "useEffect for side effects"],
            anti_patterns=["Don't call hooks conditionally"],
            confidence=0.9,
            source_learning_count=10,
        )

        # Estimate savings
        savings = reflector.estimate_token_savings(mental_model)

        assert savings["individual_learnings_tokens"] > 0
        assert savings["mental_model_tokens"] > 0
        assert savings["savings_tokens"] > 0
        assert savings["savings_percent"] > 0
        # Should achieve ~30% savings
        assert 20 <= savings["savings_percent"] <= 40


@pytest.mark.asyncio
class TestReflectionIntegration:
    """Integration tests for reflection system."""

    async def test_trigger_reflection_on_threshold(self):
        """Test automatic reflection triggering."""
        reflector = Reflector()

        # Simulate 50+ learnings (auto-trigger threshold)
        constraints = [
            Learning(id=f"l{i}", fact=f"Constraint {i}", category="constraint")
            for i in range(15)
        ]

        # Should trigger reflection
        with patch.object(reflector.causality_analyzer, "analyze_causality", new_callable=AsyncMock) as mock_analyze:
            mock_analyze.return_value = {
                "theme": "Test theme",
                "causality": "Test causality",
                "summary": "Test summary",
            }

            reflection = await reflector.reflect_on_constraints(constraints)

            assert reflection is not None
            assert len(reflection.source_learning_ids) == 15

    async def test_reflection_to_learning_conversion(self):
        """Test converting reflection to learning."""
        reflection = Reflection(
            reflection_id="r1",
            theme="React state management",
            causality="React's rendering model requires pure components",
            summary="Functional programming enables predictable UI",
            source_learning_ids=["l1", "l2", "l3"],
            confidence=0.9,
        )

        learning = reflection.to_learning()

        assert learning.category == "reflection"
        assert "React state management" in learning.fact
        assert "causality" in learning.fact.lower() or "Functional programming" in learning.fact
        assert learning.confidence == 0.9

    async def test_mental_model_to_prompt(self):
        """Test converting mental model to prompt format."""
        mental_model = MentalModel(
            topic="React hooks",
            core_principles=[
                "Use hooks in functional components",
                "Follow rules of hooks",
            ],
            key_patterns=[
                "useState for local state",
                "useEffect for side effects",
            ],
            anti_patterns=[
                "Don't call hooks conditionally",
                "Avoid infinite render loops",
            ],
            confidence=0.9,
            source_learning_count=10,
        )

        prompt = mental_model.to_prompt()

        # Should be formatted for injection into planning context
        assert "React hooks" in prompt
        assert "Core Principles:" in prompt
        assert "Key Patterns:" in prompt
        assert "Anti-Patterns:" in prompt
        assert "useState" in prompt
        assert "Don't call hooks conditionally" in prompt

    async def test_mental_model_token_efficiency(self):
        """Test that mental models are more token-efficient."""
        # Individual learnings
        learnings = [
            Learning(id="l1", fact="Use useState for local state in functional components", category="pattern"),
            Learning(id="l2", fact="Use useEffect for side effects and cleanup", category="pattern"),
            Learning(id="l3", fact="Don't call hooks conditionally or in loops", category="constraint"),
            Learning(id="l4", fact="Extract custom hooks for reusable logic", category="pattern"),
            Learning(id="l5", fact="Avoid infinite loops by managing dependencies", category="dead_end"),
        ]

        # Approximate token count for individual learnings
        individual_tokens = sum(len(l.fact.split()) for l in learnings) * 1.3  # ~1.3 tokens per word

        # Mental model (synthesized)
        mental_model = MentalModel(
            topic="React hooks",
            core_principles=["Hooks enable state in functional components"],
            key_patterns=["useState, useEffect, custom hooks"],
            anti_patterns=["Conditional calls, infinite loops"],
            confidence=0.9,
            source_learning_count=5,
        )

        prompt = mental_model.to_prompt()
        model_tokens = len(prompt.split()) * 1.3

        # Mental model should be more compact
        savings_percent = ((individual_tokens - model_tokens) / individual_tokens) * 100
        assert savings_percent > 20  # Should save at least 20%


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
