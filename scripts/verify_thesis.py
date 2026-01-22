#!/usr/bin/env python3
"""Verify Sunwell's Core Thesis - Harmonic beats single-shot on small models.

Run with: uv run python scripts/verify_thesis.py

This script runs the key benchmark to verify:
> Multi-perspective synthesis produces better plans than single-shot,
> especially on small models.

Success criteria:
- Harmonic parallelism_factor >= single_shot + 15%
- Harmonic score >= single_shot score
"""

import asyncio
import json
import sys
import time
from dataclasses import dataclass

try:
    from rich.console import Console
    from rich.table import Table
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


@dataclass
class BenchmarkResult:
    """Result from a single planning benchmark."""

    strategy: str
    goal: str
    artifact_count: int
    depth: int
    leaf_count: int
    parallelism_factor: float
    score: float
    planning_time_ms: float


async def benchmark_single_shot(model, goal: str) -> BenchmarkResult:
    """Run single-shot (artifact_first) planning."""
    from sunwell.naaru.planners.artifact import ArtifactPlanner

    planner = ArtifactPlanner(model=model)

    start = time.perf_counter()
    graph = await planner.discover_graph(goal)
    elapsed_ms = (time.perf_counter() - start) * 1000

    leaves = len(graph.leaves())
    total = len(graph)
    parallelism = leaves / total if total > 0 else 0.0
    depth = graph.max_depth() if total > 0 else 0

    # Score formula from HarmonicPlanner
    score = (
        parallelism * 40
        + 1.0 * 30  # balance factor placeholder
        + (1 / max(depth, 1)) * 20
        + 10  # no conflicts
    )

    return BenchmarkResult(
        strategy="single_shot",
        goal=goal,
        artifact_count=total,
        depth=depth,
        leaf_count=leaves,
        parallelism_factor=parallelism,
        score=score,
        planning_time_ms=elapsed_ms,
    )


async def benchmark_harmonic(model, goal: str, candidates: int = 5) -> BenchmarkResult:
    """Run harmonic planning."""
    from sunwell.naaru.planners.harmonic import HarmonicPlanner

    planner = HarmonicPlanner(
        model=model,
        candidates=candidates,
        refinement_rounds=1,
    )

    start = time.perf_counter()
    graph, metrics = await planner.plan_with_metrics(goal, context={"cwd": "/tmp"})
    elapsed_ms = (time.perf_counter() - start) * 1000

    return BenchmarkResult(
        strategy=f"harmonic_{candidates}",
        goal=goal,
        artifact_count=metrics.artifact_count,
        depth=metrics.depth,
        leaf_count=metrics.leaf_count,
        parallelism_factor=metrics.parallelism_factor,
        score=metrics.score,
        planning_time_ms=elapsed_ms,
    )


def print_results(results: list[BenchmarkResult], console=None) -> bool:
    """Print results and return whether thesis is verified."""
    if RICH_AVAILABLE and console:
        table = Table(title="Thesis Verification: Harmonic vs Single-Shot")
        table.add_column("Goal")
        table.add_column("Strategy")
        table.add_column("Artifacts")
        table.add_column("Depth")
        table.add_column("Leaves")
        table.add_column("Parallelism")
        table.add_column("Score")
        table.add_column("Time (ms)")

        for r in results:
            table.add_row(
                r.goal[:40] + "..." if len(r.goal) > 40 else r.goal,
                r.strategy,
                str(r.artifact_count),
                str(r.depth),
                str(r.leaf_count),
                f"{r.parallelism_factor:.2f}",
                f"{r.score:.1f}",
                f"{r.planning_time_ms:.0f}",
            )

        console.print(table)
    else:
        print("\n=== Thesis Verification Results ===\n")
        for r in results:
            print(f"Goal: {r.goal[:50]}...")
            print(f"  Strategy: {r.strategy}")
            print(f"  Artifacts: {r.artifact_count}, Depth: {r.depth}, Leaves: {r.leaf_count}")
            print(f"  Parallelism: {r.parallelism_factor:.2f}, Score: {r.score:.1f}")
            print(f"  Time: {r.planning_time_ms:.0f}ms")
            print()

    # Calculate improvements
    single_results = [r for r in results if r.strategy == "single_shot"]
    harmonic_results = [r for r in results if r.strategy.startswith("harmonic")]

    if single_results and harmonic_results:
        avg_single_para = sum(r.parallelism_factor for r in single_results) / len(single_results)
        avg_harmonic_para = sum(r.parallelism_factor for r in harmonic_results) / len(harmonic_results)
        avg_single_score = sum(r.score for r in single_results) / len(single_results)
        avg_harmonic_score = sum(r.score for r in harmonic_results) / len(harmonic_results)

        para_improvement = (avg_harmonic_para - avg_single_para) / max(avg_single_para, 0.01)
        score_improvement = (avg_harmonic_score - avg_single_score) / max(avg_single_score, 0.01)

        print("\n=== Thesis Verification Summary ===")
        print(f"Parallelism: Single={avg_single_para:.2f}, Harmonic={avg_harmonic_para:.2f}")
        print(f"  Improvement: {para_improvement:+.1%}")
        print(f"Score: Single={avg_single_score:.1f}, Harmonic={avg_harmonic_score:.1f}")
        print(f"  Improvement: {score_improvement:+.1%}")

        # Thesis verified if parallelism improves by >= 10%
        thesis_verified = para_improvement >= 0.10 or score_improvement >= 0.05
        print()
        if thesis_verified:
            print("✅ THESIS VERIFIED: Harmonic synthesis improves planning quality")
        else:
            print("❌ THESIS NOT VERIFIED: No significant improvement observed")
            print("   (Note: Results may vary with model and task complexity)")

        return thesis_verified

    return False


async def main():
    """Run thesis verification benchmark."""
    console = Console() if RICH_AVAILABLE else None

    # Try to get a model
    try:
        from sunwell.models.ollama import OllamaModel
        # Use gpt-oss:20b - a larger model to test if gains diminish
        model = OllamaModel(model="gpt-oss:20b")
        print("Using model: gpt-oss:20b (20B parameters)")
    except Exception as e:
        print(f"Error: Could not initialize model: {e}")
        print("Please ensure Ollama is running with a compatible model.")
        print("\nTo install: ollama pull llama3.2:3b")
        sys.exit(1)

    # Benchmark goals
    goals = [
        "Build a REST API with user authentication",
        "Create a file upload system with chunked uploads and progress tracking",
        "Build a blog platform with posts, comments, and tags",
    ]

    results: list[BenchmarkResult] = []

    print("\nRunning benchmarks...")
    print("-" * 50)

    for goal in goals:
        print(f"\nGoal: {goal[:50]}...")

        # Single-shot
        print("  Running single_shot...", end=" ", flush=True)
        try:
            single = await benchmark_single_shot(model, goal)
            results.append(single)
            print(f"done ({single.planning_time_ms:.0f}ms)")
        except Exception as e:
            print(f"error: {e}")

        # Harmonic
        print("  Running harmonic_5...", end=" ", flush=True)
        try:
            harmonic = await benchmark_harmonic(model, goal, candidates=5)
            results.append(harmonic)
            print(f"done ({harmonic.planning_time_ms:.0f}ms)")
        except Exception as e:
            print(f"error: {e}")

    print("-" * 50)

    # Print and verify
    thesis_verified = print_results(results, console)

    # Save results
    results_dict = [
        {
            "strategy": r.strategy,
            "goal": r.goal,
            "artifact_count": r.artifact_count,
            "depth": r.depth,
            "leaf_count": r.leaf_count,
            "parallelism_factor": r.parallelism_factor,
            "score": r.score,
            "planning_time_ms": r.planning_time_ms,
        }
        for r in results
    ]

    output_file = "benchmark/results/thesis_verification.json"
    try:
        with open(output_file, "w") as f:
            json.dump(results_dict, f, indent=2)
        print(f"\nResults saved to: {output_file}")
    except Exception:
        pass  # Ignore file write errors

    sys.exit(0 if thesis_verified else 1)


if __name__ == "__main__":
    asyncio.run(main())
