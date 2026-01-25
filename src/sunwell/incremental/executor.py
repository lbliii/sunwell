"""Incremental executor with content-addressed caching for RFC-074.

Executes artifact graphs with change detection, skipping unchanged artifacts.
Preserves RFC-040 integrations:
- RFC-060 event callbacks
- RFC-067 integration verification (stub detection)
- Trace logging

Inspired by Pachyderm's skippableDatum pattern:
https://github.com/pachyderm/pachyderm/blob/master/src/server/worker/pipeline/transform/worker.go

Example:
    >>> cache = ExecutionCache(Path(".sunwell/cache/execution.db"))
    >>> executor = IncrementalExecutor(graph, cache)
    >>> result = await executor.execute(create_fn)
"""

import asyncio
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sunwell.incremental.cache import ExecutionCache, ExecutionStatus
from sunwell.incremental.hasher import compute_input_hash, compute_spec_hash

if TYPE_CHECKING:
    from sunwell.naaru.artifacts import ArtifactGraph, ArtifactSpec

# Type alias for artifact creation function
CreateArtifactFn = Callable[["ArtifactSpec"], Awaitable[str]]


class SkipReason(Enum):
    """Why an artifact was or wasn't skipped.

    Provides explicit observability into skip decisions.
    """

    # Can skip
    UNCHANGED_SUCCESS = "unchanged_success"
    """Same hash as previous successful execution."""

    # Cannot skip
    NO_CACHE = "no_cache"
    """No previous execution in cache."""

    HASH_CHANGED = "hash_changed"
    """Input hash differs from cached execution."""

    PREVIOUS_FAILED = "previous_failed"
    """Previous execution failed, need to retry."""

    FORCE_RERUN = "force_rerun"
    """User requested re-execution."""

    DEPENDENCY_CHANGED = "dependency_changed"
    """Upstream artifact changed (transitive invalidation)."""

    PREVIOUS_INCOMPLETE = "previous_incomplete"
    """Previous execution was interrupted (running/pending)."""


@dataclass(frozen=True, slots=True)
class SkipDecision:
    """Decision about whether to skip an artifact.

    Provides all information needed to understand why an artifact
    was or wasn't skipped.

    Attributes:
        artifact_id: The artifact this decision is for.
        can_skip: Whether the artifact can be skipped.
        reason: Why the decision was made.
        current_hash: Computed input hash for current state.
        previous_hash: Cached input hash (if available).
        cached_result: Cached result data (if skipping).
    """

    artifact_id: str
    can_skip: bool
    reason: SkipReason
    current_hash: str
    previous_hash: str | None = None
    cached_result: dict[str, Any] | None = None


def should_skip(
    spec: ArtifactSpec,
    cache: ExecutionCache,
    dependency_hashes: dict[str, str],
    force_rerun: bool = False,
) -> SkipDecision:
    """Determine if an artifact can be skipped.

    Inspired by Pachyderm's skippableDatum logic:
    Skip conditions (ALL must be true):
    1. Previous execution exists in cache
    2. Previous execution completed successfully
    3. Current input hash matches previous input hash
    4. No force rerun requested

    Args:
        spec: The artifact specification.
        cache: Execution cache for lookups.
        dependency_hashes: Map of artifact_id → input_hash for dependencies.
        force_rerun: If True, never skip.

    Returns:
        SkipDecision with can_skip, reason, and cached data.
    """
    current_hash = compute_input_hash(spec, dependency_hashes)

    # Check force rerun
    if force_rerun:
        return SkipDecision(
            artifact_id=spec.id,
            can_skip=False,
            reason=SkipReason.FORCE_RERUN,
            current_hash=current_hash,
        )

    # Check cache
    cached = cache.get(spec.id)

    if cached is None:
        return SkipDecision(
            artifact_id=spec.id,
            can_skip=False,
            reason=SkipReason.NO_CACHE,
            current_hash=current_hash,
        )

    # Check previous status
    if cached.status == ExecutionStatus.FAILED:
        return SkipDecision(
            artifact_id=spec.id,
            can_skip=False,
            reason=SkipReason.PREVIOUS_FAILED,
            current_hash=current_hash,
            previous_hash=cached.input_hash,
        )

    if cached.status in (ExecutionStatus.PENDING, ExecutionStatus.RUNNING):
        return SkipDecision(
            artifact_id=spec.id,
            can_skip=False,
            reason=SkipReason.PREVIOUS_INCOMPLETE,
            current_hash=current_hash,
            previous_hash=cached.input_hash,
        )

    # Check hash match
    if current_hash != cached.input_hash:
        return SkipDecision(
            artifact_id=spec.id,
            can_skip=False,
            reason=SkipReason.HASH_CHANGED,
            current_hash=current_hash,
            previous_hash=cached.input_hash,
        )

    # All conditions met — can skip!
    return SkipDecision(
        artifact_id=spec.id,
        can_skip=True,
        reason=SkipReason.UNCHANGED_SUCCESS,
        current_hash=current_hash,
        previous_hash=cached.input_hash,
        cached_result=cached.result,
    )


@dataclass(slots=True)
class ExecutionPlan:
    """Plan for which artifacts to execute vs skip.

    Attributes:
        to_execute: Artifact IDs that need execution.
        to_skip: Artifact IDs that can be skipped.
        decisions: Full skip decisions for all artifacts.
        computed_hashes: Input hashes computed during planning.
    """

    to_execute: list[str]
    to_skip: list[str]
    decisions: dict[str, SkipDecision]
    computed_hashes: dict[str, str]

    @property
    def total(self) -> int:
        """Total number of artifacts."""
        return len(self.to_execute) + len(self.to_skip)

    @property
    def skip_percentage(self) -> float:
        """Percentage of artifacts that will be skipped."""
        if self.total == 0:
            return 0.0
        return len(self.to_skip) / self.total * 100

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "total_artifacts": self.total,
            "to_execute": len(self.to_execute),
            "to_skip": len(self.to_skip),
            "skip_percentage": self.skip_percentage,
            "execute_ids": self.to_execute,
            "skip_ids": self.to_skip,
            "decisions": {
                aid: {
                    "can_skip": d.can_skip,
                    "reason": d.reason.value,
                    "current_hash": d.current_hash,
                    "previous_hash": d.previous_hash,
                }
                for aid, d in self.decisions.items()
            },
        }


@dataclass(slots=True)
class IncrementalResult:
    """Result of incremental execution.

    Attributes:
        completed: Successfully completed artifacts with results.
        failed: Failed artifacts with error messages.
        skipped: Skipped artifacts with cached results.
        run_id: Unique identifier for this execution run.
        duration_ms: Total execution time.
    """

    completed: dict[str, dict[str, Any]]
    failed: dict[str, str]
    skipped: dict[str, dict[str, Any] | None]
    run_id: str
    duration_ms: float = 0

    @property
    def success(self) -> bool:
        """Whether execution completed without failures."""
        return len(self.failed) == 0

    @property
    def total(self) -> int:
        """Total artifacts processed."""
        return len(self.completed) + len(self.failed) + len(self.skipped)


class IncrementalExecutor:
    """Execute artifact graphs with change detection.

    Computes hashes in topological order, skipping unchanged artifacts.

    Preserves RFC-040 integration features:
    - RFC-060 event callbacks
    - RFC-067 integration verification (stub detection)
    - Trace logging

    Example:
        >>> cache = ExecutionCache(Path(".sunwell/cache/execution.db"))
        >>> executor = IncrementalExecutor(graph, cache)
        >>>
        >>> # Preview what will be executed
        >>> plan = executor.plan_execution()
        >>> print(f"Will execute {len(plan.to_execute)}, skip {len(plan.to_skip)}")
        >>>
        >>> # Execute
        >>> result = await executor.execute(create_fn)
    """

    def __init__(
        self,
        graph: ArtifactGraph,
        cache: ExecutionCache,
        # Preserved from RFC-040:
        event_callback: Callable[[Any], None] | None = None,
        integration_verifier: Any | None = None,
        project_root: Path | None = None,
        trace_enabled: bool = True,
    ) -> None:
        """Initialize executor.

        Args:
            graph: The artifact graph to execute.
            cache: Execution cache for skip decisions.
            event_callback: Optional callback for RFC-060 events.
            integration_verifier: Optional RFC-067 integration verifier.
            project_root: Project root for file paths.
            trace_enabled: Whether to write trace logs.
        """
        self.graph = graph
        self.cache = cache
        self._computed_hashes: dict[str, str] = {}

        # RFC-040 integrations
        self.event_callback = event_callback
        self.integration_verifier = integration_verifier
        self.project_root = project_root
        self.trace_enabled = trace_enabled

        # Populate provenance from graph structure
        self._sync_provenance()

    def _sync_provenance(self) -> None:
        """Sync provenance table with current graph structure."""
        for artifact_id in self.graph:
            spec = self.graph.get(artifact_id)
            if spec:
                for req_id in spec.requires:
                    self.cache.add_provenance(artifact_id, req_id, "requires")

    def _emit_event(self, event_type: str, **data: Any) -> None:
        """Emit an event via callback if configured (RFC-060).

        Args:
            event_type: Event type string (e.g., 'task_start', 'task_complete')
            **data: Event payload data
        """
        if self.event_callback is None:
            return

        try:
            from sunwell.agent.event_schema import create_validated_event
            from sunwell.agent.events import EventType

            event = create_validated_event(EventType(event_type), data)
            self.event_callback(event)
        except (ValueError, ImportError):
            # Unknown event type, validation failure, or missing module - skip
            pass

    def plan_execution(
        self,
        force_rerun: frozenset[str] | None = None,
    ) -> ExecutionPlan:
        """Plan which artifacts to execute vs skip.

        Processes artifacts in topological order so dependency hashes
        are available when computing each artifact's hash.

        Args:
            force_rerun: Frozenset of artifact IDs to force re-execute.

        Returns:
            ExecutionPlan with to_execute, to_skip, and decisions.
        """
        to_execute: list[str] = []
        to_skip: list[str] = []
        decisions: dict[str, SkipDecision] = {}

        # Clear computed hashes for fresh planning
        self._computed_hashes.clear()

        # Process in topological order so dependencies are hashed first
        for artifact_id in self.graph.topological_sort():
            spec = self.graph.get(artifact_id)
            if not spec:
                continue

            # Get dependency hashes (already computed due to topo order)
            dep_hashes = {
                dep_id: self._computed_hashes.get(dep_id, "UNKNOWN") for dep_id in spec.requires
            }

            decision = should_skip(
                spec=spec,
                cache=self.cache,
                dependency_hashes=dep_hashes,
                force_rerun=force_rerun is not None and artifact_id in force_rerun,
            )

            # Record hash for downstream artifacts
            self._computed_hashes[artifact_id] = decision.current_hash
            decisions[artifact_id] = decision

            if decision.can_skip:
                to_skip.append(artifact_id)
            else:
                to_execute.append(artifact_id)

        return ExecutionPlan(
            to_execute=to_execute,
            to_skip=to_skip,
            decisions=decisions,
            computed_hashes=dict(self._computed_hashes),
        )

    def get_execution_summary(self) -> dict[str, Any]:
        """Get summary of planned execution.

        Returns:
            Dict with execution plan summary.
        """
        plan = self.plan_execution()
        return plan.to_dict()

    def impact_analysis(self, artifact_id: str) -> dict[str, Any]:
        """Analyze impact of changing an artifact.

        Args:
            artifact_id: The artifact to analyze.

        Returns:
            Dict with direct_dependents, transitive_dependents, will_invalidate.
        """
        direct = self.cache.get_direct_dependents(artifact_id)
        transitive = self.cache.get_downstream(artifact_id)

        return {
            "artifact": artifact_id,
            "direct_dependents": direct,
            "transitive_dependents": transitive,
            "will_invalidate": transitive,
        }

    async def execute(
        self,
        create_fn: CreateArtifactFn,
        force_rerun: frozenset[str] | None = None,
        on_progress: Callable[[str], None] | None = None,
    ) -> IncrementalResult:
        """Execute artifact graph with incremental rebuild.

        Args:
            create_fn: Function to create artifacts.
            force_rerun: Set of artifact IDs to force re-execute.
            on_progress: Optional progress callback.

        Returns:
            IncrementalResult with completed/failed/skipped artifacts.
        """
        start_time = time.time()
        run_id = str(uuid.uuid4())[:8]

        # Plan execution
        plan = self.plan_execution(force_rerun)

        # Start run tracking
        self.cache.start_run(run_id, plan.total)

        if on_progress:
            on_progress(
                f"📊 Incremental: {len(plan.to_skip)} cached, {len(plan.to_execute)} to execute"
            )

        # Initialize result
        result = IncrementalResult(
            completed={},
            failed={},
            skipped={},
            run_id=run_id,
        )

        # Record skipped artifacts
        for artifact_id in plan.to_skip:
            decision = plan.decisions[artifact_id]
            result.skipped[artifact_id] = decision.cached_result
            self.cache.record_skip(artifact_id)

            # Emit skip event
            self._emit_event(
                "task_complete",
                task_id=artifact_id,
                duration_ms=0,
                skipped=True,
                reason=decision.reason.value,
            )

        # Execute in waves (parallel within wave)
        waves = self.graph.execution_waves()

        for wave_num, wave in enumerate(waves):
            # Filter to artifacts that need execution
            to_execute = [aid for aid in wave if aid in plan.to_execute]

            if not to_execute:
                continue

            if on_progress:
                on_progress(f"Wave {wave_num + 1}: {', '.join(to_execute)}")

            # Execute artifacts in parallel
            wave_results = await asyncio.gather(
                *[self._execute_artifact(aid, create_fn, plan) for aid in to_execute],
                return_exceptions=True,
            )

            # Process results
            for artifact_id, wave_result in zip(to_execute, wave_results, strict=True):
                if isinstance(wave_result, Exception):
                    error = str(wave_result)
                    result.failed[artifact_id] = error
                    self.cache.set(
                        artifact_id,
                        plan.computed_hashes.get(artifact_id, ""),
                        ExecutionStatus.FAILED,
                        error=error,
                    )
                elif wave_result is not None:
                    result.completed[artifact_id] = wave_result

        # Finish run tracking
        duration_ms = (time.time() - start_time) * 1000
        result.duration_ms = duration_ms

        self.cache.finish_run(
            run_id,
            executed=len(result.completed),
            skipped=len(result.skipped),
            failed=len(result.failed),
            status="completed" if result.success else "failed",
        )

        return result

    async def _execute_artifact(
        self,
        artifact_id: str,
        create_fn: CreateArtifactFn,
        plan: ExecutionPlan,
    ) -> dict[str, Any] | None:
        """Execute a single artifact.

        Args:
            artifact_id: ID of artifact to create.
            create_fn: Function to create the artifact.
            plan: Execution plan with computed hashes.

        Returns:
            Result dict with content and metadata, or None on failure.
        """
        spec = self.graph.get(artifact_id)
        if not spec:
            return None

        # Get input hash from plan
        input_hash = plan.computed_hashes.get(artifact_id, "")
        spec_hash = compute_spec_hash(spec)

        # Mark as running
        self.cache.set(artifact_id, input_hash, ExecutionStatus.RUNNING, spec_hash=spec_hash)

        # Emit task_start event
        self._emit_event(
            "task_start",
            task_id=artifact_id,
            description=spec.description,
        )

        start = datetime.now()

        try:
            content = await create_fn(spec)
            duration_ms = int((datetime.now() - start).total_seconds() * 1000)

            # RFC-067: Run integration checks (stub detection)
            await self._run_integration_checks(spec, content)

            # Build result
            result: dict[str, Any] = {
                "artifact_id": artifact_id,
                "content": content,
                "duration_ms": duration_ms,
            }

            # Cache successful execution
            self.cache.set(
                artifact_id,
                input_hash,
                ExecutionStatus.COMPLETED,
                result=result,
                execution_time_ms=duration_ms,
                spec_hash=spec_hash,
            )

            # Emit task_complete event
            self._emit_event(
                "task_complete",
                task_id=artifact_id,
                duration_ms=duration_ms,
            )

            return result

        except Exception as e:
            duration_ms = int((datetime.now() - start).total_seconds() * 1000)

            # Cache failure
            self.cache.set(
                artifact_id,
                input_hash,
                ExecutionStatus.FAILED,
                execution_time_ms=duration_ms,
                spec_hash=spec_hash,
                error=str(e),
            )

            # Emit task_failed event
            self._emit_event(
                "task_failed",
                task_id=artifact_id,
                error=str(e),
            )

            raise

    async def _run_integration_checks(
        self,
        artifact: ArtifactSpec,
        content: str,
    ) -> None:
        """Run RFC-067 integration checks after artifact creation.

        Detects stub implementations and emits warnings (advisory, doesn't fail).
        """
        if not self.integration_verifier or not artifact.produces_file:
            return

        file_path = Path(artifact.produces_file)
        if file_path.suffix != ".py":
            return

        try:
            full_path = self.project_root / file_path if self.project_root else file_path

            if full_path.exists():
                stubs = await self.integration_verifier.detect_stubs(full_path)
                if stubs:
                    stub_names = ", ".join(s.symbol for s in stubs[:3])
                    self._emit_event(
                        "integration_warning",
                        artifact_id=artifact.id,
                        message=f"⚠️ Stub implementations detected: {stub_names}",
                    )
        except Exception:
            # Integration checks are advisory, don't fail execution
            pass
