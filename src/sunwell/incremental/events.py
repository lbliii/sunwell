"""Events for incremental execution observability (RFC-074).

These events integrate with the existing RFC-060 event system to provide
visibility into cache behavior, skip decisions, and execution planning.

Example:
    >>> from sunwell.incremental.events import ArtifactSkipped, ExecutionPlanComputed
    >>>
    >>> event = ArtifactSkipped(
    ...     artifact_id="UserModel",
    ...     input_hash="a1b2c3d4",
    ...     reason="unchanged_success",
    ...     cached_at=1705123456.0,
    ...     skip_count=5,
    ... )
"""

from dataclasses import dataclass, field
from time import time
from typing import Any

from sunwell.agent.events import AgentEvent, EventType

# =============================================================================
# Event Data Classes
# =============================================================================


@dataclass(frozen=True, slots=True)
class ArtifactHashComputed:
    """Emitted when an artifact's input hash is computed.

    Attributes:
        artifact_id: The artifact this hash is for.
        input_hash: The computed input hash.
        dependency_count: Number of dependencies included in hash.
        timestamp: When the hash was computed.
    """

    artifact_id: str
    input_hash: str
    dependency_count: int
    timestamp: float = field(default_factory=time)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "artifact_id": self.artifact_id,
            "input_hash": self.input_hash,
            "dependency_count": self.dependency_count,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True, slots=True)
class ArtifactSkipped:
    """Emitted when an artifact is skipped due to cache hit.

    Attributes:
        artifact_id: The artifact that was skipped.
        input_hash: The matching input hash.
        reason: Why it was skipped (e.g., "unchanged_success").
        cached_at: When the cached result was created.
        skip_count: How many times this artifact has been skipped.
        timestamp: When the skip occurred.
    """

    artifact_id: str
    input_hash: str
    reason: str
    cached_at: float
    skip_count: int
    timestamp: float = field(default_factory=time)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "artifact_id": self.artifact_id,
            "input_hash": self.input_hash,
            "reason": self.reason,
            "cached_at": self.cached_at,
            "skip_count": self.skip_count,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True, slots=True)
class ArtifactCacheHit:
    """Emitted when cache lookup succeeds.

    Attributes:
        artifact_id: The artifact that had a cache hit.
        input_hash: The matching input hash.
        cached_status: Status of the cached execution.
        cache_age_seconds: How old the cached result is.
        timestamp: When the lookup occurred.
    """

    artifact_id: str
    input_hash: str
    cached_status: str
    cache_age_seconds: float
    timestamp: float = field(default_factory=time)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "artifact_id": self.artifact_id,
            "input_hash": self.input_hash,
            "cached_status": self.cached_status,
            "cache_age_seconds": self.cache_age_seconds,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True, slots=True)
class ArtifactCacheMiss:
    """Emitted when cache lookup fails.

    Attributes:
        artifact_id: The artifact that had a cache miss.
        computed_hash: The computed input hash.
        reason: Why the miss occurred (e.g., "no_cache", "hash_changed").
        previous_hash: The cached hash (if any).
        timestamp: When the lookup occurred.
    """

    artifact_id: str
    computed_hash: str
    reason: str
    previous_hash: str | None
    timestamp: float = field(default_factory=time)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "artifact_id": self.artifact_id,
            "computed_hash": self.computed_hash,
            "reason": self.reason,
            "previous_hash": self.previous_hash,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True, slots=True)
class ExecutionPlanComputed:
    """Emitted when execution plan is ready.

    Attributes:
        total_artifacts: Total number of artifacts in the graph.
        to_execute: Number of artifacts that will be executed.
        to_skip: Number of artifacts that will be skipped.
        skip_percentage: Percentage of work being skipped.
        estimated_savings_ms: Estimated time saved by caching.
        timestamp: When the plan was computed.
    """

    total_artifacts: int
    to_execute: int
    to_skip: int
    skip_percentage: float
    estimated_savings_ms: float
    timestamp: float = field(default_factory=time)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "total_artifacts": self.total_artifacts,
            "to_execute": self.to_execute,
            "to_skip": self.to_skip,
            "skip_percentage": self.skip_percentage,
            "estimated_savings_ms": self.estimated_savings_ms,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True, slots=True)
class ProvenanceQueryResult:
    """Emitted when a provenance query completes.

    Attributes:
        artifact_id: The starting artifact.
        query_type: Type of query ("upstream" or "downstream").
        result_count: Number of artifacts found.
        max_depth: Depth limit used.
        query_time_ms: Time taken for the query.
        timestamp: When the query completed.
    """

    artifact_id: str
    query_type: str
    result_count: int
    max_depth: int
    query_time_ms: float
    timestamp: float = field(default_factory=time)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "artifact_id": self.artifact_id,
            "query_type": self.query_type,
            "result_count": self.result_count,
            "max_depth": self.max_depth,
            "query_time_ms": self.query_time_ms,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True, slots=True)
class CacheInvalidation:
    """Emitted when cache entries are invalidated.

    Attributes:
        trigger_artifact: The artifact that triggered invalidation.
        invalidated_count: Number of artifacts invalidated.
        invalidated_ids: List of invalidated artifact IDs.
        timestamp: When the invalidation occurred.
    """

    trigger_artifact: str
    invalidated_count: int
    invalidated_ids: list[str]
    timestamp: float = field(default_factory=time)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "trigger_artifact": self.trigger_artifact,
            "invalidated_count": self.invalidated_count,
            "invalidated_ids": self.invalidated_ids,
            "timestamp": self.timestamp,
        }


# =============================================================================
# Event Factory Helpers
# =============================================================================


def artifact_hash_computed_event(
    artifact_id: str,
    input_hash: str,
    dependency_count: int,
    **kwargs: Any,
) -> AgentEvent:
    """Create an artifact hash computed event."""
    return AgentEvent(
        EventType.TASK_PROGRESS,
        {
            "stage": "hash_computed",
            "artifact_id": artifact_id,
            "input_hash": input_hash,
            "dependency_count": dependency_count,
            **kwargs,
        },
    )


def artifact_skipped_event(
    artifact_id: str,
    input_hash: str,
    reason: str,
    cached_at: float,
    skip_count: int,
    **kwargs: Any,
) -> AgentEvent:
    """Create an artifact skipped event."""
    return AgentEvent(
        EventType.TASK_COMPLETE,
        {
            "task_id": artifact_id,
            "skipped": True,
            "input_hash": input_hash,
            "reason": reason,
            "cached_at": cached_at,
            "skip_count": skip_count,
            "duration_ms": 0,
            **kwargs,
        },
    )


def artifact_cache_hit_event(
    artifact_id: str,
    input_hash: str,
    cached_status: str,
    cache_age_seconds: float,
    **kwargs: Any,
) -> AgentEvent:
    """Create an artifact cache hit event."""
    return AgentEvent(
        EventType.TASK_PROGRESS,
        {
            "stage": "cache_hit",
            "artifact_id": artifact_id,
            "input_hash": input_hash,
            "cached_status": cached_status,
            "cache_age_seconds": cache_age_seconds,
            **kwargs,
        },
    )


def artifact_cache_miss_event(
    artifact_id: str,
    computed_hash: str,
    reason: str,
    previous_hash: str | None = None,
    **kwargs: Any,
) -> AgentEvent:
    """Create an artifact cache miss event."""
    return AgentEvent(
        EventType.TASK_PROGRESS,
        {
            "stage": "cache_miss",
            "artifact_id": artifact_id,
            "computed_hash": computed_hash,
            "reason": reason,
            "previous_hash": previous_hash,
            **kwargs,
        },
    )


def execution_plan_computed_event(
    total_artifacts: int,
    to_execute: int,
    to_skip: int,
    skip_percentage: float,
    estimated_savings_ms: float = 0,
    **kwargs: Any,
) -> AgentEvent:
    """Create an execution plan computed event."""
    return AgentEvent(
        EventType.PLAN_WINNER,
        {
            "total_artifacts": total_artifacts,
            "to_execute": to_execute,
            "to_skip": to_skip,
            "skip_percentage": skip_percentage,
            "estimated_savings_ms": estimated_savings_ms,
            **kwargs,
        },
    )


def cache_invalidation_event(
    trigger_artifact: str,
    invalidated_count: int,
    invalidated_ids: list[str],
    **kwargs: Any,
) -> AgentEvent:
    """Create a cache invalidation event."""
    return AgentEvent(
        EventType.TASK_PROGRESS,
        {
            "stage": "cache_invalidation",
            "trigger_artifact": trigger_artifact,
            "invalidated_count": invalidated_count,
            "invalidated_ids": invalidated_ids,
            **kwargs,
        },
    )
