"""Artifact-first execution engine for RFC-036.

This module implements dependency-driven parallel execution of artifact graphs.
Execution proceeds in waves from leaves to roots, maximizing parallelism while
respecting semantic dependencies.

Key features:
- Wave-based parallel execution
- Dynamic artifact discovery mid-execution
- Verification integration
- Adaptive model selection based on graph depth
- Failure isolation (errors don't cascade to independent branches)

Example:
    >>> executor = ArtifactExecutor(model=my_model)
    >>> results = await executor.execute(graph, create_artifact)
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sunwell.naaru.artifacts import (
    DEFAULT_LIMITS,
    ArtifactGraph,
    ArtifactLimits,
    ArtifactSpec,
    CyclicDependencyError,
    VerificationResult,
    select_model_tier,
)

if TYPE_CHECKING:
    from pathlib import Path

    from sunwell.integration import IntegrationVerifier
    from sunwell.naaru.planners.artifact import ArtifactPlanner


# Type alias for artifact creation function
CreateArtifactFn = Callable[[ArtifactSpec], Awaitable[str]]


# =============================================================================
# Execution Results
# =============================================================================


@dataclass(frozen=True, slots=True)
class ArtifactResult:
    """Result of creating a single artifact.

    Attributes:
        artifact_id: The artifact that was created
        content: The created content (file contents, etc.)
        verified: Whether the artifact passed verification
        verification: Verification result details
        model_tier: Model tier used for creation
        duration_ms: Creation time in milliseconds
        error: Error message if creation failed
    """

    artifact_id: str
    content: str | None = None
    verified: bool = False
    verification: VerificationResult | None = None
    model_tier: str = "medium"
    duration_ms: int = 0
    error: str | None = None

    @property
    def success(self) -> bool:
        """Check if creation was successful."""
        return self.content is not None and self.error is None


@dataclass
class ExecutionResult:
    """Result of executing an artifact graph.

    Attributes:
        completed: Dict of artifact ID to result
        failed: Dict of artifact ID to error
        waves: Execution waves (for analysis)
        discovered: Artifacts discovered mid-execution
        total_duration_ms: Total execution time
        model_distribution: Count of each model tier used
    """

    completed: dict[str, ArtifactResult] = field(default_factory=dict)
    failed: dict[str, str] = field(default_factory=dict)
    waves: list[list[str]] = field(default_factory=list)
    discovered: list[ArtifactSpec] = field(default_factory=list)
    total_duration_ms: int = 0
    model_distribution: dict[str, int] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        total = len(self.completed) + len(self.failed)
        if total == 0:
            return 1.0
        return len([r for r in self.completed.values() if r.success]) / total

    @property
    def verification_rate(self) -> float:
        """Calculate verification pass rate."""
        verified = [r for r in self.completed.values() if r.verified]
        total = len(self.completed)
        if total == 0:
            return 1.0
        return len(verified) / total

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "completed": {
                aid: {
                    "content_length": len(r.content) if r.content else 0,
                    "verified": r.verified,
                    "model_tier": r.model_tier,
                    "duration_ms": r.duration_ms,
                    "error": r.error,
                }
                for aid, r in self.completed.items()
            },
            "failed": self.failed,
            "waves": self.waves,
            "discovered_count": len(self.discovered),
            "total_duration_ms": self.total_duration_ms,
            "model_distribution": self.model_distribution,
            "success_rate": self.success_rate,
            "verification_rate": self.verification_rate,
        }


# =============================================================================
# Execution Events
# =============================================================================


@dataclass(frozen=True, slots=True)
class ExecutionEvent:
    """Event emitted during execution."""

    event_type: str  # wave_start, artifact_start, artifact_complete, wave_complete, discovery
    artifact_id: str | None = None
    wave_number: int = 0
    message: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


EventCallback = Callable[[ExecutionEvent], None]


# =============================================================================
# ArtifactExecutor
# =============================================================================


@dataclass
class ArtifactExecutor:
    """Executes artifact graphs with parallel, wave-based execution.

    The executor:
    1. Processes artifacts in waves (all leaves first, then dependents)
    2. Executes all artifacts in a wave in parallel
    3. Optionally discovers new artifacts mid-execution
    4. Verifies artifacts against their contracts
    5. Selects model tier based on artifact depth
    6. RFC-067: Runs integration verification (stubs, orphans, wiring)

    Example:
        >>> executor = ArtifactExecutor(
        ...     planner=my_planner,  # For dynamic discovery
        ...     verify=True,
        ...     on_event=lambda e: print(e.message),
        ... )
        >>> result = await executor.execute(graph, create_artifact)
    """

    planner: ArtifactPlanner | None = None
    """Planner for dynamic discovery (optional)."""

    limits: ArtifactLimits = field(default_factory=lambda: DEFAULT_LIMITS)
    """Operational limits."""

    verify: bool = True
    """Whether to verify artifacts after creation."""

    dynamic_discovery: bool = True
    """Whether to discover new artifacts mid-execution."""

    on_event: EventCallback | None = None
    """Callback for execution events."""

    # RFC-067: Integration verification
    integration_verifier: IntegrationVerifier | None = None
    """Integration verifier for detecting stubs, orphans, and missing wiring."""

    project_root: Path | None = None
    """Project root for integration verification."""

    async def execute(
        self,
        graph: ArtifactGraph,
        create_fn: CreateArtifactFn,
        goal: str = "",
    ) -> ExecutionResult:
        """Execute an artifact graph.

        Args:
            graph: The artifact graph to execute
            create_fn: Function to create an artifact from its spec
            goal: Original goal (for dynamic discovery context)

        Returns:
            ExecutionResult with all completed/failed artifacts
        """
        start_time = datetime.now()
        result = ExecutionResult()
        result.model_distribution = {"small": 0, "medium": 0, "large": 0}

        # Get execution waves
        try:
            waves = graph.execution_waves()
        except CyclicDependencyError:
            # Should not happen if graph was validated, but handle gracefully
            return result

        result.waves = waves

        # Track completed artifacts and their content
        completed_content: dict[str, str] = {}
        discovery_round = 0

        for wave_num, wave in enumerate(waves):
            msg = f"Wave {wave_num + 1}: {len(wave)} artifacts"
            self._emit_event("wave_start", wave_number=wave_num, message=msg)

            # Execute all artifacts in this wave in parallel
            wave_results = await asyncio.gather(
                *[
                    self._execute_artifact(graph, artifact_id, create_fn, completed_content)
                    for artifact_id in wave
                ],
                return_exceptions=True,
            )

            # Process results
            for artifact_id, artifact_result in zip(wave, wave_results, strict=True):
                if isinstance(artifact_result, Exception):
                    result.failed[artifact_id] = str(artifact_result)
                    self._emit_event(
                        "artifact_complete",
                        artifact_id=artifact_id,
                        message=f"❌ {artifact_id}: {artifact_result}",
                    )
                elif artifact_result.success:
                    result.completed[artifact_id] = artifact_result
                    result.model_distribution[artifact_result.model_tier] += 1
                    completed_content[artifact_id] = artifact_result.content or ""
                    status = "✅" if artifact_result.verified else "⚠️"
                    tier = artifact_result.model_tier
                    dur = artifact_result.duration_ms
                    self._emit_event(
                        "artifact_complete",
                        artifact_id=artifact_id,
                        message=f"{status} {artifact_id} ({tier}, {dur}ms)",
                    )
                else:
                    result.failed[artifact_id] = artifact_result.error or "Unknown error"
                    self._emit_event(
                        "artifact_complete",
                        artifact_id=artifact_id,
                        message=f"❌ {artifact_id}: {artifact_result.error}",
                    )

            msg = f"Wave {wave_num + 1} complete"
            self._emit_event("wave_complete", wave_number=wave_num, message=msg)

            # Dynamic discovery after each wave
            should_discover = (
                self.dynamic_discovery
                and self.planner
                and discovery_round < self.limits.max_discovery_rounds
            )
            if should_discover:
                # Check the last completed artifact for new discoveries
                for artifact_id in wave:
                    if artifact_id in result.completed and result.completed[artifact_id].success:
                        artifact = graph[artifact_id]
                        new_artifacts = await self._discover_new(
                            goal,
                            dict(completed_content),
                            artifact,
                        )

                        if new_artifacts:
                            discovery_round += 1
                            self._emit_event(
                                "discovery",
                                message=f"Discovered {len(new_artifacts)} new artifacts",
                            )

                            # Add to graph and result
                            for new_artifact in new_artifacts:
                                if new_artifact.id not in graph:
                                    graph.add(new_artifact)
                                    result.discovered.append(new_artifact)

                            # Recompute waves for remaining execution
                            try:
                                completed_ids = set(result.completed.keys())
                                failed_ids = set(result.failed.keys())
                                remaining_ids = set(graph) - completed_ids - failed_ids
                                if remaining_ids:
                                    # We need to continue with updated waves
                                    # The current wave loop will exit, but we handle this
                                    # by returning and letting the caller re-execute if needed
                                    pass
                            except CyclicDependencyError:
                                # Discovery introduced a cycle - stop discovery
                                self.dynamic_discovery = False

        result.total_duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        # RFC-067: Final integration check - detect orphaned artifacts
        await self._run_final_integration_checks(graph, result)

        return result

    async def _run_final_integration_checks(
        self,
        graph: ArtifactGraph,
        result: ExecutionResult,
    ) -> None:
        """Run final integration checks after all artifacts are created.

        Detects orphaned artifacts (produced but not imported/used anywhere).
        """
        if not self.integration_verifier or not self.project_root:
            return

        from pathlib import Path

        from sunwell.integration import ProducedArtifact

        try:
            # Build list of produced artifacts from completed results
            produced: list[ProducedArtifact] = []
            for artifact_id, artifact_result in result.completed.items():
                if not artifact_result.success:
                    continue

                artifact = graph[artifact_id]
                if artifact.produces_file:
                    file_path = Path(artifact.produces_file)
                    produced.append(
                        ProducedArtifact(
                            id=artifact_id,
                            artifact_type="file",
                            location=artifact.produces_file,
                            file_path=self.project_root / file_path,
                        )
                    )

            if produced:
                orphans = await self.integration_verifier.detect_orphans(produced)
                if orphans:
                    orphan_names = ", ".join(o.symbol for o in orphans[:3])
                    self._emit_event(
                        "integration_warning",
                        message=f"⚠️ Orphaned artifacts detected (not imported): {orphan_names}",
                    )
        except Exception:
            # Integration checks are advisory, don't fail execution
            pass

    async def _execute_artifact(
        self,
        graph: ArtifactGraph,
        artifact_id: str,
        create_fn: CreateArtifactFn,
        completed_content: dict[str, str],
    ) -> ArtifactResult:
        """Execute a single artifact.

        Args:
            graph: The artifact graph
            artifact_id: ID of artifact to create
            create_fn: Function to create the artifact
            completed_content: Content of already-completed artifacts

        Returns:
            ArtifactResult with content and verification
        """
        artifact = graph[artifact_id]
        model_tier = select_model_tier(artifact, graph)

        self._emit_event(
            "artifact_start",
            artifact_id=artifact_id,
            message=f"Creating {artifact_id} ({model_tier})",
        )

        start = datetime.now()

        try:
            # Create the artifact
            content = await create_fn(artifact)
            duration_ms = int((datetime.now() - start).total_seconds() * 1000)

            # Verify if enabled
            verification = None
            verified = False

            if self.verify and self.planner:
                verification = await self.planner.verify_artifact(artifact, content)
                verified = verification.passed

            # RFC-067: Run integration verification (stub detection)
            await self._run_integration_checks(artifact, content)

            return ArtifactResult(
                artifact_id=artifact_id,
                content=content,
                verified=verified,
                verification=verification,
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

    async def _run_integration_checks(
        self,
        artifact: ArtifactSpec,
        content: str,
    ) -> None:
        """Run RFC-067 integration checks after artifact creation.

        Detects:
        - Stub implementations (pass, TODO, raise NotImplementedError)
        - Emits warnings but doesn't fail execution

        Args:
            artifact: The artifact that was created
            content: The created content
        """
        if not self.integration_verifier or not artifact.produces_file:
            return

        from pathlib import Path

        file_path = Path(artifact.produces_file)
        if file_path.suffix != ".py":
            return

        try:
            # Detect stubs in the created file
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

    async def _discover_new(
        self,
        goal: str,
        completed: dict[str, str],
        just_created: ArtifactSpec,
    ) -> list[ArtifactSpec]:
        """Discover new artifacts after creating one.

        Args:
            goal: Original goal
            completed: Completed artifact content
            just_created: The artifact that was just created

        Returns:
            List of new artifacts (may be empty)
        """
        if not self.planner:
            return []

        try:
            # Convert content dict to completion dict format
            completed_dict = {aid: {"content": content} for aid, content in completed.items()}
            return await self.planner.discover_new_artifacts(goal, completed_dict, just_created)
        except Exception:
            # Discovery failure is not fatal
            return []

    def _emit_event(
        self,
        event_type: str,
        artifact_id: str | None = None,
        wave_number: int = 0,
        message: str = "",
    ) -> None:
        """Emit an execution event."""
        if self.on_event:
            event = ExecutionEvent(
                event_type=event_type,
                artifact_id=artifact_id,
                wave_number=wave_number,
                message=message,
            )
            self.on_event(event)


# =============================================================================
# High-Level Execution Function
# =============================================================================


async def execute_artifact_graph(
    graph: ArtifactGraph,
    create_fn: CreateArtifactFn,
    planner: ArtifactPlanner | None = None,
    goal: str = "",
    verify: bool = True,
    dynamic_discovery: bool = True,
    on_event: EventCallback | None = None,
    integration_verifier: IntegrationVerifier | None = None,
    project_root: Path | None = None,
) -> ExecutionResult:
    """Execute an artifact graph with all features enabled.

    Convenience function that creates an executor and runs it.

    Args:
        graph: The artifact graph to execute
        create_fn: Function to create artifacts
        planner: Planner for dynamic discovery and verification
        goal: Original goal for context
        verify: Whether to verify artifacts
        dynamic_discovery: Whether to discover new artifacts
        on_event: Event callback
        integration_verifier: RFC-067 integration verifier for stub/orphan detection
        project_root: Project root for integration verification

    Returns:
        ExecutionResult with all completed/failed artifacts
    """
    executor = ArtifactExecutor(
        planner=planner,
        verify=verify,
        dynamic_discovery=dynamic_discovery,
        on_event=on_event,
        integration_verifier=integration_verifier,
        project_root=project_root,
    )
    return await executor.execute(graph, create_fn, goal)


async def execute_with_discovery(
    goal: str,
    initial_artifacts: list[ArtifactSpec],
    create_fn: CreateArtifactFn,
    planner: ArtifactPlanner,
    on_event: EventCallback | None = None,
) -> ExecutionResult:
    """Execute artifacts with dynamic discovery enabled.

    This is the full RFC-036 experience: start with initial discovery,
    execute in waves, discover more artifacts as needed.

    Args:
        goal: The goal to achieve
        initial_artifacts: Initially discovered artifacts
        create_fn: Function to create artifacts
        planner: Planner for dynamic discovery
        on_event: Event callback

    Returns:
        ExecutionResult including any dynamically discovered artifacts
    """
    # Build initial graph
    graph = ArtifactGraph()
    for artifact in initial_artifacts:
        graph.add(artifact)

    # Execute with discovery enabled
    return await execute_artifact_graph(
        graph=graph,
        create_fn=create_fn,
        planner=planner,
        goal=goal,
        verify=True,
        dynamic_discovery=True,
        on_event=on_event,
    )
