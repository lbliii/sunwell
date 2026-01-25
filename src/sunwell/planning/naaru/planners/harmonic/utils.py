"""Utility functions for harmonic planning."""

import re

from sunwell.planning.naaru.planners.metrics import PlanMetrics, PlanMetricsV2

# Stopwords for keyword extraction (fast, no LLM)
_STOPWORDS: frozenset[str] = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", "of",
    "with", "by", "from", "as", "is", "was", "are", "were", "been", "be", "have",
    "has", "had", "do", "does", "did", "will", "would", "could", "should", "may",
    "might", "must", "shall", "can", "need", "dare", "ought", "used", "it", "its",
    "this", "that", "these", "those", "i", "you", "he", "she", "we", "they", "me",
    "him", "her", "us", "them", "my", "your", "his", "our", "their", "what", "which",
    "who", "whom", "where", "when", "why", "how", "all", "each", "every", "both",
    "few", "more", "most", "other", "some", "such", "no", "nor", "not", "only",
    "same", "so", "than", "too", "very", "just", "also", "now", "here", "there",
    "then", "once", "into", "onto", "upon", "after", "before", "above", "below",
    "between", "under", "over", "through", "during", "without", "within", "along",
    "following", "across", "behind", "beyond", "plus", "except", "about", "like",
    "create", "build", "make", "add", "implement", "write", "using", "use",
})

# Pre-compiled regex patterns for performance (avoid recompiling per-call)
_RE_WORD_SPLIT = re.compile(r"[^a-zA-Z0-9]+")


def extract_keywords(text: str) -> list[str]:
    """Extract significant keywords from text (fast, no LLM).

    RFC-116: Used for lightweight semantic checking.
    Filters stopwords and short words, returns lowercase keywords.
    """
    if not text:
        return []
    # Split on non-alphanumeric, lowercase, filter
    words = _RE_WORD_SPLIT.split(text.lower())
    return [w for w in words if len(w) > 3 and w not in _STOPWORDS]


def get_effective_score(metrics: PlanMetrics | PlanMetricsV2) -> float:
    """Get the effective score based on scoring version.

    RFC-116: V2 metrics use score_v2, V1 metrics use score.
    """
    if isinstance(metrics, PlanMetricsV2):
        return metrics.score_v2
    return metrics.score


def metrics_to_dict(metrics: PlanMetrics | PlanMetricsV2) -> dict[str, int | float | bool | list[int]]:
    """Convert metrics to dict for event emission."""
    base = {
        "depth": metrics.depth,
        "width": metrics.width,
        "leaf_count": metrics.leaf_count,
        "artifact_count": metrics.artifact_count,
        "parallelism_factor": metrics.parallelism_factor,
        "balance_factor": metrics.balance_factor,
        "file_conflicts": metrics.file_conflicts,
        "estimated_waves": metrics.estimated_waves,
        "score_v1": metrics.score,
    }
    if isinstance(metrics, PlanMetricsV2):
        base.update({
            "score_v2": metrics.score_v2,
            "wave_sizes": list(metrics.wave_sizes),
            "avg_wave_width": metrics.avg_wave_width,
            "parallel_work_ratio": metrics.parallel_work_ratio,
            "wave_variance": metrics.wave_variance,
            "keyword_coverage": metrics.keyword_coverage,
            "has_convergence": metrics.has_convergence,
            "depth_utilization": metrics.depth_utilization,
        })
    return base


def format_selection_reason(
    best_metrics: PlanMetrics | PlanMetricsV2,
    candidate_count: int,
) -> str:
    """Format selection reason for winner event.

    RFC-116: Different descriptions for V1 vs V2 scoring.
    """
    if candidate_count == 1:
        return "Only candidate generated"

    if isinstance(best_metrics, PlanMetricsV2):
        return (
            "Highest V2 score (parallel_work_ratio + depth_utilization "
            "+ keyword_coverage + wave_balance - conflicts)"
        )
    return "Highest V1 score (parallelism + balance - depth penalty)"
