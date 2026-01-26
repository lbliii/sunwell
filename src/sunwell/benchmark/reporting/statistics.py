"""Statistical calculations for benchmark analysis.

Implements RFC-018 statistical rigor requirements:
- Mann-Whitney U / Wilcoxon signed-rank tests
- Cohen's d effect size
- Bootstrap confidence intervals
"""


import numpy as np

from sunwell.benchmark.types import StatisticalSummary

__all__ = [
    "bootstrap_ci",
    "cohens_d",
    "empty_summary",
    "interpret_effect_size",
    "significance_test",
]


def significance_test(
    selective: np.ndarray,
    baseline: np.ndarray,
) -> tuple[float, float, str]:
    """Run appropriate significance test.

    Uses Wilcoxon signed-rank for paired data (same tasks),
    Mann-Whitney U for independent samples.

    Returns:
        Tuple of (p_value, test_statistic, test_name).
        Returns (1.0, 0.0, "insufficient_data") if arrays are too small.
    """
    # Need at least 2 samples for meaningful statistical test
    if len(selective) < 2 or len(baseline) < 2:
        return 1.0, 0.0, "insufficient_data"

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


def cohens_d(
    selective: np.ndarray,
    baseline: np.ndarray,
) -> float:
    """Calculate Cohen's d effect size.

    Returns 0.0 for insufficient data (need n >= 2 in each group for
    meaningful variance estimation with ddof=1).
    """
    # Need at least 2 samples per group for ddof=1 variance
    if len(selective) < 2 or len(baseline) < 2:
        return 0.0

    mean_diff = np.mean(selective) - np.mean(baseline)

    # Pooled standard deviation
    n1, n2 = len(selective), len(baseline)
    var1, var2 = np.var(selective, ddof=1), np.var(baseline, ddof=1)

    # Handle NaN from variance calculation (shouldn't happen with n>=2, but defensive)
    if np.isnan(var1) or np.isnan(var2):
        return 0.0

    # Handle zero variance edge case
    if var1 == 0 and var2 == 0:
        return 0.0 if mean_diff == 0 else float('inf') * np.sign(mean_diff)

    pooled_std = np.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))

    if pooled_std == 0 or np.isnan(pooled_std):
        return 0.0

    return float(mean_diff / pooled_std)


def interpret_effect_size(d: float) -> str:
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


def bootstrap_ci(
    selective: np.ndarray,
    baseline: np.ndarray,
    ci_level: float = 0.95,
    bootstrap_samples: int = 1000,
) -> tuple[float, float]:
    """Calculate bootstrap confidence intervals for mean difference.

    Returns (0.0, 0.0) if insufficient data for meaningful CI estimation.
    Need at least 2 samples per group for bootstrap to produce variance.
    """
    # Need at least 2 samples per group for meaningful bootstrap CI
    if len(selective) < 2 or len(baseline) < 2:
        return 0.0, 0.0

    rng = np.random.default_rng(42)  # Reproducible

    diffs: list[float] = []
    n_sel, n_base = len(selective), len(baseline)

    for _ in range(bootstrap_samples):
        # Resample with replacement
        sel_sample = rng.choice(selective, size=n_sel, replace=True)
        base_sample = rng.choice(baseline, size=n_base, replace=True)

        diffs.append(float(np.mean(sel_sample) - np.mean(base_sample)))

    diffs_arr = np.array(diffs)
    alpha = (1 - ci_level) / 2

    ci_lower = float(np.percentile(diffs_arr, alpha * 100))
    ci_upper = float(np.percentile(diffs_arr, (1 - alpha) * 100))

    return ci_lower, ci_upper


def empty_summary() -> StatisticalSummary:
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
