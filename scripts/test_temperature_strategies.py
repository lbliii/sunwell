#!/usr/bin/env python3
"""Test different temperature strategies for Harmonic Synthesis.

Compares:
- uniform_med: All personas at 0.7 (current default)
- uniform_high: All personas at 0.9 (Self-Consistency paper)
- spread: 0.3, 0.7, 1.0 (conservative to creative)
- divergent: Adversarial personas with matched temps
"""

import asyncio
import json
from pathlib import Path

from sunwell.benchmark.naaru.conditions import run_harmonic
from sunwell.benchmark.types import BenchmarkTask, TaskCategory, TaskEvaluation
from sunwell.models.ollama import OllamaModel


async def main() -> None:
    """Run temperature strategy comparison."""
    model = OllamaModel(model="gemma3:1b")

    # Test task
    task = BenchmarkTask(
        id="temp-test-001",
        category=TaskCategory.CODE_GENERATION,
        subcategory="function",
        prompt="""Write a Python function that validates an email address.
Requirements:
- Check for @ symbol
- Check for valid domain
- Return True/False
- Handle edge cases""",
        lens="tech-writer.lens",
        evaluation=TaskEvaluation(),
    )

    strategies = ["uniform_med", "uniform_high", "spread", "divergent"]

    print("=" * 70)
    print("🔬 TEMPERATURE STRATEGY COMPARISON")
    print("=" * 70)
    print()

    results = {}

    for strategy in strategies:
        print(f"Running {strategy}...", end=" ", flush=True)

        output = await run_harmonic(model, task, temperature_strategy=strategy)

        results[strategy] = {
            "consensus": output.harmonic_metrics.consensus_strength,
            "diversity": output.harmonic_metrics.persona_diversity,
            "winning": output.harmonic_metrics.winning_persona,
            "temps": output.harmonic_metrics.persona_temperatures,
            "votes": output.harmonic_metrics.vote_distribution,
            "tokens": output.tokens_used,
            "time": output.time_seconds,
        }

        print(f"✓ (consensus={results[strategy]['consensus']:.0%})")

    print()
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)

    # Summary table
    print()
    print(f"{'Strategy':<15} {'Consensus':>10} {'Diversity':>10} {'Winner':<12} {'Tokens':>8}")
    print("-" * 60)

    for strategy, data in results.items():
        print(
            f"{strategy:<15} "
            f"{data['consensus']:>10.0%} "
            f"{data['diversity']:>10.2f} "
            f"{data['winning']:<12} "
            f"{data['tokens']:>8}"
        )

    print()
    print("Vote distributions:")
    for strategy, data in results.items():
        print(f"  {strategy}: {data['votes']}")

    print()
    print("Temperatures used:")
    for strategy, data in results.items():
        temps_str = ", ".join(f"{t:.1f}" for t in data['temps'])
        print(f"  {strategy}: [{temps_str}]")

    # Save results
    output_path = Path("benchmark/results/temperature_test.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print()
    print(f"📁 Results saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
