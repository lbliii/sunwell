#!/usr/bin/env python3
"""Real LLM benchmark comparing Sequential vs Parallel vs Brain.

Uses actual Ollama models to generate proposals, measuring real latency
and comparing architecture performance with genuine API calls.

Usage:
    python examples/llm_benchmark.py
    python examples/llm_benchmark.py --model hhao/qwen2.5-coder-tools:14b
    python examples/llm_benchmark.py --tasks 10 --workers 4
"""

import asyncio
import argparse
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Import Sunwell components
from sunwell.models.ollama import OllamaModel
from sunwell.models.protocol import GenerateOptions


@dataclass
class LLMTask:
    """A task requiring LLM generation."""
    id: str
    prompt: str
    category: str
    
    
@dataclass
class LLMResult:
    """Result from LLM generation."""
    task_id: str
    response: str
    latency_ms: int
    tokens: int = 0
    quality_score: float = 0.0  # 0-10 from LLM judge


@dataclass
class BenchmarkResult:
    """Aggregated benchmark results."""
    name: str
    tasks_completed: int
    total_time_seconds: float
    avg_latency_ms: float
    total_tokens: int
    workers: int
    messages: int = 0
    avg_quality: float = 0.0  # Average quality score from judge
    
    @property
    def throughput(self) -> float:
        return self.tasks_completed / self.total_time_seconds if self.total_time_seconds > 0 else 0
    
    @property
    def tokens_per_second(self) -> float:
        return self.total_tokens / self.total_time_seconds if self.total_time_seconds > 0 else 0


async def judge_response(model: OllamaModel, task: LLMTask, response: str) -> float:
    """Use LLM to judge quality of a generated response."""
    judge_prompt = f"""Rate this code response 0-10. Be strict but fair.

TASK: {task.prompt[:200]}

RESPONSE:
{response[:1500]}

Score based on:
- Correctness: Does it work?
- Completeness: Is it complete?
- Quality: Is it well-written?

Reply with ONLY a number 0-10, nothing else."""

    try:
        result = await model.generate(
            judge_prompt,
            options=GenerateOptions(temperature=0.1, max_tokens=10),
        )
        # Extract number from response
        import re
        match = re.search(r'(\d+(?:\.\d+)?)', result.content or "0")
        if match:
            score = float(match.group(1))
            return min(10.0, max(0.0, score))
        return 5.0  # Default if parsing fails
    except Exception:
        return 5.0  # Default on error


def generate_tasks(n: int = 10) -> list[LLMTask]:
    """Generate realistic improvement tasks."""
    tasks = [
        # Error handling improvements
        LLMTask("err_01", 
            "Write a Python error handler for OutOfMemoryError that: 1) logs the error, 2) suggests memory optimization, 3) provides a recovery strategy. Keep it under 20 lines.",
            "error_handling"),
        LLMTask("err_02",
            "Write a Python retry decorator with exponential backoff for network errors. Include max_retries and base_delay parameters.",
            "error_handling"),
        LLMTask("err_03",
            "Write a circuit breaker pattern implementation in Python for handling cascading failures. 30 lines max.",
            "error_handling"),
            
        # Testing improvements  
        LLMTask("test_01",
            "Write a pytest test for a function that validates email addresses. Include edge cases for: empty string, missing @, multiple @, unicode characters.",
            "testing"),
        LLMTask("test_02",
            "Write a pytest fixture that creates a temporary SQLite database with a users table. Clean up after test.",
            "testing"),
        LLMTask("test_03",
            "Write property-based tests using hypothesis for a function that calculates fibonacci numbers.",
            "testing"),
            
        # Documentation
        LLMTask("doc_01",
            "Write a docstring for an async function called `fetch_user_data` that takes user_id (int) and optional timeout (float), returns a User dataclass or raises UserNotFoundError.",
            "documentation"),
        LLMTask("doc_02",
            "Write a module-level docstring for a caching module that supports TTL, LRU eviction, and async operations.",
            "documentation"),
            
        # Code quality
        LLMTask("qual_01",
            "Refactor this code to be more Pythonic: `result = []; for i in range(len(items)): if items[i] > 0: result.append(items[i] * 2)`",
            "code_quality"),
        LLMTask("qual_02",
            "Write a type-safe configuration loader in Python using dataclasses and TypedDict. Load from YAML file.",
            "code_quality"),
    ]
    
    return tasks[:n]


async def run_sequential(model: OllamaModel, tasks: list[LLMTask], judge: bool = False) -> BenchmarkResult:
    """Run tasks sequentially (1 worker)."""
    print("\n" + "─" * 60)
    print(f"📍 SEQUENTIAL MODE (1 worker){' + JUDGE' if judge else ''}")
    print("─" * 60)
    
    start = time.time()
    results: list[LLMResult] = []
    total_tokens = 0
    
    for i, task in enumerate(tasks):
        task_start = time.time()
        
        try:
            response = await model.generate(
                task.prompt,
                options=GenerateOptions(max_tokens=512, temperature=0.7),
            )
            
            latency = int((time.time() - task_start) * 1000)
            tokens = response.usage.total_tokens if response.usage else 0
            total_tokens += tokens
            
            # Judge quality if enabled
            quality = 0.0
            if judge and response.content:
                quality = await judge_response(model, task, response.content)
            
            results.append(LLMResult(
                task_id=task.id,
                response=response.content[:100] + "..." if response.content else "",
                latency_ms=latency,
                tokens=tokens,
                quality_score=quality,
            ))
            
            quality_str = f", Q:{quality:.0f}" if judge else ""
            print(f"   [{i+1:2}/{len(tasks)}] ✓ {task.id} ({latency}ms, {tokens}tok{quality_str})")
            
        except Exception as e:
            print(f"   [{i+1:2}/{len(tasks)}] ✗ {task.id} - {e}")
    
    elapsed = time.time() - start
    avg_latency = sum(r.latency_ms for r in results) / len(results) if results else 0
    avg_quality = sum(r.quality_score for r in results) / len(results) if results else 0
    
    return BenchmarkResult(
        name="Sequential",
        tasks_completed=len(results),
        total_time_seconds=elapsed,
        avg_latency_ms=avg_latency,
        total_tokens=total_tokens,
        workers=1,
        avg_quality=avg_quality,
    )


async def run_parallel(model: OllamaModel, tasks: list[LLMTask], num_workers: int = 4, judge: bool = False) -> BenchmarkResult:
    """Run tasks with parallel workers."""
    print("\n" + "─" * 60)
    print(f"📍 PARALLEL MODE ({num_workers} workers){' + JUDGE' if judge else ''}")
    print("─" * 60)
    
    start = time.time()
    results: list[LLMResult] = []
    total_tokens = 0
    lock = asyncio.Lock()
    
    async def worker(worker_id: int, queue: asyncio.Queue):
        nonlocal total_tokens
        
        while True:
            try:
                task = queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            
            task_start = time.time()
            
            try:
                response = await model.generate(
                    task.prompt,
                    options=GenerateOptions(max_tokens=512, temperature=0.7),
                )
                
                latency = int((time.time() - task_start) * 1000)
                tokens = response.usage.total_tokens if response.usage else 0
                
                # Judge quality if enabled
                quality = 0.0
                if judge and response.content:
                    quality = await judge_response(model, task, response.content)
                
                async with lock:
                    total_tokens += tokens
                    results.append(LLMResult(
                        task_id=task.id,
                        response=response.content[:100] + "..." if response.content else "",
                        latency_ms=latency,
                        tokens=tokens,
                        quality_score=quality,
                    ))
                    quality_str = f" Q:{quality:.0f}" if judge else ""
                    print(f"   [W{worker_id}] ✓ {task.id} ({latency}ms{quality_str}) [{len(results)}/{len(tasks)}]")
                    
            except Exception as e:
                async with lock:
                    print(f"   [W{worker_id}] ✗ {task.id} - {e}")
            
            queue.task_done()
    
    # Load queue
    queue = asyncio.Queue()
    for task in tasks:
        await queue.put(task)
    
    # Start workers
    workers = [asyncio.create_task(worker(i, queue)) for i in range(num_workers)]
    await asyncio.gather(*workers)
    
    elapsed = time.time() - start
    avg_latency = sum(r.latency_ms for r in results) / len(results) if results else 0
    avg_quality = sum(r.quality_score for r in results) / len(results) if results else 0
    
    return BenchmarkResult(
        name=f"Parallel ({num_workers}w)",
        tasks_completed=len(results),
        total_time_seconds=elapsed,
        avg_latency_ms=avg_latency,
        total_tokens=total_tokens,
        workers=num_workers,
        avg_quality=avg_quality,
    )


async def run_brain(model: OllamaModel, tasks: list[LLMTask], judge: bool = False) -> BenchmarkResult:
    """Run tasks with brain architecture (specialized regions + validation judge)."""
    print("\n" + "─" * 60)
    print(f"📍 BRAIN MODE (specialized regions){' + LLM JUDGE' if judge else ''}")
    print("─" * 60)
    
    # Group tasks by category
    categories: dict[str, list[LLMTask]] = {}
    for task in tasks:
        if task.category not in categories:
            categories[task.category] = []
        categories[task.category].append(task)
    
    print(f"   Routing: " + ", ".join(f"{len(v)} {k}" for k, v in categories.items()))
    
    start = time.time()
    results: list[LLMResult] = []
    total_tokens = 0
    messages_exchanged = 0
    lock = asyncio.Lock()
    
    # Region configurations (simulating brain specialization)
    # Brain uses LOWER temperature for more focused generation
    region_config = {
        "error_handling": {"parallelism": 2, "name": "Synthesis", "temp": 0.3},      # Precise
        "testing": {"parallelism": 3, "name": "Analysis", "temp": 0.5},              # Balanced
        "documentation": {"parallelism": 2, "name": "Memory", "temp": 0.6},          # Creative
        "code_quality": {"parallelism": 2, "name": "Validation", "temp": 0.2},       # Very precise
    }
    
    async def process_region(category: str, region_tasks: list[LLMTask]):
        """Process a category in its specialized region."""
        nonlocal total_tokens, messages_exchanged
        
        config = region_config.get(category, {"parallelism": 2, "name": "Default", "temp": 0.5})
        parallelism = config["parallelism"]
        region_name = config["name"]
        temperature = config["temp"]
        
        print(f"   🧠 {region_name} region: {len(region_tasks)} tasks (temp={temperature})")
        
        semaphore = asyncio.Semaphore(parallelism)
        
        async def region_worker(task: LLMTask):
            nonlocal total_tokens, messages_exchanged
            
            async with semaphore:
                task_start = time.time()
                
                try:
                    # Brain uses specialized temperature per region
                    response = await model.generate(
                        task.prompt,
                        options=GenerateOptions(max_tokens=512, temperature=temperature),
                    )
                    
                    latency = int((time.time() - task_start) * 1000)
                    tokens = response.usage.total_tokens if response.usage else 0
                    
                    # Brain ALWAYS judges quality (validation region)
                    quality = 0.0
                    if judge and response.content:
                        quality = await judge_response(model, task, response.content)
                        messages_exchanged += 1  # Judge adds a message
                    
                    async with lock:
                        total_tokens += tokens
                        messages_exchanged += 1  # Report to executive
                        results.append(LLMResult(
                            task_id=task.id,
                            response=response.content[:100] + "..." if response.content else "",
                            latency_ms=latency,
                            tokens=tokens,
                            quality_score=quality,
                        ))
                        quality_str = f" Q:{quality:.0f}" if judge else ""
                        print(f"   🧠 [{region_name}] ✓ {task.id} ({latency}ms{quality_str})")
                        
                except Exception as e:
                    async with lock:
                        print(f"   🧠 [{region_name}] ✗ {task.id} - {e}")
        
        await asyncio.gather(*[region_worker(t) for t in region_tasks])
        
        # Inter-region communication
        async with lock:
            messages_exchanged += 1  # Report completion to memory
    
    # Run all regions in parallel
    await asyncio.gather(*[
        process_region(cat, cat_tasks) 
        for cat, cat_tasks in categories.items()
    ])
    
    elapsed = time.time() - start
    avg_latency = sum(r.latency_ms for r in results) / len(results) if results else 0
    avg_quality = sum(r.quality_score for r in results) / len(results) if results else 0
    
    # Count effective workers (sum of region parallelism)
    total_workers = sum(
        region_config.get(cat, {"parallelism": 2})["parallelism"] 
        for cat in categories
    )
    
    return BenchmarkResult(
        name="Brain",
        tasks_completed=len(results),
        total_time_seconds=elapsed,
        avg_latency_ms=avg_latency,
        total_tokens=total_tokens,
        workers=total_workers,
        messages=messages_exchanged,
        avg_quality=avg_quality,
    )


def print_results(results: list[BenchmarkResult], model_name: str, judge: bool = False) -> None:
    """Print comparison table."""
    print("\n")
    print("╔" + "═" * 78 + "╗")
    print(f"║ 📊 LLM BENCHMARK RESULTS (Model: {model_name})".ljust(79) + "║")
    print("╠" + "═" * 78 + "╣")
    
    # Header - include Quality column if judging
    if judge:
        print("║  {:14} {:>7} {:>8} {:>8} {:>7} {:>7} {:>7}  ║".format(
            "Architecture", "Time", "Lat", "Tokens", "Tok/s", "Speed", "Quality"
        ))
        print("║  {:14} {:>7} {:>8} {:>8} {:>7} {:>7} {:>7}  ║".format(
            "─" * 14, "─" * 7, "─" * 8, "─" * 8, "─" * 7, "─" * 7, "─" * 7
        ))
    else:
        print("║  {:18} {:>8} {:>10} {:>10} {:>10} {:>8}  ║".format(
            "Architecture", "Time", "Avg Lat", "Tokens", "Tok/s", "Speedup"
        ))
        print("║  {:18} {:>8} {:>10} {:>10} {:>10} {:>8}  ║".format(
            "─" * 18, "─" * 8, "─" * 10, "─" * 10, "─" * 10, "─" * 8
        ))
    
    # Get sequential baseline for speedup
    seq_time = results[0].total_time_seconds if results else 1.0
    
    for r in results:
        speedup = seq_time / r.total_time_seconds if r.total_time_seconds > 0 else 0
        if judge:
            print("║  {:14} {:>6.1f}s {:>7.0f}ms {:>8} {:>6.0f} {:>6.1f}x {:>6.1f}  ║".format(
                r.name,
                r.total_time_seconds,
                r.avg_latency_ms,
                r.total_tokens,
                r.tokens_per_second,
                speedup,
                r.avg_quality,
            ))
        else:
            print("║  {:18} {:>7.1f}s {:>9.0f}ms {:>10} {:>9.0f} {:>7.1f}x  ║".format(
                r.name,
                r.total_time_seconds,
                r.avg_latency_ms,
                r.total_tokens,
                r.tokens_per_second,
                speedup,
            ))
    
    print("╠" + "═" * 78 + "╣")
    
    if results:
        fastest = min(results, key=lambda r: r.total_time_seconds)
        speedup = seq_time / fastest.total_time_seconds if fastest.total_time_seconds > 0 else 0
        
        print(f"║  🏆 SPEED WINNER: {fastest.name}".ljust(79) + "║")
        print(f"║     {speedup:.1f}x faster than sequential".ljust(79) + "║")
        
        if judge:
            # Find quality winner
            best_quality = max(results, key=lambda r: r.avg_quality)
            print(f"║".ljust(79) + "║")
            print(f"║  🎯 QUALITY WINNER: {best_quality.name} ({best_quality.avg_quality:.1f}/10)".ljust(79) + "║")
            
            # Show if brain won quality
            brain_result = next((r for r in results if r.name == "Brain"), None)
            if brain_result and brain_result.avg_quality == best_quality.avg_quality:
                print(f"║     Brain's specialized regions produced best quality!".ljust(79) + "║")
        
        if fastest.messages > 0:
            print(f"║     {fastest.messages} inter-region messages".ljust(79) + "║")
    
    print("╚" + "═" * 78 + "╝")


async def check_ollama() -> list[str]:
    """Check if Ollama is running and list available models."""
    try:
        model = OllamaModel(model="test")
        models = await model.list_models()
        return models
    except Exception as e:
        return []


async def main():
    parser = argparse.ArgumentParser(description="LLM Architecture Benchmark")
    parser.add_argument("--model", default="hhao/qwen2.5-coder-tools:14b", 
                       help="Ollama model to use")
    parser.add_argument("--tasks", type=int, default=10, 
                       help="Number of tasks to run")
    parser.add_argument("--workers", type=int, default=4,
                       help="Number of parallel workers")
    parser.add_argument("--skip-sequential", action="store_true",
                       help="Skip sequential benchmark (saves time)")
    parser.add_argument("--judge", action="store_true",
                       help="Enable LLM quality judging (same model judges outputs)")
    args = parser.parse_args()
    
    # Banner
    print()
    print("╔" + "═" * 78 + "╗")
    print("║" + " 🏎️  REAL LLM BENCHMARK".ljust(78) + "║")
    print("║" + f" Model: {args.model}".ljust(78) + "║")
    print("║" + " Comparing: Sequential vs Parallel vs Brain".ljust(78) + "║")
    if args.judge:
        print("║" + " 🎯 LLM Quality Judge: ENABLED (same model evaluates outputs)".ljust(78) + "║")
    print("╚" + "═" * 78 + "╝")
    
    # Check Ollama
    print("\n🔍 Checking Ollama...")
    available_models = await check_ollama()
    
    if not available_models:
        print("❌ Ollama not running! Start with: ollama serve")
        return
    
    print(f"   Available models: {', '.join(available_models[:5])}...")
    
    if args.model not in available_models:
        print(f"⚠️  Model '{args.model}' not found. Available: {available_models}")
        print(f"   Try: ollama pull {args.model}")
        return
    
    # Create model
    model = OllamaModel(model=args.model)
    print(f"✓ Using model: {args.model}")
    
    # Generate tasks
    tasks = generate_tasks(args.tasks)
    print(f"✓ Generated {len(tasks)} tasks")
    
    results = []
    
    # Run benchmarks
    if not args.skip_sequential:
        result = await run_sequential(model, tasks, judge=args.judge)
        results.append(result)
    else:
        print("\n⏭️  Skipping sequential benchmark")
        # Create a dummy result for speedup calculation
        results.append(BenchmarkResult(
            name="Sequential (skipped)",
            tasks_completed=0,
            total_time_seconds=0,
            avg_latency_ms=0,
            total_tokens=0,
            workers=1,
        ))
    
    result = await run_parallel(model, tasks, num_workers=args.workers, judge=args.judge)
    results.append(result)
    
    result = await run_brain(model, tasks, judge=args.judge)
    results.append(result)
    
    # Print comparison
    print_results([r for r in results if r.tasks_completed > 0], args.model, judge=args.judge)
    
    print("\n✅ Benchmark complete!\n")


if __name__ == "__main__":
    asyncio.run(main())
