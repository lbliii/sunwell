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
- **Naaru**: The coordinator
- **Convergence**: Shared working memory (7±2 slots)
- **Shards**: Parallel helpers (CPU-bound while GPU generates)
- **Harmonic Synthesis**: Multi-persona generation with voting
- **Resonance**: Feedback loop for rejected proposals
- **Tiered Validation**: FunctionGemma → Full LLM cascade

Example:
    >>> from sunwell.naaru import Naaru, NaaruConfig
    >>> 
    >>> naaru = Naaru(
    ...     synthesis_model=OllamaModel("gemma3:1b"),
    ...     judge_model=OllamaModel("gemma3:4b"),
    ...     config=NaaruConfig(
    ...         harmonic_synthesis=True,
    ...         resonance_max_attempts=2,
    ...     ),
    ... )
    >>> 
    >>> results = await naaru.illuminate(
    ...     goals=["improve error handling"],
    ...     max_time_seconds=120,
    ... )

Lore:
    In World of Warcraft, the Naaru are beings of pure Light that coordinate and guide.
    The Sunwell was restored by a Naaru (M'uru). The metaphor fits:
    - Naaru = The coordinator
    - Convergence = Shared purpose/working memory
    - Shards = Fragments working in parallel
    - Resonance = Feedback that amplifies quality
    - Harmonic = Multiple voices in alignment
    - Illuminate = The Naaru's light reveals the best path
"""

from __future__ import annotations

import asyncio
import json
import uuid
from abc import ABC, abstractmethod
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from sunwell.mirror import MirrorHandler
from sunwell.naaru.rotation import (
    ModelSize,
    ThoughtLexer,
)
from sunwell.types.config import NaaruConfig

# =============================================================================
# Message Bus (Corpus Callosum equivalent)
# =============================================================================


class NaaruRegion(Enum):
    """Specialized regions of the Naaru architecture."""

    ANALYSIS = "analysis"      # Reading, pattern detection, introspection
    SYNTHESIS = "synthesis"    # Proposal generation, solution creation
    VALIDATION = "validation"  # Safety checks, testing, quality gates
    MEMORY = "memory"          # Simulacrum operations, learning
    EXECUTIVE = "executive"    # Coordination, prioritization
    ROUTING = "routing"        # RFC-020: Intent-aware routing
    TOOLS = "tools"            # RFC-032: Tool execution for agent mode


class MessageType(Enum):
    """Types of messages on the message bus."""

    # Discoveries
    PATTERN_FOUND = "pattern_found"
    OPPORTUNITY_FOUND = "opportunity_found"

    # Requests
    ANALYZE_REQUEST = "analyze_request"
    VALIDATE_REQUEST = "validate_request"
    MEMORIZE_REQUEST = "memorize_request"
    REFINE_REQUEST = "refine_request"  # Resonance: rejected → refine
    ROUTE_REQUEST = "route_request"    # RFC-020: Intent classification request

    # Responses
    ANALYSIS_COMPLETE = "analysis_complete"
    PROPOSAL_READY = "proposal_ready"
    VALIDATION_RESULT = "validation_result"
    ROUTE_COMPLETE = "route_complete"  # RFC-020: Routing decision ready

    # RFC-032: Tool execution messages
    TOOL_REQUEST = "tool_request"           # Execute a tool
    TOOL_RESULT = "tool_result"             # Tool execution result
    TOOL_BATCH = "tool_batch"               # Execute multiple tools
    TOOL_BATCH_RESULT = "tool_batch_result" # Batch execution results
    TASK_READY = "task_ready"               # Task ready for execution
    TASK_COMPLETE = "task_complete"         # Task completed
    TASK_FAILED = "task_failed"             # Task execution failed

    # Control
    ATTENTION_SHIFT = "attention_shift"
    PRIORITY_CHANGE = "priority_change"
    SHUTDOWN = "shutdown"


@dataclass
class NaaruMessage:
    """Message passed through the Naaru message bus."""

    id: str
    type: MessageType
    source: NaaruRegion
    target: NaaruRegion | None  # None = broadcast
    payload: dict[str, Any]
    priority: int = 5  # 1-10, higher = more urgent
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "source": self.source.value,
            "target": self.target.value if self.target else None,
            "payload": self.payload,
            "priority": self.priority,
        }


class MessageBus:
    """Central communication bus connecting Naaru regions.
    
    Like the brain's corpus callosum, this allows different specialized
    regions to communicate and coordinate.
    """

    def __init__(self):
        self._queues: dict[NaaruRegion, asyncio.Queue] = {
            region: asyncio.Queue() for region in NaaruRegion
        }
        self._message_log: list[NaaruMessage] = []
        self._lock = asyncio.Lock()

    async def send(self, message: NaaruMessage) -> None:
        """Send a message to a specific region or broadcast."""
        async with self._lock:
            self._message_log.append(message)

        if message.target:
            await self._queues[message.target].put(message)
        else:
            # Broadcast to all
            for region_queue in self._queues.values():
                await region_queue.put(message)

    async def receive(self, region: NaaruRegion, timeout: float = 0.1) -> NaaruMessage | None:
        """Receive a message for a specific region."""
        try:
            return await asyncio.wait_for(
                self._queues[region].get(),
                timeout=timeout,
            )
        except TimeoutError:
            return None

    def get_stats(self) -> dict:
        """Get communication statistics."""
        by_type = {}
        for msg in self._message_log:
            by_type[msg.type.value] = by_type.get(msg.type.value, 0) + 1

        return {
            "total_messages": len(self._message_log),
            "by_type": by_type,
            "queue_sizes": {
                region.value: self._queues[region].qsize()
                for region in NaaruRegion
            },
        }


# =============================================================================
# Region Workers
# =============================================================================


class RegionWorker(ABC):
    """Base class for Naaru region workers."""

    def __init__(
        self,
        region: NaaruRegion,
        bus: MessageBus,
        sunwell_root: Path,
        worker_id: int = 0,
    ):
        self.region = region
        self.bus = bus
        self.sunwell_root = sunwell_root
        self.worker_id = worker_id
        self._stop_event = asyncio.Event()
        self.stats = {"tasks_completed": 0, "messages_sent": 0}

    @abstractmethod
    async def process(self) -> None:
        """Main processing loop for this region."""
        pass

    def stop(self) -> None:
        """Signal this worker to stop."""
        self._stop_event.set()

    async def send_message(
        self,
        msg_type: MessageType,
        target: NaaruRegion | None,
        payload: dict,
        priority: int = 5,
    ) -> None:
        """Send a message through the bus."""
        msg = NaaruMessage(
            id=f"{self.region.value}_{uuid.uuid4().hex[:8]}",
            type=msg_type,
            source=self.region,
            target=target,
            payload=payload,
            priority=priority,
        )
        await self.bus.send(msg)
        self.stats["messages_sent"] += 1


class AnalysisWorker(RegionWorker):
    """Analysis region - reads code, finds patterns, introspection."""

    def __init__(self, *args, **kwargs):
        super().__init__(NaaruRegion.ANALYSIS, *args, **kwargs)
        self.mirror = MirrorHandler(
            sunwell_root=self.sunwell_root,
            storage_path=self.sunwell_root / ".sunwell" / "naaru" / f"analysis_{self.worker_id}",
        )

    async def process(self) -> None:
        """Analyze code and report findings."""
        while not self._stop_event.is_set():
            msg = await self.bus.receive(self.region)

            if msg and msg.type == MessageType.ANALYZE_REQUEST:
                target = msg.payload.get("target")
                result = await self._analyze(target)

                await self.send_message(
                    MessageType.ANALYSIS_COMPLETE,
                    NaaruRegion.SYNTHESIS,
                    {"target": target, "findings": result},
                )
                self.stats["tasks_completed"] += 1

            elif msg and msg.type == MessageType.SHUTDOWN:
                break

            await asyncio.sleep(0.01)

    async def _analyze(self, target: str) -> dict:
        """Analyze a target module."""
        try:
            result = await self.mirror.handle("introspect_source", {"module": target})
            return json.loads(result)
        except Exception as e:
            return {"error": str(e)}


class HarmonicSynthesisWorker(RegionWorker):
    """Synthesis region with Harmonic Synthesis (multi-persona generation).
    
    Harmonic Synthesis: Instead of generating once, the Naaru generates with
    MULTIPLE PERSONAS in parallel, then has them vote on the best solution.
    
    The key insight: temperature diversity gives random variance,
    lens diversity gives STRUCTURED variance based on domain knowledge.
    """

    # Lens personas for harmonic synthesis
    LENS_PERSONAS = {
        "security": {
            "name": "Security Expert",
            "system": "You are a security expert. Focus on attack vectors, edge cases, and defensive coding.",
        },
        "code_quality": {
            "name": "Code Reviewer",
            "system": "You are a senior Python developer. Focus on clean, maintainable, idiomatic code.",
        },
        "testing": {
            "name": "QA Engineer",
            "system": "You are a QA engineer. Focus on testability, edge cases, and failure modes.",
        },
    }

    def __init__(
        self,
        *args,
        model=None,
        config: NaaruConfig | None = None,
        convergence=None,
        shard_pool=None,
        routing_worker=None,  # RFC-020: Attunement
        **kwargs,
    ):
        super().__init__(NaaruRegion.SYNTHESIS, *args, **kwargs)
        self.model = model
        self.config = config or NaaruConfig()
        self.convergence = convergence  # Working memory
        self.shard_pool = shard_pool    # Parallel helpers
        self.routing_worker = routing_worker  # RFC-020: Attunement
        self.mirror = MirrorHandler(
            sunwell_root=self.sunwell_root,
            storage_path=self.sunwell_root / ".sunwell" / "naaru" / f"synthesis_{self.worker_id}",
        )
        self._pending_work: list[dict] = []
        self.generated_code: list[dict] = []
        self._prefetch_cache: dict = {}
        # RFC-028: ThoughtLexer uses synthesis model (already tiny: gemma3:1b)
        # Will be initialized lazily when model is available
        self._thought_lexer: ThoughtLexer | None = None

    @property
    def model_size(self) -> ModelSize:
        """Detect model size from the synthesis model name (RFC-028)."""
        if not self.model:
            return ModelSize.SMALL
        model_name = getattr(self.model, "model_id", "") or getattr(self.model, "name", "")
        return ModelSize.from_model_name(model_name)

    @property
    def thought_lexer(self) -> ThoughtLexer:
        """Get or create the ThoughtLexer (RFC-028).
        
        Model priority for task classification:
        1. config.lexer_model (explicit)
        2. routing_worker.router_model (attunement model, typically qwen2.5:3b)
        3. None (falls back to keyword classification)
        
        Does NOT use synthesis model - it's too small for reliable JSON.
        """
        if self._thought_lexer is None:
            # Priority: explicit lexer_model > router_model > keywords
            lexer_model = self.config.lexer_model
            if lexer_model is None and self.routing_worker:
                lexer_model = getattr(self.routing_worker, 'router_model', None)

            self._thought_lexer = ThoughtLexer(
                tiny_model=lexer_model,
                default_model_size=self.model_size,
            )
        return self._thought_lexer

    async def process(self) -> None:
        """Generate proposals using Harmonic Synthesis or Shard-assisted generation."""
        while not self._stop_event.is_set():
            msg = await self.bus.receive(self.region)

            if msg and msg.type == MessageType.ANALYSIS_COMPLETE:
                findings = msg.payload.get("findings", {})
                proposal = await self._synthesize_basic(findings)

                if proposal:
                    await self.send_message(
                        MessageType.VALIDATE_REQUEST,
                        NaaruRegion.VALIDATION,
                        {"proposal": proposal},
                    )
                self.stats["tasks_completed"] += 1

            elif msg and msg.type == MessageType.OPPORTUNITY_FOUND:
                opp = msg.payload
                self._pending_work.append(opp)

                if self.model:
                    next_opp = self._pending_work[0] if len(self._pending_work) > 1 else None

                    # RFC-020: Attunement - route task to get intent + lens
                    routing = None
                    if self.routing_worker and self.config.attunement:
                        task_desc = opp.get("description", "") or opp.get("category", "")
                        routing = await self.routing_worker.route_sync(task_desc)
                        self.stats["routed_tasks"] = self.stats.get("routed_tasks", 0) + 1

                    # Choose synthesis strategy
                    if self.config.harmonic_synthesis:
                        proposal = await self.harmonize(opp, routing=routing)
                    elif self.shard_pool:
                        proposal = await self.illuminate_with_shards(opp, next_opp, routing=routing)
                    else:
                        proposal = await self._synthesize_with_llm(opp, routing=routing)

                    if proposal:
                        await self.send_message(
                            MessageType.VALIDATE_REQUEST,
                            NaaruRegion.VALIDATION,
                            {"proposal": proposal},
                        )
                    self.stats["tasks_completed"] += 1
                else:
                    await self.send_message(
                        MessageType.ANALYZE_REQUEST,
                        NaaruRegion.ANALYSIS,
                        {"target": opp.get("target_module")},
                    )

            elif msg and msg.type == MessageType.REFINE_REQUEST:
                # Resonance: Refine rejected proposal
                if self.model:
                    refined = await self._refine_with_feedback(msg.payload)
                    if refined:
                        await self.send_message(
                            MessageType.VALIDATE_REQUEST,
                            NaaruRegion.VALIDATION,
                            {"proposal": refined},
                        )
                    self.stats["refinements"] = self.stats.get("refinements", 0) + 1

            elif msg and msg.type == MessageType.SHUTDOWN:
                break

            await asyncio.sleep(0.01)

    async def harmonize(self, opportunity: dict, routing: dict | None = None) -> dict | None:
        """Harmonic Synthesis - Multi-persona generation with voting.
        
        This is the novel technique from RFC-019:
        1. Generate with ALL lens personas IN PARALLEL
        2. Each persona votes on all candidates
        3. Winner = majority vote
        
        Theory: Standard self-consistency uses temperature for variance.
        Harmonic Synthesis uses STRUCTURED variance via domain expertise.
        
        Args:
            opportunity: Task description and metadata
            routing: RFC-020 Attunement decision with intent, lens, focus
        """
        if not self.model:
            return None

        description = opportunity.get("description", "")
        category = opportunity.get("category", "code_quality")

        # RFC-020: Use routing to enhance synthesis
        routing_context = ""
        recommended_lens = None
        if routing:
            intent = routing.get("intent", "unknown")
            recommended_lens = routing.get("lens")
            focus = routing.get("focus", [])
            if focus:
                routing_context = f"\nFOCUS AREAS: {', '.join(focus)}"
            self.stats["routed_intents"] = self.stats.get("routed_intents", {})
            self.stats["routed_intents"][intent] = self.stats["routed_intents"].get(intent, 0) + 1

        from sunwell.models.protocol import GenerateOptions

        # Step 1: Generate with ALL lens personas IN PARALLEL
        # RFC-028: Get rotation plan based on model size and config
        rotation_prompt = ""
        if self.config.rotation and self.config.rotation_intensity != "none":
            # Use ThoughtLexer (with tiny model) for intelligent task classification
            rotation_plan = await self.thought_lexer.lex(description, self.model_size)
            rotation_prompt = rotation_plan.to_system_prompt()
            self.stats["rotation_enabled"] = True
            self.stats["rotation_intensity"] = self.config.rotation_intensity
            self.stats["rotation_task_type"] = rotation_plan.task_type

        async def generate_with_lens(lens_id: str, lens: dict) -> dict | None:
            # RFC-020: Boost recommended lens with extra context
            boost = ""
            if recommended_lens and lens_id == recommended_lens:
                boost = "\n[You are the RECOMMENDED expert for this task. Be thorough.]"

            # Build prompt: Lens identity + optional rotation structure + task
            prompt = f"""{lens['system']}{boost}
{rotation_prompt}
TASK: {description}{routing_context}
Code only:"""
            try:
                result = await self.model.generate(
                    prompt,
                    options=GenerateOptions(
                        temperature=self.config.voice_temperature,
                        max_tokens=1024,
                    ),
                )
                return {
                    "lens": lens_id,
                    "lens_name": lens["name"],
                    "code": result.content or "",
                    "tokens": result.usage.total_tokens if result.usage else 0,
                }
            except Exception:
                return None

        generation_tasks = [
            generate_with_lens(lens_id, lens)
            for lens_id, lens in self.LENS_PERSONAS.items()
        ]
        results = await asyncio.gather(*generation_tasks)

        candidates = [r for r in results if r is not None]
        total_tokens = sum(c["tokens"] for c in candidates)

        if not candidates:
            return None

        # Step 2: Build vote prompt
        vote_prompt = f"""You are selecting the BEST code solution.

TASK: {description}

"""
        for i, c in enumerate(candidates):
            vote_prompt += f"""
SOLUTION {i+1} (from {c['lens_name']}):
```python
{c['code'][:500]}
```
"""

        vote_prompt += """
Which solution is BEST? Consider correctness, completeness, and code quality.
Respond with ONLY the number (1, 2, or 3):"""

        # Step 3: Collect votes IN PARALLEL
        async def vote_as_lens(lens_id: str, lens: dict) -> tuple[int, int]:
            try:
                vote_result = await self.model.generate(
                    f"{lens['system']}\n\n{vote_prompt}",
                    options=GenerateOptions(temperature=0.1, max_tokens=10),
                )
                tokens = vote_result.usage.total_tokens if vote_result.usage else 0
                vote_text = vote_result.content or "1"
                vote = int("".join(c for c in vote_text if c.isdigit())[:1]) - 1
                vote = max(0, min(vote, len(candidates) - 1))
                return vote, tokens
            except Exception:
                return 0, 0

        vote_tasks = [
            vote_as_lens(lens_id, lens)
            for lens_id, lens in self.LENS_PERSONAS.items()
        ]
        vote_results = await asyncio.gather(*vote_tasks)

        votes = [v[0] for v in vote_results]
        total_tokens += sum(v[1] for v in vote_results)

        # Majority vote
        winner_idx = Counter(votes).most_common(1)[0][0]
        best = candidates[winner_idx]

        proposal_id = f"harmonic_{uuid.uuid4().hex[:8]}"

        self.generated_code.append({
            "id": proposal_id,
            "category": category,
            "code": best["code"],
            "tokens": total_tokens,
            "harmonic_synthesis": True,
            "winning_lens": best["lens"],
            "votes": votes,
        })

        self.stats["harmonic_wins"] = self.stats.get("harmonic_wins", 0) + 1

        return {
            "proposal_id": proposal_id,
            "diff": best["code"],
            "summary": {
                "rationale": f"{description} (via Harmonic Synthesis, winner: {best['lens_name']})",
                "category": category,
            },
        }

    async def illuminate_with_shards(
        self,
        opportunity: dict,
        next_opportunity: dict | None = None,
        routing: dict | None = None,
    ) -> dict | None:
        """Shard-assisted synthesis - Overlap generation with CPU helpers.
        
        While the GPU generates tokens, CPU-bound Shards gather context:
        - Memory Fetcher: Query SimulacrumStore
        - Context Preparer: Load lens, embed query
        - Lookahead: Pre-fetch for next task
        
        This overlaps I/O with compute for faster wall-clock time.
        
        Args:
            routing: RFC-020 Attunement decision with intent, lens, focus
        """
        if not self.model:
            return None

        description = opportunity.get("description", "")
        category = opportunity.get("category", "code_quality")

        from sunwell.models.protocol import GenerateOptions

        # RFC-020: Use routing to enhance context
        routing_context = ""
        if routing:
            focus = routing.get("focus", [])
            if focus:
                routing_context = f"\nFOCUS AREAS: {', '.join(focus)}"

        # Check prefetch cache
        task_key = f"{category}:{description[:50]}"
        prefetched = self._prefetch_cache.pop(task_key, None)

        context_section = ""
        if prefetched:
            memories = prefetched.get("memories", [])
            if memories:
                context_section = "\nRELEVANT CONTEXT:\n" + "\n".join(f"- {m}" for m in memories[:3])
            self.stats["prefetch_hits"] = self.stats.get("prefetch_hits", 0) + 1

        prompt = f"""{description}{routing_context}{context_section}
Code only:"""

        # Generate AND prefetch next task in parallel
        async def generate():
            return await self.model.generate(
                prompt,
                options=GenerateOptions(
                    temperature=self.config.voice_temperature,
                    max_tokens=512,
                ),
            )

        async def prefetch_next():
            if not next_opportunity or not self.shard_pool:
                return None

            next_desc = next_opportunity.get("description", "")
            next_cat = next_opportunity.get("category", "")
            next_key = f"{next_cat}:{next_desc[:50]}"

            try:
                await self.shard_pool.prepare_for_task(next_opportunity)

                if self.convergence:
                    memories_slot = await self.convergence.get(f"memories:{next_cat}")
                    memories = memories_slot.content if memories_slot else []

                    self._prefetch_cache[next_key] = {
                        "memories": memories,
                        "from_shards": True,
                    }
                    self.stats["shard_prefetch"] = self.stats.get("shard_prefetch", 0) + 1
                return True
            except Exception:
                return None

        # Run both in parallel
        results = await asyncio.gather(generate(), prefetch_next(), return_exceptions=True)

        result = results[0]
        if isinstance(result, Exception):
            return {"error": str(result)}

        code = result.content or ""
        proposal_id = f"shard_{uuid.uuid4().hex[:8]}"

        self.generated_code.append({
            "id": proposal_id,
            "category": category,
            "code": code,
            "tokens": result.usage.total_tokens if result.usage else 0,
            "shard_assisted": True,
            "had_prefetched_context": prefetched is not None,
        })

        return {
            "proposal_id": proposal_id,
            "diff": code,
            "summary": {
                "rationale": description,
                "category": category,
            },
        }

    async def _synthesize_with_llm(self, opportunity: dict, routing: dict | None = None) -> dict | None:
        """Standard LLM synthesis (no Harmonic or Shards).
        
        Args:
            routing: RFC-020 Attunement decision with intent, lens, focus
        """
        if not self.model:
            return None

        description = opportunity.get("description", "")
        category = opportunity.get("category", "code_quality")

        # RFC-020: Use routing to enhance prompt
        routing_context = ""
        if routing:
            focus = routing.get("focus", [])
            if focus:
                routing_context = f"\nFOCUS: {', '.join(focus)}\n"

        # RFC-028: Get rotation prompt (for single-gen, only for medium/light models)
        rotation_section = ""
        if self.config.rotation and self.config.rotation_intensity in ("light", "standard"):
            rotation_plan = await self.thought_lexer.lex(description, self.model_size)
            rotation_section = rotation_plan.to_system_prompt() + "\n\n"

        prompts = {
            "error_handling": f"{rotation_section}Write Python error handling for: {description}{routing_context}\nCode only:",
            "testing": f"{rotation_section}Write pytest test for: {description}{routing_context}\nCode only:",
            "documentation": f"{rotation_section}Write docstring for: {description}{routing_context}\nDocstring only:",
            "code_quality": f"{rotation_section}Improve this Python code: {description}{routing_context}\nCode only:",
        }

        prompt = prompts.get(category, prompts["code_quality"])

        try:
            from sunwell.models.protocol import GenerateOptions

            result = await self.model.generate(
                prompt,
                options=GenerateOptions(
                    temperature=self.config.voice_temperature,
                    max_tokens=512,
                ),
            )

            code = result.content or ""
            proposal_id = f"synth_{uuid.uuid4().hex[:8]}"

            self.generated_code.append({
                "id": proposal_id,
                "category": category,
                "code": code,
                "tokens": result.usage.total_tokens if result.usage else 0,
            })

            return {
                "proposal_id": proposal_id,
                "diff": code,
                "summary": {"rationale": description, "category": category},
            }

        except Exception as e:
            return {"error": str(e)}

    async def _synthesize_basic(self, findings: dict) -> dict | None:
        """Generate a proposal from findings (MirrorHandler fallback)."""
        if "error" in findings:
            return None

        try:
            result = await self.mirror.handle("propose_improvement", {
                "scope": "heuristic",
                "problem": "Improve based on analysis",
                "evidence": [json.dumps(findings)[:500]],
                "diff": "# Auto-generated improvement",
            })
            return json.loads(result)
        except Exception:
            return None

    async def _refine_with_feedback(self, payload: dict) -> dict | None:
        """Resonance: Refine rejected code based on feedback."""
        if not self.model:
            return None

        original_code = payload.get("original_code", "")
        feedback = payload.get("feedback", "")
        issues = payload.get("issues", [])
        category = payload.get("category", "code_quality")
        original_id = payload.get("proposal_id", "")
        attempt = payload.get("attempt", 1)

        issues_text = "\n".join(f"- {issue}" for issue in issues) if issues else feedback

        refine_prompt = f"""The following code was rejected by quality review.

ORIGINAL CODE:
```python
{original_code}
```

ISSUES TO FIX:
{issues_text}

Write an IMPROVED version that fixes ALL the issues above.
Keep the same functionality but address the quality concerns.
Code only, no explanations:"""

        try:
            from sunwell.models.protocol import GenerateOptions

            result = await self.model.generate(
                refine_prompt,
                options=GenerateOptions(
                    temperature=min(self.config.voice_temperature + 0.1, 0.7),
                    max_tokens=768,
                ),
            )

            refined_code = result.content or ""
            proposal_id = f"{original_id}_r{attempt}"

            self.generated_code.append({
                "id": proposal_id,
                "category": category,
                "code": refined_code,
                "tokens": result.usage.total_tokens if result.usage else 0,
                "is_refinement": True,
                "original_id": original_id,
                "attempt": attempt,
            })

            return {
                "proposal_id": proposal_id,
                "diff": refined_code,
                "summary": {
                    "rationale": f"Refined based on feedback: {feedback[:100]}",
                    "category": category,
                },
                "refinement_attempt": attempt,
                "original_proposal_id": original_id,
            }

        except Exception as e:
            # CRITICAL: Must include refinement_attempt to prevent infinite loop
            return {
                "error": str(e),
                "refinement_attempt": attempt,  # Preserve attempt count
                "proposal_id": f"{original_id}_r{attempt}_error",
            }


class ValidationWorker(RegionWorker):
    """Validation region with Tiered Validation.
    
    Tiered Validation:
    1. Structural checks (no LLM) - catch syntax errors, missing imports
    2. FunctionGemma (270M) - fast approve/reject for clear cases
    3. Full LLM judge - only for borderline/uncertain cases
    """

    def __init__(
        self,
        *args,
        model=None,
        config: NaaruConfig | None = None,
        resonance=None,
        **kwargs,
    ):
        super().__init__(NaaruRegion.VALIDATION, *args, **kwargs)
        self.model = model
        self.config = config or NaaruConfig()
        self.resonance = resonance
        self.approved_count = 0
        self.rejected_count = 0
        self.refined_count = 0
        self.quality_scores: list[float] = []
        self.lightweight_decisions = 0
        self.escalated_to_llm = 0

        self._discernment = None
        if self.config.discernment:
            try:
                from sunwell.naaru.discernment import Discernment
                self._discernment = Discernment()
            except ImportError:
                pass

    async def process(self) -> None:
        """Validate proposals using tiered validation."""
        while not self._stop_event.is_set():
            msg = await self.bus.receive(self.region)

            if msg and msg.type == MessageType.VALIDATE_REQUEST:
                proposal = msg.payload.get("proposal", {})

                if self._discernment:
                    is_valid, reason, score, issues = await self._validate_tiered(proposal)
                elif self.model:
                    is_valid, reason, score, issues = await self._validate_with_llm(proposal)
                    self.quality_scores.append(score)
                else:
                    is_valid, reason = self._validate_basic(proposal)
                    score = 10.0 if is_valid else 0.0
                    issues = []

                current_attempt = proposal.get("refinement_attempt", 0)

                if is_valid:
                    await self.send_message(
                        MessageType.VALIDATION_RESULT,
                        NaaruRegion.EXECUTIVE,
                        {
                            "proposal_id": proposal.get("proposal_id"),
                            "valid": True,
                            "reason": reason,
                            "quality_score": score,
                            "refinement_attempts": current_attempt,
                        },
                    )
                    self.approved_count += 1
                    if current_attempt > 0:
                        self.refined_count += 1

                elif current_attempt < self.config.resonance:
                    # Resonance: Send back for refinement
                    await self.send_message(
                        MessageType.REFINE_REQUEST,
                        NaaruRegion.SYNTHESIS,
                        {
                            "proposal_id": proposal.get("proposal_id"),
                            "original_code": proposal.get("diff", ""),
                            "feedback": reason,
                            "issues": issues,
                            "score": score,
                            "category": proposal.get("summary", {}).get("category", "code_quality"),
                            "attempt": current_attempt + 1,
                        },
                    )
                    self.stats["resonance_requests"] = self.stats.get("resonance_requests", 0) + 1

                else:
                    # Final rejection
                    await self.send_message(
                        MessageType.VALIDATION_RESULT,
                        NaaruRegion.EXECUTIVE,
                        {
                            "proposal_id": proposal.get("proposal_id"),
                            "valid": False,
                            "reason": f"Rejected after {current_attempt} refinement attempts: {reason}",
                            "quality_score": score,
                            "refinement_attempts": current_attempt,
                        },
                    )
                    self.rejected_count += 1

                self.stats["tasks_completed"] += 1

            elif msg and msg.type == MessageType.SHUTDOWN:
                break

            await asyncio.sleep(0.01)

    async def _validate_tiered(self, proposal: dict) -> tuple[bool, str, float, list[str]]:
        """Tiered validation: FunctionGemma first, escalate if uncertain."""
        from sunwell.naaru.discernment import DiscernmentVerdict

        result = await self._discernment.evaluate(proposal)

        if result.confident:
            self.lightweight_decisions += 1
            self.quality_scores.append(result.score)

            if result.verdict == DiscernmentVerdict.APPROVE:
                return True, result.reason, result.score, result.issues
            elif result.verdict in (DiscernmentVerdict.REJECT, DiscernmentVerdict.NEEDS_REFINEMENT):
                return False, result.reason, result.score, result.issues

        # Escalate to full LLM
        self.escalated_to_llm += 1

        if self.model:
            return await self._validate_with_llm(proposal)
        else:
            is_valid = result.score >= self.config.purity_threshold
            return is_valid, result.reason, result.score, result.issues

    async def _validate_with_llm(self, proposal: dict) -> tuple[bool, str, float, list[str]]:
        """Full LLM judge validation."""
        diff = proposal.get("diff", "")
        rationale = proposal.get("summary", {}).get("rationale", "")
        category = proposal.get("summary", {}).get("category", "code_quality")

        judge_prompt = f"""You are an expert code reviewer. Evaluate this code:

INTENT: {rationale}
CATEGORY: {category}

CODE:
```python
{diff[:2500]}
```

CRITERIA (score each):
1. CORRECTNESS (0-3): Does it work?
2. CODE QUALITY (0-3): Is it idiomatic?
3. SAFETY (0-2): Any vulnerabilities?
4. COMPLETENESS (0-2): Is it complete?

Score >= 6 = production-ready.

Respond with ONLY JSON:
{{"score": <0-10>, "issues": ["issue1", "issue2"], "verdict": "approve" or "reject"}}"""

        try:
            from sunwell.models.protocol import GenerateOptions

            result = await self.model.generate(
                judge_prompt,
                options=GenerateOptions(temperature=0.1, max_tokens=500),
            )

            response_text = result.content or ""

            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                judge_result = json.loads(json_match.group())
                score = float(judge_result.get("score", 0))
                issues = judge_result.get("issues", [])
                verdict = judge_result.get("verdict", "reject")

                is_valid = score >= self.config.purity_threshold and verdict == "approve"
                reason = f"Score: {score}/10" + (f" Issues: {', '.join(issues[:2])}" if issues else "")

                return is_valid, reason, score, issues
            else:
                return True, "Judge parse error - defaulting to approve", 7.0, []

        except Exception as e:
            is_valid, reason = self._validate_basic(proposal)
            return is_valid, f"LLM error ({e}) - basic validation: {reason}", 5.0, []

    def _validate_basic(self, proposal: dict) -> tuple[bool, str]:
        """Basic structural validation (fallback)."""
        if "error" in proposal:
            return False, proposal["error"]
        if not proposal.get("proposal_id"):
            return False, "No proposal ID"
        return True, "OK"

    def get_quality_stats(self) -> dict:
        """Get quality scoring statistics."""
        if not self.quality_scores:
            return {"avg_score": 0, "min_score": 0, "max_score": 0, "count": 0}

        return {
            "avg_score": sum(self.quality_scores) / len(self.quality_scores),
            "min_score": min(self.quality_scores),
            "max_score": max(self.quality_scores),
            "count": len(self.quality_scores),
        }


class MemoryWorker(RegionWorker):
    """Memory region - simulacrum operations, learning persistence."""

    def __init__(self, *args, **kwargs):
        super().__init__(NaaruRegion.MEMORY, *args, **kwargs)
        self.learnings: list[dict] = []

    async def process(self) -> None:
        """Handle memory operations."""
        while not self._stop_event.is_set():
            msg = await self.bus.receive(self.region)

            if msg and msg.type == MessageType.MEMORIZE_REQUEST:
                learning = msg.payload
                self.learnings.append({
                    "content": learning,
                    "timestamp": datetime.now().isoformat(),
                    "source": msg.source.value,
                })
                self.stats["tasks_completed"] += 1

            elif msg and msg.type == MessageType.PATTERN_FOUND:
                self.learnings.append({
                    "type": "pattern",
                    "content": msg.payload,
                    "timestamp": datetime.now().isoformat(),
                })

            elif msg and msg.type == MessageType.SHUTDOWN:
                break

            await asyncio.sleep(0.01)


class ExecutiveWorker(RegionWorker):
    """Executive region - coordination, prioritization, attention."""

    def __init__(self, *args, on_output: Callable = None, **kwargs):
        super().__init__(NaaruRegion.EXECUTIVE, *args, **kwargs)
        self.on_output = on_output
        self.completed_proposals: list[dict] = []
        self.attention_focus: str | None = None

    async def process(self) -> None:
        """Coordinate other regions and track progress."""
        while not self._stop_event.is_set():
            msg = await self.bus.receive(self.region)

            if msg and msg.type == MessageType.VALIDATION_RESULT:
                result = msg.payload
                self.completed_proposals.append(result)

                if self.on_output:
                    status = "✅" if result["valid"] else "❌"
                    self.on_output(f"{status} {result.get('proposal_id', '?')}")

                self.stats["tasks_completed"] += 1

            elif msg and msg.type == MessageType.ATTENTION_SHIFT:
                self.attention_focus = msg.payload.get("focus")

            elif msg and msg.type == MessageType.SHUTDOWN:
                break

            await asyncio.sleep(0.01)


class CognitiveRoutingWorker(RegionWorker):
    """Routing region - RFC-030 UnifiedRouter for all routing decisions.
    
    RFC-030 MIGRATION: Now uses UnifiedRouter instead of CognitiveRouter.
    The UnifiedRouter handles ALL routing decisions in a single inference:
    - intent: What kind of task is this?
    - complexity: How complex is the task?
    - lens: Which lens should handle it?
    - tools: What tools might be needed?
    - mood: User's emotional state
    - expertise: User's skill level
    - confidence: How certain is the routing?
    
    Backward Compatibility:
        The output format is compatible with legacy consumers via
        LegacyRoutingAdapter. Existing code using the routing dict
        will continue to work.
    """

    def __init__(
        self,
        *args,
        router_model=None,
        available_lenses: list[str] | None = None,
        use_unified_router: bool = True,  # RFC-030: Default to new router
        cache_size: int = 1000,
        **kwargs,
    ):
        super().__init__(NaaruRegion.ROUTING, *args, **kwargs)
        self.router_model = router_model
        self.available_lenses = available_lenses or []
        self.use_unified_router = use_unified_router
        self.cache_size = cache_size
        self._router = None
        self._legacy_adapter = None
        self._routing_history: list[dict] = []

    async def _ensure_router(self):
        """Lazily initialize the router (UnifiedRouter or CognitiveRouter)."""
        if self._router is None and self.router_model is not None:
            if self.use_unified_router:
                # RFC-030: Use UnifiedRouter
                from sunwell.routing import LegacyRoutingAdapter, UnifiedRouter
                self._router = UnifiedRouter(
                    model=self.router_model,
                    cache_size=self.cache_size,
                    available_lenses=self.available_lenses,
                )
                self._legacy_adapter = LegacyRoutingAdapter(self._router)
            else:
                # Legacy: Use CognitiveRouter (deprecated)
                from sunwell.routing import CognitiveRouter
                self._router = CognitiveRouter(
                    router_model=self.router_model,
                    available_lenses=self.available_lenses,
                )

    async def process(self) -> None:
        """Process routing requests."""
        while not self._stop_event.is_set():
            msg = await self.bus.receive(self.region)

            if msg and msg.type == MessageType.ROUTE_REQUEST:
                task = msg.payload.get("task", "")
                context = msg.payload.get("context")

                routing = await self._route_task(task, context)

                await self.send_message(
                    MessageType.ROUTE_COMPLETE,
                    msg.source,  # Reply to sender
                    {
                        "task": task,
                        "routing": routing,
                    },
                )
                self.stats["tasks_completed"] += 1

            elif msg and msg.type == MessageType.SHUTDOWN:
                break

            await asyncio.sleep(0.01)

    async def _route_task(self, task: str, context: dict | None = None) -> dict:
        """Route a task and return the routing decision.
        
        RFC-030: Uses UnifiedRouter by default, falling back to heuristics.
        Output format is backward-compatible with legacy consumers.
        """
        await self._ensure_router()

        if self._router is None:
            # Fallback: heuristic routing without LLM
            return self._heuristic_route(task)

        try:
            if self.use_unified_router and self._legacy_adapter:
                # RFC-030: Use UnifiedRouter with legacy adapter
                decision = await self._router.route(task, context)
                # Include both unified and legacy format
                result = decision.to_dict()
                # Add legacy-compatible fields
                legacy = await self._legacy_adapter.to_cognitive_router_decision(task, context)
                result.update({
                    "top_k": legacy["top_k"],
                    "threshold": legacy["threshold"],
                })
            else:
                # Legacy CognitiveRouter path
                decision = await self._router.route(task, context)
                result = decision.to_dict()

            self._routing_history.append({
                "task": task[:100],
                "decision": result,
                "timestamp": datetime.now().isoformat(),
            })
            return result
        except Exception as e:
            return {
                "error": str(e),
                "fallback": self._heuristic_route(task),
            }

    def _heuristic_route(self, task: str) -> dict:
        """Fallback heuristic routing without LLM."""
        task_lower = task.lower()

        # Simple keyword matching
        if any(kw in task_lower for kw in ["security", "vulnerability", "injection"]):
            return {
                "intent": "code_review",
                "lens": "code-reviewer",
                "focus": ["security", "vulnerability"],
                "top_k": 5,
                "confidence": 0.3,
            }
        elif any(kw in task_lower for kw in ["test", "coverage", "unittest"]):
            return {
                "intent": "testing",
                "lens": "team-qa",
                "focus": ["testing", "edge cases"],
                "top_k": 5,
                "confidence": 0.3,
            }
        elif any(kw in task_lower for kw in ["document", "readme", "explain"]):
            return {
                "intent": "documentation",
                "lens": "tech-writer",
                "focus": ["clarity", "examples"],
                "top_k": 5,
                "confidence": 0.3,
            }
        else:
            return {
                "intent": "unknown",
                "lens": "helper",
                "focus": [],
                "top_k": 5,
                "confidence": 0.1,
            }

    async def route_sync(self, task: str, context: dict | None = None) -> dict:
        """Synchronous routing for direct use (not via message bus)."""
        return await self._route_task(task, context)


class ToolRegionWorker(RegionWorker):
    """Executes tools on behalf of other regions (RFC-032).
    
    This is the bridge between Naaru's cognitive architecture and
    the outside world. All file I/O, commands, and web access
    flow through here.
    
    Message Types Handled:
    - TOOL_REQUEST: Execute a tool and return result
    - TOOL_BATCH: Execute multiple tools (parallel when possible)
    """

    def __init__(
        self,
        *args,
        tool_executor=None,
        **kwargs,
    ):
        super().__init__(NaaruRegion.TOOLS, *args, **kwargs)
        self.tool_executor = tool_executor
        self.execution_log: list[dict] = []

    async def process(self) -> None:
        """Process tool execution requests."""
        while not self._stop_event.is_set():
            msg = await self.bus.receive(self.region)

            if msg and msg.type == MessageType.TOOL_REQUEST:
                from sunwell.models.protocol import ToolCall

                tool_call = ToolCall(
                    id=msg.id,
                    name=msg.payload["tool"],
                    arguments=msg.payload["arguments"],
                )

                result = await self.tool_executor.execute(tool_call)

                # Log execution
                self.execution_log.append({
                    "request_id": msg.id,
                    "tool": msg.payload["tool"],
                    "success": result.success,
                    "timestamp": datetime.now().isoformat(),
                })

                await self.send_message(
                    MessageType.TOOL_RESULT,
                    msg.source,  # Reply to requester
                    {
                        "request_id": msg.id,
                        "success": result.success,
                        "output": result.output,
                        "artifacts": [str(p) for p in result.artifacts],
                    },
                )
                self.stats["tools_executed"] = self.stats.get("tools_executed", 0) + 1

            elif msg and msg.type == MessageType.TOOL_BATCH:
                # Execute multiple tools, parallel where possible
                results = await self._execute_batch(msg.payload["tools"])

                await self.send_message(
                    MessageType.TOOL_BATCH_RESULT,
                    msg.source,
                    {"results": results},
                )

            elif msg and msg.type == MessageType.SHUTDOWN:
                break

            await asyncio.sleep(0.01)

    async def _execute_batch(self, tool_specs: list[dict]) -> list[dict]:
        """Execute multiple tools, parallelizing independent ones."""
        from sunwell.models.protocol import ToolCall

        # For now, execute sequentially (safe default)
        results = []
        for spec in tool_specs:
            tool_call = ToolCall(
                id=spec.get("id", str(uuid.uuid4())),
                name=spec["tool"],
                arguments=spec["arguments"],
            )
            result = await self.tool_executor.execute(tool_call)
            results.append({
                "tool": spec["tool"],
                "success": result.success,
                "output": result.output,
            })
        return results


# =============================================================================
# RFC-032: Agent Mode Types
# =============================================================================


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


# =============================================================================
# Main Naaru Class
# =============================================================================


@dataclass
class Naaru:
    """The Naaru - Coordinated Intelligence for Local Models.
    
    This is the main entry point for the RFC-019 architecture.
    It coordinates all components to maximize quality and throughput
    from small local models.
    
    RFC-032 additions:
    - planner: TaskPlanner for goal decomposition
    - tool_executor: ToolExecutor for external actions
    - run(): Execute arbitrary user tasks (agent mode)
    
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
    convergence: Any = None  # Working memory (Convergence)
    shard_pool: Any = None   # Parallel helpers (ShardPool)
    resonance: Any = None    # Feedback loop (Resonance)

    # RFC-032: Agent mode components
    planner: Any = None      # TaskPlanner for goal decomposition
    tool_executor: Any = None  # ToolExecutor for external actions

    # Internal state
    bus: MessageBus = field(init=False)
    workers: list[RegionWorker] = field(init=False)
    _validation_worker: ValidationWorker = field(init=False)
    _synthesis_workers: list[HarmonicSynthesisWorker] = field(init=False)
    _routing_worker: CognitiveRoutingWorker | None = field(init=False)
    _tool_worker: ToolRegionWorker | None = field(init=False)

    def __post_init__(self):
        self.bus = MessageBus()
        self.workers = []
        self._routing_worker = None
        self._tool_worker = None

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
            output(f"   🎵 Harmonic Synthesis: {'ENABLED' if self.config.harmonic_synthesis else 'disabled'}")
        if self.judge_model:
            output(f"   🎯 Judge: ENABLED (threshold={self.config.purity_threshold})")
        if self.config.discernment:
            output("   ⚡ Tiered Validation: ENABLED")
        output(f"   🔄 Resonance: max {self.config.resonance} attempts")
        if self.config.attunement:
            router_name = getattr(self.config.attunement_model, 'model_id', None) or "synthesis model"
            output(f"   🧭 Cognitive Routing: ENABLED (RFC-020) via {router_name}")
        output("")

        # Create workers
        self._create_workers(on_output=output)

        # Start workers
        output("🚀 Starting Naaru regions...")
        tasks = []
        for worker in self.workers:
            task = asyncio.create_task(worker.process())
            tasks.append(task)

        # Discover opportunities
        output("🔍 Discovering opportunities...")
        from sunwell.naaru.discovery import OpportunityDiscoverer

        discoverer = OpportunityDiscoverer(
            mirror=MirrorHandler(self.sunwell_root, self.sunwell_root / ".sunwell" / "naaru"),
            sunwell_root=self.sunwell_root,
        )
        opportunities = await discoverer.discover(goals)
        output(f"   Found {len(opportunities)} opportunities")
        output("")

        # Feed opportunities
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

        # Let Naaru think
        output("💭 Illuminating...")
        await asyncio.sleep(max_time_seconds)

        # Shutdown
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
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Collect results
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
            output(f"   Approved: {results['approved_count']}, Rejected: {results['rejected_count']}")

        return results

    # =========================================================================
    # RFC-032: Agent Mode
    # =========================================================================

    async def run(
        self,
        goal: str,
        context: dict[str, Any] | None = None,
        on_progress: Callable[[str], None] | None = None,
        max_time_seconds: float = 300,
    ) -> AgentResult:
        """Execute an arbitrary user task (RFC-032 Agent Mode).
        
        This is the RFC-032 agent mode entry point. Unlike illuminate(),
        which focuses on self-improvement, run() can execute any user goal.
        
        Args:
            goal: What the user wants to accomplish
            context: Optional context (cwd, file state, etc.)
            on_progress: Callback for progress updates
            max_time_seconds: Maximum execution time
            
        Returns:
            AgentResult with outputs, artifacts, and execution trace
            
        Example:
            >>> result = await naaru.run(
            ...     "Build a React forum app",
            ...     context={"cwd": "/tmp/project"},
            ...     max_time_seconds=600,
            ... )
            >>> print(f"Completed: {result.completed_count}/{len(result.tasks)}")
        """
        from sunwell.naaru.types import TaskStatus

        output = on_progress or print
        start_time = datetime.now()

        # Ensure we have a planner
        if self.planner is None:
            from sunwell.naaru.planners import AgentPlanner

            available_tools = frozenset()
            if self.tool_executor:
                available_tools = frozenset(self.tool_executor.get_available_tools())

            self.planner = AgentPlanner(
                model=self.synthesis_model,
                available_tools=available_tools,
            )

        # Phase 1: Plan
        output("🎯 Planning...")
        tasks = await self.planner.plan([goal], context)
        output(f"   Created {len(tasks)} tasks")

        for i, task in enumerate(tasks, 1):
            deps = f" (after: {', '.join(task.depends_on)})" if task.depends_on else ""
            output(f"   {i}. {task.description}{deps}")
        output("")

        # Phase 2: Execute
        output("⚡ Executing...")
        tasks = await self._execute_task_graph(tasks, output, max_time_seconds)

        # Phase 3: Report
        completed = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)
        failed = sum(1 for t in tasks if t.status == TaskStatus.FAILED)

        elapsed = (datetime.now() - start_time).total_seconds()

        output(f"\n✨ Complete: {completed}/{len(tasks)} tasks succeeded ({elapsed:.1f}s)")
        if failed:
            output(f"   ⚠️ {failed} tasks failed")

        # Collect artifacts
        artifacts = self._collect_artifacts(tasks)

        return AgentResult(
            goal=goal,
            tasks=tasks,
            completed_count=completed,
            failed_count=failed,
            artifacts=artifacts,
            execution_time_seconds=elapsed,
        )

    async def _execute_task_graph(
        self,
        tasks: list,
        output: Callable[[str], None],
        max_time: float,
    ) -> list:
        """Execute tasks respecting dependencies AND parallelization (RFC-032, RFC-034).
        
        RFC-034 enhancements:
        - Tracks produced artifacts for artifact-based dependencies
        - Groups ready tasks for parallel execution based on resource conflicts
        - Respects parallel_group hints for safe concurrent execution
        """
        from sunwell.naaru.types import TaskStatus

        completed_ids: set[str] = set()
        completed_artifacts: set[str] = set()  # RFC-034: Track produced artifacts
        start_time = datetime.now()

        while True:
            # Check timeout
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed > max_time:
                output("⏰ Timeout reached")
                break

            # Find ready tasks (RFC-034: check both task deps AND artifact deps)
            ready = [
                t for t in tasks
                if t.status == TaskStatus.PENDING
                and t.is_ready(completed_ids, completed_artifacts)
            ]

            if not ready:
                # Check if we're done or stuck
                pending = [t for t in tasks if t.status == TaskStatus.PENDING]
                if not pending:
                    break  # All done

                # Check for deadlock (failed dependencies or missing artifacts)
                blocked = self._detect_deadlock(tasks, completed_ids, completed_artifacts)
                if blocked:
                    output(f"⚠️ {len(blocked)} tasks blocked")
                    for task in blocked:
                        output(f"   • {task.id}: {task.error}")
                break

            # RFC-034: Group ready tasks for parallel execution
            if self.config.enable_parallel_execution and len(ready) > 1:
                parallel_batches = self._group_for_parallel_execution(ready)
            else:
                # Sequential fallback: each task is its own batch
                parallel_batches = [[t] for t in ready]

            for batch in parallel_batches:
                if len(batch) == 1:
                    # Single task - execute directly
                    task = batch[0]
                    task.status = TaskStatus.IN_PROGRESS
                    output(f"   → {task.description}")

                    try:
                        await self._execute_single_task(task)
                        task.status = TaskStatus.COMPLETED
                        completed_ids.add(task.id)
                        completed_artifacts.update(task.produces)
                        output(f"   ✅ {task.id}")
                    except Exception as e:
                        task.status = TaskStatus.FAILED
                        task.error = str(e)
                        output(f"   ❌ {task.id}: {e}")
                else:
                    # Multiple tasks - execute in parallel (RFC-034)
                    output(f"   ⚡ Executing {len(batch)} tasks in parallel")
                    for task in batch:
                        task.status = TaskStatus.IN_PROGRESS
                        output(f"      → {task.description}")

                    # Execute all tasks concurrently
                    results = await asyncio.gather(
                        *[self._execute_single_task(t) for t in batch],
                        return_exceptions=True,
                    )

                    for task, result in zip(batch, results, strict=True):
                        if isinstance(result, Exception):
                            task.status = TaskStatus.FAILED
                            task.error = str(result)
                            output(f"      ❌ {task.id}: {result}")
                        else:
                            task.status = TaskStatus.COMPLETED
                            completed_ids.add(task.id)
                            completed_artifacts.update(task.produces)
                            output(f"      ✅ {task.id}")

        return tasks

    def _group_for_parallel_execution(self, ready: list) -> list[list]:
        """Group ready tasks into parallel-safe batches (RFC-034).
        
        Tasks can run in parallel if:
        1. They're in the same parallel_group (or both have None)
        2. Their `modifies` sets don't overlap (no file conflicts)
        
        Args:
            ready: List of ready tasks
            
        Returns:
            List of batches, where each batch can execute concurrently
        """
        batches: list[list] = []
        remaining = list(ready)
        max_batch_size = self.config.max_parallel_tasks

        while remaining:
            batch: list = [remaining.pop(0)]
            batch_modifies: set[str] = set(batch[0].modifies)
            batch_group = batch[0].parallel_group

            i = 0
            while i < len(remaining) and len(batch) < max_batch_size:
                task = remaining[i]

                # Check for conflicts
                has_file_conflict = bool(task.modifies & batch_modifies)
                same_group = (task.parallel_group == batch_group) or (
                    task.parallel_group is None and batch_group is None
                )

                if not has_file_conflict and same_group:
                    # No conflict - can parallelize
                    batch.append(task)
                    batch_modifies.update(task.modifies)
                    remaining.pop(i)
                else:
                    i += 1

            batches.append(batch)

        return batches

    async def _execute_single_task(self, task) -> None:
        """Execute a single task using synthesis + tools (RFC-032)."""
        from sunwell.naaru.types import TaskMode

        if task.mode == TaskMode.RESEARCH:
            # Research: use synthesis to gather info, no tools
            await self._research_task(task)

        elif task.mode == TaskMode.EXECUTE:
            # Execute: run command
            await self._execute_command_task(task)

        elif task.mode in (TaskMode.GENERATE, TaskMode.MODIFY):
            # Generate/Modify: use synthesis + write_file
            await self._generate_task(task)

        elif task.mode == TaskMode.COMPOSITE:
            # Composite: execute subtasks
            for subtask in task.subtasks:
                await self._execute_single_task(subtask)

        elif task.mode == TaskMode.SELF_IMPROVE:
            # Self-improvement: use existing synthesis workflow
            await self._self_improve_task(task)

        # Verify if verification command specified
        if task.verification_command:
            await self._verify_task(task)

    async def _research_task(self, task) -> None:
        """Execute a research task (gather information)."""
        if not self.synthesis_model:
            task.result = {"info": "No synthesis model available for research"}
            return

        from sunwell.models.protocol import GenerateOptions

        prompt = f"""Research the following topic and provide a summary:

TOPIC: {task.description}

Provide key findings in a structured format."""

        result = await self.synthesis_model.generate(
            prompt,
            options=GenerateOptions(temperature=0.3, max_tokens=1024),
        )

        task.result = {"research": result.content or ""}

    async def _execute_command_task(self, task) -> None:
        """Execute a shell command task using the task's specified tools.
        
        RFC-032: Tasks specify which tools they need. For execute mode:
        - If task has tools like git_init, use those directly
        - Fall back to run_command only if no specific tools specified
        """
        if not self.tool_executor:
            raise RuntimeError("No tool_executor configured for command execution")

        from sunwell.models.protocol import ToolCall

        available_tools = frozenset(self.tool_executor.get_available_tools())

        # Determine which tool to use
        # Priority: task's specified tools > run_command fallback
        tool_to_use = None
        tool_args: dict = {}

        # Check if task specifies tools that are available
        for tool_name in task.tools:
            if tool_name in available_tools and tool_name != "run_command":
                tool_to_use = tool_name
                break

        # Build tool call based on the tool type
        if tool_to_use:
            # Use the specific tool the task requested
            if tool_to_use == "git_init":
                tool_args = {"path": task.target_path or task.working_directory}
            elif tool_to_use == "mkdir":
                tool_args = {"path": task.target_path or task.description.split()[-1]}
            elif tool_to_use == "write_file":
                # GUARD: write_file needs content - redirect to _generate_task
                # This handles LLM incorrectly using mode=execute for file generation
                from sunwell.naaru.types import TaskMode
                task.mode = TaskMode.GENERATE
                return await self._generate_task(task)
            else:
                # Generic: pass target_path or description as the primary arg
                tool_args = {"path": task.target_path} if task.target_path else {}
        elif "run_command" in available_tools:
            # Fall back to run_command if available
            tool_to_use = "run_command"
            command = task.details.get("command") or task.description
            tool_args = {
                "command": command,
                "cwd": task.working_directory,
                "timeout": 120,
            }
        else:
            # Neither specific tools nor run_command available
            raise RuntimeError(
                f"Cannot execute task: requested tools {task.tools} not available, "
                f"and run_command not in available tools: {sorted(available_tools)}"
            )

        tool_call = ToolCall(
            id=f"exec_{task.id}",
            name=tool_to_use,
            arguments=tool_args,
        )
        result = await self.tool_executor.execute(tool_call)

        if not result.success:
            raise RuntimeError(f"Command failed: {result.output}")

        task.result = {"output": result.output}

    async def _generate_task(self, task) -> None:
        """Generate content using synthesis, then write to file."""
        if not self.synthesis_model:
            raise RuntimeError("No synthesis model available for content generation")

        from sunwell.models.protocol import GenerateOptions, ToolCall

        # Use synthesis to generate content
        prompt = f"""Generate the following content:

TASK: {task.description}

Provide only the content, no explanations:"""

        result = await self.synthesis_model.generate(
            prompt,
            options=GenerateOptions(temperature=0.3, max_tokens=2048),
        )

        content = result.content or ""

        # Write to file if target_path specified and tool_executor available
        if task.target_path and self.tool_executor:
            tool_call = ToolCall(
                id=f"write_{task.id}",
                name="write_file",
                arguments={"path": task.target_path, "content": content},
            )
            write_result = await self.tool_executor.execute(tool_call)

            if not write_result.success:
                raise RuntimeError(f"Write failed: {write_result.output}")

            task.result = {"content": content, "path": task.target_path}
        else:
            task.result = {"content": content}

    async def _self_improve_task(self, task) -> None:
        """Execute a self-improvement task (RFC-019 behavior)."""
        # This uses the existing synthesis workflow
        if self._synthesis_workers:
            worker = self._synthesis_workers[0]
            result = await worker.harmonize({
                "description": task.description,
                "category": task.category,
                "target_module": task.target_path,
            })
            task.result = result
        else:
            task.result = {"error": "No synthesis workers available"}

    async def _verify_task(self, task) -> None:
        """Run verification command for a task."""
        if not self.tool_executor or not task.verification_command:
            return

        from sunwell.models.protocol import ToolCall

        tool_call = ToolCall(
            id=f"verify_{task.id}",
            name="run_command",
            arguments={
                "command": task.verification_command,
                "cwd": task.working_directory,
                "timeout": 30,
            },
        )
        result = await self.tool_executor.execute(tool_call)

        if not result.success:
            raise RuntimeError(f"Verification failed: {result.output}")

    def _detect_deadlock(
        self,
        tasks: list,
        completed_ids: set[str],
        completed_artifacts: set[str] | None = None,
    ) -> list:
        """Detect tasks blocked by failed dependencies or missing artifacts (RFC-032, RFC-034).
        
        RFC-034: Also detects artifact-based deadlocks where required artifacts
        will never be produced (because the producing task failed).
        """
        from sunwell.naaru.types import TaskStatus

        failed_ids = {t.id for t in tasks if t.status == TaskStatus.FAILED}

        # RFC-034: Find artifacts that will never be produced
        failed_artifacts: set[str] = set()
        for task in tasks:
            if task.status == TaskStatus.FAILED:
                failed_artifacts.update(task.produces)

        blocked = []

        for task in tasks:
            if task.status != TaskStatus.PENDING:
                continue

            # Check if any task dependency failed
            failed_deps = set(task.depends_on) & failed_ids
            if failed_deps:
                task.status = TaskStatus.SKIPPED
                task.error = f"Blocked by failed tasks: {', '.join(failed_deps)}"
                blocked.append(task)
                continue

            # RFC-034: Check if any required artifact will never be produced
            if completed_artifacts is not None:
                missing_artifacts = task.requires - completed_artifacts
                blocked_artifacts = missing_artifacts & failed_artifacts
                if blocked_artifacts:
                    task.status = TaskStatus.SKIPPED
                    task.error = f"Blocked by missing artifacts: {', '.join(blocked_artifacts)}"
                    blocked.append(task)

        return blocked

    def _collect_artifacts(self, tasks: list) -> list[Path]:
        """Collect artifacts (created/modified files) from tasks."""
        artifacts = []
        for task in tasks:
            if task.result and task.result.get("path"):
                artifacts.append(Path(task.result["path"]))
        return artifacts

    def _get_available_tools(self) -> frozenset[str]:
        """Get available tools from tool_executor."""
        if self.tool_executor:
            return frozenset(self.tool_executor.get_available_tools())
        return frozenset()

    def _create_workers(self, on_output: Callable = None) -> None:
        """Create all Naaru region workers."""
        self._synthesis_workers = []

        # RFC-030: Create UnifiedRouter worker (replaces CognitiveRouter)
        if self.config.attunement:
            # RFC-030: Prefer new router config, fallback to legacy attunement_model
            router_model = None
            if hasattr(self.config, "router") and self.config.router:
                # Use configured router model
                from sunwell.models.ollama import OllamaModel
                router_model = OllamaModel(model=self.config.router)
            elif self.config.attunement_model:
                # Legacy: Use attunement_model
                router_model = self.config.attunement_model
            else:
                # Fallback to synthesis model
                router_model = self.synthesis_model

            # Discover available lenses
            lens_dir = self.sunwell_root / "lenses"
            available_lenses = []
            if lens_dir.exists():
                available_lenses = [p.stem for p in lens_dir.glob("*.lens")]

            # Get cache size from config
            cache_size = getattr(self.config, "router_cache_size", 1000)

            self._routing_worker = CognitiveRoutingWorker(
                bus=self.bus,
                sunwell_root=self.sunwell_root,
                router_model=router_model,
                available_lenses=available_lenses,
                use_unified_router=True,  # RFC-030: Enable new router
                cache_size=cache_size,
            )
            self.workers.append(self._routing_worker)

        # RFC-032: Tool execution region
        if self.tool_executor:
            self._tool_worker = ToolRegionWorker(
                bus=self.bus,
                sunwell_root=self.sunwell_root,
                tool_executor=self.tool_executor,
            )
            self.workers.append(self._tool_worker)

        # Analysis shards
        for i in range(self.config.num_analysis_shards):
            self.workers.append(AnalysisWorker(
                bus=self.bus,
                sunwell_root=self.sunwell_root,
                worker_id=i,
            ))

        # Synthesis shards with Harmonic Synthesis + Attunement
        for i in range(self.config.num_synthesis_shards):
            worker = HarmonicSynthesisWorker(
                bus=self.bus,
                sunwell_root=self.sunwell_root,
                worker_id=i,
                model=self.synthesis_model,
                config=self.config,
                convergence=self.convergence,
                shard_pool=self.shard_pool,
                routing_worker=self._routing_worker,  # RFC-020: Attunement
            )
            self._synthesis_workers.append(worker)
            self.workers.append(worker)

        # Validation worker with Tiered Validation
        self._validation_worker = ValidationWorker(
            bus=self.bus,
            sunwell_root=self.sunwell_root,
            model=self.judge_model,
            config=self.config,
            resonance=self.resonance,
        )
        self.workers.append(self._validation_worker)

        # Memory worker
        self.workers.append(MemoryWorker(
            bus=self.bus,
            sunwell_root=self.sunwell_root,
        ))

        # Executive worker
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


# =============================================================================
# Demo
# =============================================================================


async def demo():
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

    print("\nExample usage:")
    print('''
    from sunwell.naaru import Naaru, NaaruConfig
    
    naaru = Naaru(
        sunwell_root=Path("."),
        synthesis_model=OllamaModel("gemma3:1b"),
        judge_model=OllamaModel("gemma3:4b"),
        config=NaaruConfig(
            harmonic_synthesis=True,
            resonance=2,
        ),
    )
    
    results = await naaru.illuminate(
        goals=["improve error handling"],
        max_time_seconds=120,
    )
    ''')


if __name__ == "__main__":
    import asyncio
    asyncio.run(demo())
