#!/usr/bin/env python3
"""Realistic benchmark simulating actual I/O workloads.

The mock benchmark showed sequential winning because operations were instant.
This benchmark simulates realistic latencies:
- LLM API calls: 100-500ms
- File analysis: 50-200ms
- Validation: 50-100ms

Usage:
    python examples/realistic_benchmark.py
"""

import asyncio
import random
import time
from dataclasses import dataclass, field


@dataclass
class Task:
    """A simulated task with realistic latency."""
    id: str
    category: str
    simulated_latency_ms: int = 200


@dataclass 
class SimulatedResult:
    """Result from simulated architecture."""
    name: str
    tasks_completed: int
    time_seconds: float
    workers: int
    messages: int = 0
    
    @property
    def throughput(self) -> float:
        return self.tasks_completed / self.time_seconds if self.time_seconds > 0 else 0
    
    @property
    def speedup_vs_sequential(self) -> float:
        """Calculate vs a sequential baseline."""
        return 0.0  # Will be calculated later


def generate_tasks(n: int = 20) -> list[Task]:
    """Generate tasks with realistic latency distribution."""
    tasks = []
    categories = ["llm_call", "file_analysis", "validation"]
    latencies = {
        "llm_call": (200, 500),      # LLM API: 200-500ms
        "file_analysis": (50, 200),   # File ops: 50-200ms  
        "validation": (50, 100),      # Validation: 50-100ms
    }
    
    for i in range(n):
        cat = random.choice(categories)
        lat_min, lat_max = latencies[cat]
        tasks.append(Task(
            id=f"task_{i:03d}",
            category=cat,
            simulated_latency_ms=random.randint(lat_min, lat_max),
        ))
    
    return tasks


async def simulate_sequential(tasks: list[Task]) -> SimulatedResult:
    """Simulate sequential execution (1 worker)."""
    print("\n" + "─" * 60)
    print("📍 SEQUENTIAL (1 worker)")
    print("─" * 60)
    
    start = time.time()
    
    for i, task in enumerate(tasks):
        # Simulate the work
        await asyncio.sleep(task.simulated_latency_ms / 1000.0)
        print(f"   [{i+1:2}/{len(tasks)}] ✓ {task.id} ({task.category}: {task.simulated_latency_ms}ms)")
    
    elapsed = time.time() - start
    
    return SimulatedResult(
        name="Sequential",
        tasks_completed=len(tasks),
        time_seconds=elapsed,
        workers=1,
    )


async def simulate_parallel(tasks: list[Task], num_workers: int = 8) -> SimulatedResult:
    """Simulate parallel worker pool."""
    print("\n" + "─" * 60)
    print(f"📍 PARALLEL ({num_workers} workers)")
    print("─" * 60)
    
    start = time.time()
    completed = 0
    lock = asyncio.Lock()
    
    async def worker(worker_id: int, queue: asyncio.Queue):
        nonlocal completed
        while True:
            try:
                task = queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            
            # Simulate the work
            await asyncio.sleep(task.simulated_latency_ms / 1000.0)
            
            async with lock:
                completed += 1
                print(f"   [W{worker_id}] ✓ {task.id} ({task.simulated_latency_ms}ms) [{completed}/{len(tasks)}]")
            
            queue.task_done()
    
    # Load queue
    queue = asyncio.Queue()
    for task in tasks:
        await queue.put(task)
    
    # Start workers
    workers = [asyncio.create_task(worker(i, queue)) for i in range(num_workers)]
    await asyncio.gather(*workers)
    
    elapsed = time.time() - start
    
    return SimulatedResult(
        name=f"Parallel ({num_workers}w)",
        tasks_completed=len(tasks),
        time_seconds=elapsed,
        workers=num_workers,
    )


async def simulate_brain(tasks: list[Task]) -> SimulatedResult:
    """Simulate brain architecture with specialized regions."""
    print("\n" + "─" * 60)
    print("📍 BRAIN (specialized regions)")
    print("─" * 60)
    
    start = time.time()
    messages_exchanged = 0
    
    # Group tasks by type (like brain routing)
    llm_tasks = [t for t in tasks if t.category == "llm_call"]
    file_tasks = [t for t in tasks if t.category == "file_analysis"]
    validation_tasks = [t for t in tasks if t.category == "validation"]
    
    print(f"   Routing: {len(llm_tasks)} LLM, {len(file_tasks)} file, {len(validation_tasks)} validation")
    
    # Simulate inter-region messaging (small overhead)
    async def send_message():
        nonlocal messages_exchanged
        await asyncio.sleep(0.001)  # 1ms message latency
        messages_exchanged += 1
    
    async def process_region(name: str, region_tasks: list[Task], parallelism: int):
        """Process tasks in a specialized region with local parallelism."""
        if not region_tasks:
            return
            
        print(f"   🧠 {name} region processing {len(region_tasks)} tasks ({parallelism} workers)...")
        
        async def region_worker(task: Task):
            await asyncio.sleep(task.simulated_latency_ms / 1000.0)
            await send_message()  # Report completion to executive
            return task.id
        
        # Process with region-specific parallelism
        semaphore = asyncio.Semaphore(parallelism)
        
        async def limited_worker(task: Task):
            async with semaphore:
                return await region_worker(task)
        
        results = await asyncio.gather(*[limited_worker(t) for t in region_tasks])
        print(f"   🧠 {name} completed: {len(results)} tasks")
        
        # Send results to memory region
        await send_message()
    
    # Process regions in parallel (like brain regions working simultaneously)
    await asyncio.gather(
        process_region("Synthesis", llm_tasks, parallelism=2),      # LLM calls need throttling
        process_region("Analysis", file_tasks, parallelism=4),      # File ops can be parallel
        process_region("Validation", validation_tasks, parallelism=2),
    )
    
    elapsed = time.time() - start
    
    return SimulatedResult(
        name="Brain",
        tasks_completed=len(tasks),
        time_seconds=elapsed,
        workers=8,  # 2+4+2 across regions
        messages=messages_exchanged,
    )


def print_comparison(results: list[SimulatedResult], tasks: list[Task]) -> None:
    """Print comparison with proper speedup calculations."""
    print("\n")
    print("╔" + "═" * 78 + "╗")
    print("║" + " 📊 REALISTIC BENCHMARK RESULTS (with simulated I/O latency)".ljust(78) + "║")
    print("╠" + "═" * 78 + "╣")
    
    # Calculate total sequential time (sum of all latencies)
    total_latency_ms = sum(t.simulated_latency_ms for t in tasks)
    theoretical_sequential = total_latency_ms / 1000.0
    
    print(f"║  Total Task Latency: {total_latency_ms}ms ({theoretical_sequential:.2f}s sequential minimum)".ljust(79) + "║")
    print("║" + "".ljust(78) + "║")
    
    # Header
    print("║  {:20} {:>10} {:>10} {:>12} {:>10}  ║".format(
        "Architecture", "Time", "Workers", "Throughput", "Speedup"
    ))
    print("║  {:20} {:>10} {:>10} {:>12} {:>10}  ║".format(
        "─" * 20, "─" * 10, "─" * 10, "─" * 12, "─" * 10
    ))
    
    # Get sequential baseline
    seq_time = results[0].time_seconds if results else 1.0
    
    for r in results:
        speedup = seq_time / r.time_seconds if r.time_seconds > 0 else 0
        print("║  {:20} {:>9.2f}s {:>10} {:>10.1f}/s {:>9.1f}x  ║".format(
            r.name,
            r.time_seconds,
            r.workers,
            r.throughput,
            speedup,
        ))
    
    print("╠" + "═" * 78 + "╣")
    
    if results:
        fastest = min(results, key=lambda r: r.time_seconds)
        speedup = seq_time / fastest.time_seconds if fastest.time_seconds > 0 else 0
        
        print(f"║  🏆 WINNER: {fastest.name}".ljust(79) + "║")
        print(f"║     {speedup:.1f}x faster than sequential".ljust(79) + "║")
        
        if fastest.messages > 0:
            print(f"║     {fastest.messages} inter-region messages exchanged".ljust(79) + "║")
    
    print("╚" + "═" * 78 + "╝")


async def main():
    """Run realistic benchmark."""
    print()
    print("╔" + "═" * 78 + "╗")
    print("║" + " 🏎️  REALISTIC BENCHMARK (Simulated I/O Latency)".ljust(78) + "║")
    print("║" + " LLM calls: 200-500ms | File ops: 50-200ms | Validation: 50-100ms".ljust(78) + "║")
    print("╚" + "═" * 78 + "╝")
    
    # Generate consistent task set
    random.seed(42)  # Reproducible
    tasks = generate_tasks(n=20)
    
    total_ms = sum(t.simulated_latency_ms for t in tasks)
    print(f"\n📋 Generated {len(tasks)} tasks with {total_ms}ms total latency")
    
    results = []
    
    # Run benchmarks
    results.append(await simulate_sequential(tasks))
    results.append(await simulate_parallel(tasks, num_workers=8))
    results.append(await simulate_brain(tasks))
    
    print_comparison(results, tasks)
    
    print("\n" + "─" * 60)
    print("💡 KEY INSIGHT:")
    print("   With real I/O latency, parallel architectures CRUSH sequential.")
    print("   The brain architecture adds coordination overhead but enables")
    print("   specialized processing per task type (like throttling LLM calls).")
    print("─" * 60)
    print()


if __name__ == "__main__":
    asyncio.run(main())
