"""Storage configuration for SimulacrumStore."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StorageConfig:
    """Configuration for tiered storage."""

    hot_max_turns: int = 100
    """Max turns to keep in hot storage."""

    warm_max_age_hours: int = 24 * 7  # 1 week
    """Max age before moving to cold storage."""

    cold_compression: bool = True
    """Whether to compress cold storage."""

    auto_cleanup: bool = True
    """Auto-move old turns to cold storage."""

    # RFC-084: Auto-wiring configuration
    auto_topology: bool = True
    """Auto-extract topology relationships every N turns."""

    topology_interval: int = 10
    """Extract topology every N turns (when auto_topology=True)."""

    auto_cold_demotion: bool = True
    """Auto-demote warm chunks to cold tier based on age/count."""

    warm_retention_days: int = 7
    """Days to keep chunks in warm tier before demoting to cold."""

    max_warm_chunks: int = 50
    """Maximum warm chunks to keep (oldest demoted when exceeded)."""

    auto_summarize: bool = True
    """Auto-generate summaries for chunks (uses HeuristicSummarizer if no LLM)."""
