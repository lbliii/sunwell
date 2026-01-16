"""Benchmark Reporter (RFC-018).

Statistical analysis and report generation for benchmark results.
Implements RFC-018 statistical rigor requirements:
- Mann-Whitney U / Wilcoxon signed-rank tests
- Cohen's d effect size
- Bootstrap confidence intervals
- Per-category breakdowns
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from sunwell.benchmark.types import (
    BenchmarkResults,
    CategoryStats,
    EvaluationResult,
    StatisticalSummary,
    TaskResult,
    Verdict,
)

if TYPE_CHECKING:
    pass


@dataclass
class BenchmarkReporter:
    """Generate statistical reports from benchmark results.
    
    Usage:
        reporter = BenchmarkReporter()
        summary = reporter.compute_statistics(results, evaluations)
        reporter.save_report(results, evaluations, summary, output_dir)
    """
    
    ci_level: float = 0.95
    bootstrap_samples: int = 1000
    
    def compute_statistics(
        self,
        results: list[TaskResult],
        evaluations: list[EvaluationResult],
    ) -> StatisticalSummary:
        """Compute comprehensive statistics from evaluation results.
        
        Implements RFC-018 statistical rigor requirements.
        """
        if not evaluations:
            return self._empty_summary()
        
        # Extract scores for statistical tests
        selective_scores: list[float] = []
        baseline_scores: list[float] = []
        
        wins = 0
        losses = 0
        ties = 0
        
        category_data: dict[str, dict] = {}
        
        for eval_result in evaluations:
            # Find the task result for category info
            task_result = next(
                (r for r in results if r.task_id == eval_result.task_id),
                None,
            )
            
            # Extract category from task_id (e.g., "docs-api-ref-001" -> "docs")
            category = eval_result.task_id.split("-")[0] if "-" in eval_result.task_id else "other"
            
            if category not in category_data:
                category_data[category] = {
                    "wins": 0,
                    "losses": 0,
                    "ties": 0,
                    "selective_scores": [],
                    "baseline_scores": [],
                }
            
            # Aggregate judge results
            for key, verdict in eval_result.judge_results.items():
                # B is selective in our comparisons
                selective_scores.append(verdict.avg_score_b)
                baseline_scores.append(verdict.avg_score_a)
                
                category_data[category]["selective_scores"].append(verdict.avg_score_b)
                category_data[category]["baseline_scores"].append(verdict.avg_score_a)
                
                if verdict.winner == Verdict.B_WINS:
                    wins += 1
                    category_data[category]["wins"] += 1
                elif verdict.winner == Verdict.A_WINS:
                    losses += 1
                    category_data[category]["losses"] += 1
                else:
                    ties += 1
                    category_data[category]["ties"] += 1
        
        # Convert to numpy arrays
        selective_arr = np.array(selective_scores, dtype=np.float64)
        baseline_arr = np.array(baseline_scores, dtype=np.float64)
        
        # Statistical tests
        p_value, test_statistic, test_name = self._significance_test(
            selective_arr, baseline_arr
        )
        
        # Effect size
        effect_size = self._cohens_d(selective_arr, baseline_arr)
        effect_interpretation = self._interpret_effect_size(effect_size)
        
        # Bootstrap confidence intervals
        ci_lower, ci_upper = self._bootstrap_ci(selective_arr, baseline_arr)
        
        # Per-category stats
        category_stats: list[CategoryStats] = []
        for cat, data in category_data.items():
            sel_scores = data["selective_scores"]
            base_scores = data["baseline_scores"]
            
            category_stats.append(CategoryStats(
                category=cat,
                total_tasks=data["wins"] + data["losses"] + data["ties"],
                wins=data["wins"],
                losses=data["losses"],
                ties=data["ties"],
                avg_selective_score=np.mean(sel_scores) if sel_scores else 0.0,
                avg_baseline_score=np.mean(base_scores) if base_scores else 0.0,
            ))
        
        return StatisticalSummary(
            n_tasks=len(evaluations),
            n_per_category={cat: len(data["selective_scores"]) for cat, data in category_data.items()},
            wins=wins,
            losses=losses,
            ties=ties,
            effect_size_cohens_d=effect_size,
            effect_size_interpretation=effect_interpretation,
            p_value=p_value,
            test_statistic=test_statistic,
            test_name=test_name,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            ci_level=self.ci_level,
            category_stats=tuple(category_stats),
        )
    
    def _significance_test(
        self,
        selective: np.ndarray,
        baseline: np.ndarray,
    ) -> tuple[float, float, str]:
        """Run appropriate significance test.
        
        Uses Wilcoxon signed-rank for paired data (same tasks),
        Mann-Whitney U for independent samples.
        """
        try:
            from scipy import stats
        except ImportError:
            # Return defaults if scipy not available
            return 1.0, 0.0, "scipy_not_available"
        
        if len(selective) != len(baseline):
            # Independent samples
            statistic, p_value = stats.mannwhitneyu(
                selective, baseline, alternative='greater'
            )
            return float(p_value), float(statistic), "Mann-Whitney U"
        else:
            # Paired samples
            try:
                statistic, p_value = stats.wilcoxon(
                    selective, baseline, alternative='greater'
                )
                return float(p_value), float(statistic), "Wilcoxon signed-rank"
            except ValueError:
                # Fall back to Mann-Whitney if Wilcoxon fails
                statistic, p_value = stats.mannwhitneyu(
                    selective, baseline, alternative='greater'
                )
                return float(p_value), float(statistic), "Mann-Whitney U"
    
    def _cohens_d(
        self,
        selective: np.ndarray,
        baseline: np.ndarray,
    ) -> float:
        """Calculate Cohen's d effect size."""
        if len(selective) == 0 or len(baseline) == 0:
            return 0.0
        
        mean_diff = np.mean(selective) - np.mean(baseline)
        
        # Pooled standard deviation
        n1, n2 = len(selective), len(baseline)
        var1, var2 = np.var(selective, ddof=1), np.var(baseline, ddof=1)
        
        # Handle zero variance edge case
        if var1 == 0 and var2 == 0:
            return 0.0 if mean_diff == 0 else float('inf') * np.sign(mean_diff)
        
        pooled_std = np.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))
        
        if pooled_std == 0:
            return 0.0
        
        return float(mean_diff / pooled_std)
    
    def _interpret_effect_size(self, d: float) -> str:
        """Interpret Cohen's d effect size."""
        d_abs = abs(d)
        if d_abs >= 0.8:
            return "large"
        elif d_abs >= 0.5:
            return "medium"
        elif d_abs >= 0.2:
            return "small"
        else:
            return "negligible"
    
    def _bootstrap_ci(
        self,
        selective: np.ndarray,
        baseline: np.ndarray,
    ) -> tuple[float, float]:
        """Calculate bootstrap confidence intervals for mean difference."""
        if len(selective) == 0 or len(baseline) == 0:
            return 0.0, 0.0
        
        rng = np.random.default_rng(42)  # Reproducible
        
        diffs: list[float] = []
        n_sel, n_base = len(selective), len(baseline)
        
        for _ in range(self.bootstrap_samples):
            # Resample with replacement
            sel_sample = rng.choice(selective, size=n_sel, replace=True)
            base_sample = rng.choice(baseline, size=n_base, replace=True)
            
            diffs.append(float(np.mean(sel_sample) - np.mean(base_sample)))
        
        diffs_arr = np.array(diffs)
        alpha = (1 - self.ci_level) / 2
        
        ci_lower = float(np.percentile(diffs_arr, alpha * 100))
        ci_upper = float(np.percentile(diffs_arr, (1 - alpha) * 100))
        
        return ci_lower, ci_upper
    
    def _empty_summary(self) -> StatisticalSummary:
        """Return empty summary when no data available."""
        return StatisticalSummary(
            n_tasks=0,
            n_per_category={},
            wins=0,
            losses=0,
            ties=0,
            effect_size_cohens_d=0.0,
            effect_size_interpretation="negligible",
            p_value=1.0,
            test_statistic=0.0,
            test_name="none",
            ci_lower=0.0,
            ci_upper=0.0,
        )
    
    def generate_markdown_report(
        self,
        results: BenchmarkResults,
        evaluations: list[EvaluationResult],
        summary: StatisticalSummary,
    ) -> str:
        """Generate a comprehensive markdown report."""
        lines: list[str] = []
        
        # Header
        lines.append("# Quality Benchmark Report")
        lines.append("")
        lines.append(f"**Generated**: {datetime.now().isoformat()}")
        lines.append(f"**Model**: {results.model}")
        lines.append(f"**Tasks**: {summary.n_tasks}")
        lines.append("")
        
        # Summary Statistics
        lines.append("## Summary")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Win Rate | {summary.win_rate:.1%} ({summary.wins}W / {summary.losses}L / {summary.ties}T) |")
        lines.append(f"| Effect Size (Cohen's d) | {summary.effect_size_cohens_d:.3f} ({summary.effect_size_interpretation}) |")
        lines.append(f"| Statistical Test | {summary.test_name} |")
        lines.append(f"| p-value | {summary.p_value:.4f} {'✓' if summary.significant else '✗'} |")
        lines.append(f"| 95% CI | [{summary.ci_lower:.3f}, {summary.ci_upper:.3f}] |")
        lines.append(f"| **Claim Level** | {summary.claim_level()} |")
        lines.append("")
        
        # Interpretation
        lines.append("### Interpretation")
        lines.append("")
        claim = summary.claim_level()
        if claim == "strong evidence":
            lines.append("✅ **Strong evidence** that selective retrieval improves output quality.")
        elif claim == "shows improvement":
            lines.append("✓ Results **show improvement** from selective retrieval.")
        elif claim == "suggests improvement":
            lines.append("⚠️ Results **suggest improvement** but more data needed.")
        else:
            lines.append("❌ **Insufficient evidence** to claim improvement. More tasks needed.")
        lines.append("")
        
        # Per-Category Breakdown
        if summary.category_stats:
            lines.append("## Category Breakdown")
            lines.append("")
            lines.append("| Category | Tasks | Wins | Losses | Ties | Win Rate | Avg Δ |")
            lines.append("|----------|-------|------|--------|------|----------|-------|")
            
            for cat in summary.category_stats:
                delta = cat.avg_selective_score - cat.avg_baseline_score
                lines.append(
                    f"| {cat.category} | {cat.total_tasks} | {cat.wins} | "
                    f"{cat.losses} | {cat.ties} | {cat.win_rate:.0%} | "
                    f"{delta:+.2f} |"
                )
            lines.append("")
        
        # Detailed Results
        lines.append("## Detailed Results")
        lines.append("")
        
        for eval_result in evaluations:
            lines.append(f"### {eval_result.task_id}")
            lines.append("")
            
            # Deterministic checks
            for condition, det_result in eval_result.deterministic.items():
                status = "✅" if det_result.passed else "⚠️"
                lines.append(f"**{condition}**: {status}")
                
                if det_result.must_contain_results:
                    missing = [k for k, v in det_result.must_contain_results.items() if not v]
                    if missing:
                        lines.append(f"  - Missing: {', '.join(missing)}")
                
                if det_result.must_not_contain_results:
                    found = [k for k, v in det_result.must_not_contain_results.items() if not v]
                    if found:
                        lines.append(f"  - Found (shouldn't): {', '.join(found)}")
            
            lines.append("")
            
            # Judge results
            for comparison, verdict in eval_result.judge_results.items():
                winner = "SELECTIVE" if verdict.winner == Verdict.B_WINS else (
                    "BASELINE" if verdict.winner == Verdict.A_WINS else "TIE"
                )
                lines.append(f"**{comparison}**: {winner}")
                lines.append(f"  - Scores: baseline={verdict.avg_score_a:.1f}, selective={verdict.avg_score_b:.1f}")
                lines.append(f"  - Agreement: {verdict.agreement_rate:.0%}, Position bias: {verdict.position_bias:.2f}")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def save_results(
        self,
        results: BenchmarkResults,
        evaluations: list[EvaluationResult],
        summary: StatisticalSummary,
        output_dir: Path,
    ) -> None:
        """Save all results to the output directory."""
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d")
        
        # Create dated subdirectory
        dated_dir = output_dir / timestamp
        dated_dir.mkdir(exist_ok=True)
        
        # Save raw outputs
        raw_outputs: list[dict] = []
        for result in results.task_results:
            raw_outputs.append({
                "task_id": result.task_id,
                "timestamp": result.timestamp,
                "outputs": {
                    k: {
                        "condition": v.condition.value,
                        "content": v.content,
                        "tokens_input": v.tokens_input,
                        "tokens_output": v.tokens_output,
                        "latency_ms": v.latency_ms,
                    }
                    for k, v in result.outputs.items()
                },
            })
        
        with open(dated_dir / "raw_outputs.jsonl", "w") as f:
            for output in raw_outputs:
                f.write(json.dumps(output) + "\n")
        
        # Save evaluation results
        eval_data: list[dict] = []
        for eval_result in evaluations:
            eval_data.append({
                "task_id": eval_result.task_id,
                "overall_winner": eval_result.overall_winner,
                "selective_wins": eval_result.selective_wins,
                "deterministic": {
                    k: {
                        "passed": v.passed,
                        "must_contain": v.must_contain_results,
                        "must_not_contain": v.must_not_contain_results,
                    }
                    for k, v in eval_result.deterministic.items()
                },
                "judge_results": {
                    k: {
                        "winner": v.winner.value,
                        "avg_score_a": v.avg_score_a,
                        "avg_score_b": v.avg_score_b,
                        "agreement_rate": v.agreement_rate,
                    }
                    for k, v in eval_result.judge_results.items()
                },
            })
        
        with open(dated_dir / "evaluations.json", "w") as f:
            json.dump(eval_data, f, indent=2)
        
        # Save statistical summary
        summary_data = {
            "n_tasks": summary.n_tasks,
            "wins": summary.wins,
            "losses": summary.losses,
            "ties": summary.ties,
            "win_rate": summary.win_rate,
            "effect_size_cohens_d": summary.effect_size_cohens_d,
            "effect_size_interpretation": summary.effect_size_interpretation,
            "p_value": summary.p_value,
            "test_name": summary.test_name,
            "significant": summary.significant,
            "ci_lower": summary.ci_lower,
            "ci_upper": summary.ci_upper,
            "claim_level": summary.claim_level(),
            "category_breakdown": {
                cat.category: {
                    "wins": cat.wins,
                    "losses": cat.losses,
                    "ties": cat.ties,
                    "win_rate": cat.win_rate,
                }
                for cat in summary.category_stats
            },
        }
        
        with open(dated_dir / "statistics.json", "w") as f:
            json.dump(summary_data, f, indent=2)
        
        # Generate and save markdown report
        report = self.generate_markdown_report(results, evaluations, summary)
        with open(dated_dir / "report.md", "w") as f:
            f.write(report)
        
        print(f"Results saved to {dated_dir}/")
