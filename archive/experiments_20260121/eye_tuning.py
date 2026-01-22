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

from sunwell.vortex import Vortex, VortexConfig, VortexResult


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


# =============================================================================
# Eye Detection — Measure emergence from VortexResult
# =============================================================================


@dataclass(frozen=True, slots=True)
class EyeObservation:
    """Observed eye metrics from a vortex run."""

    # Core emergence signal
    emergence_delta: float
    """Quality improvement from vortex (positive = emergence)."""

    # Agreement metrics
    initial_agreement: float
    """Agreement from interference (if run)."""

    final_agreement: float
    """Final winner confidence."""

    # Complexity indicators
    used_interference: bool
    used_dialectic: bool

    # Synthesis quality proxy
    synthesis_length: int
    """Length of synthesis (proxy for completeness)."""

    distinct_cultures: int
    """Cultural diversity from islands."""

    # Derived
    @property
    def eye_formed(self) -> bool:
        """Did an eye form? (positive emergence)."""
        return self.emergence_delta > 0.05

    @property
    def eye_strength(self) -> float:
        """Strength of eye formation."""
        return max(0.0, min(1.0, self.emergence_delta))

    @property
    def eye_category(self) -> str:
        """Categorize the eye."""
        if self.emergence_delta > 0.2:
            return "strong"
        elif self.emergence_delta > 0.05:
            return "formed"
        elif self.emergence_delta > -0.05:
            return "neutral"
        else:
            return "degraded"


async def detect_eye(
    task: str,
    vortex_result: VortexResult,
    model: "ModelProtocol",
) -> EyeObservation:
    """Detect eye formation from vortex result.

    Compares vortex output quality against single-model baseline.
    """
    from sunwell.models.protocol import GenerateOptions

    # Get single-model baseline
    baseline = await model.generate(task, options=GenerateOptions(max_tokens=500))
    baseline_len = len(baseline.text)

    # Vortex synthesis length
    vortex_len = len(vortex_result.synthesis)

    # Simple emergence proxy: relative length improvement
    # (Longer, more complete answers = better for complex tasks)
    if baseline_len > 0:
        length_ratio = vortex_len / baseline_len
        emergence_delta = (length_ratio - 1.0) * 0.5  # Scale to reasonable range
    else:
        emergence_delta = 0.5 if vortex_len > 100 else 0.0

    # Agreement from interference
    if vortex_result.interference_result:
        initial_agreement = vortex_result.interference_result.agreement
    else:
        initial_agreement = 1.0  # No interference = assumed agreement

    return EyeObservation(
        emergence_delta=emergence_delta,
        initial_agreement=initial_agreement,
        final_agreement=vortex_result.winner.confidence,
        used_interference=vortex_result.interference_result is not None,
        used_dialectic=vortex_result.dialectic_result is not None,
        synthesis_length=vortex_len,
        distinct_cultures=vortex_result.distinct_cultures,
    )


# =============================================================================
# Result Types
# =============================================================================


@dataclass
class EyeTuningResult:
    """Result from a single eye tuning experiment."""

    task: str
    task_category: str

    # Vortex execution
    total_signals: int
    distinct_cultures: int
    total_time_s: float

    # Eye observation
    eye_formed: bool
    eye_strength: float
    eye_category: str
    emergence_delta: float

    # Features that might predict eye formation
    initial_agreement: float
    final_agreement: float
    synthesis_length: int
    used_interference: bool
    used_dialectic: bool

    def to_dict(self) -> dict:
        """Export as dictionary."""
        return {
            "task": self.task,
            "task_category": self.task_category,
            "total_signals": self.total_signals,
            "distinct_cultures": self.distinct_cultures,
            "total_time_s": self.total_time_s,
            "eye_formed": self.eye_formed,
            "eye_strength": self.eye_strength,
            "eye_category": self.eye_category,
            "emergence_delta": self.emergence_delta,
            "initial_agreement": self.initial_agreement,
            "final_agreement": self.final_agreement,
            "synthesis_length": self.synthesis_length,
            "used_interference": self.used_interference,
            "used_dialectic": self.used_dialectic,
        }


@dataclass
class EyeTuningExperiment:
    """Run eye tuning experiments across task bank."""

    results: list[EyeTuningResult] = field(default_factory=list)

    async def run(
        self,
        model: "ModelProtocol",
        categories: list[str] | None = None,
        tasks_per_category: int = 3,
        config: VortexConfig | None = None,
        on_result: callable | None = None,
    ) -> None:
        """Run experiments across task bank.

        Args:
            model: Model to use
            categories: Which task categories (None = all)
            tasks_per_category: How many tasks per category
            config: Vortex configuration
            on_result: Callback for each result
        """
        vortex = Vortex(model, config)
        categories = categories or list(TASK_BANK.keys())

        for category in categories:
            tasks = TASK_BANK.get(category, [])[:tasks_per_category]

            for task in tasks:
                try:
                    # Run vortex
                    vortex_result = await vortex.solve(task)

                    # Detect eye
                    eye = await detect_eye(task, vortex_result, model)

                    result = EyeTuningResult(
                        task=task,
                        task_category=category,
                        total_signals=vortex_result.total_signals,
                        distinct_cultures=vortex_result.distinct_cultures,
                        total_time_s=vortex_result.total_time_s,
                        eye_formed=eye.eye_formed,
                        eye_strength=eye.eye_strength,
                        eye_category=eye.eye_category,
                        emergence_delta=eye.emergence_delta,
                        initial_agreement=eye.initial_agreement,
                        final_agreement=eye.final_agreement,
                        synthesis_length=eye.synthesis_length,
                        used_interference=eye.used_interference,
                        used_dialectic=eye.used_dialectic,
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
                "synthesis_length": {
                    "formed": avg(formed, "synthesis_length"),
                    "not_formed": avg(not_formed, "synthesis_length"),
                },
                "emergence_delta": {
                    "formed": avg(formed, "emergence_delta"),
                    "not_formed": avg(not_formed, "emergence_delta"),
                },
                "distinct_cultures": {
                    "formed": avg(formed, "distinct_cultures"),
                    "not_formed": avg(not_formed, "distinct_cultures"),
                },
            },
            # By category
            "by_category": {},
        }

        # By category
        for category in set(r.task_category for r in self.results):
            cat_results = [r for r in self.results if r.task_category == category]
            cat_formed = [r for r in cat_results if r.eye_formed]
            analysis["by_category"][category] = {
                "total": len(cat_results),
                "eyes_formed": len(cat_formed),
                "formation_rate": len(cat_formed) / len(cat_results) if cat_results else 0,
                "avg_emergence": avg(cat_results, "emergence_delta"),
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
        if ia.get("formed", 0) < ia.get("not_formed", 0):
            suggestions.append(
                f"✓ Lower initial agreement correlates with eye formation "
                f"(formed: {ia.get('formed', 0):.2f} vs not: {ia.get('not_formed', 0):.2f}). "
                f"Vortex helps when there's disagreement - this is expected."
            )

        # Synthesis length
        sl = fc.get("synthesis_length", {})
        if sl.get("formed", 0) > sl.get("not_formed", 0):
            suggestions.append(
                f"✓ Longer synthesis correlates with eye formation "
                f"(formed: {sl.get('formed', 0):.0f} vs not: {sl.get('not_formed', 0):.0f}). "
                f"More complete answers emerge from vortex."
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
                f"Consider: (1) more island diversity, (2) lower dialectic threshold, "
                f"(3) more discovery iterations."
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
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "results": [r.to_dict() for r in self.results],
            "analysis": self.analyze(),
            "suggestions": self.suggest_tuning(),
        }
        path.write_text(json.dumps(data, indent=2))


# =============================================================================
# Ablation Study — What happens with different configs?
# =============================================================================


async def ablation_study(
    task: str,
    model: "ModelProtocol",
) -> dict:
    """Run ablation study to see which config settings matter.

    Runs the task with different vortex configurations
    to understand contribution of each setting.
    """
    from sunwell.vortex import FAST_CONFIG, QUALITY_CONFIG

    results = {}

    configs = [
        ("fast", FAST_CONFIG),
        ("default", VortexConfig()),
        ("quality", QUALITY_CONFIG),
    ]

    for name, config in configs:
        vortex = Vortex(model, config)
        vortex_result = await vortex.solve(task)
        eye = await detect_eye(task, vortex_result, model)

        results[name] = {
            "synthesis_length": len(vortex_result.synthesis),
            "emergence": eye.emergence_delta,
            "eye_formed": eye.eye_formed,
            "total_signals": vortex_result.total_signals,
            "total_time_s": vortex_result.total_time_s,
        }

    return {
        "task": task,
        "ablation": results,
        "best_config": max(results.keys(), key=lambda k: results[k]["emergence"]),
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
        "synthesis_length",
        "distinct_cultures",
        "total_signals",
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
            (v - value_mean) * (t - target_mean) for v, t in zip(values, targets, strict=True)
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
        print(
            f"{emoji} {result.task_category}: {result.task[:40]}... "
            f"emergence={result.emergence_delta:+.2f}"
        )

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
