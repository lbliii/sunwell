"""Incremental rebuild support for RFC-040.

This module provides change detection and incremental execution:
- Detect what changed since last execution
- Compute invalidation cascade (dependents of changed artifacts)
- Execute only what's needed

Like Make or Bazel, Sunwell can now skip unchanged work.

Example:
    >>> detector = ChangeDetector()
    >>> changes = detector.detect(graph, previous_execution)
    >>>
    >>> executor = IncrementalExecutor(store=store)
    >>> result = await executor.execute(graph, create_fn, goal)
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from sunwell.naaru.artifacts import ArtifactGraph, ArtifactSpec
from sunwell.naaru.executor import ArtifactResult, ExecutionResult
from sunwell.naaru.persistence import (
    ExecutionStatus,
    PlanStore,
    SavedExecution,
    TraceLogger,
    hash_file,
    hash_goal,
)

# Type alias for artifact creation function
CreateArtifactFn = Callable[[ArtifactSpec], Awaitable[str]]


# =============================================================================
# Change Detection
# =============================================================================


@dataclass
class ChangeReport:
    """Report of what changed between executions.

    Attributes:
        added: New artifacts (not in previous plan)
        removed: Removed artifacts (in previous but not current)
        contract_changed: Artifacts with modified contracts
        deps_changed: Artifacts with modified dependencies
        output_modified: Artifacts with modified output files
    """

    added: set[str] = field(default_factory=set)
    removed: set[str] = field(default_factory=set)
    contract_changed: set[str] = field(default_factory=set)
    deps_changed: set[str] = field(default_factory=set)
    output_modified: set[str] = field(default_factory=set)

    @property
    def all_changed(self) -> set[str]:
        """All artifacts that need re-execution."""
        return (
            self.added | self.contract_changed | self.deps_changed | self.output_modified
        )

    @property
    def has_changes(self) -> bool:
        """Check if any changes were detected."""
        return bool(self.all_changed) or bool(self.removed)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "added": list(self.added),
            "removed": list(self.removed),
            "contract_changed": list(self.contract_changed),
            "deps_changed": list(self.deps_changed),
            "output_modified": list(self.output_modified),
            "total_changed": len(self.all_changed),
        }


@dataclass
class ChangeDetector:
    """Detects what changed since last execution.

    Compares artifacts by:
    1. Presence (new or removed)
    2. Contract (specification changed)
    3. Dependencies (requires changed)
    4. Output (file content changed)

    Example:
        >>> detector = ChangeDetector()
        >>> changes = detector.detect(new_graph, previous_execution)
        >>> print(f"Changed: {changes.all_changed}")
    """

    check_output_files: bool = True
    """Whether to check output file hashes."""

    def detect(
        self,
        graph: ArtifactGraph,
        previous: SavedExecution,
    ) -> ChangeReport:
        """Detect all changes between current graph and previous execution.

        Args:
            graph: Current artifact graph
            previous: Previous execution state

        Returns:
            ChangeReport with all detected changes
        """
        changes = ChangeReport()

        # Check each artifact in current graph
        for artifact_id in graph:
            artifact = graph[artifact_id]

            # New artifact (not in previous plan)
            if artifact_id not in previous.graph:
                changes.added.add(artifact_id)
                continue

            prev_artifact = previous.graph[artifact_id]

            # Contract changed (spec modified)
            if artifact.contract != prev_artifact.contract:
                changes.contract_changed.add(artifact_id)
                continue

            # Dependencies changed
            if artifact.requires != prev_artifact.requires:
                changes.deps_changed.add(artifact_id)
                continue

            # Output file modified externally
            if self.check_output_files and artifact.produces_file:
                current_hash = hash_file(Path(artifact.produces_file))
                prev_hash = previous.content_hashes.get(artifact_id)

                if current_hash is not None and current_hash != prev_hash:
                    changes.output_modified.add(artifact_id)

        # Removed artifacts (in previous but not current)
        for artifact_id in previous.graph:
            if artifact_id not in graph:
                changes.removed.add(artifact_id)

        return changes


# =============================================================================
# Invalidation Cascade
# =============================================================================


def find_invalidated(
    graph: ArtifactGraph,
    changed_ids: set[str],
) -> set[str]:
    """Find all artifacts invalidated by changes.

    Uses BFS to cascade from changed artifacts to their dependents.
    If A changed and B depends on A, B is invalidated.

    Args:
        graph: The artifact graph
        changed_ids: Set of directly changed artifact IDs

    Returns:
        Set of all invalidated artifact IDs (includes changed_ids)
    """
    invalidated = set(changed_ids)

    # BFS from changed artifacts to their dependents
    queue = list(changed_ids)
    while queue:
        artifact_id = queue.pop(0)
        for dependent_id in graph.get_dependents(artifact_id):
            if dependent_id not in invalidated:
                invalidated.add(dependent_id)
                queue.append(dependent_id)

    return invalidated


def compute_rebuild_set(
    graph: ArtifactGraph,
    changes: ChangeReport,
    previous: SavedExecution | None = None,
) -> set[str]:
    """Compute minimal set of artifacts to rebuild.

    Args:
        graph: Current artifact graph
        changes: Detected changes
        previous: Previous execution (for incomplete check)

    Returns:
        Set of artifact IDs that need to be rebuilt
    """
    # Start with directly changed artifacts
    to_rebuild = changes.all_changed.copy()

    # Cascade to dependents
    to_rebuild = find_invalidated(graph, to_rebuild)

    # Add incomplete artifacts from previous execution
    if previous:
        incomplete = previous.pending_ids
        to_rebuild |= incomplete

        # Also add failed artifacts (may want to retry)
        to_rebuild |= previous.failed_ids

    return to_rebuild


# =============================================================================
# Incremental Executor
# =============================================================================


@dataclass
class IncrementalExecutor:
    """Executes artifact graphs with incremental rebuild support.

    Like a build system, only rebuilds what changed and its dependents.

    Attributes:
        store: PlanStore for loading/saving executions
        detector: ChangeDetector for finding changes
        verify: Whether to verify artifacts after creation
        trace_enabled: Whether to write trace logs

    Example:
        >>> executor = IncrementalExecutor(store=PlanStore())
        >>> result = await executor.execute(graph, create_fn, "Build API")
    """

    store: PlanStore = field(default_factory=PlanStore)
    detector: ChangeDetector = field(default_factory=ChangeDetector)
    verify: bool = True
    trace_enabled: bool = True

    async def execute(
        self,
        graph: ArtifactGraph,
        create_fn: CreateArtifactFn,
        goal: str,
        force_rebuild: bool = False,
        on_progress: Callable[[str], None] | None = None,
    ) -> ExecutionResult:
        """Execute with incremental rebuild support.

        Args:
            graph: The artifact graph to execute
            create_fn: Function to create artifacts
            goal: Goal text (for persistence lookup)
            force_rebuild: If True, ignore previous execution
            on_progress: Optional progress callback

        Returns:
            ExecutionResult with completed/failed artifacts
        """
        import asyncio

        goal_hash = hash_goal(goal)

        # Initialize trace logger
        trace = TraceLogger(goal_hash) if self.trace_enabled else None

        # Load previous execution if exists
        previous = self.store.load(goal_hash) if not force_rebuild else None

        # Determine what needs to run
        if previous and not force_rebuild:
            changes = self.detector.detect(graph, previous)
            to_rebuild = compute_rebuild_set(graph, changes, previous)

            if trace:
                trace.log_event(
                    "incremental_analysis",
                    added=len(changes.added),
                    contract_changed=len(changes.contract_changed),
                    deps_changed=len(changes.deps_changed),
                    output_modified=len(changes.output_modified),
                    total_rebuild=len(to_rebuild),
                )

            if on_progress:
                skip_count = len(graph) - len(to_rebuild)
                on_progress(
                    f"📊 Incremental: {skip_count} unchanged, {len(to_rebuild)} to rebuild"
                )
        else:
            to_rebuild = set(graph)
            changes = None

            if trace:
                trace.log_event("full_rebuild", artifact_count=len(graph))

        # Create SavedExecution
        execution = SavedExecution(
            goal=goal,
            goal_hash=goal_hash,
            graph=graph,
            status=ExecutionStatus.IN_PROGRESS,
            created_at=previous.created_at if previous else datetime.now(),
            updated_at=datetime.now(),
        )

        # Copy completed artifacts from previous (if not rebuilding them)
        if previous:
            for artifact_id, completion in previous.completed.items():
                if artifact_id not in to_rebuild and artifact_id in graph:
                    execution.completed[artifact_id] = completion
                    execution.content_hashes[artifact_id] = completion.content_hash

        # Get execution waves
        waves = graph.execution_waves()

        if trace:
            trace.log_event("plan_created", artifact_count=len(graph), waves=len(waves))

        # Execute waves
        result = ExecutionResult()
        result.model_distribution = {"small": 0, "medium": 0, "large": 0}

        for wave_num, wave in enumerate(waves):
            # Filter to artifacts that need rebuilding
            to_execute = [aid for aid in wave if aid in to_rebuild]

            if not to_execute:
                # Skip this wave entirely
                continue

            if on_progress:
                on_progress(f"Wave {wave_num + 1}: {', '.join(to_execute)}")

            if trace:
                trace.log_event("wave_start", wave=wave_num, artifacts=to_execute)

            # Execute artifacts in parallel
            wave_results = await asyncio.gather(
                *[self._execute_artifact(graph, aid, create_fn) for aid in to_execute],
                return_exceptions=True,
            )

            # Process results
            for artifact_id, wave_result in zip(to_execute, wave_results, strict=True):
                if isinstance(wave_result, Exception):
                    result.failed[artifact_id] = str(wave_result)
                    execution.mark_failed(artifact_id, str(wave_result))

                    if trace:
                        trace.log_event(
                            "artifact_failed",
                            id=artifact_id,
                            error=str(wave_result),
                        )
                elif wave_result.success:
                    result.completed[artifact_id] = wave_result
                    result.model_distribution[wave_result.model_tier] += 1
                    execution.mark_completed(wave_result)

                    if trace:
                        trace.log_event(
                            "artifact_complete",
                            id=artifact_id,
                            duration_ms=wave_result.duration_ms,
                            verified=wave_result.verified,
                        )
                else:
                    error = wave_result.error or "Unknown error"
                    result.failed[artifact_id] = error
                    execution.mark_failed(artifact_id, error)

            if trace:
                trace.log_event("wave_complete", wave=wave_num)

            # Save checkpoint after each wave
            self.store.save(execution)

        # Final status
        execution.status = (
            ExecutionStatus.COMPLETED if execution.is_complete else ExecutionStatus.PAUSED
        )
        self.store.save(execution)

        if trace:
            trace.log_event(
                "execution_complete",
                completed=len(result.completed),
                failed=len(result.failed),
                status=execution.status.value,
            )

        return result

    async def _execute_artifact(
        self,
        graph: ArtifactGraph,
        artifact_id: str,
        create_fn: CreateArtifactFn,
    ) -> ArtifactResult:
        """Execute a single artifact.

        Args:
            graph: The artifact graph
            artifact_id: ID of artifact to create
            create_fn: Function to create the artifact

        Returns:
            ArtifactResult with content and metadata
        """
        from sunwell.naaru.artifacts import select_model_tier

        artifact = graph[artifact_id]
        model_tier = select_model_tier(artifact, graph)

        start = datetime.now()

        try:
            content = await create_fn(artifact)
            duration_ms = int((datetime.now() - start).total_seconds() * 1000)

            return ArtifactResult(
                artifact_id=artifact_id,
                content=content,
                verified=False,  # Verification can be added later
                model_tier=model_tier,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((datetime.now() - start).total_seconds() * 1000)
            return ArtifactResult(
                artifact_id=artifact_id,
                model_tier=model_tier,
                duration_ms=duration_ms,
                error=str(e),
            )


# =============================================================================
# Plan Preview
# =============================================================================


# Cost estimates per model tier (rough approximations)
COST_PER_ARTIFACT = {
    "small": {"tokens": 1000, "cost_usd": 0.001, "duration_s": 3},
    "medium": {"tokens": 2500, "cost_usd": 0.003, "duration_s": 8},
    "large": {"tokens": 5000, "cost_usd": 0.008, "duration_s": 15},
}


@dataclass
class PlanPreview:
    """Preview of execution plan with cost estimates.

    Attributes:
        graph: The artifact graph
        waves: Execution waves
        model_distribution: Count per model tier
        estimated_tokens: Total estimated tokens
        estimated_cost_usd: Estimated cost in USD
        estimated_duration_seconds: Estimated wall-clock time
        previous: Previous execution (for comparison)
        changes: Detected changes (for incremental)
    """

    graph: ArtifactGraph
    waves: list[list[str]] = field(default_factory=list)
    model_distribution: dict[str, int] = field(
        default_factory=lambda: {"small": 0, "medium": 0, "large": 0}
    )

    # Estimates
    estimated_tokens: int = 0
    estimated_cost_usd: float = 0.0
    estimated_duration_seconds: float = 0.0

    # Comparison
    previous: SavedExecution | None = None
    changes: ChangeReport | None = None
    to_rebuild: set[str] = field(default_factory=set)

    @classmethod
    def create(
        cls,
        graph: ArtifactGraph,
        goal: str | None = None,
        store: PlanStore | None = None,
    ) -> PlanPreview:
        """Create a preview for an artifact graph.

        Args:
            graph: The artifact graph
            goal: Optional goal for loading previous execution
            store: Optional store for loading previous execution

        Returns:
            PlanPreview with estimates
        """
        from sunwell.naaru.artifacts import select_model_tier

        # Get waves
        waves = graph.execution_waves()

        # Compute model distribution
        distribution = {"small": 0, "medium": 0, "large": 0}
        for artifact_id in graph:
            artifact = graph[artifact_id]
            tier = select_model_tier(artifact, graph)
            distribution[tier] += 1

        # Compute estimates
        total_tokens = sum(
            COST_PER_ARTIFACT[tier]["tokens"] * count
            for tier, count in distribution.items()
        )
        total_cost = sum(
            COST_PER_ARTIFACT[tier]["cost_usd"] * count
            for tier, count in distribution.items()
        )

        # Duration estimate (parallel execution)
        # Each wave runs in parallel, so sum the max duration per wave
        duration = 0.0
        for wave in waves:
            wave_durations = []
            for artifact_id in wave:
                artifact = graph[artifact_id]
                tier = select_model_tier(artifact, graph)
                wave_durations.append(COST_PER_ARTIFACT[tier]["duration_s"])
            if wave_durations:
                duration += max(wave_durations)

        preview = cls(
            graph=graph,
            waves=waves,
            model_distribution=distribution,
            estimated_tokens=total_tokens,
            estimated_cost_usd=total_cost,
            estimated_duration_seconds=duration,
        )

        # Load previous if available
        if goal and store:
            previous = store.find_by_goal(goal)
            if previous:
                preview.previous = previous
                detector = ChangeDetector()
                preview.changes = detector.detect(graph, previous)
                preview.to_rebuild = compute_rebuild_set(graph, preview.changes, previous)

        return preview

    @property
    def parallelization_factor(self) -> float:
        """Calculate parallelization factor.

        Higher is better - indicates more parallel work.
        """
        if not self.waves:
            return 1.0
        return len(self.graph) / len(self.waves)

    @property
    def skip_count(self) -> int:
        """Number of artifacts that will be skipped (incremental)."""
        if not self.to_rebuild:
            return 0
        return len(self.graph) - len(self.to_rebuild)

    @property
    def savings_percent(self) -> float:
        """Percentage of work saved by incremental rebuild."""
        if not self.previous or not self.to_rebuild:
            return 0.0
        return (self.skip_count / len(self.graph)) * 100

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "artifact_count": len(self.graph),
            "wave_count": len(self.waves),
            "model_distribution": self.model_distribution,
            "parallelization_factor": self.parallelization_factor,
            "estimated_tokens": self.estimated_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "estimated_duration_seconds": self.estimated_duration_seconds,
            "incremental": {
                "has_previous": self.previous is not None,
                "to_rebuild": len(self.to_rebuild),
                "skip_count": self.skip_count,
                "savings_percent": self.savings_percent,
            }
            if self.previous
            else None,
            "changes": self.changes.to_dict() if self.changes else None,
        }


# =============================================================================
# Utility Functions
# =============================================================================


def display_incremental_analysis(
    changes: ChangeReport,
    to_rebuild: set[str],
    total_artifacts: int,
) -> str:
    """Generate display string for incremental analysis.

    Args:
        changes: Detected changes
        to_rebuild: Set of artifacts to rebuild
        total_artifacts: Total artifact count

    Returns:
        Formatted display string
    """
    lines = ["📊 Change Analysis:"]

    if changes.added:
        lines.append(f"   ✨ Added: {len(changes.added)} ({', '.join(sorted(changes.added)[:3])}...)")
    if changes.contract_changed:
        lines.append(f"   📝 Contract changed: {len(changes.contract_changed)}")
    if changes.deps_changed:
        lines.append(f"   🔗 Dependencies changed: {len(changes.deps_changed)}")
    if changes.output_modified:
        lines.append(f"   📄 Output modified: {len(changes.output_modified)}")

    skip_count = total_artifacts - len(to_rebuild)
    lines.append("")
    lines.append("🎯 Rebuild Plan:")
    lines.append(f"   Skip: {skip_count} artifacts (unchanged)")
    lines.append(f"   Build: {len(to_rebuild)} artifacts")
    lines.append(f"   Savings: {(skip_count / total_artifacts) * 100:.0f}%")

    return "\n".join(lines)
