"""Harmonic synthesis worker - multi-persona generation with voting."""


import asyncio
import json
import uuid
from collections import Counter, deque
from typing import TYPE_CHECKING

from sunwell.features.mirror import MirrorHandler
from sunwell.foundation.types.config import NaaruConfig
from sunwell.foundation.types.model_size import ModelSize
from sunwell.planning.naaru.core.bus import MessageType, NaaruRegion
from sunwell.planning.naaru.core.worker import RegionWorker
from sunwell.planning.naaru.expertise.language import Language

if TYPE_CHECKING:
    from sunwell.foundation.core.lens import Lens


# Language-specific default personas when no lens is available
# These are language-appropriate alternatives to avoid Python bias
LANGUAGE_DEFAULT_PERSONAS: dict[Language, dict[str, dict[str, str]]] = {
    Language.PYTHON: {
        "security": {
            "name": "Security Expert",
            "system": "Security expert. Focus on attack vectors, edge cases, defensive coding.",
        },
        "code_quality": {
            "name": "Code Reviewer",
            "system": "Senior Python developer. Clean, maintainable, idiomatic Python.",
        },
        "testing": {
            "name": "QA Engineer",
            "system": "QA engineer. Testability, edge cases, failure modes.",
        },
    },
    Language.TYPESCRIPT: {
        "security": {
            "name": "Security Expert",
            "system": "Security expert. Attack vectors, input validation, secure TS patterns.",
        },
        "code_quality": {
            "name": "Code Reviewer",
            "system": "Senior TypeScript developer. Type safety, clean architecture.",
        },
        "testing": {
            "name": "QA Engineer",
            "system": "QA engineer. Jest/Vitest testing, edge cases, failure modes.",
        },
    },
    Language.JAVASCRIPT: {
        "security": {
            "name": "Security Expert",
            "system": "Security expert. XSS prevention, input validation, secure JS patterns.",
        },
        "code_quality": {
            "name": "Code Reviewer",
            "system": "Senior JavaScript developer. Clean, readable, idiomatic JavaScript.",
        },
        "testing": {
            "name": "QA Engineer",
            "system": "QA engineer. Testability, edge cases, failure modes.",
        },
    },
    Language.RUST: {
        "security": {
            "name": "Security Expert",
            "system": "Security expert. Memory safety, unsafe blocks, secure Rust patterns.",
        },
        "code_quality": {
            "name": "Code Reviewer",
            "system": "Senior Rust developer. Ownership, lifetimes, idiomatic Rust.",
        },
        "testing": {
            "name": "QA Engineer",
            "system": "QA engineer. Property-based testing, edge cases, failure modes.",
        },
    },
    Language.GO: {
        "security": {
            "name": "Security Expert",
            "system": "Security expert. Concurrency safety, input validation, secure Go.",
        },
        "code_quality": {
            "name": "Code Reviewer",
            "system": "Senior Go developer. Simplicity, error handling, idiomatic Go.",
        },
        "testing": {
            "name": "QA Engineer",
            "system": "QA engineer. Table-driven tests, edge cases, failure modes.",
        },
    },
}

# Generic fallback personas (language-agnostic)
GENERIC_PERSONAS: dict[str, dict[str, str]] = {
    "security": {
        "name": "Security Expert",
        "system": "Security expert. Attack vectors, edge cases, defensive coding.",
    },
    "code_quality": {
        "name": "Code Reviewer",
        "system": "Senior developer. Clean, maintainable, idiomatic code.",
    },
    "testing": {
        "name": "QA Engineer",
        "system": "QA engineer. Testability, edge cases, failure modes.",
    },
}


class HarmonicSynthesisWorker(RegionWorker):
    """Synthesis region with Harmonic Synthesis (multi-persona generation).

    Harmonic Synthesis: Instead of generating once, the Naaru generates with
    MULTIPLE PERSONAS in parallel, then has them vote on the best solution.

    The key insight: temperature diversity gives random variance,
    lens diversity gives STRUCTURED variance based on domain knowledge.
    """

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
            workspace=self.workspace,
            storage_path=self.workspace / ".sunwell" / "naaru" / f"synthesis_{self.worker_id}",
        )
        self._pending_work: list[dict] = []
        # Bounded deque to prevent memory leak (keeps last 1000 generated code entries)
        self.generated_code: deque[dict] = deque(maxlen=1000)
        self._prefetch_cache: dict = {}

    def _get_personas(
        self,
        lens: Lens | None = None,
        language: Language = Language.UNKNOWN,
    ) -> dict[str, dict[str, str]]:
        """Get personas for harmonic synthesis from lens or language defaults.

        Priority:
        1. Derive from lens communication style and heuristics
        2. Use language-specific default personas
        3. Fall back to generic personas

        Args:
            lens: Optional lens to derive personas from
            language: Detected language for fallback personas

        Returns:
            Dict of persona_id -> {name, system} for harmonic synthesis
        """
        # If we have a lens with communication style, derive personas from it
        if lens and lens.communication:
            style = lens.communication.style or ""
            principles = lens.communication.principles or ()

            # Build a language-aware code quality persona from lens
            code_quality_system = style
            if principles:
                code_quality_system += f" {principles[0]}"

            return {
                "security": {
                    "name": "Security Expert",
                    "system": "Security expert. Attack vectors, edge cases, defensive coding.",
                },
                "code_quality": {
                    "name": lens.metadata.name,
                    "system": code_quality_system,
                },
                "testing": {
                    "name": "QA Engineer",
                    "system": "QA engineer. Testability, edge cases, failure modes.",
                },
            }

        # Use language-specific defaults
        if language in LANGUAGE_DEFAULT_PERSONAS:
            return LANGUAGE_DEFAULT_PERSONAS[language]

        # Fall back to generic
        return GENERIC_PERSONAS

    @property
    def model_size(self) -> ModelSize:
        """Detect model size from the synthesis model name."""
        if not self.model:
            return ModelSize.SMALL
        model_name = getattr(self.model, "model_id", "") or getattr(self.model, "name", "")
        return ModelSize.from_model_name(model_name)

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

                    # RFC-030: Unified Router - route task to get intent + lens
                    routing = None
                    if self.routing_worker and hasattr(self.config, "router") and self.config.router:
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

        # Detect language from description to select appropriate personas
        from sunwell.planning.naaru.expertise.language import detect_language

        lang_result = detect_language(description, self.workspace)
        language = lang_result.language

        # Get personas from lens or language defaults (no more hardcoded Python bias)
        # Note: lens loading would need to be passed through routing in future
        personas = self._get_personas(lens=None, language=language)

        from sunwell.models import GenerateOptions

        # Step 1: Generate with ALL lens personas IN PARALLEL
        async def generate_with_lens(lens_id: str, lens: dict) -> dict | None:
            # RFC-020: Boost recommended lens with extra context
            boost = ""
            if recommended_lens and lens_id == recommended_lens:
                boost = "\n[You are the RECOMMENDED expert for this task. Be thorough.]"

            # Build prompt: Lens identity + task
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
            for lens_id, lens in personas.items()
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
```
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
            for lens_id, lens in personas.items()
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

        from sunwell.models import GenerateOptions

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

        # Detect language from description
        lang_result = detect_language(description, self.workspace)
        language = lang_result.language
        lang_name = {
            Language.PYTHON: "Python",
            Language.TYPESCRIPT: "TypeScript",
            Language.JAVASCRIPT: "JavaScript",
            Language.RUST: "Rust",
            Language.GO: "Go",
        }.get(language, "")

        # Language-specific test framework
        test_framework = {
            Language.PYTHON: "pytest",
            Language.TYPESCRIPT: "Jest/Vitest",
            Language.JAVASCRIPT: "Jest",
            Language.RUST: "Rust #[test]",
            Language.GO: "Go testing",
        }.get(language, "unit")

        # RFC-020: Use routing to enhance prompt
        routing_context = ""
        if routing:
            focus = routing.get("focus", [])
            if focus:
                routing_context = f"\nFOCUS: {', '.join(focus)}\n"

        # Language-aware prompts
        lang_prefix = f"{lang_name} " if lang_name else ""
        prompts = {
            "error_handling": f"Write {lang_prefix}error handling for: {description}{routing_context}\nCode only:",
            "testing": f"Write {test_framework} test for: {description}{routing_context}\nCode only:",
            "documentation": f"Write docstring/comment for: {description}{routing_context}\nDoc only:",
            "code_quality": f"Improve this {lang_prefix}code: {description}{routing_context}\nCode only:",
        }

        prompt = prompts.get(category, prompts["code_quality"])

        try:
            from sunwell.models import GenerateOptions

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
            from sunwell.models import GenerateOptions

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
