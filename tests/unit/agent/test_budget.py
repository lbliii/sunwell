"""Tests for AdaptiveBudget and cost estimation (RFC-042).

Tests token budget management and technique routing.
"""

import pytest

from sunwell.agent.budget import (
    DEFAULT_TECHNIQUE_MULTIPLIERS,
    AdaptiveBudget,
    CostEstimate,
    estimate_plan_cost,
    estimate_task_cost,
)


class TestAdaptiveBudget:
    """Tests for AdaptiveBudget class."""

    def test_default_values(self) -> None:
        """Budget has sensible defaults."""
        budget = AdaptiveBudget()

        assert budget.total_budget == 50_000
        assert budget.spent == 0
        assert budget.reserve_ratio == 0.2
        assert budget.remaining == 50_000

    def test_remaining_calculation(self) -> None:
        """Remaining budget decreases with spending."""
        budget = AdaptiveBudget(total_budget=10_000)

        assert budget.remaining == 10_000

        budget.record_spend(3_000)
        assert budget.remaining == 7_000

        budget.record_spend(7_000)
        assert budget.remaining == 0

    def test_remaining_never_negative(self) -> None:
        """Remaining budget doesn't go below zero."""
        budget = AdaptiveBudget(total_budget=1_000)
        budget.record_spend(2_000)  # Overspend

        assert budget.remaining == 0

    def test_available_for_tasks_excludes_reserve(self) -> None:
        """Available budget excludes reserve."""
        budget = AdaptiveBudget(total_budget=10_000, reserve_ratio=0.2)

        # 20% reserve = 2000, so available = 8000
        assert budget.available_for_tasks == 8_000

        budget.record_spend(5_000)
        # Remaining = 5000, reserve = 2000, available = 3000
        assert budget.available_for_tasks == 3_000

    def test_is_low_threshold(self) -> None:
        """is_low triggers at 30% remaining."""
        budget = AdaptiveBudget(total_budget=10_000)

        assert not budget.is_low

        budget.record_spend(7_000)  # 30% remaining
        assert not budget.is_low

        budget.record_spend(1)  # Just under 30%
        assert budget.is_low

    def test_is_critical_threshold(self) -> None:
        """is_critical triggers at 10% remaining."""
        budget = AdaptiveBudget(total_budget=10_000)

        assert not budget.is_critical

        budget.record_spend(9_000)  # 10% remaining
        assert not budget.is_critical

        budget.record_spend(1)  # Just under 10%
        assert budget.is_critical

    def test_can_afford_simple(self) -> None:
        """can_afford checks against available budget."""
        budget = AdaptiveBudget(total_budget=10_000, reserve_ratio=0.2)
        # Available = 8000

        assert budget.can_afford("single_shot", 1_000)  # 1000 * 1.0 = 1000
        assert budget.can_afford("interference", 2_000)  # 2000 * 3.0 = 6000
        assert not budget.can_afford("vortex", 1_000)  # 1000 * 15.0 = 15000

    def test_route_for_budget_ideal_affordable(self) -> None:
        """route_for_budget returns ideal technique if affordable."""
        budget = AdaptiveBudget(total_budget=100_000)

        assert budget.route_for_budget("vortex", 1_000) == "vortex"
        assert budget.route_for_budget("harmonic_5", 1_000) == "harmonic_5"

    def test_route_for_budget_downgrades(self) -> None:
        """route_for_budget downgrades when budget is tight."""
        budget = AdaptiveBudget(total_budget=5_000, reserve_ratio=0.0)

        # Can't afford vortex (15x), should downgrade to interference (3x)
        assert budget.route_for_budget("vortex", 1_000) == "interference"

        # Can't afford harmonic_5 (6x), should downgrade to harmonic_3 (3.5x)
        assert budget.route_for_budget("harmonic_5", 1_000) == "harmonic_3"

    def test_route_for_budget_single_shot_fallback(self) -> None:
        """route_for_budget falls back to single_shot when nothing else fits."""
        budget = AdaptiveBudget(total_budget=1_000, reserve_ratio=0.0)

        # Can only afford single_shot
        assert budget.route_for_budget("vortex", 500) == "single_shot"

    def test_estimate_cost(self) -> None:
        """estimate_cost applies correct multipliers."""
        budget = AdaptiveBudget()

        assert budget.estimate_cost("single_shot", 1_000) == 1_000
        assert budget.estimate_cost("interference", 1_000) == 3_000
        assert budget.estimate_cost("vortex", 1_000) == 15_000

    def test_custom_multipliers(self) -> None:
        """Budget accepts custom multipliers."""
        budget = AdaptiveBudget(vortex=20.0, interference=5.0)

        assert budget.estimate_cost("vortex", 1_000) == 20_000
        assert budget.estimate_cost("interference", 1_000) == 5_000

    def test_unknown_technique_defaults_to_1(self) -> None:
        """Unknown techniques default to 1.0 multiplier."""
        budget = AdaptiveBudget()

        assert budget.estimate_cost("unknown_technique", 1_000) == 1_000

    def test_to_dict(self) -> None:
        """to_dict serializes budget state."""
        budget = AdaptiveBudget(total_budget=10_000)
        budget.record_spend(3_000)

        result = budget.to_dict()

        assert result["total_budget"] == 10_000
        assert result["spent"] == 3_000
        assert result["remaining"] == 7_000
        assert "is_low" in result
        assert "is_critical" in result


class TestCostEstimate:
    """Tests for CostEstimate dataclass."""

    def test_cost_estimate_creation(self) -> None:
        """CostEstimate stores all fields."""
        estimate = CostEstimate(
            tokens=1_000,
            technique="vortex",
            time_s=10.0,
            confidence=0.8,
        )

        assert estimate.tokens == 1_000
        assert estimate.technique == "vortex"
        assert estimate.time_s == 10.0
        assert estimate.confidence == 0.8

    def test_cost_estimate_default_confidence(self) -> None:
        """CostEstimate has default confidence."""
        estimate = CostEstimate(tokens=500, technique="single_shot", time_s=5.0)

        assert estimate.confidence == 0.7


class TestEstimateTaskCost:
    """Tests for estimate_task_cost function."""

    def test_simple_task_estimate(self) -> None:
        """Simple tasks get base estimate."""
        estimate = estimate_task_cost("Fix the typo")

        # 3 words * 2 + 500 base = 506 tokens
        assert estimate.tokens > 0
        assert estimate.technique == "single_shot"
        assert estimate.time_s > 0

    def test_technique_multiplier_applied(self) -> None:
        """Technique multiplier affects estimate."""
        single = estimate_task_cost("Fix the typo", technique="single_shot")
        vortex = estimate_task_cost("Fix the typo", technique="vortex")

        assert vortex.tokens > single.tokens
        assert vortex.tokens == single.tokens * 15  # vortex = 15x


class TestEstimatePlanCost:
    """Tests for estimate_plan_cost function."""

    def test_plan_cost_scales_with_tasks(self) -> None:
        """More tasks = higher cost."""
        small = estimate_plan_cost(tasks=3)
        large = estimate_plan_cost(tasks=10)

        assert large.tokens > small.tokens

    def test_complexity_affects_cost(self) -> None:
        """Higher complexity = higher cost."""
        low = estimate_plan_cost(tasks=5, avg_complexity="low")
        high = estimate_plan_cost(tasks=5, avg_complexity="high")

        assert high.tokens > low.tokens

    def test_technique_multiplier_in_plan(self) -> None:
        """Plan technique affects total cost."""
        single = estimate_plan_cost(tasks=5, technique="single_shot")
        vortex = estimate_plan_cost(tasks=5, technique="vortex")

        assert vortex.tokens > single.tokens

    def test_plan_has_lower_confidence(self) -> None:
        """Plans have lower confidence than individual tasks."""
        estimate = estimate_plan_cost(tasks=5)

        assert estimate.confidence == 0.6


class TestDefaultMultipliers:
    """Tests for DEFAULT_TECHNIQUE_MULTIPLIERS."""

    def test_all_techniques_have_multipliers(self) -> None:
        """All known techniques have defined multipliers."""
        expected = {
            "single_shot",
            "interference",
            "harmonic_3",
            "harmonic_5",
            "vortex",
            "compound_eye",
            "lateral_only",
            "resonance",
        }

        assert set(DEFAULT_TECHNIQUE_MULTIPLIERS.keys()) == expected

    def test_multipliers_are_ordered(self) -> None:
        """Multipliers increase with technique power."""
        assert DEFAULT_TECHNIQUE_MULTIPLIERS["single_shot"] < DEFAULT_TECHNIQUE_MULTIPLIERS["interference"]
        assert DEFAULT_TECHNIQUE_MULTIPLIERS["interference"] < DEFAULT_TECHNIQUE_MULTIPLIERS["vortex"]
        assert DEFAULT_TECHNIQUE_MULTIPLIERS["harmonic_3"] < DEFAULT_TECHNIQUE_MULTIPLIERS["harmonic_5"]
