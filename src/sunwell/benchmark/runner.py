"""Benchmark Runner (RFC-018).

Executes benchmark tasks across multiple conditions:
- Bare: No system prompt (raw model capability)
- Flat: Full lens context injected
- Selective: Sunwell's selective retrieval approach
- Competitor: Optional external baseline
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from sunwell.benchmark.types import (
    BenchmarkTask,
    BenchmarkResults,
    Condition,
    ConditionOutput,
    RetrievalMetrics,
    RoutingMetrics,
    RubricDimension,
    TaskCategory,
    TaskEvaluation,
    TaskResult,
)
from sunwell.models.protocol import GenerateOptions, ModelProtocol

if TYPE_CHECKING:
    from sunwell.core.lens import Lens
    from sunwell.schema.loader import LensLoader


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
        )
        results = await runner.run_suite(category="docs")
    """
    
    model: ModelProtocol
    lens_loader: "LensLoader"
    tasks_dir: Path
    output_dir: Path
    lens_dir: Path = Path("lenses")  # Directory containing lens files
    top_k: int = 3  # Number of heuristics to retrieve
    seed: int | None = 42  # For reproducibility where supported
    router_model: ModelProtocol | None = None  # RFC-020: Tiny LLM for routing
    
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
        
        return TaskResult(
            task_id=task.id,
            outputs=outputs,
            retrieval_metrics=retrieval_metrics,
            routing_metrics=routing_metrics,
        )
    
    async def _run_condition(
        self,
        task: BenchmarkTask,
        system_prompt: str,
        condition: Condition,
    ) -> ConditionOutput:
        """Execute a single condition and measure results."""
        # Count input tokens
        input_tokens = self._count_tokens(system_prompt + "\n\n" + task.prompt)
        
        start_time = time.perf_counter()
        
        # Generate with system prompt
        options = GenerateOptions(
            temperature=0.7,
            max_tokens=2048,
            system_prompt=system_prompt if system_prompt else None,
        )
        
        result = await self.model.generate(task.prompt, options=options)
        
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        
        # Count output tokens
        output_tokens = result.usage.completion_tokens if result.usage else self._count_tokens(result.text)
        
        return ConditionOutput(
            condition=condition,
            content=result.text,
            tokens_input=input_tokens,
            tokens_output=output_tokens,
            latency_ms=latency_ms,
            system_prompt=system_prompt,
        )
    
    async def _selective_retrieve(
        self,
        lens: "Lens",
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
            
            # Build context from retrieved heuristics
            retrieved_texts = [r.metadata["text"] for r in search_results]
            context = f"# Expertise: {lens.metadata.name}\n\n## Retrieved Heuristics\n\n"
            context += "\n\n".join(retrieved_texts)
            
            # Add communication style if present
            if lens.communication:
                context += "\n\n## Communication Style\n"
                context += lens.communication.to_prompt_fragment()
            
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
        task: "BenchmarkTask",
    ) -> tuple[str, RoutingMetrics, RetrievalMetrics]:
        """Perform routed retrieval using CognitiveRouter (RFC-020).
        
        1. Router classifies intent and selects lens
        2. Router adjusts top_k based on complexity
        3. Retrieval is boosted with focus terms
        
        Returns:
            Tuple of (context_string, routing_metrics, retrieval_metrics)
        """
        from sunwell.routing import CognitiveRouter
        from sunwell.embedding import create_embedder
        from sunwell.embedding.index import InMemoryIndex
        
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
    lens_loader: "LensLoader | None" = None,
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
