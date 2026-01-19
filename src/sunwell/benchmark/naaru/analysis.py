"""Naaru Benchmark Statistical Analysis (RFC-027).

Provides statistical analysis for Naaru benchmark results:
- Effect size (Cohen's d) per technique
- Pairwise significance (Wilcoxon signed-rank)
- Interaction effects (Naaru × Lens)
- Cost-quality Pareto frontier
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sunwell.benchmark.naaru.types import (
    ConditionStats,
    NaaruAnalysis,
    NaaruCondition,
    PairwiseComparison,
)

if TYPE_CHECKING:
    from sunwell.benchmark.naaru.types import NaaruBenchmarkResults


def interpret_cohens_d(d: float) -> str:
    """Interpret effect size magnitude.

    Cohen's d interpretation:
    - |d| < 0.2: negligible
    - |d| < 0.5: small
    - |d| < 0.8: medium
    - |d| >= 0.8: large
    """
    d = abs(d)
    if d < 0.2:
        return "negligible"
    elif d < 0.5:
        return "small"
    elif d < 0.8:
        return "medium"
    else:
        return "large"


def compute_cohens_d(scores_a: list[float], scores_b: list[float]) -> float:
    """Compute Cohen's d effect size for paired samples.

    Formula: d = mean(diff) / std(diff)
    """
    if len(scores_a) != len(scores_b) or len(scores_a) == 0:
        return 0.0

    import math

    diff = [a - b for a, b in zip(scores_a, scores_b, strict=True)]
    mean_diff = sum(diff) / len(diff)

    if len(diff) < 2:
        return 0.0

    variance = sum((x - mean_diff) ** 2 for x in diff) / (len(diff) - 1)
    std_diff = math.sqrt(variance) if variance > 0 else 1.0

    return mean_diff / std_diff if std_diff > 0 else 0.0


def wilcoxon_test(scores_a: list[float], scores_b: list[float]) -> tuple[float, float]:
    """Compute Wilcoxon signed-rank test for paired samples.

    Returns:
        Tuple of (test_statistic, p_value)

    Uses scipy if available, otherwise returns placeholder.
    """
    try:
        from scipy import stats

        # Filter out ties for Wilcoxon
        pairs = [(a, b) for a, b in zip(scores_a, scores_b, strict=True) if a != b]
        if len(pairs) < 3:
            return 0.0, 1.0

        a_filtered = [p[0] for p in pairs]
        b_filtered = [p[1] for p in pairs]

        stat, p_value = stats.wilcoxon(a_filtered, b_filtered)
        return float(stat), float(p_value)
    except ImportError:
        # Fallback: simple sign test approximation
        n_positive = sum(1 for a, b in zip(scores_a, scores_b, strict=True) if a > b)
        n_negative = sum(1 for a, b in zip(scores_a, scores_b, strict=True) if a < b)
        n_total = n_positive + n_negative

        if n_total == 0:
            return 0.0, 1.0

        # Approximate p-value using binomial
        p_value = 2 * min(n_positive, n_negative) / n_total if n_total > 0 else 1.0
        return float(min(n_positive, n_negative)), p_value


def analyze_conditions(
    results: NaaruBenchmarkResults,
    evaluations: dict[str, dict[NaaruCondition, float]],
    alpha: float = 0.05,
) -> NaaruAnalysis:
    """Compute statistical analysis across all condition pairs.

    Args:
        results: Benchmark results
        evaluations: Task ID → Condition → quality score
        alpha: Significance level (default 0.05)

    Returns:
        NaaruAnalysis with all statistical comparisons
    """
    conditions = results.conditions
    n_comparisons = len(conditions) * (len(conditions) - 1) // 2
    alpha_corrected = alpha / n_comparisons if n_comparisons > 0 else alpha  # Bonferroni

    # Compute per-condition statistics
    condition_stats = _compute_condition_stats(results, evaluations)

    # Compute pairwise comparisons
    comparisons: list[PairwiseComparison] = []

    for i, cond_a in enumerate(conditions):
        for cond_b in conditions[i+1:]:
            comparison = _compare_conditions(
                cond_a, cond_b, evaluations, alpha_corrected
            )
            if comparison:
                comparisons.append(comparison)

    # Compute interaction effect
    interaction, interpretation = _compute_interaction_effect(evaluations)

    # Compute Pareto frontier
    pareto = _compute_pareto_frontier(condition_stats)

    # Compute hypothesis results
    hypothesis_results = _evaluate_hypotheses(comparisons, evaluations)

    return NaaruAnalysis(
        condition_stats=condition_stats,
        comparisons=comparisons,
        hypothesis_results=hypothesis_results,
        interaction_effect=interaction,
        interaction_interpretation=interpretation,
        pareto_frontier=pareto,
    )


def _compute_condition_stats(
    results: NaaruBenchmarkResults,
    evaluations: dict[str, dict[NaaruCondition, float]],
) -> dict[NaaruCondition, ConditionStats]:
    """Compute aggregate statistics for each condition."""
    import math

    stats: dict[NaaruCondition, ConditionStats] = {}

    for condition in results.conditions:
        scores: list[float] = []
        tokens: list[int] = []
        times: list[float] = []
        consensus: list[float] = []
        refinements: list[int] = []
        refinement_gains: list[float] = []
        escalations: list[bool] = []

        for task_result in results.results:
            output = task_result.outputs.get(condition)
            if output is None:
                continue

            # Get quality score from evaluations
            task_scores = evaluations.get(task_result.task_id, {})
            if condition in task_scores:
                scores.append(task_scores[condition])

            tokens.append(output.tokens_used)
            times.append(output.time_seconds)

            if output.harmonic_metrics:
                consensus.append(output.harmonic_metrics.consensus_strength)

            if output.resonance_metrics:
                refinements.append(output.resonance_metrics.refinement_attempts)
                refinement_gains.append(output.resonance_metrics.refinement_gain)
                escalations.append(output.resonance_metrics.escalated_to_full_judge)

        if not scores:
            continue

        mean_score = sum(scores) / len(scores)
        std_score = math.sqrt(
            sum((s - mean_score) ** 2 for s in scores) / max(1, len(scores) - 1)
        ) if len(scores) > 1 else 0.0

        stats[condition] = ConditionStats(
            condition=condition,
            n_tasks=len(scores),
            mean_score=mean_score,
            std_score=std_score,
            min_score=min(scores),
            max_score=max(scores),
            mean_tokens=sum(tokens) / len(tokens) if tokens else 0,
            total_tokens=sum(tokens),
            mean_time_seconds=sum(times) / len(times) if times else 0,
            total_time_seconds=sum(times),
            mean_consensus_strength=(
                sum(consensus) / len(consensus) if consensus else None
            ),
            mean_refinement_attempts=(
                sum(refinements) / len(refinements) if refinements else None
            ),
            mean_refinement_gain=(
                sum(refinement_gains) / len(refinement_gains) if refinement_gains else None
            ),
            escalation_rate=(
                sum(1 for e in escalations if e) / len(escalations) if escalations else None
            ),
        )

    return stats


def _compare_conditions(
    cond_a: NaaruCondition,
    cond_b: NaaruCondition,
    evaluations: dict[str, dict[NaaruCondition, float]],
    alpha_corrected: float,
) -> PairwiseComparison | None:
    """Compare two conditions statistically."""
    scores_a: list[float] = []
    scores_b: list[float] = []

    for _task_id, task_scores in evaluations.items():
        if cond_a in task_scores and cond_b in task_scores:
            scores_a.append(task_scores[cond_a])
            scores_b.append(task_scores[cond_b])

    if len(scores_a) < 3:
        return None

    # Compute effect size
    d = compute_cohens_d(scores_a, scores_b)

    # Compute significance
    stat, p_value = wilcoxon_test(scores_a, scores_b)

    # Win/loss/tie
    wins_a = sum(1 for a, b in zip(scores_a, scores_b, strict=True) if a > b)
    wins_b = sum(1 for a, b in zip(scores_a, scores_b, strict=True) if b > a)
    ties = sum(1 for a, b in zip(scores_a, scores_b, strict=True) if a == b)

    return PairwiseComparison(
        condition_a=cond_a,
        condition_b=cond_b,
        mean_a=sum(scores_a) / len(scores_a),
        mean_b=sum(scores_b) / len(scores_b),
        cohens_d=d,
        effect_interpretation=interpret_cohens_d(d),
        statistic=stat,
        p_value=p_value,
        significant=p_value < alpha_corrected,
        wins_a=wins_a,
        wins_b=wins_b,
        ties=ties,
    )


def _compute_interaction_effect(
    evaluations: dict[str, dict[NaaruCondition, float]],
) -> tuple[float, str]:
    """Compute interaction effect between Naaru and Lens.

    Interaction = (G - A) - ((F - A) + (B - A))

    If interaction > 0: synergistic (combined > sum of parts)
    If interaction ≈ 0: additive (combined = sum of parts)
    If interaction < 0: diminishing returns (combined < sum of parts)
    """
    baseline_scores: list[float] = []
    baseline_lens_scores: list[float] = []
    naaru_full_scores: list[float] = []
    naaru_full_lens_scores: list[float] = []

    for _task_id, task_scores in evaluations.items():
        if all(c in task_scores for c in [
            NaaruCondition.BASELINE,
            NaaruCondition.BASELINE_LENS,
            NaaruCondition.NAARU_FULL,
            NaaruCondition.NAARU_FULL_LENS,
        ]):
            baseline_scores.append(task_scores[NaaruCondition.BASELINE])
            baseline_lens_scores.append(task_scores[NaaruCondition.BASELINE_LENS])
            naaru_full_scores.append(task_scores[NaaruCondition.NAARU_FULL])
            naaru_full_lens_scores.append(task_scores[NaaruCondition.NAARU_FULL_LENS])

    if not baseline_scores:
        return 0.0, "insufficient data"

    n = len(baseline_scores)
    mean_a = sum(baseline_scores) / n
    mean_b = sum(baseline_lens_scores) / n
    mean_f = sum(naaru_full_scores) / n
    mean_g = sum(naaru_full_lens_scores) / n

    # Interaction effect
    naaru_effect = mean_f - mean_a
    lens_effect = mean_b - mean_a
    combined_effect = mean_g - mean_a
    interaction = combined_effect - (naaru_effect + lens_effect)

    # Interpret
    if interaction > 0.5:
        interpretation = "strongly synergistic"
    elif interaction > 0.1:
        interpretation = "synergistic"
    elif interaction > -0.1:
        interpretation = "additive"
    elif interaction > -0.5:
        interpretation = "diminishing returns"
    else:
        interpretation = "strongly diminishing"

    return interaction, interpretation


def _compute_pareto_frontier(
    stats: dict[NaaruCondition, ConditionStats],
) -> list[NaaruCondition]:
    """Compute the cost-quality Pareto frontier.

    A condition is on the frontier if no other condition dominates it
    (higher quality AND lower cost).
    """
    frontier: list[NaaruCondition] = []

    conditions = list(stats.keys())

    for cond in conditions:
        cond_stats = stats[cond]
        is_dominated = False

        for other in conditions:
            if other == cond:
                continue

            other_stats = stats[other]

            # Check if other dominates cond
            # (higher quality AND lower cost)
            if (
                other_stats.mean_score >= cond_stats.mean_score
                and other_stats.mean_tokens <= cond_stats.mean_tokens
                and (
                    other_stats.mean_score > cond_stats.mean_score
                    or other_stats.mean_tokens < cond_stats.mean_tokens
                )
            ):
                is_dominated = True
                break

        if not is_dominated:
            frontier.append(cond)

    # Sort by quality
    frontier.sort(key=lambda c: stats[c].mean_score, reverse=True)

    return frontier


def _evaluate_hypotheses(
    comparisons: list[PairwiseComparison],
    evaluations: dict[str, dict[NaaruCondition, float]],
) -> dict[str, dict]:
    """Evaluate the 6 primary hypotheses from RFC-027.

    H1: Harmonic improves quality (C vs A, d > 0.3, p < 0.05)
    H2: Lens amplifies Harmonic (D vs C, d > 0.2, p < 0.05)
    H3: Resonance adds incremental value (E vs C, d > 0.2, p < 0.05)
    H4: Full Naaru beats baseline significantly (F vs A, d > 0.5, p < 0.01)
    H5: Naaru + Lens is best overall (G vs all, win rate > 60%)
    H6: Tiered validation reduces cost (F vs E, tokens -40%, quality within 0.5 pts)
    """
    results: dict[str, dict] = {}

    # Helper to find a comparison
    def find_comparison(a: NaaruCondition, b: NaaruCondition) -> PairwiseComparison | None:
        for c in comparisons:
            if (c.condition_a == a and c.condition_b == b) or \
               (c.condition_a == b and c.condition_b == a):
                return c
        return None

    # H1: Harmonic improves quality (C vs A)
    h1_comp = find_comparison(NaaruCondition.HARMONIC, NaaruCondition.BASELINE)
    if h1_comp:
        # Ensure we're measuring C - A (HARMONIC should be higher)
        is_harmonic_first = h1_comp.condition_a == NaaruCondition.HARMONIC
        d = h1_comp.cohens_d if is_harmonic_first else -h1_comp.cohens_d
        results["H1"] = {
            "description": "Harmonic improves quality",
            "comparison": "HARMONIC vs BASELINE",
            "cohens_d": d,
            "p_value": h1_comp.p_value,
            "target": "d > 0.3, p < 0.05",
            "passed": d > 0.3 and h1_comp.p_value < 0.05,
        }

    # H2: Lens amplifies Harmonic (D vs C)
    h2_comp = find_comparison(NaaruCondition.HARMONIC_LENS, NaaruCondition.HARMONIC)
    if h2_comp:
        is_lens_first = h2_comp.condition_a == NaaruCondition.HARMONIC_LENS
        d = h2_comp.cohens_d if is_lens_first else -h2_comp.cohens_d
        results["H2"] = {
            "description": "Lens amplifies Harmonic",
            "comparison": "HARMONIC_LENS vs HARMONIC",
            "cohens_d": d,
            "p_value": h2_comp.p_value,
            "target": "d > 0.2, p < 0.05",
            "passed": d > 0.2 and h2_comp.p_value < 0.05,
        }

    # H3: Resonance adds incremental value (E vs C)
    h3_comp = find_comparison(NaaruCondition.RESONANCE, NaaruCondition.HARMONIC)
    if h3_comp:
        is_resonance_first = h3_comp.condition_a == NaaruCondition.RESONANCE
        d = h3_comp.cohens_d if is_resonance_first else -h3_comp.cohens_d
        results["H3"] = {
            "description": "Resonance adds incremental value",
            "comparison": "RESONANCE vs HARMONIC",
            "cohens_d": d,
            "p_value": h3_comp.p_value,
            "target": "d > 0.2, p < 0.05",
            "passed": d > 0.2 and h3_comp.p_value < 0.05,
        }

    # H4: Full Naaru beats baseline significantly (F vs A)
    h4_comp = find_comparison(NaaruCondition.NAARU_FULL, NaaruCondition.BASELINE)
    if h4_comp:
        is_naaru_first = h4_comp.condition_a == NaaruCondition.NAARU_FULL
        d = h4_comp.cohens_d if is_naaru_first else -h4_comp.cohens_d
        results["H4"] = {
            "description": "Full Naaru beats baseline",
            "comparison": "NAARU_FULL vs BASELINE",
            "cohens_d": d,
            "p_value": h4_comp.p_value,
            "target": "d > 0.5, p < 0.01",
            "passed": d > 0.5 and h4_comp.p_value < 0.01,
        }

    # H5: Naaru + Lens is best overall (G vs all)
    wins = 0
    total = 0
    for comp in comparisons:
        if comp.condition_a == NaaruCondition.NAARU_FULL_LENS:
            wins += comp.wins_a
            total += comp.wins_a + comp.wins_b + comp.ties
        elif comp.condition_b == NaaruCondition.NAARU_FULL_LENS:
            wins += comp.wins_b
            total += comp.wins_a + comp.wins_b + comp.ties

    win_rate = wins / total if total > 0 else 0
    results["H5"] = {
        "description": "Naaru + Lens is best overall",
        "comparison": "NAARU_FULL_LENS vs all",
        "win_rate": win_rate,
        "wins": wins,
        "total": total,
        "target": "win rate > 60%",
        "passed": win_rate > 0.6,
    }

    # H6: Tiered validation reduces cost (F vs E)
    h6_comp = find_comparison(NaaruCondition.NAARU_FULL, NaaruCondition.RESONANCE)
    if h6_comp:
        # Need to get token comparison from elsewhere
        results["H6"] = {
            "description": "Tiered validation reduces cost",
            "comparison": "NAARU_FULL vs RESONANCE",
            "quality_diff": h6_comp.mean_difference,
            "target": "tokens -40%, quality within 0.5 pts",
            "passed": abs(h6_comp.mean_difference) <= 0.5,
            "note": "Token comparison requires condition_stats",
        }

    return results


@dataclass
class NaaruReportGenerator:
    """Generate markdown reports from Naaru benchmark analysis."""

    def generate(
        self,
        results: NaaruBenchmarkResults,
        analysis: NaaruAnalysis,
    ) -> str:
        """Generate a full markdown report."""
        lines = [
            "# Naaru Benchmark Report",
            "",
            f"**Date**: {results.timestamp[:10]}",
            f"**Model**: {results.model} (synthesis) / {results.judge_model} (judge)",
            f"**Tasks**: {results.n_tasks}",
            "",
            "## Executive Summary",
            "",
            self._generate_summary_table(analysis),
            "",
            "## Key Findings",
            "",
            self._generate_findings(analysis),
            "",
            "## Hypothesis Results",
            "",
            self._generate_hypothesis_table(analysis),
            "",
            "## Cost-Quality Tradeoff",
            "",
            self._generate_pareto_section(analysis),
            "",
            "## Statistical Details",
            "",
            self._generate_stats_details(analysis),
        ]

        return "\n".join(lines)

    def _generate_summary_table(self, analysis: NaaruAnalysis) -> str:
        """Generate the executive summary table."""
        lines = [
            "| Condition | Mean Score | vs Baseline | Effect Size | Significant? |",
            "|-----------|------------|-------------|-------------|--------------|",
        ]

        baseline_score = 0.0
        if NaaruCondition.BASELINE in analysis.condition_stats:
            baseline_score = analysis.condition_stats[NaaruCondition.BASELINE].mean_score

        for cond in NaaruCondition:
            if cond not in analysis.condition_stats:
                continue

            stats = analysis.condition_stats[cond]
            diff = stats.mean_score - baseline_score if cond != NaaruCondition.BASELINE else 0
            diff_str = f"+{diff:.1f}" if diff > 0 else f"{diff:.1f}" if diff < 0 else "—"

            # Find comparison with baseline
            effect = "—"
            sig = "—"
            for comp in analysis.comparisons:
                is_baseline = NaaruCondition.BASELINE in (comp.condition_a, comp.condition_b)
                is_this_cond = cond in (comp.condition_a, comp.condition_b)
                if is_baseline and is_this_cond:
                    effect = f"{abs(comp.cohens_d):.2f} ({comp.effect_interpretation})"
                    sig = "✅ Yes" if comp.significant else "❌ No"
                    break

            lines.append(
                f"| {cond.value} | {stats.mean_score:.1f} | {diff_str} | {effect} | {sig} |"
            )

        return "\n".join(lines)

    def _generate_findings(self, analysis: NaaruAnalysis) -> str:
        """Generate key findings list."""
        findings = []

        # Check hypothesis results
        if "H1" in analysis.hypothesis_results:
            h1 = analysis.hypothesis_results["H1"]
            if h1["passed"]:
                findings.append(
                    f"1. **Harmonic Synthesis works**: "
                    f"d={h1['cohens_d']:.2f}, p={h1['p_value']:.4f}"
                )

        if "H4" in analysis.hypothesis_results:
            h4 = analysis.hypothesis_results["H4"]
            if h4["passed"]:
                findings.append(
                    f"2. **Full Naaru significantly beats baseline**: "
                    f"d={h4['cohens_d']:.2f}, p={h4['p_value']:.4f}"
                )

        # Interaction effect
        findings.append(
            f"3. **Naaru × Lens interaction**: {analysis.interaction_interpretation} "
            f"(effect={analysis.interaction_effect:.2f})"
        )

        return "\n".join(findings) if findings else "No significant findings."

    def _generate_hypothesis_table(self, analysis: NaaruAnalysis) -> str:
        """Generate hypothesis results table."""
        lines = [
            "| # | Hypothesis | Result | Target | Passed |",
            "|---|------------|--------|--------|--------|",
        ]

        for h_id, h_data in analysis.hypothesis_results.items():
            result_str = ""
            if "cohens_d" in h_data:
                result_str = f"d={h_data['cohens_d']:.2f}, p={h_data.get('p_value', 0):.4f}"
            elif "win_rate" in h_data:
                result_str = f"win rate={h_data['win_rate']:.1%}"

            passed = "✅" if h_data.get("passed", False) else "❌"

            lines.append(
                f"| {h_id} | {h_data['description']} | {result_str} "
                f"| {h_data['target']} | {passed} |"
            )

        return "\n".join(lines)

    def _generate_pareto_section(self, analysis: NaaruAnalysis) -> str:
        """Generate Pareto frontier section."""
        lines = [
            "| Condition | Quality | Tokens | Quality/1K Tokens |",
            "|-----------|---------|--------|-------------------|",
        ]

        for cond in analysis.pareto_frontier:
            if cond not in analysis.condition_stats:
                continue
            stats = analysis.condition_stats[cond]
            lines.append(
                f"| {cond.value} | {stats.mean_score:.1f} | {stats.mean_tokens:.0f} | "
                f"{stats.quality_per_token:.2f} |"
            )

        lines.append("")
        pareto_names = ", ".join(c.value for c in analysis.pareto_frontier)
        lines.append(f"**Pareto optimal conditions**: {pareto_names}")

        return "\n".join(lines)

    def _generate_stats_details(self, analysis: NaaruAnalysis) -> str:
        """Generate detailed statistics section."""
        lines = [
            "### Pairwise Comparisons",
            "",
            "| A | B | Mean A | Mean B | Cohen's d | p-value | W/L/T |",
            "|---|---|--------|--------|-----------|---------|-------|",
        ]

        for comp in analysis.comparisons:
            lines.append(
                f"| {comp.condition_a.value} | {comp.condition_b.value} | "
                f"{comp.mean_a:.2f} | {comp.mean_b:.2f} | {comp.cohens_d:.3f} | "
                f"{comp.p_value:.4f} | {comp.wins_a}/{comp.wins_b}/{comp.ties} |"
            )

        return "\n".join(lines)
