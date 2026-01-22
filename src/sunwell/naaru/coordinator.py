"""Naaru Architecture - Unified Orchestration Layer (RFC-019, RFC-083).

The Naaru is Sunwell's unified orchestration layer. ALL entry points (CLI, chat,
Studio, API) route through Naaru, which coordinates workers, shards, and
convergence to execute tasks.

RFC-083 Unification:
- Single entry point: naaru.process()
- All routing through RoutingWorker
- All context through Convergence
- All events through MessageBus

Architecture:
```
              ┌─────────────────┐
              │      NAARU      │  ← Single entry: process()
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
- **Naaru**: The unified coordinator
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
from sunwell.types.naaru_api import (
    CompositionSpec,
    NaaruError,
    NaaruEvent,
    NaaruEventType,
    ProcessInput,
    ProcessMode,
    ProcessOutput,
    RoutingDecision,
)


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

    workspace: Path
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
            workspace=self.workspace,
            synthesis_model=self.synthesis_model,
            judge_model=self.judge_model,
            tool_executor=self.tool_executor,
            event_emitter=self._event_emitter,
            config=self.config,
        )
        self._learning_extractor = LearningExtractor(
            workspace=self.workspace,
            event_emitter=self._event_emitter,
        )

    # =========================================================================
    # process() - Unified Entry Point (RFC-083)
    # =========================================================================

    async def process(
        self,
        input: ProcessInput,
    ) -> AsyncIterator[NaaruEvent]:
        """THE unified entry point. All roads lead here. (RFC-083)

        This is the single entry point for all Naaru processing:
        - CLI goals
        - Chat messages
        - Studio interactions
        - API calls

        The flow:
        1. Route (RoutingWorker) — What kind of request?
        2. Compose (Compositor Shard) — What UI to show?
        3. Prepare (Context Shards) — Gather context in parallel
        4. Execute (Execute Region) — Run tasks/tools
        5. Validate (Validation Worker) — Check quality
        6. Learn (Consolidator Shard) — Persist learnings
        7. Respond — Return result

        Args:
            input: ProcessInput with content, mode, and options

        Yields:
            NaaruEvent stream as processing happens

        Example:
            async for event in naaru.process(ProcessInput(content="Build API")):
                print(event.type, event.data)
        """
        start_time = datetime.now()

        # Emit process start
        yield NaaruEvent(
            type=NaaruEventType.PROCESS_START,
            data={"content": input.content, "mode": input.mode.value},
        )

        try:
            # Step 1: Route the request
            routing = await self._route_input(input)
            yield NaaruEvent(
                type=NaaruEventType.ROUTE_DECISION,
                data=routing.to_dict(),
            )

            # Store routing in Convergence
            if self.convergence:
                from sunwell.naaru.convergence import Slot, SlotSource

                await self.convergence.add(Slot(
                    id="routing:current",
                    content=routing.to_dict(),
                    relevance=1.0,
                    source=SlotSource.NAARU,
                    ttl=30,  # Routing is per-request
                ))

            # Step 2: Compose UI (parallel with context preparation)
            composition = await self._compose_ui(input, routing)
            if composition:
                yield NaaruEvent(
                    type=NaaruEventType.COMPOSITION_READY,
                    data=composition.to_dict(),
                )

            # Step 3-6: Execute based on mode
            is_agent_mode = input.mode == ProcessMode.AGENT
            is_auto_action = (
                input.mode == ProcessMode.AUTO
                and routing.interaction_type in ("action", "workspace")
            )
            if is_agent_mode or is_auto_action:
                # Agent mode: Full task execution
                async for event in self._execute_agent_mode(input, routing):
                    yield event
            elif input.mode == ProcessMode.CHAT or (
                input.mode == ProcessMode.AUTO and routing.interaction_type == "conversation"
            ):
                # Chat mode: Conversational response
                async for event in self._execute_chat_mode(input, routing):
                    yield event
            elif input.mode == ProcessMode.INTERFACE:
                # Interface mode: UI-focused routing
                async for event in self._execute_interface_mode(input, routing):
                    yield event
            else:
                # Auto mode with hybrid/view
                async for event in self._execute_hybrid_mode(input, routing):
                    yield event

            # Step 7: Process complete
            elapsed = (datetime.now() - start_time).total_seconds()
            yield NaaruEvent(
                type=NaaruEventType.PROCESS_COMPLETE,
                data={
                    "duration_s": elapsed,
                    "route_type": routing.interaction_type,
                    "confidence": routing.confidence,
                },
            )

        except Exception as e:
            yield NaaruEvent(
                type=NaaruEventType.PROCESS_ERROR,
                data={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "recoverable": not isinstance(e, (KeyboardInterrupt, SystemExit)),
                },
            )
            raise NaaruError(
                code="PROCESS_ERROR",
                message=str(e),
                recoverable=True,
                context={"input": input.content[:100]},
            ) from e

    async def process_sync(self, input: ProcessInput) -> ProcessOutput:
        """Non-streaming process that returns final ProcessOutput.

        Convenience method that collects all events and returns the final result.

        Args:
            input: ProcessInput with content, mode, and options

        Returns:
            ProcessOutput with response and metadata
        """
        events: list[NaaruEvent] = []
        response = ""
        route_type = "conversation"
        confidence = 0.0
        composition: CompositionSpec | None = None
        routing: RoutingDecision | None = None
        tasks_completed = 0
        artifacts: list[str] = []

        async for event in self.process(input):
            events.append(event)

            if event.type == NaaruEventType.ROUTE_DECISION:
                route_type = event.data.get("interaction_type", "conversation")
                confidence = event.data.get("confidence", 0.0)
                routing = RoutingDecision(
                    interaction_type=route_type,
                    confidence=confidence,
                    tier=event.data.get("tier", 1),
                    lens=event.data.get("lens"),
                    page_type=event.data.get("page_type", "home"),
                    tools=event.data.get("tools", []),
                    mood=event.data.get("mood"),
                    reasoning=event.data.get("reasoning"),
                )
            elif event.type == NaaruEventType.COMPOSITION_READY:
                composition = CompositionSpec(
                    page_type=event.data.get("page_type", "home"),
                    panels=event.data.get("panels", []),
                    input_mode=event.data.get("input_mode", "hero"),
                    suggested_tools=event.data.get("suggested_tools", []),
                    confidence=event.data.get("confidence", 0.0),
                    source=event.data.get("source", "regex"),
                )
            elif event.type == NaaruEventType.MODEL_TOKENS:
                response += event.data.get("content", "")
            elif event.type == NaaruEventType.TASK_COMPLETE:
                tasks_completed += 1
                if event.data.get("artifact"):
                    artifacts.append(event.data["artifact"])

        return ProcessOutput(
            response=response or "I'm here to help.",
            route_type=route_type,
            confidence=confidence,
            composition=composition,
            tasks_completed=tasks_completed,
            artifacts=artifacts,
            events=events,
            routing=routing,
        )

    async def _route_input(self, input: ProcessInput) -> RoutingDecision:
        """Route the input using RoutingWorker or heuristics.

        Args:
            input: ProcessInput to route

        Returns:
            RoutingDecision with interaction type and metadata
        """
        # If mode is explicit, use it
        if input.mode != ProcessMode.AUTO:
            mode_to_type = {
                ProcessMode.CHAT: "conversation",
                ProcessMode.AGENT: "action",
                ProcessMode.INTERFACE: "view",
            }
            return RoutingDecision(
                interaction_type=mode_to_type.get(input.mode, "conversation"),
                confidence=1.0,
                tier=1,
                page_type=input.page_type,
            )

        # Try to use routing worker if available
        if self._routing_worker:
            routing_dict = await self._routing_worker.route_sync(
                input.content,
                context=input.context,
            )
            return RoutingDecision(
                interaction_type=routing_dict.get("intent", "conversation"),
                confidence=routing_dict.get("confidence", 0.5),
                tier=routing_dict.get("tier", 1),
                lens=routing_dict.get("lens"),
                page_type=input.page_type,
                tools=routing_dict.get("tools", []),
                mood=routing_dict.get("mood"),
                reasoning=routing_dict.get("reasoning"),
            )

        # Fallback: heuristic routing
        return self._heuristic_route(input.content)

    def _heuristic_route(self, content: str) -> RoutingDecision:
        """Fallback heuristic routing without LLM.

        Updated to use IntentClassifier's patterns for consistency.
        """
        import re

        content_lower = content.lower()

        # WORKSPACE patterns — complex creation tasks (NOT action)
        # These should open a full workspace, not just execute an action
        workspace_patterns = [
            r"\b(build|create|make|develop|implement|write)\s+(a|an|the|me|us)?\s*\w*\s*(app|application|game|site|website|webapp|tool|project|system|platform|service|api|backend|frontend|cli|script)",
            r"\b(start|begin|new)\s+(a|an)?\s*(project|app|game|codebase)",
            r"\b(code|program|develop)\s+(a|an|the|me)?\s*\w+",
            r"\blet'?s?\s+(build|create|make|code|develop)",
            r"\bi\s+want\s+to\s+(build|create|make|code|develop)",
        ]

        for pattern in workspace_patterns:
            if re.search(pattern, content_lower):
                return RoutingDecision(
                    interaction_type="workspace",
                    confidence=0.85,
                    tier=2,
                    page_type="project",
                )

        # ACTION patterns — simple, immediate tasks
        action_patterns = [
            r"\b(add|put)\s+.+\s+(to|on|in)\s+(my\s+)?(list|todo|calendar|reminders?)",
            r"\b(remind|alert)\s+me\s+(to|about|at|in)",
            r"\b(set|create)\s+(a\s+)?(timer|alarm|reminder)",
            r"\b(complete|finish|done|check\s+off)\s+.+",
        ]

        for pattern in action_patterns:
            if re.search(pattern, content_lower):
                return RoutingDecision(
                    interaction_type="action",
                    confidence=0.7,
                    tier=1,
                    page_type="home",
                )

        # VIEW patterns
        if any(kw in content_lower for kw in ["show", "display", "list", "what is", "find"]):
            return RoutingDecision(
                interaction_type="view",
                confidence=0.5,
                tier=1,
                page_type="home",
            )

        # Default to conversation
        return RoutingDecision(
            interaction_type="conversation",
            confidence=0.4,
            tier=1,
            page_type="conversation",
        )

    async def _compose_ui(
        self,
        input: ProcessInput,
        routing: RoutingDecision,
    ) -> CompositionSpec | None:
        """Compose UI layout based on routing decision.

        Args:
            input: ProcessInput
            routing: RoutingDecision from router

        Returns:
            CompositionSpec or None if no UI needed
        """
        # Simple composition based on routing
        panels: list[dict[str, Any]] = []

        if routing.interaction_type == "conversation":
            # Check for auxiliary panel triggers
            content_lower = input.content.lower()
            if any(kw in content_lower for kw in ["plan", "schedule", "week", "day", "calendar"]):
                panels.append({"panel_type": "calendar", "title": "Schedule"})
            if any(kw in content_lower for kw in ["todo", "task", "remind"]):
                panels.append({"panel_type": "tasks", "title": "Tasks"})

        return CompositionSpec(
            page_type=routing.page_type,
            panels=panels,
            input_mode="chat" if routing.interaction_type == "conversation" else "hero",
            suggested_tools=[],
            confidence=routing.confidence,
            source="regex",
        )

    async def _execute_agent_mode(
        self,
        input: ProcessInput,
        routing: RoutingDecision,
    ) -> AsyncIterator[NaaruEvent]:
        """Execute in agent mode (task execution).

        Args:
            input: ProcessInput
            routing: RoutingDecision

        Yields:
            NaaruEvent stream
        """
        # Use existing run() implementation
        result = await self.run(
            goal=input.content,
            context=input.context,
            max_time_seconds=input.timeout,
        )

        # Convert to events
        for i, task in enumerate(result.tasks):
            if hasattr(task, "status") and task.status.value == "completed":
                yield NaaruEvent(
                    type=NaaruEventType.TASK_COMPLETE,
                    data={
                        "task_id": getattr(task, "id", str(i)),
                        "description": getattr(task, "description", ""),
                    },
                )

        # Final response
        summary = f"Completed {result.completed_count}/{len(result.tasks)} tasks"
        if result.artifacts:
            summary += f". Created: {', '.join(str(a) for a in result.artifacts[:5])}"

        yield NaaruEvent(
            type=NaaruEventType.MODEL_TOKENS,
            data={"content": summary},
        )

    async def _execute_chat_mode(
        self,
        input: ProcessInput,
        routing: RoutingDecision,
    ) -> AsyncIterator[NaaruEvent]:
        """Execute in chat mode (conversational).

        Args:
            input: ProcessInput
            routing: RoutingDecision

        Yields:
            NaaruEvent stream
        """
        yield NaaruEvent(
            type=NaaruEventType.MODEL_START,
            data={"mode": "chat"},
        )

        if self.synthesis_model is None:
            no_model_msg = "I'm here to help! However, no model is configured."
            yield NaaruEvent(
                type=NaaruEventType.MODEL_TOKENS,
                data={"content": no_model_msg},
            )
            yield NaaruEvent(type=NaaruEventType.MODEL_COMPLETE, data={})
            return

        # Build prompt with conversation history
        messages = []
        for msg in input.conversation_history:
            messages.append({"role": msg.role, "content": msg.content})
        messages.append({"role": "user", "content": input.content})

        # Generate response
        try:
            from sunwell.models.protocol import GenerateOptions

            prompt = self._build_chat_prompt(messages)
            result = await self.synthesis_model.generate(
                prompt,
                options=GenerateOptions(temperature=0.7, max_tokens=1000),
            )

            yield NaaruEvent(
                type=NaaruEventType.MODEL_TOKENS,
                data={"content": result.content or ""},
            )
        except Exception as e:
            yield NaaruEvent(
                type=NaaruEventType.MODEL_TOKENS,
                data={"content": f"I encountered an error: {e}"},
            )

        yield NaaruEvent(type=NaaruEventType.MODEL_COMPLETE, data={})

    def _build_chat_prompt(self, messages: list[dict[str, str]]) -> str:
        """Build chat prompt from message history."""
        prompt_parts = ["You are a helpful assistant. Respond conversationally.\n"]

        for msg in messages[-10:]:  # Last 10 messages
            role = msg["role"].title()
            content = msg["content"]
            prompt_parts.append(f"{role}: {content}\n")

        prompt_parts.append("Assistant: ")
        return "".join(prompt_parts)

    async def _execute_interface_mode(
        self,
        input: ProcessInput,
        routing: RoutingDecision,
    ) -> AsyncIterator[NaaruEvent]:
        """Execute in interface mode (UI composition).

        Args:
            input: ProcessInput
            routing: RoutingDecision

        Yields:
            NaaruEvent stream
        """
        # Interface mode focuses on UI composition
        # The composition is already done, just acknowledge
        yield NaaruEvent(
            type=NaaruEventType.MODEL_TOKENS,
            data={"content": "Here's what I found for you."},
        )

    async def _execute_hybrid_mode(
        self,
        input: ProcessInput,
        routing: RoutingDecision,
    ) -> AsyncIterator[NaaruEvent]:
        """Execute in hybrid mode (action + view).

        Args:
            input: ProcessInput
            routing: RoutingDecision

        Yields:
            NaaruEvent stream
        """
        # For hybrid, do both chat and return view data
        async for event in self._execute_chat_mode(input, routing):
            yield event

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
            mirror=MirrorHandler(self.workspace, self.workspace / ".sunwell" / "naaru"),
            workspace=self.workspace,
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

        cache_path = self.workspace / ".sunwell" / "cache" / "execution.db"
        cache = ExecutionCache(cache_path)
        goal_hash = hash_goal(goal)

        executor = IncrementalExecutor(
            graph=graph,
            cache=cache,
            event_callback=self.config.event_callback,
            integration_verifier=self._get_integration_verifier(),
            project_root=self.workspace,
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
            self.workers.append(AnalysisWorker(
                bus=self.bus,
                workspace=self.workspace,
                worker_id=i,
            ))

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

        self.workers.append(MemoryWorker(
            bus=self.bus,
            workspace=self.workspace,
        ))

        self.workers.append(ExecutiveWorker(
            bus=self.bus,
            workspace=self.workspace,
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
