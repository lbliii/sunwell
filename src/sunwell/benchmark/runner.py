"""Benchmark Runner (RFC-018).

Executes benchmark tasks across multiple conditions:
- Bare: No system prompt (raw model capability)
- Flat: Full lens context injected
- Selective: Sunwell's selective retrieval approach
- Competitor: Optional external baseline
"""


import asyncio
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from sunwell.benchmark.types import (
    BenchmarkResults,
    BenchmarkTask,
    Condition,
    ConditionOutput,
    NaaruMode,
    PromptStrategy,
    RetrievalMetrics,
    RoutingMetrics,
    RubricDimension,
    SelfDirectedMetrics,
    TaskCategory,
    TaskEvaluation,
    TaskResult,
)
from sunwell.models.protocol import GenerateOptions, ModelProtocol

if TYPE_CHECKING:
    from sunwell.benchmark.types import PrefetchMetrics
    from sunwell.core.heuristic import Heuristic
    from sunwell.core.lens import Lens
    from sunwell.schema.loader import LensLoader


# =============================================================================
# Prompt Strategies
# =============================================================================

class PromptBuilder:
    """Build system prompts using different strategies.

    Strategies are based on prompting research:
    - https://www.promptingguide.ai/techniques
    - https://www.promptingguide.ai/agents/context-engineering
    """

    @staticmethod
    def build(
        heuristics: list[Heuristic],
        strategy: PromptStrategy,
        lens_name: str = "Expert",
    ) -> str:
        """Build a system prompt from heuristics using the specified strategy."""
        if not heuristics:
            return ""

        if strategy == PromptStrategy.RAW:
            return PromptBuilder._raw(heuristics)
        elif strategy == PromptStrategy.GUIDED:
            return PromptBuilder._guided(heuristics, lens_name)
        elif strategy == PromptStrategy.COT:
            return PromptBuilder._chain_of_thought(heuristics, lens_name)
        elif strategy == PromptStrategy.CONSTRAINTS:
            return PromptBuilder._constraints(heuristics)
        elif strategy == PromptStrategy.FEW_SHOT:
            return PromptBuilder._few_shot(heuristics, lens_name)
        else:
            return PromptBuilder._raw(heuristics)

    @staticmethod
    def _raw(heuristics: list[Heuristic]) -> str:
        """Just dump heuristics as-is."""
        return "\n\n".join(h.to_prompt_fragment() for h in heuristics)

    @staticmethod
    def _guided(heuristics: list[Heuristic], lens_name: str) -> str:
        """Add meta-instructions for applying heuristics."""
        heuristic_block = "\n\n".join(h.to_prompt_fragment() for h in heuristics)
        return f"""# Expert Guidance: {lens_name}

You have access to these professional coding principles. Apply them to your response.

{heuristic_block}

## How to Use

1. Review which heuristics apply to this task
2. Follow the "always" patterns, avoid the "never" patterns
3. Verify your code follows these principles before responding

Apply these naturally - don't just list them, embody them in your code."""

    @staticmethod
    def _chain_of_thought(heuristics: list[Heuristic], lens_name: str) -> str:
        """Chain-of-thought prompting for larger models."""
        heuristic_block = "\n\n".join(h.to_prompt_fragment() for h in heuristics)
        return f"""# Expert Principles: {lens_name}

{heuristic_block}

---

## INSTRUCTIONS (Chain-of-Thought)

Before writing code, you MUST:

1. **THINK**: Which 1-2 heuristics from above are most relevant to this task?
2. **PLAN**: How will you apply them? What patterns will you use/avoid?
3. **CODE**: Write the solution following those heuristics.
4. **VERIFY**: Does your code follow the "always" and avoid the "never" patterns?

Format your response as:

```
THINKING: [Which heuristics apply and why]
PLAN: [How you'll apply them]
```

```python
# Your code here
```"""

    @staticmethod
    def _constraints(heuristics: list[Heuristic]) -> str:
        """Extract direct MUST/MUST NOT constraints for small models."""
        must_do = []
        must_not = []

        for h in heuristics:
            if h.always:
                must_do.extend(h.always[:3])  # Top 3 per heuristic
            if h.never:
                must_not.extend(h.never[:2])  # Top 2 per heuristic

        parts = ["# Coding Requirements\n"]
        if must_do:
            parts.append("You MUST:")
            parts.extend(f"- {item}" for item in must_do[:8])
            parts.append("")
        if must_not:
            parts.append("You MUST NOT:")
            parts.extend(f"- {item}" for item in must_not[:5])
            parts.append("")

        parts.append("Write clean, professional code following these requirements.")
        return "\n".join(parts)

    @staticmethod
    def _few_shot(heuristics: list[Heuristic], lens_name: str) -> str:
        """Include an example of applying heuristics."""
        # Use first heuristic for the example
        example_h = heuristics[0] if heuristics else None
        heuristic_block = "\n\n".join(h.to_prompt_fragment() for h in heuristics)

        example = ""
        if example_h and example_h.always:
            example = f"""
## Example: Applying "{example_h.name}"

Task: Write a function to fetch user data

BAD (ignores heuristic):
```python
def get_user(id):
    return db.query(id)
```

GOOD (follows heuristic - "{example_h.always[0]}"):
```python
def get_user(user_id: int) -> User | None:
    \"\"\"Fetch user by ID.\"\"\"
    return db.query(User, user_id)
```
"""

        return f"""# Expert Principles: {lens_name}

{heuristic_block}
{example}
Apply these principles to your response. Show your work like the example above."""


@dataclass
class BenchmarkRunner:
    """Execute benchmark tasks across conditions.

    Usage:
        runner = BenchmarkRunner(
            model=model,
            lens_loader=loader,
            tasks_dir=Path("benchmark/tasks"),
            output_dir=Path("benchmark/results"),
            lens_dir=Path("lenses"),
            prompt_strategy=PromptStrategy.CONSTRAINTS,  # Best for small models
        )
        results = await runner.run_suite(category="docs")

    Prompt strategies (from prompting research):
        - RAW: Just dump heuristics as-is
        - GUIDED: "Apply these principles" meta-instructions
        - COT: Chain-of-thought (THINK → PLAN → CODE → VERIFY)
        - CONSTRAINTS: Extract MUST/MUST NOT (best for small models)
        - FEW_SHOT: Include example of applying heuristics

    Naaru modes:
        - NONE: Single generation
        - HARMONIC: Multi-persona voting (Self-Consistency, 3x tokens)
        - RESONANCE: Feedback loop (1.5x tokens)
        - FULL: Both (4x tokens)
    """

    model: ModelProtocol
    lens_loader: LensLoader
    tasks_dir: Path
    output_dir: Path
    lens_dir: Path = Path("lenses")  # Directory containing lens files
    top_k: int = 3  # Number of heuristics to retrieve
    seed: int | None = 42  # For reproducibility where supported
    router_model: ModelProtocol | None = None  # RFC-020: Tiny LLM for routing
    prompt_strategy: PromptStrategy = PromptStrategy.CONSTRAINTS  # Best for small models
    naaru_mode: NaaruMode = NaaruMode.NONE  # Coordination layer

    async def run_task(
        self,
        task: BenchmarkTask,
        skip_conditions: tuple[Condition, ...] = (),
    ) -> TaskResult:
        """Run a single task against all conditions.

        Args:
            task: The benchmark task to run
            skip_conditions: Conditions to skip (e.g., for ablation tests)

        Returns:
            TaskResult with outputs from all conditions
        """
        # Load lens for this task - resolve relative to lens_dir
        lens_path = self.lens_dir / task.lens
        lens = self.lens_loader.load(lens_path)

        outputs: dict[str, ConditionOutput] = {}
        retrieval_metrics: RetrievalMetrics | None = None

        # Condition A: No system prompt (bare model)
        if Condition.BARE not in skip_conditions:
            outputs[Condition.BARE.value] = await self._run_condition(
                task=task,
                system_prompt="",
                condition=Condition.BARE,
            )

        # Condition B: Flat injection (all heuristics)
        if Condition.FLAT not in skip_conditions:
            full_context = lens.to_context()
            outputs[Condition.FLAT.value] = await self._run_condition(
                task=task,
                system_prompt=full_context,
                condition=Condition.FLAT,
            )

        # Condition C: Selective retrieval (Sunwell's approach)
        if Condition.SELECTIVE not in skip_conditions:
            selective_context, retrieval_metrics = await self._selective_retrieve(
                lens=lens,
                query=task.prompt,
            )
            outputs[Condition.SELECTIVE.value] = await self._run_condition(
                task=task,
                system_prompt=selective_context,
                condition=Condition.SELECTIVE,
            )

        # Condition D: Routed retrieval (RFC-020 CognitiveRouter)
        routing_metrics: RoutingMetrics | None = None
        if Condition.ROUTED not in skip_conditions and self.router_model is not None:
            routed_context, routing_metrics, routed_retrieval = await self._routed_retrieve(
                task=task,
            )
            outputs[Condition.ROUTED.value] = await self._run_condition(
                task=task,
                system_prompt=routed_context,
                condition=Condition.ROUTED,
            )
            # Use routed retrieval metrics if selective wasn't run
            if retrieval_metrics is None:
                retrieval_metrics = routed_retrieval

        # Condition E: Self-directed expertise retrieval (RFC-027)
        self_directed_metrics = None
        if Condition.SELF_DIRECTED not in skip_conditions:
            try:
                self_directed_output, self_directed_metrics = await self._run_self_directed(
                    task=task,
                    lens=lens,
                )
                outputs[Condition.SELF_DIRECTED.value] = self_directed_output
            except ImportError:
                # RFC-027 tools not fully installed
                pass
            except Exception:
                # Log but don't fail the whole benchmark
                pass

        # Condition F: Prefetch expertise via Tool Orchestrator Shard (RFC-031)
        prefetch_metrics = None
        if Condition.PREFETCH not in skip_conditions:
            try:
                prefetch_output, prefetch_metrics = await self._run_prefetch(
                    task=task,
                    lens=lens,
                )
                outputs[Condition.PREFETCH.value] = prefetch_output
            except ImportError as e:
                # RFC-031 Tool Orchestrator not available
                import sys
                print(f"Prefetch ImportError: {e}", file=sys.stderr)
            except Exception as e:
                # Log but don't fail the whole benchmark
                import sys
                print(f"Prefetch Error: {e}", file=sys.stderr)

        return TaskResult(
            task_id=task.id,
            outputs=outputs,
            retrieval_metrics=retrieval_metrics,
            routing_metrics=routing_metrics,
            self_directed_metrics=self_directed_metrics,
            prefetch_metrics=prefetch_metrics,
        )

    async def _run_condition(
        self,
        task: BenchmarkTask,
        system_prompt: str,
        condition: Condition,
    ) -> ConditionOutput:
        """Execute a single condition and measure results.

        Supports Naaru modes for enhanced generation:
        - NONE: Single generation
        - HARMONIC: Multi-persona generation with voting (Self-Consistency)
        - RESONANCE: Generate + validate + refine loop
        - FULL: Harmonic + Resonance combined
        """
        # Count input tokens
        input_tokens = self._count_tokens(system_prompt + "\n\n" + task.prompt)

        start_time = time.perf_counter()

        # Apply Naaru mode for selective condition only (not bare/flat)
        if condition == Condition.SELECTIVE and self.naaru_mode != NaaruMode.NONE:
            result_text, extra_tokens = await self._run_with_naaru(
                task=task,
                system_prompt=system_prompt,
            )
            input_tokens += extra_tokens  # Account for extra generations
        else:
            # Standard single generation
            options = GenerateOptions(
                temperature=0.7,
                max_tokens=2048,
                system_prompt=system_prompt if system_prompt else None,
            )
            result = await self.model.generate(task.prompt, options=options)
            result_text = result.text

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        # Count output tokens
        output_tokens = self._count_tokens(result_text)

        return ConditionOutput(
            condition=condition,
            content=result_text,
            tokens_input=input_tokens,
            tokens_output=output_tokens,
            latency_ms=latency_ms,
            system_prompt=system_prompt,
        )

    async def _run_with_naaru(
        self,
        task: BenchmarkTask,
        system_prompt: str,
    ) -> tuple[str, int]:
        """Run generation with Naaru coordination.

        Returns:
            Tuple of (best_response, extra_tokens_used)
        """
        extra_tokens = 0

        if self.naaru_mode in (NaaruMode.HARMONIC, NaaruMode.FULL):
            # Harmonic Synthesis: Generate with multiple personas, vote on best
            responses = await self._harmonic_synthesis(task, system_prompt)
            extra_tokens += sum(self._count_tokens(r) for r in responses) * 2  # Estimate

            # Vote on best response
            best_response = await self._vote_on_responses(task, responses)
        else:
            # Single generation for resonance-only mode
            options = GenerateOptions(
                temperature=0.7,
                max_tokens=2048,
                system_prompt=system_prompt if system_prompt else None,
            )
            result = await self.model.generate(task.prompt, options=options)
            best_response = result.text

        if self.naaru_mode in (NaaruMode.RESONANCE, NaaruMode.FULL):
            # Resonance: Validate and refine if needed
            best_response, refine_tokens = await self._resonance_loop(
                task, system_prompt, best_response
            )
            extra_tokens += refine_tokens

        return best_response, extra_tokens

    async def _harmonic_synthesis(
        self,
        task: BenchmarkTask,
        base_system_prompt: str,
    ) -> list[str]:
        """Generate responses from multiple personas (Self-Consistency).

        Uses 3 personas with structured variance based on domain expertise.
        """
        # Persona definitions for structured variance
        personas = [
            {
                "name": "Pragmatist",
                "modifier": "Focus on simple, working code. Prioritize readability and maintainability over cleverness.",
            },
            {
                "name": "Perfectionist",
                "modifier": "Focus on robust, complete code. Handle all edge cases and add comprehensive type hints.",
            },
            {
                "name": "Minimalist",
                "modifier": "Focus on minimal, elegant code. Remove anything unnecessary while preserving functionality.",
            },
        ]

        # Generate in parallel with each persona
        async def generate_with_persona(persona: dict) -> str:
            enhanced_prompt = f"{base_system_prompt}\n\n## Persona: {persona['name']}\n{persona['modifier']}"
            options = GenerateOptions(
                temperature=0.7,
                max_tokens=2048,
                system_prompt=enhanced_prompt,
            )
            result = await self.model.generate(task.prompt, options=options)
            return result.text

        responses = await asyncio.gather(*[
            generate_with_persona(p) for p in personas
        ])

        return list(responses)

    async def _vote_on_responses(
        self,
        task: BenchmarkTask,
        responses: list[str],
    ) -> str:
        """Have the model vote on the best response.

        Simple majority voting using the same model as judge.
        """
        if len(responses) == 1:
            return responses[0]

        # Format responses for voting
        options_text = "\n\n".join([
            f"## Option {chr(65 + i)}\n```\n{r[:1500]}\n```"
            for i, r in enumerate(responses)
        ])

        vote_prompt = f"""You are evaluating code solutions. Pick the BEST one.

Task: {task.prompt[:500]}

{options_text}

Which option is best? Respond with just the letter (A, B, or C)."""

        options = GenerateOptions(
            temperature=0.0,  # Deterministic for voting
            max_tokens=10,
        )

        result = await self.model.generate(vote_prompt, options=options)

        # Parse vote
        vote = result.text.strip().upper()
        if vote.startswith("A"):
            return responses[0]
        elif vote.startswith("B"):
            return responses[1] if len(responses) > 1 else responses[0]
        elif vote.startswith("C"):
            return responses[2] if len(responses) > 2 else responses[0]
        else:
            # Default to first if parsing fails
            return responses[0]

    async def _resonance_loop(
        self,
        task: BenchmarkTask,
        system_prompt: str,
        initial_response: str,
        max_attempts: int = 2,
    ) -> tuple[str, int]:
        """Resonance: Validate and refine response if issues found.

        Returns:
            Tuple of (final_response, extra_tokens_used)
        """
        extra_tokens = 0
        current_response = initial_response

        for _attempt in range(max_attempts):
            # Quick validation
            issues = await self._validate_response(task, current_response)

            if not issues:
                break  # Response is good

            # Refine based on issues
            refine_prompt = f"""Your previous response had issues:
{issues}

Original task: {task.prompt[:500]}

Please fix these issues and provide an improved response."""

            options = GenerateOptions(
                temperature=0.5,  # Lower temp for refinement
                max_tokens=2048,
                system_prompt=system_prompt,
            )

            result = await self.model.generate(refine_prompt, options=options)
            current_response = result.text
            extra_tokens += self._count_tokens(refine_prompt) + self._count_tokens(result.text)

        return current_response, extra_tokens

    async def _validate_response(
        self,
        task: BenchmarkTask,
        response: str,
    ) -> str | None:
        """Quick validation of response quality.

        Returns issues string if problems found, None if OK.
        """
        # Simple heuristic checks for code tasks
        issues = []

        if task.category in (TaskCategory.CODE_GENERATION,):
            # Check for common issues
            if "```" not in response:
                issues.append("- Missing code block")
            if "def " not in response and "class " not in response:
                issues.append("- No function or class definition found")
            if "pass" in response and response.count("pass") > 2:
                issues.append("- Too many placeholder 'pass' statements")

        # Check deterministic criteria from task
        if task.evaluation:
            for must in task.evaluation.must_contain:
                if must.lower() not in response.lower():
                    issues.append(f"- Missing required element: {must}")
            for must_not in task.evaluation.must_not_contain:
                if must_not.lower() in response.lower():
                    issues.append(f"- Contains forbidden element: {must_not}")

        return "\n".join(issues) if issues else None

    async def _selective_retrieve(
        self,
        lens: Lens,
        query: str,
    ) -> tuple[str, RetrievalMetrics]:
        """Perform selective retrieval using Sunwell's approach.

        Returns:
            Tuple of (context_string, retrieval_metrics)
        """
        from sunwell.embedding import create_embedder
        from sunwell.embedding.index import InMemoryIndex

        start_time = time.perf_counter()

        # Create embedder and index (create_embedder is sync)
        embedder = create_embedder()
        index = InMemoryIndex(_dimensions=embedder.dimensions)

        # Index all heuristics
        heuristic_texts = []
        heuristic_ids = []
        for h in lens.heuristics:
            text = h.to_prompt_fragment()
            heuristic_texts.append(text)
            heuristic_ids.append(h.name)

        if heuristic_texts:
            # Embed all heuristics
            result = await embedder.embed(heuristic_texts)
            index.add_batch(
                ids=heuristic_ids,
                vectors=result.vectors,
                metadata=[{"text": t} for t in heuristic_texts],
            )

            # Embed query and retrieve top-k
            query_vector = await embedder.embed_single(query)
            search_results = index.search(query_vector, top_k=self.top_k)

            # Get actual heuristic objects for the retrieved results
            retrieved_heuristics = []
            for r in search_results:
                # Find the heuristic by name
                for h in lens.heuristics:
                    if h.name == r.id:
                        retrieved_heuristics.append(h)
                        break

            # Build context using the configured prompt strategy
            # Different strategies work better for different model sizes
            context = PromptBuilder.build(
                heuristics=retrieved_heuristics,
                strategy=self.prompt_strategy,
                lens_name=lens.metadata.name,
            )

            # Add communication style if present
            if lens.communication:
                context += f"\n\n## Communication Style\n{lens.communication.to_prompt_fragment()}"

            latency_ms = int((time.perf_counter() - start_time) * 1000)

            metrics = RetrievalMetrics(
                precision_at_k=len(search_results) / self.top_k if search_results else 0.0,
                recall=len(search_results) / len(heuristic_ids) if heuristic_ids else 1.0,
                avg_relevance=sum(r.score for r in search_results) / len(search_results) if search_results else 0.0,
                retrieval_latency_ms=latency_ms,
                retrieved_ids=tuple(r.id for r in search_results),
            )

            return context, metrics

        # No heuristics to retrieve
        return "", RetrievalMetrics.empty()

    async def _routed_retrieve(
        self,
        task: BenchmarkTask,
    ) -> tuple[str, RoutingMetrics, RetrievalMetrics]:
        """Perform routed retrieval using CognitiveRouter (RFC-020).

        1. Router classifies intent and selects lens
        2. Router adjusts top_k based on complexity
        3. Retrieval is boosted with focus terms

        Returns:
            Tuple of (context_string, routing_metrics, retrieval_metrics)
        """
        from sunwell.embedding import create_embedder
        from sunwell.embedding.index import InMemoryIndex
        from sunwell.routing import CognitiveRouter

        # Initialize router
        available_lenses = [p.stem for p in self.lens_dir.glob("*.lens")]
        router = CognitiveRouter(
            router_model=self.router_model,
            available_lenses=available_lenses,
        )

        # Get routing decision
        start_time = time.perf_counter()
        routing = await router.route(task.prompt)
        routing_latency = int((time.perf_counter() - start_time) * 1000)

        # Load the lens selected by router (or fallback to task's lens)
        lens_name = routing.lens if routing.lens in available_lenses else task.lens.replace(".lens", "")
        lens_path = self.lens_dir / f"{lens_name}.lens"

        if lens_path.exists():
            lens = self.lens_loader.load(lens_path)
        else:
            # Fallback to task's specified lens
            lens_path = self.lens_dir / task.lens
            lens = self.lens_loader.load(lens_path)

        # Use router's top_k (adjusted by complexity)
        top_k = routing.top_k

        # Build boosted query with focus terms
        boosted_query = f"{task.prompt} {' '.join(routing.focus)}"

        # Now do selective retrieval with router-adjusted parameters
        retrieval_start = time.perf_counter()
        embedder = create_embedder()
        index = InMemoryIndex(_dimensions=embedder.dimensions)

        heuristic_texts = []
        heuristic_ids = []
        for h in lens.heuristics:
            text = h.to_prompt_fragment()
            heuristic_texts.append(text)
            heuristic_ids.append(h.name)

        context = ""
        retrieval_metrics = RetrievalMetrics.empty()

        if heuristic_texts:
            # Embed all heuristics
            result = await embedder.embed(heuristic_texts)
            index.add_batch(
                ids=heuristic_ids,
                vectors=result.vectors,
                metadata=[{"text": t} for t in heuristic_texts],
            )

            # Embed boosted query and retrieve
            query_vector = await embedder.embed_single(boosted_query)
            search_results = index.search(query_vector, top_k=top_k, threshold=routing.threshold)

            # Build context from retrieved heuristics
            retrieved_texts = [r.metadata["text"] for r in search_results]
            context = f"# Expertise: {lens.metadata.name}\n"
            context += f"## Intent: {routing.intent.value}\n"
            context += f"## Focus: {', '.join(routing.focus)}\n\n"
            context += "## Retrieved Heuristics\n\n"
            context += "\n\n".join(retrieved_texts)

            # Add communication style if present
            if lens.communication:
                context += "\n\n## Communication Style\n"
                context += lens.communication.to_prompt_fragment()

            retrieval_latency = int((time.perf_counter() - retrieval_start) * 1000)

            retrieval_metrics = RetrievalMetrics(
                precision_at_k=len(search_results) / top_k if search_results else 0.0,
                recall=len(search_results) / len(heuristic_ids) if heuristic_ids else 1.0,
                avg_relevance=sum(r.score for r in search_results) / len(search_results) if search_results else 0.0,
                retrieval_latency_ms=retrieval_latency,
                retrieved_ids=tuple(r.id for r in search_results),
            )

        routing_metrics = RoutingMetrics(
            intent=routing.intent.value,
            lens_selected=routing.lens,
            focus_terms=tuple(routing.focus),
            complexity=routing.complexity.value,
            confidence=routing.confidence,
            routing_latency_ms=routing_latency,
            top_k_adjusted=top_k,
            reasoning=routing.reasoning,
        )

        return context, routing_metrics, retrieval_metrics

    async def _run_self_directed(
        self,
        task: BenchmarkTask,
        lens: Lens,
    ) -> tuple[ConditionOutput, SelfDirectedMetrics]:
        """Run task with self-directed expertise retrieval (RFC-027).

        The model can call expertise tools during generation:
        - get_expertise(topic): Retrieve relevant heuristics
        - verify_against_expertise(code): Check code against heuristics
        - list_expertise_areas(): List available expertise categories

        Args:
            task: The benchmark task
            lens: The lens to use for expertise retrieval

        Returns:
            Tuple of (ConditionOutput, SelfDirectedMetrics)
        """
        from sunwell.embedding import create_embedder
        from sunwell.runtime.retriever import ExpertiseRetriever
        from sunwell.tools.builtins import EXPERTISE_TOOLS
        from sunwell.tools.expertise import ExpertiseToolHandler

        start_time = time.perf_counter()
        total_tool_latency_ms = 0

        # Set up expertise retrieval infrastructure
        embedder = create_embedder()
        retriever = ExpertiseRetriever(
            lens=lens,
            embedder=embedder,
            top_k=self.top_k,
        )
        await retriever.initialize()

        # Create expertise tool handler
        expertise_handler = ExpertiseToolHandler(
            retriever=retriever,
            lens=lens,
        )

        # Build system prompt with self-directed expertise hint
        # RFC-029: Include prompted format for small models that can't use native tools
        from sunwell.tools.prompted import get_prompted_tools_system

        # Use prompted format (simpler, works with small models)
        # Native tool calling will be tried first, but if it fails,
        # we'll parse [TOOL:name(args)] tags from the text
        system_prompt = get_prompted_tools_system()

        # Add minimal lens context (just identity, not heuristics)
        if lens.communication:
            system_prompt += f"\n\n## Communication Style\n{lens.communication.to_prompt_fragment()}"

        # Format tools for the model (for native tool calling if supported)
        tools = list(EXPERTISE_TOOLS.values())

        # Track tokens and iterations
        input_tokens = self._count_tokens(system_prompt + "\n\n" + task.prompt)
        output_tokens = 0
        max_iterations = 5  # Prevent infinite tool loops

        # RFC-027 Metrics tracking
        list_expertise_calls = 0
        get_expertise_calls = 0
        verify_calls = 0
        topics_queried: list[str] = []
        heuristics_retrieved = 0
        verification_passed: bool | None = None
        react_iterations = 0

        # ReAct loop: Model generates, optionally calls tools, repeat until done
        messages = [{"role": "user", "content": task.prompt}]
        final_response = ""

        for iteration in range(max_iterations):
            react_iterations = iteration + 1

            options = GenerateOptions(
                temperature=0.7,
                max_tokens=2048,
                system_prompt=system_prompt,
                tools=tools,
            )

            result = await self.model.generate(
                messages[-1]["content"] if messages else task.prompt,
                options=options,
            )

            # Check if model made tool calls (native API or prompted tags)
            # RFC-029: Fall back to parsing [TOOL:name(args)] tags for small models
            from sunwell.tools.prompted import convert_to_tool_calls, has_tool_tags, parse_tool_tags

            tool_calls = result.tool_calls

            # If no native tool calls, try parsing tags from text (small model fallback)
            if not tool_calls and result.text and has_tool_tags(result.text):
                parsed = parse_tool_tags(result.text)
                if parsed:
                    tool_calls = tuple(convert_to_tool_calls(parsed))

            if tool_calls:
                # Execute each tool call
                tool_results = []
                for tc in tool_calls:
                    # Track tool call metrics
                    tool_start = time.perf_counter()
                    tool_output = await expertise_handler.handle(tc.name, tc.arguments)
                    total_tool_latency_ms += int((time.perf_counter() - tool_start) * 1000)

                    # Track per-tool metrics
                    if tc.name == "list_expertise_areas":
                        list_expertise_calls += 1
                    elif tc.name == "get_expertise":
                        get_expertise_calls += 1
                        if "topic" in tc.arguments:
                            topics_queried.append(tc.arguments["topic"])
                        # Count heuristics in response (look for "### " pattern)
                        heuristics_retrieved += tool_output.count("### ")
                    elif tc.name == "verify_against_expertise":
                        verify_calls += 1
                        # Check if verification passed
                        verification_passed = "No Violations Found" in tool_output

                    tool_results.append({
                        "tool_call_id": tc.id,
                        "content": tool_output,
                    })
                    input_tokens += self._count_tokens(tool_output)

                # Add assistant message with tool calls
                messages.append({
                    "role": "assistant",
                    "content": result.text or "",
                    "tool_calls": tool_calls,
                })

                # Add tool results as a combined message for next iteration
                tool_context = "\n\n".join([
                    f"[Tool Result: {tr['tool_call_id']}]\n{tr['content']}"
                    for tr in tool_results
                ])
                messages.append({
                    "role": "user",
                    "content": f"Tool results:\n\n{tool_context}\n\nPlease continue with the task.",
                })

                output_tokens += self._count_tokens(result.text or "")
            else:
                # No tool calls - model is done
                final_response = result.text
                output_tokens += self._count_tokens(final_response)
                break
        else:
            # Max iterations reached - use last response
            if messages:
                final_response = result.text or "Max tool iterations reached"

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        # Build metrics
        total_tool_calls = list_expertise_calls + get_expertise_calls + verify_calls
        metrics = SelfDirectedMetrics(
            total_tool_calls=total_tool_calls,
            list_expertise_calls=list_expertise_calls,
            get_expertise_calls=get_expertise_calls,
            verify_calls=verify_calls,
            topics_queried=tuple(topics_queried),
            heuristics_retrieved=heuristics_retrieved,
            verification_passed=verification_passed,
            react_iterations=react_iterations,
            tool_latency_ms=total_tool_latency_ms,
        )

        output = ConditionOutput(
            condition=Condition.SELF_DIRECTED,
            content=final_response,
            tokens_input=input_tokens,
            tokens_output=output_tokens,
            latency_ms=latency_ms,
            system_prompt=system_prompt,
        )

        return output, metrics

    async def _run_prefetch(
        self,
        task: BenchmarkTask,
        lens: Lens,
    ) -> tuple[ConditionOutput, PrefetchMetrics]:
        """Run prefetch condition: Tool Orchestrator Shard pre-fetches expertise (RFC-031).

        Unlike self-directed mode where the model calls tools during generation,
        prefetch mode uses semantic similarity to fetch relevant expertise BEFORE
        generation. The model receives an enriched prompt and doesn't need
        tool-calling capability.

        This is ideal for small models (1-3B parameters) that struggle with
        native tool calling.
        """
        from sunwell.benchmark.types import PrefetchMetrics
        from sunwell.naaru.tool_shard import ToolOrchestratorShard

        start_time = time.perf_counter()

        # Create Tool Orchestrator Shard
        shard = ToolOrchestratorShard(
            lens=lens,
            threshold=0.5,  # 50% similarity threshold
            top_k=5,
        )

        # Prefetch expertise using semantic similarity
        shard_result = await shard.process(task.prompt)

        # Now generate with the enriched prompt (no tools needed!)
        options = GenerateOptions(
            temperature=0.7,
            max_tokens=2048,
            system_prompt="",  # Expertise is in the enriched prompt
            tools=None,  # No tool calling - that's the point!
        )

        result = await self.model.generate(
            shard_result.enriched_prompt,
            options=options,
        )

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        # Calculate token counts
        input_tokens = self._count_tokens(shard_result.enriched_prompt)
        output_tokens = self._count_tokens(result.text)

        # Expertise expansion tokens (how many tokens were added)
        original_tokens = self._count_tokens(task.prompt)
        expansion_tokens = input_tokens - original_tokens

        # Build metrics
        relevance_scores = [e.score for e in shard_result.expertise]
        metrics = PrefetchMetrics(
            topics_detected=shard_result.topics_detected,
            expertise_items=len(shard_result.expertise),
            max_relevance_score=max(relevance_scores) if relevance_scores else 0.0,
            min_relevance_score=min(relevance_scores) if relevance_scores else 0.0,
            prefetch_latency_ms=shard_result.latency_ms,
            threshold_used=0.5,
            prompt_expansion_tokens=expansion_tokens,
            reasoning=shard_result.reasoning,
        )

        output = ConditionOutput(
            condition=Condition.PREFETCH,
            content=result.text,
            tokens_input=input_tokens,
            tokens_output=output_tokens,
            latency_ms=latency_ms,
            system_prompt=shard_result.enriched_prompt,
        )

        return output, metrics

    def _count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken.

        Falls back to word-based estimate if tiktoken unavailable.
        """
        try:
            import tiktoken

            # Try to get encoding for specific model
            try:
                encoding = tiktoken.encoding_for_model(self.model.model_id)
            except KeyError:
                # Fall back to cl100k_base (GPT-4/Claude compatible)
                encoding = tiktoken.get_encoding("cl100k_base")

            return len(encoding.encode(text))
        except ImportError:
            # Rough estimate: ~4 chars per token
            return len(text) // 4

    async def run_suite(
        self,
        category: str | None = None,
        task_ids: list[str] | None = None,
        max_tasks: int | None = None,
    ) -> BenchmarkResults:
        """Run all tasks in a category or the full suite.

        Args:
            category: Filter to specific category (docs, review, code)
            task_ids: Filter to specific task IDs
            max_tasks: Limit number of tasks (for quick runs)

        Returns:
            BenchmarkResults with all task outcomes
        """
        tasks = self._load_tasks(category=category, task_ids=task_ids)

        if max_tasks:
            tasks = tasks[:max_tasks]

        results: list[TaskResult] = []

        for i, task in enumerate(tasks):
            print(f"  [{i+1}/{len(tasks)}] Running {task.id}...", end=" ", flush=True)
            try:
                result = await self.run_task(task)
                results.append(result)
                print("✓")
            except Exception as e:
                print(f"✗ {e}")

        return BenchmarkResults(
            timestamp=datetime.now().isoformat(),
            model=self.model.model_id,
            task_results=tuple(results),
        )

    async def run_ablation(
        self,
        task: BenchmarkTask,
        k_values: tuple[int, ...] = (1, 3, 5),
    ) -> dict[int, TaskResult]:
        """Run retrieval ablation test with different top_k values.

        Tests: What minimum retrieval depth is needed to maintain quality?
        """
        results: dict[int, TaskResult] = {}

        original_k = self.top_k

        for k in k_values:
            self.top_k = k
            result = await self.run_task(
                task,
                skip_conditions=(Condition.BARE, Condition.FLAT),
            )
            results[k] = result

        self.top_k = original_k
        return results

    def _load_tasks(
        self,
        category: str | None = None,
        task_ids: list[str] | None = None,
    ) -> list[BenchmarkTask]:
        """Load benchmark tasks from YAML files.

        Searches benchmark/tasks/ for .yaml files.
        """
        tasks: list[BenchmarkTask] = []

        # Find all YAML files in tasks directory
        for yaml_path in self.tasks_dir.rglob("*.yaml"):
            task = self._load_task_file(yaml_path)
            if task is None:
                continue

            # Filter by category
            if category and task.category.value != category:
                continue

            # Filter by task ID
            if task_ids and task.id not in task_ids:
                continue

            tasks.append(task)

        return sorted(tasks, key=lambda t: t.id)

    def _load_task_file(self, path: Path) -> BenchmarkTask | None:
        """Load a single task from a YAML file."""
        try:
            with open(path) as f:
                data = yaml.safe_load(f)

            if not data or "task" not in data:
                return None

            task_data = data["task"]

            # Parse evaluation
            eval_data = task_data.get("evaluation", {})
            rubric = tuple(
                RubricDimension(
                    dimension=r["dimension"],
                    weight=r.get("weight", 0.25),
                    criteria=r.get("criteria", ""),
                )
                for r in eval_data.get("rubric", [])
            )

            evaluation = TaskEvaluation(
                rubric=rubric,
                must_contain=tuple(eval_data.get("must_contain", [])),
                must_not_contain=tuple(eval_data.get("must_not_contain", [])),
                ground_truth_issues=tuple(eval_data.get("ground_truth_issues", [])),
            )

            # Parse category
            category_str = task_data.get("category", "documentation")
            try:
                category = TaskCategory(category_str)
            except ValueError:
                category = TaskCategory.DOCUMENTATION

            return BenchmarkTask(
                id=task_data["id"],
                category=category,
                subcategory=task_data.get("subcategory", "general"),
                prompt=task_data["prompt"],
                lens=task_data.get("lens", "tech-writer.lens"),
                evaluation=evaluation,
                context_files=tuple(task_data.get("context_files", [])),
                test_suite=task_data.get("test_suite"),
                target_persona=task_data.get("target_persona"),
                source_path=path,
            )
        except Exception as e:
            print(f"Warning: Failed to load {path}: {e}")
            return None


async def create_runner(
    model: ModelProtocol | None = None,
    lens_loader: LensLoader | None = None,
    tasks_dir: Path | str = "benchmark/tasks",
    output_dir: Path | str = "benchmark/results",
    lens_dir: Path | str = "lenses",
    router_model: ModelProtocol | None = None,
) -> BenchmarkRunner:
    """Create a BenchmarkRunner with default configuration.

    If model is not provided, uses Ollama with default model.
    If lens_loader is not provided, creates one with default paths.
    If router_model is provided, enables the ROUTED condition (RFC-020).
    """
    if model is None:
        from sunwell.models.ollama import OllamaModel
        model = OllamaModel(model="hhao/qwen2.5-coder-tools:14b")

    if lens_loader is None:
        from sunwell.schema.loader import LensLoader
        lens_loader = LensLoader()

    return BenchmarkRunner(
        model=model,
        lens_loader=lens_loader,
        tasks_dir=Path(tasks_dir),
        output_dir=Path(output_dir),
        lens_dir=Path(lens_dir),
        router_model=router_model,
    )
