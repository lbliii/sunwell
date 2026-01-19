"""Tests for RFC-038 Harmonic Planning.

Tests the following components:
- PlanMetrics dataclass
- VarianceStrategy enum
- HarmonicPlanner multi-candidate generation
- Plan scoring and selection
- Iterative refinement
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from sunwell.naaru.artifacts import ArtifactGraph, ArtifactSpec
from sunwell.naaru.planners import (
    HarmonicPlanner,
    PlanMetrics,
    PlanningStrategy,
    VarianceStrategy,
)


# =============================================================================
# PlanMetrics Tests
# =============================================================================


class TestPlanMetrics:
    """Tests for the PlanMetrics dataclass."""

    def test_metrics_creation(self):
        """Test basic metrics creation."""
        metrics = PlanMetrics(
            depth=3,
            width=4,
            leaf_count=2,
            artifact_count=5,
            parallelism_factor=0.4,
            balance_factor=1.33,
            file_conflicts=0,
            estimated_waves=3,
        )

        assert metrics.depth == 3
        assert metrics.width == 4
        assert metrics.leaf_count == 2
        assert metrics.artifact_count == 5
        assert metrics.parallelism_factor == 0.4
        assert metrics.balance_factor == 1.33
        assert metrics.file_conflicts == 0
        assert metrics.estimated_waves == 3

    def test_metrics_score_calculation(self):
        """Test that score is computed correctly."""
        metrics = PlanMetrics(
            depth=3,
            width=4,
            leaf_count=2,
            artifact_count=5,
            parallelism_factor=0.4,
            balance_factor=1.33,
            file_conflicts=0,
            estimated_waves=3,
        )

        # Score formula: parallelism*40 + balance*30 + (1/depth)*20 + (1/(1+conflicts))*10
        expected = (0.4 * 40) + (1.33 * 30) + (1 / 3 * 20) + (1 / 1 * 10)
        assert abs(metrics.score - expected) < 0.01

    def test_high_parallelism_scores_higher(self):
        """Test that higher parallelism produces higher score."""
        low_parallel = PlanMetrics(
            depth=4,
            width=2,
            leaf_count=1,
            artifact_count=10,
            parallelism_factor=0.1,
            balance_factor=0.5,
            file_conflicts=0,
            estimated_waves=4,
        )

        high_parallel = PlanMetrics(
            depth=2,
            width=5,
            leaf_count=5,
            artifact_count=10,
            parallelism_factor=0.5,
            balance_factor=2.5,
            file_conflicts=0,
            estimated_waves=2,
        )

        assert high_parallel.score > low_parallel.score

    def test_file_conflicts_reduce_score(self):
        """Test that file conflicts reduce score."""
        no_conflicts = PlanMetrics(
            depth=3,
            width=4,
            leaf_count=2,
            artifact_count=5,
            parallelism_factor=0.4,
            balance_factor=1.33,
            file_conflicts=0,
            estimated_waves=3,
        )

        with_conflicts = PlanMetrics(
            depth=3,
            width=4,
            leaf_count=2,
            artifact_count=5,
            parallelism_factor=0.4,
            balance_factor=1.33,
            file_conflicts=3,
            estimated_waves=3,
        )

        assert no_conflicts.score > with_conflicts.score


# =============================================================================
# VarianceStrategy Tests
# =============================================================================


class TestVarianceStrategy:
    """Tests for the VarianceStrategy enum."""

    def test_strategy_values(self):
        """Test that all strategies have expected values."""
        assert VarianceStrategy.PROMPTING.value == "prompting"
        assert VarianceStrategy.TEMPERATURE.value == "temperature"
        assert VarianceStrategy.CONSTRAINTS.value == "constraints"
        assert VarianceStrategy.MIXED.value == "mixed"

    def test_strategy_from_string(self):
        """Test creating strategy from string."""
        assert VarianceStrategy("prompting") == VarianceStrategy.PROMPTING
        assert VarianceStrategy("temperature") == VarianceStrategy.TEMPERATURE


# =============================================================================
# PlanningStrategy Tests
# =============================================================================


class TestPlanningStrategy:
    """Tests for RFC-038 addition to PlanningStrategy."""

    def test_harmonic_strategy_exists(self):
        """Test that HARMONIC strategy is defined."""
        assert PlanningStrategy.HARMONIC.value == "harmonic"

    def test_all_strategies_defined(self):
        """Test all expected strategies exist."""
        strategies = [s.value for s in PlanningStrategy]
        assert "sequential" in strategies
        assert "contract_first" in strategies
        assert "resource_aware" in strategies
        assert "artifact_first" in strategies
        assert "harmonic" in strategies


# =============================================================================
# HarmonicPlanner Tests
# =============================================================================


class TestHarmonicPlanner:
    """Tests for the HarmonicPlanner class."""

    @pytest.fixture
    def mock_model(self):
        """Create a mock model for testing."""
        model = MagicMock()
        model.generate = AsyncMock()
        return model

    def test_planner_creation(self, mock_model):
        """Test basic planner creation."""
        planner = HarmonicPlanner(
            model=mock_model,
            candidates=5,
            variance=VarianceStrategy.PROMPTING,
            refinement_rounds=1,
        )

        assert planner.candidates == 5
        assert planner.variance == VarianceStrategy.PROMPTING
        assert planner.refinement_rounds == 1

    def test_variance_configs_prompting(self, mock_model):
        """Test prompting variance configuration generation."""
        planner = HarmonicPlanner(
            model=mock_model,
            candidates=5,
            variance=VarianceStrategy.PROMPTING,
        )

        configs = planner._get_variance_configs()
        assert len(configs) == 5
        assert configs[0]["prompt_style"] == "parallel_first"
        assert configs[1]["prompt_style"] == "minimal"
        assert configs[2]["prompt_style"] == "thorough"
        assert configs[3]["prompt_style"] == "balanced"

    def test_variance_configs_temperature(self, mock_model):
        """Test temperature variance configuration generation."""
        planner = HarmonicPlanner(
            model=mock_model,
            candidates=5,
            variance=VarianceStrategy.TEMPERATURE,
        )

        configs = planner._get_variance_configs()
        assert len(configs) == 5
        assert all("temperature" in c for c in configs)
        temps = [c["temperature"] for c in configs]
        assert temps == [0.2, 0.3, 0.4, 0.5, 0.6]

    def test_variance_configs_respects_count(self, mock_model):
        """Test that variance configs respect candidate count."""
        planner = HarmonicPlanner(
            model=mock_model,
            candidates=3,
            variance=VarianceStrategy.PROMPTING,
        )

        configs = planner._get_variance_configs()
        assert len(configs) == 3

    def test_score_plan_basic(self, mock_model):
        """Test basic plan scoring."""
        planner = HarmonicPlanner(model=mock_model)

        # Create a simple graph
        graph = ArtifactGraph()
        graph.add(ArtifactSpec(
            id="A",
            description="Leaf A",
            contract="Contract A",
            produces_file="a.py",
        ))
        graph.add(ArtifactSpec(
            id="B",
            description="Leaf B",
            contract="Contract B",
            produces_file="b.py",
        ))
        graph.add(ArtifactSpec(
            id="C",
            description="Depends on A and B",
            contract="Contract C",
            produces_file="c.py",
            requires=frozenset(["A", "B"]),
        ))

        metrics = planner._score_plan(graph)

        assert metrics.artifact_count == 3
        assert metrics.leaf_count == 2
        assert metrics.depth == 1
        assert metrics.estimated_waves == 2
        assert metrics.parallelism_factor == 2 / 3

    def test_score_plan_with_conflicts(self, mock_model):
        """Test plan scoring detects file conflicts."""
        planner = HarmonicPlanner(model=mock_model)

        # Create graph with file conflicts
        graph = ArtifactGraph()
        graph.add(ArtifactSpec(
            id="A",
            description="Writes to shared.py",
            contract="Contract A",
            produces_file="shared.py",
        ))
        graph.add(ArtifactSpec(
            id="B",
            description="Also writes to shared.py",
            contract="Contract B",
            produces_file="shared.py",
        ))

        metrics = planner._score_plan(graph)

        assert metrics.file_conflicts == 1  # One pair of conflicts

    def test_identify_improvements_deep_graph(self, mock_model):
        """Test improvement identification for deep graphs."""
        planner = HarmonicPlanner(model=mock_model)

        metrics = PlanMetrics(
            depth=5,
            width=2,
            leaf_count=1,
            artifact_count=5,
            parallelism_factor=0.2,
            balance_factor=0.4,
            file_conflicts=0,
            estimated_waves=5,
        )

        feedback = planner._identify_improvements(metrics)

        assert feedback is not None
        assert "depth" in feedback.lower() or "critical path" in feedback.lower()

    def test_identify_improvements_low_parallelism(self, mock_model):
        """Test improvement identification for low parallelism."""
        planner = HarmonicPlanner(model=mock_model)

        metrics = PlanMetrics(
            depth=2,
            width=2,
            leaf_count=1,
            artifact_count=10,
            parallelism_factor=0.1,
            balance_factor=1.0,
            file_conflicts=0,
            estimated_waves=2,
        )

        feedback = planner._identify_improvements(metrics)

        assert feedback is not None
        assert "leaf" in feedback.lower() or "parallel" in feedback.lower()

    def test_identify_improvements_no_issues(self, mock_model):
        """Test improvement identification returns None for good plans."""
        planner = HarmonicPlanner(model=mock_model)

        metrics = PlanMetrics(
            depth=2,
            width=3,
            leaf_count=3,
            artifact_count=5,
            parallelism_factor=0.6,
            balance_factor=1.5,
            file_conflicts=0,
            estimated_waves=2,
        )

        feedback = planner._identify_improvements(metrics)

        # Good metrics shouldn't trigger improvement suggestions
        # (depth=2, parallelism=0.6, balance=1.5 are all good)
        assert feedback is None

    def test_apply_variance_adds_prompt(self, mock_model):
        """Test that variance application adds to goal."""
        planner = HarmonicPlanner(
            model=mock_model,
            variance=VarianceStrategy.PROMPTING,
        )

        goal = "Build a REST API"
        config = {"prompt_style": "parallel_first"}

        varied = planner._apply_variance(goal, config)

        assert goal in varied
        assert "MAXIMUM PARALLELISM" in varied

    def test_apply_variance_with_constraint(self, mock_model):
        """Test variance application with constraints."""
        planner = HarmonicPlanner(
            model=mock_model,
            variance=VarianceStrategy.CONSTRAINTS,
        )

        goal = "Build a REST API"
        config = {"prompt_style": "default", "constraint": "max_depth=2"}

        varied = planner._apply_variance(goal, config)

        assert goal in varied
        assert "max_depth=2" in varied


# =============================================================================
# Integration Tests
# =============================================================================


class TestHarmonicPlannerIntegration:
    """Integration tests for HarmonicPlanner."""

    @pytest.fixture
    def mock_model_with_response(self):
        """Create a mock model that returns valid artifact JSON."""
        model = MagicMock()

        # Create a simple artifact response
        response = '''[
            {
                "id": "UserProtocol",
                "description": "Protocol for User entity",
                "contract": "Protocol with id, email, password_hash",
                "requires": [],
                "produces_file": "src/protocols/user.py",
                "domain_type": "protocol"
            },
            {
                "id": "UserModel",
                "description": "SQLAlchemy model for User",
                "contract": "Class implementing UserProtocol",
                "requires": ["UserProtocol"],
                "produces_file": "src/models/user.py",
                "domain_type": "model"
            }
        ]'''

        result = MagicMock()
        result.content = response

        model.generate = AsyncMock(return_value=result)
        return model

    @pytest.mark.asyncio
    async def test_plan_with_metrics_basic(self, mock_model_with_response):
        """Test plan_with_metrics returns graph and metrics."""
        planner = HarmonicPlanner(
            model=mock_model_with_response,
            candidates=2,  # Fewer for faster test
            refinement_rounds=0,
        )

        graph, metrics = await planner.plan_with_metrics(
            "Build a user system",
            context={"cwd": "/tmp"},
        )

        assert isinstance(graph, ArtifactGraph)
        assert isinstance(metrics, PlanMetrics)
        assert len(graph) > 0

    @pytest.mark.asyncio
    async def test_plan_returns_tasks(self, mock_model_with_response):
        """Test plan method returns task list."""
        planner = HarmonicPlanner(
            model=mock_model_with_response,
            candidates=2,
            refinement_rounds=0,
        )

        tasks = await planner.plan(
            ["Build a user system"],
            context={"cwd": "/tmp"},
        )

        assert isinstance(tasks, list)
        assert len(tasks) > 0
        assert all(hasattr(t, "id") and hasattr(t, "description") for t in tasks)

    @pytest.mark.asyncio
    async def test_discover_graph_compatibility(self, mock_model_with_response):
        """Test discover_graph compatibility method."""
        planner = HarmonicPlanner(
            model=mock_model_with_response,
            candidates=2,
            refinement_rounds=0,
        )

        graph = await planner.discover_graph(
            "Build a user system",
            context={"cwd": "/tmp"},
        )

        assert isinstance(graph, ArtifactGraph)
