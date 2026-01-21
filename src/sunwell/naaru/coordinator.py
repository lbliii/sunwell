"""Naaru Architecture - Coordinated Intelligence for Local Models (RFC-019).

The Naaru is Sunwell's answer to maximizing quality and throughput from small local models.
Instead of a simple worker pool, it implements coordinated intelligence with specialized
components that work in harmony.

Architecture:
```
              ┌─────────────────┐
              │      NAARU      │  ← Coordinates everything
              │   (The Light)   │
              └────────┬────────┘
                       │
        ╔══════════════╧══════════════╗
        ║    CONVERGENCE (7 slots)    ║  ← Shared working memory
        ╚══════════════╤══════════════╝
                       │
     ┌─────────────────┼─────────────────┐
     │                 │                 │
     ▼                 ▼                 ▼
 ┌────────┐       ┌────────┐       ┌────────┐
 │ SHARD  │       │ SHARD  │       │ SHARD  │  ← Parallel helpers
 │ Memory │       │Context │       │ Verify │
 └────────┘       └────────┘       └────────┘
```

Components:
- **Naaru**: The coordinator (facade)
- **ExecutionCoordinator**: Task/artifact execution
- **LearningExtractor**: Learning persistence
- **NaaruEventEmitter**: Event emission
- **Convergence**: Shared working memory (7±2 slots)
- **Shards**: Parallel helpers (CPU-bound while GPU generates)
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from sunwell.mirror import MirrorHandler
from sunwell.naaru.core import MessageBus, MessageType, NaaruMessage, NaaruRegion, RegionWorker
from sunwell.naaru.events import NaaruEventEmitter
from sunwell.naaru.execution import ExecutionCoordinator
from sunwell.naaru.learnings import LearningExtractor
from sunwell.naaru.workers import (
    AnalysisWorker,
    CognitiveRoutingWorker,
    ExecutiveWorker,
    HarmonicSynthesisWorker,
    MemoryWorker,
    ToolRegionWorker,
    ValidationWorker,
)
from sunwell.types.config import NaaruConfig


@dataclass
class AgentResult:
    """Result from agent mode execution (RFC-032).

    Contains the goal, executed tasks, and any artifacts produced.
    """

    goal: str
    tasks: list
    completed_count: int
    failed_count: int
    artifacts: list[Path]
    execution_time_seconds: float = 0.0

    @property
    def success(self) -> bool:
        """True if no tasks failed."""
        return self.failed_count == 0

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "goal": self.goal,
            "tasks": [t.to_dict() if hasattr(t, "to_dict") else str(t) for t in self.tasks],
            "completed_count": self.completed_count,
            "failed_count": self.failed_count,
            "artifacts": [str(p) for p in self.artifacts],
            "execution_time_seconds": self.execution_time_seconds,
            "success": self.success,
        }


@dataclass
class Naaru:
    """The Naaru - Coordinated Intelligence for Local Models.

    This is the main entry point for the RFC-019 architecture.
    It coordinates all components to maximize quality and throughput
    from small local models.

    RFC-076: Now uses composition with focused components:
    - NaaruEventEmitter: Event emission
    - ExecutionCoordinator: Task/artifact execution
    - LearningExtractor: Learning persistence

    Example (self-improvement mode):
        >>> naaru = Naaru(
        ...     synthesis_model=OllamaModel("gemma3:1b"),
        ...     judge_model=OllamaModel("gemma3:4b"),
        ... )
        >>> results = await naaru.illuminate(goals=["improve error handling"])

    Example (agent mode - RFC-032):
        >>> naaru = Naaru(
        ...     synthesis_model=OllamaModel("gemma3:1b"),
        ...     tool_executor=ToolExecutor(workspace=Path.cwd()),
        ... )
        >>> result = await naaru.run("Build a React forum app")
    """

    sunwell_root: Path
    synthesis_model: Any = None
    judge_model: Any = None
    config: NaaruConfig = field(default_factory=NaaruConfig)

    # Optional components
    convergence: Any = None
    shard_pool: Any = None
    resonance: Any = None

    # RFC-032: Agent mode components
    planner: Any = None
    tool_executor: Any = None

    # RFC-067: Integration verification
    integration_verification_enabled: bool = True

    # Internal state
    bus: MessageBus = field(init=False)
    workers: list[RegionWorker] = field(init=False)
    _validation_worker: ValidationWorker = field(init=False)
    _synthesis_workers: list[HarmonicSynthesisWorker] = field(init=False)
    _routing_worker: CognitiveRoutingWorker | None = field(init=False)
    _tool_worker: ToolRegionWorker | None = field(init=False)
    _integration_verifier: Any = field(init=False)

    # RFC-076: Composed components
    _event_emitter: NaaruEventEmitter = field(init=False)
    _execution_coordinator: ExecutionCoordinator = field(init=False)
    _learning_extractor: LearningExtractor = field(init=False)

    def __post_init__(self) -> None:
        self.bus = MessageBus()
        self.workers = []
        self._routing_worker = None
        self._tool_worker = None
        self._synthesis_workers = []
        self._validation_worker = None
        self._integration_verifier = None

        # RFC-076: Initialize composed components
        self._event_emitter = NaaruEventEmitter(self.config.event_callback)
        self._execution_coordinator = ExecutionCoordinator(
            sunwell_root=self.sunwell_root,
            synthesis_model=self.synthesis_model,
            judge_model=self.judge_model,
            tool_executor=self.tool_executor,
            event_emitter=self._event_emitter,
            config=self.config,
        )
        self._learning_extractor = LearningExtractor(
            sunwell_root=self.sunwell_root,
            event_emitter=self._event_emitter,
        )

    def _get_integration_verifier(self) -> Any:
        """Get or create the IntegrationVerifier (lazy initialization)."""
        if not self.integration_verification_enabled:
            return None

        if self._integration_verifier is None:
            from sunwell.integration import IntegrationVerifier

            self._integration_verifier = IntegrationVerifier(
                project_root=self.sunwell_root,
            )
        return self._integration_verifier

    # =========================================================================
    # illuminate() - Self-improvement mode
    # =========================================================================

    async def illuminate(
        self,
        goals: list[str],
        max_time_seconds: float = 30,
        on_output: Callable[[str], None] = None,
    ) -> dict:
        """Have the Naaru illuminate goals and generate improvements.

        The Naaru's light reveals the best path forward.

        Args:
            goals: What to focus on
            max_time_seconds: Maximum thinking time
            on_output: Callback for progress updates

        Returns:
            Results dict with proposals and stats
        """
        output = on_output or print

        output("✨ Initializing Naaru...")
        output(f"   Synthesis shards: {self.config.num_synthesis_shards}")
        output(f"   Analysis shards: {self.config.num_analysis_shards}")
        if self.synthesis_model:
            harmony = "ENABLED" if self.config.harmonic_synthesis else "disabled"
            output(f"   🎵 Harmonic Synthesis: {harmony}")
        if self.judge_model:
            output(f"   🎯 Judge: ENABLED (threshold={self.config.purity_threshold})")
        if self.config.discernment:
            output("   ⚡ Tiered Validation: ENABLED")
        output(f"   🔄 Resonance: max {self.config.resonance} attempts")
        if self.config.attunement:
            router_name = getattr(self.config.attunement_model, "model_id", None) or "synthesis"
            output(f"   🧭 Cognitive Routing: ENABLED (RFC-020) via {router_name}")
        output("")

        self._create_workers(on_output=output)

        output("🚀 Starting Naaru regions...")
        tasks = []
        for worker in self.workers:
            task = asyncio.create_task(worker.process())
            tasks.append(task)

        output("🔍 Discovering opportunities...")
        from sunwell.naaru.discovery import OpportunityDiscoverer

        discoverer = OpportunityDiscoverer(
            mirror=MirrorHandler(self.sunwell_root, self.sunwell_root / ".sunwell" / "naaru"),
            sunwell_root=self.sunwell_root,
        )
        opportunities = await discoverer.discover(goals)
        output(f"   Found {len(opportunities)} opportunities")
        output("")

        for opp in opportunities[:20]:
            await self.bus.send(NaaruMessage(
                id=f"opp_{opp.id}",
                type=MessageType.OPPORTUNITY_FOUND,
                source=NaaruRegion.EXECUTIVE,
                target=NaaruRegion.SYNTHESIS,
                payload={
                    "id": opp.id,
                    "description": opp.description,
                    "target_module": opp.target_module,
                    "category": opp.category.value,
                },
            ))

        output("💭 Illuminating...")
        await asyncio.sleep(max_time_seconds)

        output("\n🛑 Shutting down...")
        for region in NaaruRegion:
            await self.bus.send(NaaruMessage(
                id="shutdown",
                type=MessageType.SHUTDOWN,
                source=NaaruRegion.EXECUTIVE,
                target=region,
                payload={},
                priority=10,
            ))

        for task in tasks:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

        results = self._collect_results()

        output("\n📊 Naaru Activity Summary:")
        output(f"   Messages exchanged: {results['bus_stats']['total_messages']}")
        output(f"   Proposals completed: {len(results['completed_proposals'])}")
        output(f"   Learnings stored: {results['learnings_count']}")

        if self.synthesis_model and results.get("generated_code"):
            output("\n🎵 Synthesis (Harmonic Generation):")
            output(f"   Code generated: {len(results['generated_code'])} proposals")
            output(f"   Total tokens: {results['total_tokens']}")

        if self.judge_model and results.get("quality_stats"):
            qs = results["quality_stats"]
            output("\n🎯 Quality Scores:")
            output(f"   Average: {qs['avg_score']:.1f}/10")
            output(f"   Range: {qs['min_score']:.1f} - {qs['max_score']:.1f}")
            approved = results["approved_count"]
            rejected = results["rejected_count"]
            output(f"   Approved: {approved}, Rejected: {rejected}")

        return results

    # =========================================================================
    # run() - Agent mode (RFC-032)
    # =========================================================================

    async def run(
        self,
        goal: str,
        context: dict[str, Any] | None = None,
        on_progress: Callable[[str], None] | None = None,
        max_time_seconds: float = 300,
        force_rebuild: bool = False,
    ) -> AgentResult:
        """Execute an arbitrary user task (RFC-032 Agent Mode).

        RFC-040: Automatically uses incremental execution when artifact-first
        planning is available. No flag needed - it's smart and caches.

        Args:
            goal: What the user wants to accomplish
            context: Optional context (cwd, file state, etc.)
            on_progress: Callback for progress updates
            max_time_seconds: Maximum execution time
            force_rebuild: Force rebuild all artifacts

        Returns:
            AgentResult with outputs, artifacts, and execution trace
        """
        from sunwell.naaru.types import TaskStatus

        output = on_progress or print
        start_time = datetime.now()

        if self.planner is None:
            from sunwell.naaru.planners import AgentPlanner

            available_tools = frozenset()
            if self.tool_executor:
                available_tools = frozenset(self.tool_executor.get_available_tools())

            self.planner = AgentPlanner(
                model=self.synthesis_model,
                available_tools=available_tools,
            )

        has_discover_graph = hasattr(self.planner, "discover_graph")
        use_incremental = has_discover_graph and self.tool_executor is not None

        if use_incremental:
            return await self._run_with_incremental(
                goal, context, output, start_time, max_time_seconds, force_rebuild
            )

        # Fallback to traditional task-based execution
        output("🎯 Planning...")
        self._event_emitter.emit_plan_start(goal)
        tasks = await self.planner.plan([goal], context)
        output(f"   Created {len(tasks)} tasks")

        self._event_emitter.emit_plan_winner(tasks=len(tasks))

        for i, task in enumerate(tasks, 1):
            deps = f" (after: {', '.join(task.depends_on)})" if task.depends_on else ""
            output(f"   {i}. {task.description}{deps}")
        output("")

        output("⚡ Executing...")
        tasks = await self._execution_coordinator.execute_task_graph(
            tasks, output, max_time_seconds
        )

        completed = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)
        failed = sum(1 for t in tasks if t.status == TaskStatus.FAILED)

        elapsed = (datetime.now() - start_time).total_seconds()

        output(f"\n✨ Complete: {completed}/{len(tasks)} tasks succeeded ({elapsed:.1f}s)")
        if failed:
            output(f"   ⚠️ {failed} tasks failed")

        artifacts = self._execution_coordinator.collect_artifacts(tasks)

        learnings = await self._learning_extractor.extract_from_tasks(tasks, goal)
        if learnings:
            output(f"   📚 {len(learnings)} learnings extracted")

        await self._learning_extractor.persist_execution_state(
            goal, tasks, artifacts, completed, failed, elapsed
        )

        self._event_emitter.emit_complete(
            tasks_completed=completed,
            tasks_failed=failed,
            duration_s=elapsed,
            learnings_count=len(learnings),
        )

        return AgentResult(
            goal=goal,
            tasks=tasks,
            completed_count=completed,
            failed_count=failed,
            artifacts=artifacts,
            execution_time_seconds=elapsed,
        )

    async def _run_with_incremental(
        self,
        goal: str,
        context: dict[str, Any] | None,
        output: Callable[[str], None],
        start_time: datetime,
        max_time_seconds: float,
        force_rebuild: bool = False,
    ) -> AgentResult:
        """Run with automatic incremental execution (RFC-074).

        Uses artifact-first planning with content-addressed incremental rebuild.
        """
        from sunwell.incremental import ExecutionCache, IncrementalExecutor
        from sunwell.models.protocol import ToolCall
        from sunwell.naaru.artifacts import artifacts_to_tasks
        from sunwell.naaru.persistence import hash_goal
        from sunwell.naaru.types import TaskStatus

        output("🎯 Planning (artifact-first)...")
        self._event_emitter.emit_plan_start(goal)
        graph = await self.planner.discover_graph(goal, context)
        output(f"   Discovered {len(graph)} artifacts")

        # Emit plan_winner if planner hasn't already
        planner_emitted = getattr(self.planner, "_plan_winner_emitted", False)
        if not planner_emitted:
            self._event_emitter.emit_plan_winner(tasks=len(graph), artifact_count=len(graph))

        for i, artifact_id in enumerate(graph.topological_sort(), 1):
            artifact = graph[artifact_id]
            deps = f" (requires: {', '.join(artifact.requires)})" if artifact.requires else ""
            output(f"   {i}. {artifact.description}{deps}")
        output("")

        output("⚡ Executing (incremental)...")

        cache_path = self.sunwell_root / ".sunwell" / "cache" / "execution.db"
        cache = ExecutionCache(cache_path)
        goal_hash = hash_goal(goal)

        executor = IncrementalExecutor(
            graph=graph,
            cache=cache,
            event_callback=self.config.event_callback,
            integration_verifier=self._get_integration_verifier(),
            project_root=self.sunwell_root,
        )

        force_artifacts = set(graph) if force_rebuild else None

        plan = executor.plan_execution(force_rerun=force_artifacts)
        if plan.to_skip:
            output(f"   📊 Skipping {len(plan.to_skip)} unchanged artifacts")

        completed_artifacts: dict[str, dict[str, Any]] = {}

        async def create_artifact(spec: Any) -> str:
            """Create an artifact using the planner and write to disk."""
            try:
                artifact_context = {
                    **(context or {}),
                    "completed": completed_artifacts,
                }

                content = await self.planner.create_artifact(spec, artifact_context)

                if spec.produces_file and content and self.tool_executor:
                    file_path = spec.produces_file
                    write_call = ToolCall(
                        id=f"write_{spec.id}",
                        name="write_file",
                        arguments={"path": file_path, "content": content},
                    )
                    result = await self.tool_executor.execute(write_call)
                    if not result.success:
                        raise RuntimeError(f"Failed to write {file_path}: {result.output}")

                completed_artifacts[spec.id] = {
                    "description": spec.description,
                    "contract": spec.contract,
                    "file": spec.produces_file,
                }

                return content or ""
            except Exception as e:
                output(f"   [red]✗[/red] Failed to create {spec.id}: {e}")
                raise

        def progress_handler(msg: str) -> None:
            output(f"   {msg}")

        execution_result = await executor.execute(
            create_fn=create_artifact,
            force_rerun=force_artifacts,
            on_progress=progress_handler,
        )

        all_artifact_ids = list(graph)
        cache.record_goal_execution(
            goal_hash,
            all_artifact_ids,
            execution_time_ms=execution_result.duration_ms,
        )

        tasks = artifacts_to_tasks(graph)

        for task in tasks:
            if task.id in execution_result.completed:
                task.status = TaskStatus.COMPLETED
                artifact_result = execution_result.completed[task.id]
                task.output = artifact_result.get("content", "") if artifact_result else ""
            elif task.id in execution_result.skipped:
                task.status = TaskStatus.COMPLETED
                cached_result = execution_result.skipped[task.id]
                task.output = cached_result.get("content", "") if cached_result else ""
            elif task.id in execution_result.failed:
                task.status = TaskStatus.FAILED
                task.error = execution_result.failed[task.id]

        completed = len(execution_result.completed) + len(execution_result.skipped)
        failed = len(execution_result.failed)

        elapsed = (datetime.now() - start_time).total_seconds()

        output(f"\n✨ Complete: {completed}/{len(graph)} artifacts succeeded ({elapsed:.1f}s)")
        if execution_result.skipped:
            output(f"   ⏩ {len(execution_result.skipped)} cached (skipped)")
        if failed:
            output(f"   ⚠️ {failed} artifacts failed")

        artifacts = self._execution_coordinator.collect_artifacts(tasks)

        learnings = await self._learning_extractor.extract_from_tasks(tasks, goal)
        if learnings:
            output(f"   📚 {len(learnings)} learnings extracted")

        self._event_emitter.emit_complete(
            tasks_completed=completed,
            tasks_failed=failed,
            duration_s=elapsed,
            learnings_count=len(learnings),
        )

        return AgentResult(
            goal=goal,
            tasks=tasks,
            completed_count=completed,
            failed_count=failed,
            artifacts=artifacts,
            execution_time_seconds=elapsed,
        )

    # =========================================================================
    # Worker Management
    # =========================================================================

    def _create_workers(self, on_output: Callable = None) -> None:
        """Create all Naaru region workers."""
        self._synthesis_workers = []

        if self.config.attunement:
            router_model = None
            if hasattr(self.config, "router") and self.config.router:
                from sunwell.models.ollama import OllamaModel
                router_model = OllamaModel(model=self.config.router)
            elif self.config.attunement_model:
                router_model = self.config.attunement_model
            else:
                router_model = self.synthesis_model

            lens_dir = self.sunwell_root / "lenses"
            available_lenses = []
            if lens_dir.exists():
                available_lenses = [p.stem for p in lens_dir.glob("*.lens")]

            cache_size = getattr(self.config, "router_cache_size", 1000)

            self._routing_worker = CognitiveRoutingWorker(
                bus=self.bus,
                sunwell_root=self.sunwell_root,
                router_model=router_model,
                available_lenses=available_lenses,
                use_unified_router=True,
                cache_size=cache_size,
            )
            self.workers.append(self._routing_worker)

        if self.tool_executor:
            self._tool_worker = ToolRegionWorker(
                bus=self.bus,
                sunwell_root=self.sunwell_root,
                tool_executor=self.tool_executor,
            )
            self.workers.append(self._tool_worker)

        for i in range(self.config.num_analysis_shards):
            self.workers.append(AnalysisWorker(
                bus=self.bus,
                sunwell_root=self.sunwell_root,
                worker_id=i,
            ))

        for i in range(self.config.num_synthesis_shards):
            worker = HarmonicSynthesisWorker(
                bus=self.bus,
                sunwell_root=self.sunwell_root,
                worker_id=i,
                model=self.synthesis_model,
                config=self.config,
                convergence=self.convergence,
                shard_pool=self.shard_pool,
                routing_worker=self._routing_worker,
            )
            self._synthesis_workers.append(worker)
            self.workers.append(worker)

        self._validation_worker = ValidationWorker(
            bus=self.bus,
            sunwell_root=self.sunwell_root,
            model=self.judge_model,
            config=self.config,
            resonance=self.resonance,
        )
        self.workers.append(self._validation_worker)

        self.workers.append(MemoryWorker(
            bus=self.bus,
            sunwell_root=self.sunwell_root,
        ))

        self.workers.append(ExecutiveWorker(
            bus=self.bus,
            sunwell_root=self.sunwell_root,
            on_output=on_output,
        ))

    def _collect_results(self) -> dict:
        """Collect results from all workers."""
        completed_proposals = []
        learnings = []
        worker_stats = {}
        quality_stats = {}
        approved_count = 0
        rejected_count = 0
        generated_code = []
        total_tokens = 0

        for worker in self.workers:
            worker_stats[f"{worker.region.value}_{getattr(worker, 'worker_id', 0)}"] = worker.stats

            if isinstance(worker, ExecutiveWorker):
                completed_proposals = worker.completed_proposals
            elif isinstance(worker, MemoryWorker):
                learnings = worker.learnings
            elif isinstance(worker, ValidationWorker):
                worker_stats[worker.region.value] = {
                    **worker.stats,
                    "approved": worker.approved_count,
                    "rejected": worker.rejected_count,
                }
                quality_stats = worker.get_quality_stats()
                approved_count = worker.approved_count
                rejected_count = worker.rejected_count
            elif isinstance(worker, HarmonicSynthesisWorker):
                generated_code.extend(worker.generated_code)
                total_tokens += sum(g.get("tokens", 0) for g in worker.generated_code)

        return {
            "completed_proposals": completed_proposals,
            "learnings_count": len(learnings),
            "worker_stats": worker_stats,
            "bus_stats": self.bus.get_stats(),
            "quality_stats": quality_stats,
            "approved_count": approved_count,
            "rejected_count": rejected_count,
            "generated_code": generated_code,
            "total_tokens": total_tokens,
        }

    def _get_available_tools(self) -> frozenset[str]:
        """Get available tools from tool_executor."""
        if self.tool_executor:
            return frozenset(self.tool_executor.get_available_tools())
        return frozenset()


async def demo() -> None:
    """Demonstrate the Naaru architecture."""
    print("=" * 60)
    print("Naaru Architecture Demo (RFC-019)")
    print("=" * 60)

    print("\nNaaru is the coordinated intelligence for local models.")
    print("Components:")
    print("  - Harmonic Synthesis: Multi-persona generation with voting")
    print("  - Convergence: Shared working memory (7±2 slots)")
    print("  - Shards: Parallel CPU helpers while GPU generates")
    print("  - Resonance: Feedback loop for rejected proposals")
    print("  - Discernment: Fast insight → full Wisdom cascade")


if __name__ == "__main__":
    import asyncio
    asyncio.run(demo())
