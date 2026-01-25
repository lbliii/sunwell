#!/usr/bin/env python3
"""Benchmark Harmonic Planning Candidates.

Analyzes variance strategies and prompt styles to understand:
1. Which prompt styles produce meaningfully different plans
2. V1 vs V2 scoring behavior across candidates
3. Candidate diversity (are we getting unique perspectives?)
4. Per-prompt performance characteristics

Run:
    python scripts/benchmark_harmonic_candidates.py
    python scripts/benchmark_harmonic_candidates.py --model gemma3:1b --runs 3
"""

import asyncio
import json
import logging
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Benchmark goals covering different task complexities
BENCHMARK_GOALS = [
    {
        "id": "rest-api",
        "name": "REST API",
        "goal": "Build a REST API with user authentication and a SQLite database",
        "complexity": "medium",
    },
    {
        "id": "cli-tool",
        "name": "CLI Tool",
        "goal": "Create a CLI tool with subcommands, config file support, and help system",
        "complexity": "medium",
    },
    {
        "id": "file-upload",
        "name": "File Upload",
        "goal": "Create a file upload system with chunked uploads, progress tracking, and virus scanning",
        "complexity": "high",
    },
    {
        "id": "blog-platform",
        "name": "Blog Platform",
        "goal": "Build a blog platform with posts, comments, tags, and full-text search",
        "complexity": "high",
    },
    {
        "id": "simple-function",
        "name": "Simple Function",
        "goal": "Create a Python function to validate email addresses with comprehensive tests",
        "complexity": "low",
    },
    {
        "id": "webhook-handler",
        "name": "Webhook Handler",
        "goal": "Build a webhook handler with signature verification, retry logic, and dead letter queue",
        "complexity": "medium",
    },
]


@dataclass
class CandidateMetrics:
    """Metrics for a single candidate."""

    prompt_style: str
    temperature: float | None
    constraint: str | None

    # Base metrics
    depth: int
    width: int
    leaf_count: int
    artifact_count: int
    parallelism_factor: float
    balance_factor: float
    file_conflicts: int
    estimated_waves: int

    # V1/V2 scores
    score_v1: float
    score_v2: float | None

    # V2-specific (if available)
    wave_sizes: tuple[int, ...] | None = None
    avg_wave_width: float | None = None
    parallel_work_ratio: float | None = None
    wave_variance: float | None = None
    keyword_coverage: float | None = None
    has_convergence: bool | None = None
    depth_utilization: float | None = None

    # Timing
    generation_time_ms: float = 0.0


@dataclass
class GoalResult:
    """Results for a single goal."""

    goal_id: str
    goal_name: str
    candidates: list[CandidateMetrics]
    winner_v1_style: str
    winner_v2_style: str
    v1_v2_agree: bool
    diversity_score: float  # How different are the candidates?
    total_time_ms: float


@dataclass
class PromptStyleStats:
    """Aggregated statistics for a prompt style."""

    style: str
    total_runs: int = 0
    wins_v1: int = 0
    wins_v2: int = 0

    # Metric distributions
    depths: list[int] = field(default_factory=list)
    widths: list[int] = field(default_factory=list)
    artifact_counts: list[int] = field(default_factory=list)
    parallelism_factors: list[float] = field(default_factory=list)
    balance_factors: list[float] = field(default_factory=list)
    scores_v1: list[float] = field(default_factory=list)
    scores_v2: list[float] = field(default_factory=list)
    keyword_coverages: list[float] = field(default_factory=list)
    wave_variances: list[float] = field(default_factory=list)

    @property
    def win_rate_v1(self) -> float:
        return self.wins_v1 / self.total_runs if self.total_runs > 0 else 0.0

    @property
    def win_rate_v2(self) -> float:
        return self.wins_v2 / self.total_runs if self.total_runs > 0 else 0.0

    def mean_parallelism(self) -> float:
        return statistics.mean(self.parallelism_factors) if self.parallelism_factors else 0.0

    def mean_depth(self) -> float:
        return statistics.mean(self.depths) if self.depths else 0.0

    def mean_artifacts(self) -> float:
        return statistics.mean(self.artifact_counts) if self.artifact_counts else 0.0

    def mean_score_v1(self) -> float:
        return statistics.mean(self.scores_v1) if self.scores_v1 else 0.0

    def mean_score_v2(self) -> float:
        return statistics.mean(self.scores_v2) if self.scores_v2 else 0.0

    def mean_keyword_coverage(self) -> float:
        return statistics.mean(self.keyword_coverages) if self.keyword_coverages else 0.0


def compute_candidate_diversity(candidates: list[CandidateMetrics]) -> float:
    """Compute diversity score for a set of candidates (0-1).

    Higher = more diverse candidates (better for harmonic planning).
    Measures structural variance across candidates.
    """
    if len(candidates) < 2:
        return 0.0

    # Collect structural features
    depths = [c.depth for c in candidates]
    widths = [c.width for c in candidates]
    artifacts = [c.artifact_count for c in candidates]
    parallelisms = [c.parallelism_factor for c in candidates]

    # Compute coefficient of variation for each
    def cv(values: list[float]) -> float:
        if not values or statistics.mean(values) == 0:
            return 0.0
        return statistics.stdev(values) / statistics.mean(values)

    cvs = [
        cv([float(d) for d in depths]),
        cv([float(w) for w in widths]),
        cv([float(a) for a in artifacts]),
        cv(parallelisms),
    ]

    # Average CV (higher = more diverse)
    avg_cv = statistics.mean(cvs)

    # Normalize to 0-1 (CV of 0.5 is considered "highly diverse")
    return min(avg_cv / 0.5, 1.0)


async def run_single_goal(
    model: Any,
    goal_config: dict,
    candidates: int = 5,
) -> GoalResult:
    """Run harmonic planning for a single goal and collect metrics."""
    import time

    from sunwell.planning.naaru.planners.harmonic import (
        HarmonicPlanner,
        PlanMetricsV2,
        ScoringVersion,
        VarianceStrategy,
    )

    goal = goal_config["goal"]
    start_time = time.perf_counter()

    planner = HarmonicPlanner(
        model=model,
        candidates=candidates,
        variance=VarianceStrategy.PROMPTING,
        scoring_version=ScoringVersion.V2,
        refinement_rounds=0,  # No refinement for pure candidate analysis
        use_free_threading=True,
    )

    # Generate candidates
    candidate_results = await planner._generate_candidates(goal, None)

    # Score each candidate
    candidate_metrics: list[CandidateMetrics] = []
    for result in candidate_results:
        graph = result.graph
        metrics = planner._score_plan(graph, goal)

        cm = CandidateMetrics(
            prompt_style=result.variance_config.get("prompt_style", "default"),
            temperature=result.variance_config.get("temperature"),
            constraint=result.variance_config.get("constraint"),
            depth=metrics.depth,
            width=metrics.width,
            leaf_count=metrics.leaf_count,
            artifact_count=metrics.artifact_count,
            parallelism_factor=metrics.parallelism_factor,
            balance_factor=metrics.balance_factor,
            file_conflicts=metrics.file_conflicts,
            estimated_waves=metrics.estimated_waves,
            score_v1=metrics.score,
            score_v2=metrics.score_v2 if isinstance(metrics, PlanMetricsV2) else None,
        )

        if isinstance(metrics, PlanMetricsV2):
            cm = CandidateMetrics(
                prompt_style=result.variance_config.get("prompt_style", "default"),
                temperature=result.variance_config.get("temperature"),
                constraint=result.variance_config.get("constraint"),
                depth=metrics.depth,
                width=metrics.width,
                leaf_count=metrics.leaf_count,
                artifact_count=metrics.artifact_count,
                parallelism_factor=metrics.parallelism_factor,
                balance_factor=metrics.balance_factor,
                file_conflicts=metrics.file_conflicts,
                estimated_waves=metrics.estimated_waves,
                score_v1=metrics.score,
                score_v2=metrics.score_v2,
                wave_sizes=metrics.wave_sizes,
                avg_wave_width=metrics.avg_wave_width,
                parallel_work_ratio=metrics.parallel_work_ratio,
                wave_variance=metrics.wave_variance,
                keyword_coverage=metrics.keyword_coverage,
                has_convergence=metrics.has_convergence,
                depth_utilization=metrics.depth_utilization,
            )

        candidate_metrics.append(cm)

    # Find winners
    winner_v1 = max(candidate_metrics, key=lambda c: c.score_v1)
    winner_v2 = max(candidate_metrics, key=lambda c: c.score_v2 or 0.0)

    total_time = (time.perf_counter() - start_time) * 1000

    return GoalResult(
        goal_id=goal_config["id"],
        goal_name=goal_config["name"],
        candidates=candidate_metrics,
        winner_v1_style=winner_v1.prompt_style,
        winner_v2_style=winner_v2.prompt_style,
        v1_v2_agree=winner_v1.prompt_style == winner_v2.prompt_style,
        diversity_score=compute_candidate_diversity(candidate_metrics),
        total_time_ms=total_time,
    )


def aggregate_prompt_stats(results: list[GoalResult]) -> dict[str, PromptStyleStats]:
    """Aggregate statistics per prompt style across all goals."""
    stats: dict[str, PromptStyleStats] = defaultdict(lambda: PromptStyleStats(style=""))

    for result in results:
        for candidate in result.candidates:
            style = candidate.prompt_style
            if stats[style].style == "":
                stats[style].style = style

            s = stats[style]
            s.total_runs += 1
            s.depths.append(candidate.depth)
            s.widths.append(candidate.width)
            s.artifact_counts.append(candidate.artifact_count)
            s.parallelism_factors.append(candidate.parallelism_factor)
            s.balance_factors.append(candidate.balance_factor)
            s.scores_v1.append(candidate.score_v1)
            if candidate.score_v2 is not None:
                s.scores_v2.append(candidate.score_v2)
            if candidate.keyword_coverage is not None:
                s.keyword_coverages.append(candidate.keyword_coverage)
            if candidate.wave_variance is not None:
                s.wave_variances.append(candidate.wave_variance)

        # Track wins
        stats[result.winner_v1_style].wins_v1 += 1
        stats[result.winner_v2_style].wins_v2 += 1

    return dict(stats)


def print_results(
    results: list[GoalResult],
    stats: dict[str, PromptStyleStats],
) -> None:
    """Print detailed benchmark results."""
    print("\n" + "=" * 80)
    print("HARMONIC PLANNING CANDIDATE ANALYSIS")
    print("=" * 80)

    # Per-goal results
    print("\n📊 PER-GOAL RESULTS")
    print("-" * 80)

    for result in results:
        print(f"\n🎯 {result.goal_name} ({result.goal_id})")
        print(f"   Diversity: {result.diversity_score:.2f} | Time: {result.total_time_ms:.0f}ms")
        print(f"   V1 Winner: {result.winner_v1_style} | V2 Winner: {result.winner_v2_style}", end="")
        print(" ✅" if result.v1_v2_agree else " ⚠️ DISAGREE")

        print("\n   Candidates:")
        for c in sorted(result.candidates, key=lambda x: x.score_v2 or x.score_v1, reverse=True):
            marker = ""
            if c.prompt_style == result.winner_v2_style:
                marker = " ← V2 WINNER"
            elif c.prompt_style == result.winner_v1_style and not result.v1_v2_agree:
                marker = " ← V1 WINNER"

            print(
                f"   {c.prompt_style:<15} | "
                f"depth={c.depth} width={c.width} artifacts={c.artifact_count} | "
                f"v1={c.score_v1:>5.1f} v2={c.score_v2 or 0:>5.1f} | "
                f"kw={c.keyword_coverage or 0:.2f}{marker}"
            )

    # Aggregate statistics
    print("\n\n📈 AGGREGATE PROMPT STYLE STATISTICS")
    print("-" * 80)
    print(
        f"{'Style':<15} | {'Runs':>4} | {'Win V1':>6} | {'Win V2':>6} | "
        f"{'Avg Depth':>9} | {'Avg Para':>8} | {'Avg V2':>8} | {'Avg KW':>7}"
    )
    print("-" * 80)

    for style in ["parallel_first", "minimal", "thorough", "modular", "risk_aware", "default"]:
        if style not in stats:
            continue
        s = stats[style]
        print(
            f"{style:<15} | {s.total_runs:>4} | "
            f"{s.win_rate_v1:>5.0%} | {s.win_rate_v2:>5.0%} | "
            f"{s.mean_depth():>9.1f} | {s.mean_parallelism():>8.2f} | "
            f"{s.mean_score_v2():>8.1f} | {s.mean_keyword_coverage():>7.2f}"
        )

    # V1/V2 agreement
    agreements = sum(1 for r in results if r.v1_v2_agree)
    print(f"\n🔄 V1/V2 Agreement: {agreements}/{len(results)} ({agreements / len(results):.0%})")

    # Diversity analysis
    avg_diversity = statistics.mean(r.diversity_score for r in results)
    print(f"\n🎲 Average Candidate Diversity: {avg_diversity:.2f}")
    if avg_diversity < 0.2:
        print("   ⚠️ LOW DIVERSITY: Candidates are too similar, prompts may need differentiation")
    elif avg_diversity < 0.4:
        print("   📊 MODERATE DIVERSITY: Decent variance between candidates")
    else:
        print("   ✅ HIGH DIVERSITY: Candidates provide meaningfully different perspectives")

    # Prompt effectiveness analysis
    print("\n\n🔍 PROMPT STYLE ANALYSIS")
    print("-" * 80)

    for style in ["parallel_first", "minimal", "thorough", "modular", "risk_aware", "default"]:
        if style not in stats:
            continue
        s = stats[style]
        print(f"\n{style.upper()}:")

        # Characteristic analysis
        if style == "parallel_first":
            expected = "high parallelism, shallow depth"
            if s.mean_parallelism() > 0.4:
                print(f"   ✅ Achieving {expected}: parallelism={s.mean_parallelism():.2f}")
            else:
                print(f"   ⚠️ NOT achieving {expected}: parallelism={s.mean_parallelism():.2f}")
                print("   💡 Consider: Strengthen parallelism emphasis in prompt")

        elif style == "minimal":
            expected = "fewer artifacts, direct paths"
            avg_art = s.mean_artifacts()
            if avg_art < 8:
                print(f"   ✅ Achieving {expected}: avg_artifacts={avg_art:.1f}")
            else:
                print(f"   ⚠️ NOT achieving {expected}: avg_artifacts={avg_art:.1f}")
                print("   💡 Consider: Add explicit artifact count limits")

        elif style == "thorough":
            expected = "more artifacts, higher coverage"
            if s.mean_keyword_coverage() > 0.6:
                print(f"   ✅ Achieving {expected}: coverage={s.mean_keyword_coverage():.2f}")
            else:
                print(f"   ⚠️ NOT achieving {expected}: coverage={s.mean_keyword_coverage():.2f}")
                print("   💡 Consider: Emphasize completeness over structure")

        elif style == "modular":
            expected = "clean separation of concerns"
            # Modular should have moderate depth and good parallelism from isolation
            if s.mean_parallelism() > 0.3 and s.mean_keyword_coverage() > 0.6:
                print(f"   ✅ Achieving {expected}: parallelism={s.mean_parallelism():.2f}, coverage={s.mean_keyword_coverage():.2f}")
            else:
                print(f"   ⚠️ Needs work: parallelism={s.mean_parallelism():.2f}, coverage={s.mean_keyword_coverage():.2f}")
                print("   💡 Consider: Emphasize module isolation and testability")

        elif style == "risk_aware":
            expected = "fail-fast risk identification"
            # Risk-aware should have risks as leaves (high parallelism) and good coverage
            if s.mean_parallelism() > 0.35 and s.mean_keyword_coverage() > 0.6:
                print(f"   ✅ Achieving {expected}: parallelism={s.mean_parallelism():.2f}, coverage={s.mean_keyword_coverage():.2f}")
            else:
                print(f"   ⚠️ Needs work: parallelism={s.mean_parallelism():.2f}, coverage={s.mean_keyword_coverage():.2f}")
                print("   💡 Consider: Emphasize putting risky artifacts first")

        elif style == "default":
            print(f"   📊 Baseline: depth={s.mean_depth():.1f}, artifacts={s.mean_artifacts():.1f}")

        print(f"   Win rate (V2): {s.win_rate_v2:.0%}")


def generate_json_report(
    results: list[GoalResult],
    stats: dict[str, PromptStyleStats],
    model_name: str,
) -> dict[str, Any]:
    """Generate JSON report for programmatic analysis."""
    return {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "model": model_name,
            "goals_tested": len(results),
            "total_candidates": sum(len(r.candidates) for r in results),
        },
        "summary": {
            "v1_v2_agreement_rate": sum(1 for r in results if r.v1_v2_agree) / len(results),
            "avg_diversity": statistics.mean(r.diversity_score for r in results),
            "avg_time_ms": statistics.mean(r.total_time_ms for r in results),
        },
        "prompt_styles": {
            style: {
                "total_runs": s.total_runs,
                "win_rate_v1": s.win_rate_v1,
                "win_rate_v2": s.win_rate_v2,
                "mean_depth": s.mean_depth(),
                "mean_artifacts": s.mean_artifacts(),
                "mean_parallelism": s.mean_parallelism(),
                "mean_score_v1": s.mean_score_v1(),
                "mean_score_v2": s.mean_score_v2(),
                "mean_keyword_coverage": s.mean_keyword_coverage(),
            }
            for style, s in stats.items()
        },
        "goals": [
            {
                "id": r.goal_id,
                "name": r.goal_name,
                "winner_v1": r.winner_v1_style,
                "winner_v2": r.winner_v2_style,
                "v1_v2_agree": r.v1_v2_agree,
                "diversity": r.diversity_score,
                "time_ms": r.total_time_ms,
                "candidates": [
                    {
                        "style": c.prompt_style,
                        "depth": c.depth,
                        "width": c.width,
                        "artifacts": c.artifact_count,
                        "parallelism": c.parallelism_factor,
                        "score_v1": c.score_v1,
                        "score_v2": c.score_v2,
                        "keyword_coverage": c.keyword_coverage,
                    }
                    for c in r.candidates
                ],
            }
            for r in results
        ],
    }


async def main() -> None:
    """Run the harmonic candidate benchmark."""
    import argparse

    parser = argparse.ArgumentParser(description="Benchmark Harmonic Planning Candidates")
    parser.add_argument("--model", default="gemma3:4b", help="Ollama model to use")
    parser.add_argument("--runs", type=int, default=1, help="Runs per goal (for variance)")
    parser.add_argument("--candidates", type=int, default=5, help="Candidates per run")
    parser.add_argument("--output", type=str, help="JSON output file")
    parser.add_argument("--goals", nargs="*", help="Specific goal IDs to run")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Filter goals if specified
    goals = BENCHMARK_GOALS
    if args.goals:
        goals = [g for g in BENCHMARK_GOALS if g["id"] in args.goals]
        if not goals:
            print(f"No matching goals found. Available: {[g['id'] for g in BENCHMARK_GOALS]}")
            sys.exit(1)

    print(f"🚀 Harmonic Candidate Benchmark")
    print(f"   Model: {args.model}")
    print(f"   Goals: {len(goals)}")
    print(f"   Runs per goal: {args.runs}")
    print(f"   Candidates per run: {args.candidates}")
    print()

    # Initialize model
    from sunwell.models.ollama import OllamaModel

    model = OllamaModel(model=args.model)

    # Run benchmarks
    all_results: list[GoalResult] = []

    for goal_config in goals:
        print(f"📋 Testing: {goal_config['name']}...", end=" ", flush=True)

        for run in range(args.runs):
            try:
                result = await run_single_goal(model, goal_config, args.candidates)
                all_results.append(result)
                print(f"✅ ({result.total_time_ms:.0f}ms)", end=" " if args.runs > 1 else "")
            except Exception as e:
                print(f"❌ Error: {e}")
                if args.verbose:
                    import traceback
                    traceback.print_exc()

        print()

    if not all_results:
        print("No results collected. Check model availability.")
        sys.exit(1)

    # Aggregate and print results
    stats = aggregate_prompt_stats(all_results)
    print_results(all_results, stats)

    # Save JSON report if requested
    if args.output:
        report = generate_json_report(all_results, stats, args.model)
        output_path = Path(args.output)
        output_path.write_text(json.dumps(report, indent=2))
        print(f"\n📄 JSON report saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
