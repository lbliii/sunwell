"""Eye tuning experiments — Discover what makes the eye form.

This experiment framework helps us understand:
1. Which features predict eye formation
2. What thresholds are optimal
3. Which primitives contribute most to emergence

Usage:
    python -m sunwell.experiments.eye_tuning
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.models.protocol import ModelProtocol


# =============================================================================
# Task Bank — Diverse tasks for testing eye formation
# =============================================================================

TASK_BANK = {
    # Should form strong eyes (debatable, nuanced)
    "debatable": [
        "Should I use PUT or PATCH for partial REST updates?",
        "Is it better to use exceptions or return values for error handling?",
        "Should I use inheritance or composition for code reuse?",
        "Tabs or spaces for indentation?",
        "Should microservices communicate via REST or message queues?",
    ],

    # Should form eyes (reasoning required)
    "reasoning": [
        "Is 0.1 + 0.2 == 0.3 in Python? Explain why or why not.",
        "What happens if you mutate a list while iterating over it?",
        "Why might a dictionary be faster than a list for lookups?",
        "When would you use a generator instead of a list comprehension?",
        "What's the difference between `is` and `==` in Python?",
    ],

    # Might not form eyes (factual, clear answers)
    "factual": [
        "What is 2 + 2?",
        "What is the capital of France?",
        "How many bits in a byte?",
        "What does HTTP stand for?",
        "What year was Python first released?",
    ],

    # Tricky — might be blind spots
    "tricky": [
        "Is None a singleton in Python?",
        "Does Python have switch statements?",
        "Is [] == [] True or False in Python?",
        "What does `finally` do if there's a `return` in the try block?",
        "Can you have a tuple with one element?",
    ],
}


@dataclass
class EyeTuningResult:
    """Result from a single eye tuning experiment."""

    task: str
    task_category: str

    # Vortex execution
    intensity: str
    primitives: tuple[str, ...]
    model_calls: int

    # Eye observation (updated based on experiments)
    eye_formed: bool
    eye_strength: float
    eye_category: str
    emergence_delta: float
    is_blind_spot: bool

    # Features that might predict eye formation
    initial_agreement: float
    final_agreement: float
    convergence_velocity: float
    synthesis_completeness: float  # Best predictor!
    stability_score: float  # Unreliable but kept for data
    is_overconfident: bool  # 100% agreement = warning

    # Single model baseline
    single_quality: float
    vortex_quality: float

    # Condition sensing
    is_likely_factual: bool
    avg_response_length: float

    def to_dict(self) -> dict:
        """Export as dictionary."""
        return {
            "task": self.task,
            "task_category": self.task_category,
            "intensity": self.intensity,
            "primitives": list(self.primitives),
            "model_calls": self.model_calls,
            "eye_formed": self.eye_formed,
            "eye_strength": self.eye_strength,
            "eye_category": self.eye_category,
            "emergence_delta": self.emergence_delta,
            "is_blind_spot": self.is_blind_spot,
            "initial_agreement": self.initial_agreement,
            "final_agreement": self.final_agreement,
            "convergence_velocity": self.convergence_velocity,
            "synthesis_completeness": self.synthesis_completeness,
            "stability_score": self.stability_score,
            "is_overconfident": self.is_overconfident,
            "single_quality": self.single_quality,
            "vortex_quality": self.vortex_quality,
            "is_likely_factual": self.is_likely_factual,
            "avg_response_length": self.avg_response_length,
        }


@dataclass
class EyeTuningExperiment:
    """Run eye tuning experiments across task bank."""

    results: list[EyeTuningResult] = field(default_factory=list)

    async def run(
        self,
        model: ModelProtocol,
        categories: list[str] | None = None,
        tasks_per_category: int = 3,
        on_result: callable | None = None,
    ) -> None:
        """Run experiments across task bank.

        Args:
            model: Model to use
            categories: Which task categories (None = all)
            tasks_per_category: How many tasks per category
            on_result: Callback for each result
        """
        from sunwell.prism.vortex import adaptive_route, detect_eye

        categories = categories or list(TASK_BANK.keys())

        for category in categories:
            tasks = TASK_BANK.get(category, [])[:tasks_per_category]

            for task in tasks:
                try:
                    # Run vortex
                    vortex_result = await adaptive_route(task, model)

                    # Detect eye
                    eye = await detect_eye(task, vortex_result, model)

                    result = EyeTuningResult(
                        task=task,
                        task_category=category,
                        intensity=vortex_result.intensity_used.value,
                        primitives=vortex_result.primitives_used,
                        model_calls=vortex_result.model_calls,
                        eye_formed=eye.formed,
                        eye_strength=eye.strength,
                        eye_category=eye.category,
                        emergence_delta=eye.emergence_delta,
                        is_blind_spot=eye.is_blind_spot,
                        initial_agreement=eye.initial_agreement,
                        final_agreement=eye.final_agreement,
                        convergence_velocity=eye.convergence_velocity,
                        synthesis_completeness=eye.synthesis_completeness,
                        stability_score=eye.stability_score,
                        is_overconfident=eye.is_overconfident,
                        single_quality=eye.single_model_quality,
                        vortex_quality=eye.vortex_quality,
                        is_likely_factual=vortex_result.conditions.is_likely_factual,
                        avg_response_length=vortex_result.conditions.avg_response_length,
                    )

                    self.results.append(result)

                    if on_result:
                        on_result(result)

                except Exception as e:
                    print(f"Error on task '{task}': {e}")

    def analyze(self) -> dict:
        """Analyze results to find patterns."""
        if not self.results:
            return {"error": "No results"}

        # Group by eye formation
        formed = [r for r in self.results if r.eye_formed]
        not_formed = [r for r in self.results if not r.eye_formed]

        # Feature comparison
        def avg(items: list, attr: str) -> float:
            if not items:
                return 0.0
            return sum(getattr(r, attr) for r in items) / len(items)

        analysis = {
            "total_tasks": len(self.results),
            "eyes_formed": len(formed),
            "eye_formation_rate": len(formed) / len(self.results) if self.results else 0,

            # Feature comparison: formed vs not formed
            "feature_comparison": {
                "initial_agreement": {
                    "formed": avg(formed, "initial_agreement"),
                    "not_formed": avg(not_formed, "initial_agreement"),
                },
                "stability": {
                    "formed": avg(formed, "stability_score"),
                    "not_formed": avg(not_formed, "stability_score"),
                },
                "synthesis_completeness": {
                    "formed": avg(formed, "synthesis_completeness"),
                    "not_formed": avg(not_formed, "synthesis_completeness"),
                },
                "emergence_delta": {
                    "formed": avg(formed, "emergence_delta"),
                    "not_formed": avg(not_formed, "emergence_delta"),
                },
            },

            # By category
            "by_category": {},

            # Intensity distribution
            "intensity_distribution": {},
        }

        # By category
        for category in {r.task_category for r in self.results}:
            cat_results = [r for r in self.results if r.task_category == category]
            cat_formed = [r for r in cat_results if r.eye_formed]
            analysis["by_category"][category] = {
                "total": len(cat_results),
                "eyes_formed": len(cat_formed),
                "formation_rate": len(cat_formed) / len(cat_results) if cat_results else 0,
                "avg_emergence": avg(cat_results, "emergence_delta"),
            }

        # Intensity distribution
        for intensity in {r.intensity for r in self.results}:
            int_results = [r for r in self.results if r.intensity == intensity]
            int_formed = [r for r in int_results if r.eye_formed]
            analysis["intensity_distribution"][intensity] = {
                "total": len(int_results),
                "eyes_formed": len(int_formed),
                "formation_rate": len(int_formed) / len(int_results) if int_results else 0,
            }

        return analysis

    def suggest_tuning(self) -> list[str]:
        """Suggest tuning based on analysis."""
        analysis = self.analyze()
        suggestions = []

        # Check feature differences
        fc = analysis.get("feature_comparison", {})

        # Initial agreement
        ia = fc.get("initial_agreement", {})
        if ia.get("formed", 0) > ia.get("not_formed", 0):
            suggestions.append(
                f"✓ Higher initial agreement correlates with eye formation "
                f"(formed: {ia.get('formed', 0):.2f} vs not: {ia.get('not_formed', 0):.2f}). "
                f"Consider lowering agreement_threshold_skip."
            )
        else:
            suggestions.append(
                f"⚠ Lower initial agreement correlates with eye formation "
                f"(formed: {ia.get('formed', 0):.2f} vs not: {ia.get('not_formed', 0):.2f}). "
                f"Vortex helps when there's disagreement - this is expected."
            )

        # Stability
        stab = fc.get("stability", {})
        if stab.get("formed", 0) < 0.7:
            suggestions.append(
                f"⚠ Low stability in formed eyes ({stab.get('formed', 0):.2f}). "
                f"Consider adding more resonance iterations."
            )

        # Synthesis completeness
        synth = fc.get("synthesis_completeness", {})
        if synth.get("formed", 0) < 0.5:
            suggestions.append(
                f"⚠ Low synthesis completeness ({synth.get('formed', 0):.2f}). "
                f"Dialectic may not be capturing both sides. Review prompts."
            )

        # Category analysis
        bc = analysis.get("by_category", {})
        for cat, data in bc.items():
            if data.get("formation_rate", 0) < 0.3:
                suggestions.append(
                    f"⚠ Low eye formation in '{cat}' category ({data.get('formation_rate', 0):.0%}). "
                    f"May need different primitives for this task type."
                )

        # Overall rate
        if analysis.get("eye_formation_rate", 0) < 0.3:
            suggestions.append(
                f"❌ Overall eye formation rate is low ({analysis.get('eye_formation_rate', 0):.0%}). "
                f"Consider: (1) lowering quality thresholds, (2) adding more perspectives, "
                f"(3) reviewing the quality assessment prompts."
            )

        return suggestions

    def report(self) -> str:
        """Generate human-readable report."""
        analysis = self.analyze()
        suggestions = self.suggest_tuning()

        lines = [
            "=" * 70,
            "EYE TUNING EXPERIMENT REPORT",
            "=" * 70,
            "",
            f"Total tasks: {analysis.get('total_tasks', 0)}",
            f"Eyes formed: {analysis.get('eyes_formed', 0)}",
            f"Formation rate: {analysis.get('eye_formation_rate', 0):.0%}",
            "",
            "Feature Comparison (formed vs not formed):",
            "-" * 40,
        ]

        fc = analysis.get("feature_comparison", {})
        for feature, values in fc.items():
            formed = values.get("formed", 0)
            not_formed = values.get("not_formed", 0)
            diff = formed - not_formed
            indicator = "↑" if diff > 0.05 else "↓" if diff < -0.05 else "="
            lines.append(f"  {feature}: {formed:.2f} vs {not_formed:.2f} {indicator}")

        lines.extend([
            "",
            "By Category:",
            "-" * 40,
        ])

        for cat, data in analysis.get("by_category", {}).items():
            lines.append(
                f"  {cat}: {data.get('formation_rate', 0):.0%} "
                f"({data.get('eyes_formed', 0)}/{data.get('total', 0)})"
            )

        lines.extend([
            "",
            "By Intensity:",
            "-" * 40,
        ])

        for intensity, data in analysis.get("intensity_distribution", {}).items():
            emoji = {"none": "💤", "light": "🌤️", "moderate": "⛅", "full": "🌀"}.get(intensity, "")
            lines.append(
                f"  {emoji} {intensity}: {data.get('formation_rate', 0):.0%} "
                f"({data.get('eyes_formed', 0)}/{data.get('total', 0)})"
            )

        lines.extend([
            "",
            "Tuning Suggestions:",
            "-" * 40,
        ])

        for suggestion in suggestions:
            lines.append(f"  {suggestion}")

        lines.append("")

        return "\n".join(lines)

    def save(self, path: str | Path) -> None:
        """Save results to JSON."""
        path = Path(path)
        data = {
            "results": [r.to_dict() for r in self.results],
            "analysis": self.analyze(),
            "suggestions": self.suggest_tuning(),
        }
        path.write_text(json.dumps(data, indent=2))


# =============================================================================
# Ablation Study — What happens without each primitive?
# =============================================================================

async def ablation_study(
    task: str,
    model: ModelProtocol,
) -> dict:
    """Run ablation study to see which primitives matter.

    Runs the task with different primitive configurations
    to understand contribution of each.
    """
    from sunwell.prism.vortex import VortexIntensity, adaptive_route, detect_eye

    results = {}

    configs = [
        ("single", VortexIntensity.NONE),
        ("light", VortexIntensity.LIGHT),
        ("moderate", VortexIntensity.MODERATE),
        ("full", VortexIntensity.FULL),
    ]

    for name, intensity in configs:
        vortex = await adaptive_route(task, model, force_intensity=intensity)
        eye = await detect_eye(task, vortex, model)

        results[name] = {
            "quality": eye.vortex_quality,
            "emergence": eye.emergence_delta if name != "single" else 0,
            "eye_formed": eye.formed if name != "single" else False,
            "model_calls": vortex.model_calls,
        }

    # Calculate contribution of each layer
    single_q = results["single"]["quality"]

    return {
        "task": task,
        "ablation": results,
        "contributions": {
            "interference": results["light"]["quality"] - single_q,
            "dialectic": results["moderate"]["quality"] - results["light"]["quality"],
            "resonance": results["full"]["quality"] - results["moderate"]["quality"],
        },
        "most_valuable": max(
            ["interference", "dialectic", "resonance"],
            key=lambda p: results["full"]["quality"] - single_q if p == "resonance"
                else results["moderate"]["quality"] - single_q if p == "dialectic"
                else results["light"]["quality"] - single_q
        ),
    }


# =============================================================================
# Feature Importance — Which features predict eye formation?
# =============================================================================

def compute_feature_importance(results: list[EyeTuningResult]) -> dict[str, float]:
    """Compute feature importance for eye formation prediction.

    Uses simple correlation between features and eye formation.
    Higher absolute correlation = more important feature.
    """
    if not results:
        return {}

    # Features to analyze
    features = [
        "initial_agreement",
        "final_agreement",
        "convergence_velocity",
        "synthesis_completeness",
        "stability_score",
        "model_calls",
    ]

    # Target: eye formed (0 or 1)
    targets = [1.0 if r.eye_formed else 0.0 for r in results]
    target_mean = sum(targets) / len(targets)

    importance = {}

    for feature in features:
        values = [getattr(r, feature) for r in results]
        value_mean = sum(values) / len(values)

        # Pearson correlation
        numerator = sum(
            (v - value_mean) * (t - target_mean)
            for v, t in zip(values, targets, strict=False)
        )

        var_v = sum((v - value_mean) ** 2 for v in values)
        var_t = sum((t - target_mean) ** 2 for t in targets)

        denominator = (var_v * var_t) ** 0.5

        if denominator > 0:
            importance[feature] = numerator / denominator
        else:
            importance[feature] = 0.0

    return dict(sorted(importance.items(), key=lambda x: abs(x[1]), reverse=True))


# =============================================================================
# CLI Entry Point
# =============================================================================

async def main():
    """Run eye tuning experiments."""
    from sunwell.models.ollama import OllamaModel

    print("Loading model...")
    model = OllamaModel("qwen2.5-coder:1.5b")

    print("Running eye tuning experiments...")
    experiment = EyeTuningExperiment()

    def on_result(result: EyeTuningResult):
        emoji = "👁️" if result.eye_formed else "💤"
        print(f"{emoji} {result.task_category}: {result.task[:40]}... "
              f"emergence={result.emergence_delta:+.2f}")

    await experiment.run(
        model=model,
        tasks_per_category=2,  # Quick run
        on_result=on_result,
    )

    print()
    print(experiment.report())

    # Feature importance
    print("Feature Importance:")
    print("-" * 40)
    importance = compute_feature_importance(experiment.results)
    for feature, corr in importance.items():
        indicator = "+" if corr > 0 else "-" if corr < 0 else " "
        print(f"  {feature}: {indicator}{abs(corr):.2f}")

    # Save results
    experiment.save(Path("benchmark/results/eye_tuning.json"))
    print("\nResults saved to benchmark/results/eye_tuning.json")


if __name__ == "__main__":
    asyncio.run(main())
