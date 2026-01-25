"""Incremental execution with content-addressed caching (RFC-074).

This package provides v2 incremental execution with:
- Content-addressed hashing (vs RFC-040's string equality)
- SQLite-backed cache with provenance tracking
- Work deduplication for parallel execution
- Explicit skip decisions with reason codes
- Goal→artifacts tracking for goal-based lookups

Example:
    >>> from pathlib import Path
    >>> from sunwell.agent.incremental import (
    ...     IncrementalExecutor,
    ...     ExecutionCache,
    ...     should_skip,
    ...     compute_input_hash,
    ... )
    >>>
    >>> # Initialize cache
    >>> cache = ExecutionCache(Path(".sunwell/cache/execution.db"))
    >>>
    >>> # Create executor
    >>> executor = IncrementalExecutor(graph, cache)
    >>>
    >>> # Preview what will be executed
    >>> plan = executor.plan_execution()
    >>> print(f"Will execute {len(plan.to_execute)}, skip {len(plan.to_skip)}")
    >>>
    >>> # Execute
    >>> result = await executor.execute(create_fn)
    >>>
    >>> # Record goal→artifacts mapping
    >>> cache.record_goal_execution("goal_hash", list(graph.keys()))
"""

# Hashing
# Cache
from sunwell.agent.incremental.cache import (
    CachedExecution,
    ExecutionCache,
    ExecutionStatus,
)

# Work deduplication
from sunwell.agent.incremental.deduper import (
    AsyncWorkDeduper,
    WorkDeduper,
)

# Events
from sunwell.agent.incremental.events import (
    ArtifactCacheHit,
    ArtifactCacheMiss,
    ArtifactHashComputed,
    ArtifactSkipped,
    CacheInvalidation,
    ExecutionPlanComputed,
    ProvenanceQueryResult,
    Serializable,
    artifact_cache_hit_event,
    artifact_cache_miss_event,
    artifact_hash_computed_event,
    artifact_skipped_event,
    cache_invalidation_event,
    execution_plan_computed_event,
)

# Executor
from sunwell.agent.incremental.executor import (
    CreateArtifactFn,
    ExecutionPlan,
    IncrementalExecutor,
    IncrementalResult,
    SkipDecision,
    SkipReason,
    should_skip,
)
from sunwell.agent.incremental.hasher import (
    ArtifactHash,
    compute_input_hash,
    compute_spec_hash,
    create_artifact_hash,
)

__all__ = [
    # Hashing
    "ArtifactHash",
    "compute_input_hash",
    "compute_spec_hash",
    "create_artifact_hash",
    # Cache
    "CachedExecution",
    "ExecutionCache",
    "ExecutionStatus",
    # Executor
    "CreateArtifactFn",
    "ExecutionPlan",
    "IncrementalExecutor",
    "IncrementalResult",
    "should_skip",
    "SkipDecision",
    "SkipReason",
    # Work deduplication
    "AsyncWorkDeduper",
    "WorkDeduper",
    # Events - Data classes
    "ArtifactCacheHit",
    "ArtifactCacheMiss",
    "ArtifactHashComputed",
    "ArtifactSkipped",
    "CacheInvalidation",
    "ExecutionPlanComputed",
    "ProvenanceQueryResult",
    # Events - Protocol
    "Serializable",
    # Events - Factory functions
    "artifact_cache_hit_event",
    "artifact_cache_miss_event",
    "artifact_hash_computed_event",
    "artifact_skipped_event",
    "cache_invalidation_event",
    "execution_plan_computed_event",
]
