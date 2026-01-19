#!/usr/bin/env python3
"""Compare Thought Rotation vs Harmonic Synthesis.

Tests the hypothesis from : Rotation can achieve similar quality
to Harmonic at ~1/3 the token cost by using frame markers within a 
single generation instead of parallel generations + voting.
"""

import asyncio
from sunwell.benchmark.naaru.conditions import (
    run_baseline,
    run_harmonic,
    run_harmonic_divergent,
    run_rotation,
)
from sunwell.benchmark.types import BenchmarkTask, TaskCategory, TaskEvaluation
from sunwell.models.ollama import OllamaModel


# Test tasks spanning deterministic and non-deterministic
TEST_TASKS = [
    BenchmarkTask(
        id="det-001",
        category=TaskCategory.CODE_GENERATION,
        subcategory="function",
        prompt="Write a Python function to check if a string is a palindrome.",
        lens="tech-writer.lens",
        evaluation=TaskEvaluation(),
    ),
    BenchmarkTask(
        id="nondet-001",
        category=TaskCategory.ANALYSIS,
        subcategory="design",
        prompt="""Choose between microservices vs monolith for a 5-person startup
building a SaaS product. Justify your choice. There is no correct answer.""",
        lens="tech-writer.lens",
        evaluation=TaskEvaluation(),
    ),
    BenchmarkTask(
        id="nondet-002",
        category=TaskCategory.ANALYSIS,
        subcategory="creative",
        prompt="""Write a compelling product description for a new smart water bottle
that tracks hydration. Be creative - there are many valid approaches.""",
        lens="tech-writer.lens",
        evaluation=TaskEvaluation(),
    ),
]


async def main() -> None:
    """Compare Rotation vs Harmonic."""
    model = OllamaModel(model="gemma3:1b")

    print("=" * 70)
    print("🔄 ROTATION vs HARMONIC COMPARISON")
    print("=" * 70)
    print()
    print("Testing: Does Rotation achieve Harmonic quality at lower cost?")
    print()

    conditions = [
        ("BASELINE", lambda m, t: run_baseline(m, t)),
        ("HARMONIC", lambda m, t: run_harmonic(m, t, temperature_strategy="uniform_med")),
        ("HARMONIC_DIV", lambda m, t: run_harmonic_divergent(m, t)),
        ("ROTATION", lambda m, t: run_rotation(m, t, divergent=False)),
        ("ROTATION_DIV", lambda m, t: run_rotation(m, t, divergent=True)),
    ]

    all_results = []

    for task in TEST_TASKS:
        print(f"\n{'='*70}")
        print(f"Task: {task.id} ({task.subcategory})")
        print("=" * 70)

        task_results = {}

        for name, runner in conditions:
            print(f"  Running {name}...", end=" ", flush=True)

            output = await runner(model, task)

            task_results[name] = {
                "tokens": output.tokens_used,
                "time": output.time_seconds,
                "output_len": len(output.output),
            }

            # Add metrics if available
            if output.harmonic_metrics:
                task_results[name]["consensus"] = output.harmonic_metrics.consensus_strength
                task_results[name]["diversity"] = output.harmonic_metrics.persona_diversity
            if output.rotation_metrics:
                task_results[name]["frames"] = output.rotation_metrics.n_frames
                task_results[name]["coverage"] = output.rotation_metrics.frame_coverage

            print(f"✓ ({output.tokens_used} tok, {output.time_seconds:.1f}s)")

        all_results.append({"task": task.id, "results": task_results})

        # Show comparison for this task
        print()
        print(f"  {'Condition':<15} {'Tokens':>8} {'Time':>8} {'Extra':>20}")
        print(f"  {'-'*55}")

        for name, data in task_results.items():
            extra = ""
            if "consensus" in data:
                extra = f"consensus={data['consensus']:.0%}"
            elif "frames" in data:
                extra = f"frames={data['frames']}, cov={data['coverage']:.0%}"

            print(f"  {name:<15} {data['tokens']:>8} {data['time']:>7.1f}s {extra:>20}")

    # Summary
    print()
    print("=" * 70)
    print("SUMMARY: Token Efficiency")
    print("=" * 70)
    print()

    # Average tokens per condition
    condition_totals = {name: 0 for name, _ in conditions}
    for result in all_results:
        for name, data in result["results"].items():
            condition_totals[name] += data["tokens"]

    baseline_tokens = condition_totals["BASELINE"]

    print(f"{'Condition':<15} {'Avg Tokens':>12} {'vs Baseline':>12} {'Efficiency':>12}")
    print("-" * 55)

    for name, total in condition_totals.items():
        avg = total / len(all_results)
        ratio = total / baseline_tokens if baseline_tokens else 0
        efficiency = "1.0x (base)" if name == "BASELINE" else f"{ratio:.1f}x"

        print(f"{name:<15} {avg:>12.0f} {efficiency:>12}")

    print()
    print("Key comparisons:")
    print(f"  HARMONIC vs ROTATION: {condition_totals['HARMONIC']/condition_totals['ROTATION']:.1f}x more tokens")
    print(f"  HARMONIC_DIV vs ROTATION_DIV: {condition_totals['HARMONIC_DIV']/condition_totals['ROTATION_DIV']:.1f}x more tokens")


if __name__ == "__main__":
    asyncio.run(main())
