#!/usr/bin/env python3
"""Test temperature strategies on non-deterministic tasks.

These tasks have no "correct" answer - we expect personas to genuinely disagree.
"""

import asyncio
from sunwell.benchmark.naaru.conditions import run_harmonic
from sunwell.benchmark.types import BenchmarkTask, TaskCategory, TaskEvaluation
from sunwell.models.ollama import OllamaModel


NONDETERMINISTIC_TASKS = [
    BenchmarkTask(
        id="creative-001",
        category=TaskCategory.ANALYSIS,
        subcategory="creative",
        prompt="""Write a 3-sentence product tagline for a meditation app that targets
busy executives. There are multiple valid approaches - be creative.

Constraints:
- Exactly 3 sentences
- Must mention "time" or "busy" 
- Can be serious OR playful - your choice""",
        lens="tech-writer.lens",
        evaluation=TaskEvaluation(),
    ),
    BenchmarkTask(
        id="design-001",
        category=TaskCategory.ANALYSIS,
        subcategory="design",
        prompt="""A startup needs to choose between two database architectures:

Option A: PostgreSQL with read replicas
- Proven, reliable, strong consistency
- Team knows it well

Option B: CockroachDB 
- Built-in horizontal scaling
- Learning curve for team

The startup has 10 engineers and expects 10x growth.
Make a recommendation. There is no "correct" answer.""",
        lens="tech-writer.lens",
        evaluation=TaskEvaluation(),
    ),
    BenchmarkTask(
        id="naming-001",
        category=TaskCategory.ANALYSIS,
        subcategory="naming",
        prompt="""Name a Python library that validates API responses and generates mock data.

Propose 3 names:
1. A serious/professional name
2. A clever/punny name  
3. A short/memorable name""",
        lens="tech-writer.lens",
        evaluation=TaskEvaluation(),
    ),
]


async def main() -> None:
    """Run non-deterministic task tests."""
    model = OllamaModel(model="gemma3:1b")

    strategies = ["uniform_med", "spread", "divergent"]

    print("=" * 70)
    print("🎲 NON-DETERMINISTIC TASK TESTS")
    print("=" * 70)
    print()
    print("These tasks have NO correct answer - we expect persona disagreement.")
    print()

    results = []

    for task in NONDETERMINISTIC_TASKS:
        print(f"\n{'='*70}")
        print(f"Task: {task.id}")
        print("=" * 70)

        for strategy in strategies:
            print(f"\n  Strategy: {strategy}")

            output = await run_harmonic(model, task, temperature_strategy=strategy)

            consensus = output.harmonic_metrics.consensus_strength
            winner = output.harmonic_metrics.winning_persona
            votes = output.harmonic_metrics.vote_distribution
            diversity = output.harmonic_metrics.persona_diversity

            disagreement = "✅ DISAGREEMENT" if consensus < 1.0 else "unanimous"

            print(f"    Consensus: {consensus:.0%} {disagreement}")
            print(f"    Winner: {winner}")
            print(f"    Votes: {votes}")
            print(f"    Diversity: {diversity:.2f}")

            results.append({
                "task": task.id,
                "strategy": strategy,
                "consensus": consensus,
                "winner": winner,
                "votes": votes,
                "diversity": diversity,
            })

    # Summary
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)

    disagreements = [r for r in results if r["consensus"] < 1.0]
    print(f"\nDisagreements found: {len(disagreements)} / {len(results)}")

    if disagreements:
        print("\nTasks with disagreement:")
        for r in disagreements:
            print(f"  - {r['task']} ({r['strategy']}): {r['consensus']:.0%} consensus")
    else:
        print("\n⚠️  No disagreements found - voting still converges.")
        print("   This suggests the VOTING mechanism itself causes convergence,")
        print("   not the output generation.")
        print()
        print("   Consider: Thought Rotation (RFC-028) instead of voting?")


if __name__ == "__main__":
    asyncio.run(main())
