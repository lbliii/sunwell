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
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from sunwell.naaru.types import (
    SessionConfig,
    Opportunity,
    OpportunityCategory,
    RiskLevel,
)
from sunwell.mirror import MirrorHandler
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
        except asyncio.TimeoutError:
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
        async def generate_with_lens(lens_id: str, lens: dict) -> dict | None:
            # RFC-020: Boost recommended lens with extra context
            boost = ""
            if recommended_lens and lens_id == recommended_lens:
                boost = "\n[You are the RECOMMENDED expert for this task. Be thorough.]"
            
            prompt = f"""{lens['system']}{boost}

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
        
        prompts = {
            "error_handling": f"Write Python error handling for: {description}{routing_context}\nCode only:",
            "testing": f"Write pytest test for: {description}{routing_context}\nCode only:",
            "documentation": f"Write docstring for: {description}{routing_context}\nDocstring only:",
            "code_quality": f"Improve this Python code: {description}{routing_context}\nCode only:",
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
    """Routing region - RFC-020 intent-aware routing with tiny LLM.
    
    This worker uses a CognitiveRouter to classify task intent,
    select appropriate lenses, and tune retrieval parameters.
    
    The routing decision provides:
    - intent: What kind of task is this?
    - lens: Which lens should handle it?
    - focus: What keywords to boost in retrieval?
    - top_k: How many heuristics to retrieve?
    - confidence: How certain is the routing?
    """
    
    def __init__(
        self,
        *args,
        router_model=None,
        available_lenses: list[str] | None = None,
        **kwargs,
    ):
        super().__init__(NaaruRegion.ROUTING, *args, **kwargs)
        self.router_model = router_model
        self.available_lenses = available_lenses or []
        self._router = None
        self._routing_history: list[dict] = []
    
    async def _ensure_router(self):
        """Lazily initialize the CognitiveRouter."""
        if self._router is None and self.router_model is not None:
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
        """Route a task and return the routing decision."""
        await self._ensure_router()
        
        if self._router is None:
            # Fallback: heuristic routing without LLM
            return self._heuristic_route(task)
        
        try:
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


# =============================================================================
# Main Naaru Class
# =============================================================================


@dataclass
class Naaru:
    """The Naaru - Coordinated Intelligence for Local Models.
    
    This is the main entry point for the RFC-019 architecture.
    It coordinates all components to maximize quality and throughput
    from small local models.
    
    Example:
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
    """
    
    sunwell_root: Path
    synthesis_model: Any = None
    judge_model: Any = None
    config: NaaruConfig = field(default_factory=NaaruConfig)
    
    # Optional components
    convergence: Any = None  # Working memory (Convergence)
    shard_pool: Any = None   # Parallel helpers (ShardPool)
    resonance: Any = None    # Feedback loop (Resonance)
    
    # Internal state
    bus: MessageBus = field(init=False)
    workers: list[RegionWorker] = field(init=False)
    _validation_worker: ValidationWorker = field(init=False)
    _synthesis_workers: list[HarmonicSynthesisWorker] = field(init=False)
    _routing_worker: CognitiveRoutingWorker | None = field(init=False)
    
    def __post_init__(self):
        self.bus = MessageBus()
        self.workers = []
        self._routing_worker = None
    
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
            output(f"   ⚡ Tiered Validation: ENABLED")
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
            output(f"\n🎵 Synthesis (Harmonic Generation):")
            output(f"   Code generated: {len(results['generated_code'])} proposals")
            output(f"   Total tokens: {results['total_tokens']}")
        
        if self.judge_model and results.get("quality_stats"):
            qs = results["quality_stats"]
            output(f"\n🎯 Quality Scores:")
            output(f"   Average: {qs['avg_score']:.1f}/10")
            output(f"   Range: {qs['min_score']:.1f} - {qs['max_score']:.1f}")
            output(f"   Approved: {results['approved_count']}, Rejected: {results['rejected_count']}")
        
        return results
    
    def _create_workers(self, on_output: Callable = None) -> None:
        """Create all Naaru region workers."""
        self._synthesis_workers = []
        
        # RFC-020: Create Cognitive Routing worker FIRST (needed by synthesis)
        if self.config.attunement:
            # Use dedicated router model or fallback to synthesis model
            router_model = self.config.attunement_model or self.synthesis_model
            
            # Discover available lenses
            lens_dir = self.sunwell_root / "lenses"
            available_lenses = []
            if lens_dir.exists():
                available_lenses = [p.stem for p in lens_dir.glob("*.lens")]
            
            self._routing_worker = CognitiveRoutingWorker(
                bus=self.bus,
                sunwell_root=self.sunwell_root,
                router_model=router_model,
                available_lenses=available_lenses,
            )
            self.workers.append(self._routing_worker)
        
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
