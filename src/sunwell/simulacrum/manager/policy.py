"""Policy classes for simulacrum lifecycle management.

RFC-025: Extracted from manager.py to slim it down.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SpawnPolicy:
    """Policy for automatic simulacrum spawning."""

    enabled: bool = True
    """Whether auto-spawning is enabled."""

    novelty_threshold: float = 0.7
    """How different a query must be from existing simulacrums to trigger spawn (0-1)."""

    min_queries_before_spawn: int = 3
    """Minimum queries in a new domain before spawning (prevents premature spawning)."""

    domain_coherence_threshold: float = 0.5
    """How related accumulated queries must be to form a coherent simulacrum."""

    max_simulacrums: int = 20
    """Maximum simulacrums to prevent unbounded growth."""

    auto_name: bool = True
    """Auto-generate simulacrum names from detected topics."""


@dataclass
class LifecyclePolicy:
    """Policy for simulacrum lifecycle management (archival, cleanup, shrinking)."""

    # Staleness thresholds
    stale_days: int = 30
    """Days without access before a simulacrum is considered stale."""

    archive_days: int = 90
    """Days without access before auto-archiving to cold storage."""

    # Size thresholds
    min_useful_nodes: int = 3
    """Simulacrums with fewer nodes may be candidates for cleanup."""

    min_useful_learnings: int = 1
    """Simulacrums with no learnings may be candidates for cleanup."""

    # Auto-merge thresholds
    merge_similarity_threshold: float = 0.6
    """Simulacrums with this much domain overlap are merge candidates."""

    # Cleanup behavior
    auto_archive: bool = True
    """Automatically archive stale simulacrums."""

    auto_merge_empty: bool = True
    """Auto-merge empty simulacrums into similar ones."""

    protect_recently_spawned_days: int = 7
    """Don't cleanup simulacrums spawned within this many days."""
