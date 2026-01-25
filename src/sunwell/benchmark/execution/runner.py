"""Execution runner for benchmark conditions."""

import asyncio
import time
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.benchmark.prompts import PromptBuilder
from sunwell.benchmark.types import (
    Condition,
    ConditionOutput,
    NaaruMode,
    PromptStrategy,
    RetrievalMetrics,
    RoutingMetrics,
    SelfDirectedMetrics,
    TaskCategory,
)
from sunwell.models.protocol import GenerateOptions, ModelProtocol

if TYPE_CHECKING:
    from sunwell.benchmark.types import BenchmarkTask, PrefetchMetrics
    from sunwell.foundation.core.lens import Lens
    from sunwell.foundation.schema.loader import LensLoader


class ExecutionRunner:
    """Handles execution of benchmark conditions."""

    def __init__(
        self,
        model: ModelProtocol,
        lens_loader: LensLoader,
        lens_dir: Path,
        top_k: int = 3,
        router_model: ModelProtocol | None = None,
        prompt_strategy: PromptStrategy = PromptStrategy.CONSTRAINTS,
        naaru_mode: NaaruMode = NaaruMode.NONE,
    ) -> None:
        """Initialize execution runner.

        Args:
            model: Model for generation
            lens_loader: Loader for lens files
            lens_dir: Directory containing lens files
            top_k: Number of heuristics to retrieve
            router_model: Optional router model for routed retrieval
            prompt_strategy: Strategy for building prompts
            naaru_mode: Naaru coordination mode
        """
        self.model = model
        self.lens_loader = lens_loader
        self.lens_dir = lens_dir
        self.top_k = top_k
        self.router_model = router_model
        self.prompt_strategy = prompt_strategy
        self.naaru_mode = naaru_mode

    async def run_condition(
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

    async def selective_retrieve(
        self,
        lens: Lens,
        query: str,
    ) -> tuple[str, RetrievalMetrics]:
        """Perform selective retrieval using Sunwell's approach.

        Returns:
            Tuple of (context_string, retrieval_metrics)
        """
        from sunwell.knowledge.embedding import create_embedder
        from sunwell.knowledge.embedding.index import InMemoryIndex

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

    async def routed_retrieve(
        self,
        task: BenchmarkTask,
    ) -> tuple[str, RoutingMetrics, RetrievalMetrics]:
        """Perform routed retrieval using UnifiedRouter (RFC-030).

        1. Router classifies intent and selects lens
        2. Top_k derived from complexity level
        3. Retrieval is boosted with focus terms

        Returns:
            Tuple of (context_string, routing_metrics, retrieval_metrics)
        """
        from sunwell.knowledge.embedding import create_embedder
        from sunwell.knowledge.embedding.index import InMemoryIndex
        from sunwell.planning.routing import UnifiedRouter
        from sunwell.planning.routing.unified import Complexity

        # Complexity → retrieval parameters mapping
        COMPLEXITY_PARAMS = {
            Complexity.TRIVIAL: {"top_k": 3, "threshold": 0.4},
            Complexity.STANDARD: {"top_k": 5, "threshold": 0.3},
            Complexity.COMPLEX: {"top_k": 8, "threshold": 0.2},
        }

        # Initialize router
        available_lenses = [p.stem for p in self.lens_dir.glob("*.lens")]
        router = UnifiedRouter(
            model=self.router_model,
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

        # Derive top_k and threshold from complexity
        params = COMPLEXITY_PARAMS.get(routing.complexity, COMPLEXITY_PARAMS[Complexity.STANDARD])
        top_k = params["top_k"]
        threshold = params["threshold"]

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
            search_results = index.search(query_vector, top_k=top_k, threshold=threshold)

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

    async def run_self_directed(
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
        from sunwell.knowledge.embedding import create_embedder
        from sunwell.agent.runtime.retriever import ExpertiseRetriever
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

    async def run_prefetch(
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
        from sunwell.planning.naaru.tool_shard import ToolOrchestratorShard

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
