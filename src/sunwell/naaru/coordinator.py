"""Naaru Architecture - Internal Coordination Layer (RFC-019, RFC-110).

RFC-110: Naaru is an INTERNAL coordination layer used by Agent.
- NOT an entry point — Agent.run() is THE entry point
- Used internally for parallel task execution and worker coordination
- No process() or run() methods — those were redundant with Agent

Architecture:
```
              ┌─────────────────┐
              │      AGENT      │  ← THE entry point: Agent.run()
              │   (The Brain)   │
              └────────┬────────┘
                       │ uses internally
                       ▼
              ┌─────────────────┐
              │      NAARU      │  ← Internal coordination
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
- **Naaru**: Internal task coordinator (NOT an entry point)
- **ExecutionCoordinator**: Task/artifact execution
- **LearningExtractor**: Learning persistence
- **NaaruEventEmitter**: Event emission
- **Convergence**: Shared working memory (7±2 slots)
- **Shards**: Parallel helpers (CPU-bound while GPU generates)
"""

import asyncio
import contextlib
from collections.abc import AsyncIterator, Callable
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
        """Convert to dictionary for serialization."""
        return {
            "goal": self.goal,
            "completed": self.completed_count,
            "failed": self.failed_count,
            "artifacts": [str(a) for a in self.artifacts],
            "success": self.success,
            "execution_time_seconds": self.execution_time_seconds,
        }


@dataclass
class Naaru:
    """Internal coordination layer for Sunwell (RFC-019, RFC-110).

    RFC-110: Naaru is NOT an entry point. Agent.run() is THE entry point.
    Agent uses Naaru internally for:
    - Worker coordination
    - Parallel task execution
    - Convergence (shared memory)
    - Self-improvement (illuminate)

    Example (internal use by Agent):
        naaru = Naaru(workspace=cwd, synthesis_model=model)
        # Agent uses naaru internally for coordination
    """

    workspace: Path
    """Project workspace directory."""

    synthesis_model: Any
    """Model for generation (synthesis workers)."""

    tool_executor: Any = None
    """Tool executor for file I/O, commands, etc."""

    judge_model: Any = None
    """Model for validation (defaults to synthesis_model)."""

    config: NaaruConfig = field(default_factory=NaaruConfig)
    """Naaru configuration."""

    # Optional components
    convergence: Any = None
    """Shared working memory (Convergence)."""

    resonance: Any = None
    """Feedback loop for rejected proposals."""

    shard_pool: Any = None
    """Pool of parallel CPU helpers."""

    planner: Any = None
    """Task planner."""

    integration_verification_enabled: bool = True
    """Whether to run integration verification."""

    # Internal state
    bus: MessageBus = field(default_factory=MessageBus, init=False)
    workers: list[RegionWorker] = field(default_factory=list, init=False)

    _routing_worker: CognitiveRoutingWorker | None = field(default=None, init=False)
    _tool_worker: ToolRegionWorker | None = field(default=None, init=False)
    _validation_worker: ValidationWorker | None = field(default=None, init=False)
    _synthesis_workers: list[HarmonicSynthesisWorker] = field(default_factory=list, init=False)
    _execution_coordinator: ExecutionCoordinator | None = field(default=None, init=False)
    _learning_extractor: LearningExtractor | None = field(default=None, init=False)
    _event_emitter: NaaruEventEmitter | None = field(default=None, init=False)
    _integration_verifier: Any = field(default=None, init=False)

    def __post_init__(self) -> None:
        if self.judge_model is None:
            self.judge_model = self.synthesis_model

        self.workspace = Path(self.workspace)

        # Initialize event emitter
        self._event_emitter = NaaruEventEmitter()

        # Initialize learning extractor
        self._learning_extractor = LearningExtractor(
            workspace=self.workspace,
            event_emitter=self._event_emitter,
        )

        # Initialize execution coordinator
        self._execution_coordinator = ExecutionCoordinator(
            workspace=self.workspace,
            synthesis_model=self.synthesis_model,
            tool_executor=self.tool_executor,
            event_emitter=self._event_emitter,
        )

    # =========================================================================
    # Internal: Integration Verification
    # =========================================================================

    def _get_integration_verifier(self) -> Any:
        """Get or create the IntegrationVerifier (lazy initialization)."""
        if not self.integration_verification_enabled:
            return None

        if self._integration_verifier is None:
            from sunwell.integration import IntegrationVerifier

            self._integration_verifier = IntegrationVerifier(
                project_root=self.workspace,
            )
        return self._integration_verifier

    # =========================================================================
    # illuminate() - Self-improvement mode (RFC-085)
    # =========================================================================

    async def illuminate(
        self,
        goals: list[str],
        max_time_seconds: float = 30,
        on_output: Callable[[str], None] | None = None,
    ) -> dict:
        """Self-improvement mode: Generate proposals for workspace improvements.

        This is a separate mode from normal execution - used for autonomous
        improvement suggestions when the agent has idle cycles.

        Args:
            goals: List of high-level improvement goals
            max_time_seconds: Maximum time to run
            on_output: Optional callback for progress updates

        Returns:
            Dict with proposals, learnings, and stats
        """
        output = on_output or print
        output(f"🌟 Naaru Illuminate Mode")
        output(f"   Goals: {goals}")
        output(f"   Max time: {max_time_seconds}s")
        output("")

        self._create_workers(on_output)

        for goal in goals:
            # Dispatch goal to analysis workers
            self.bus.dispatch(NaaruMessage(
                region=NaaruRegion.ANALYSIS,
                type=MessageType.PROPOSAL,
                payload={"goal": goal, "mode": "illuminate"},
            ))

        # Run workers with timeout
        async def run_workers():
            tasks = [asyncio.create_task(w.run()) for w in self.workers]
            try:
                await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=max_time_seconds,
                )
            except asyncio.TimeoutError:
                output(f"   ⏱️ Time limit reached ({max_time_seconds}s)")
            finally:
                for task in tasks:
                    if not task.done():
                        task.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await task

        await run_workers()

        results = self._collect_results()
        output(f"\n✨ Illuminate complete")
        output(f"   Proposals: {len(results['completed_proposals'])}")
        output(f"   Learnings: {results['learnings_count']}")

        return results

    # =========================================================================
    # Worker Management (Internal)
    # =========================================================================

    def _create_workers(self, on_output: Callable | None = None) -> None:
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

            lens_dir = self.workspace / "lenses"
            available_lenses = []
            if lens_dir.exists():
                available_lenses = [p.stem for p in lens_dir.glob("*.lens")]

            cache_size = getattr(self.config, "router_cache_size", 1000)

            self._routing_worker = CognitiveRoutingWorker(
                bus=self.bus,
                workspace=self.workspace,
                router_model=router_model,
                available_lenses=available_lenses,
                cache_size=cache_size,
            )
            self.workers.append(self._routing_worker)

        if self.tool_executor:
            self._tool_worker = ToolRegionWorker(
                bus=self.bus,
                workspace=self.workspace,
                tool_executor=self.tool_executor,
            )
            self.workers.append(self._tool_worker)

        for i in range(self.config.num_analysis_shards):
            self.workers.append(
                AnalysisWorker(
                    bus=self.bus,
                    workspace=self.workspace,
                    worker_id=i,
                )
            )

        for i in range(self.config.num_synthesis_shards):
            worker = HarmonicSynthesisWorker(
                bus=self.bus,
                workspace=self.workspace,
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
            workspace=self.workspace,
            model=self.judge_model,
            config=self.config,
            resonance=self.resonance,
        )
        self.workers.append(self._validation_worker)

        self.workers.append(
            MemoryWorker(
                bus=self.bus,
                workspace=self.workspace,
            )
        )

        self.workers.append(
            ExecutiveWorker(
                bus=self.bus,
                workspace=self.workspace,
                on_output=on_output,
            )
        )

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
            worker_stats[f"{worker.region.value}_{getattr(worker, 'worker_id', 0)}"] = (
                worker.stats
            )

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
    print("Naaru Architecture Demo (RFC-019, RFC-110)")
    print("=" * 60)

    print("\nRFC-110: Naaru is an INTERNAL coordination layer.")
    print("Agent.run() is THE entry point - Naaru is used internally.")
    print("")
    print("Components:")
    print("  - Harmonic Synthesis: Multi-persona generation with voting")
    print("  - Convergence: Shared working memory (7±2 slots)")
    print("  - Shards: Parallel CPU helpers while GPU generates")
    print("  - Resonance: Feedback loop for rejected proposals")
    print("  - illuminate(): Self-improvement mode")


if __name__ == "__main__":
    import asyncio

    asyncio.run(demo())
