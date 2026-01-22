"""Free-threading detection and adaptive parallelism.

Python 3.13+ supports free-threading (PEP 703) which disables the GIL.
This module detects the runtime mode and adjusts parallelism accordingly.

Key functions:
- is_free_threaded(): Check if running on a free-threaded build
- optimal_workers(): Get optimal thread count for workload type
- run_parallel(): Adaptive parallel execution

When free-threading is enabled:
- CPU-bound tasks truly run in parallel
- Higher worker counts are beneficial
- Thread overhead is amortized by real parallelism

When GIL is enabled (standard Python):
- CPU-bound tasks serialize at the GIL
- More workers don't help CPU-bound work
- Keep workers lower to reduce context-switch overhead
"""


import asyncio
import os
import sys
from collections.abc import Callable, Sequence
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum
from functools import cache
from typing import TypeVar

T = TypeVar("T")
R = TypeVar("R")


class WorkloadType(Enum):
    """Type of work being parallelized."""

    IO_BOUND = "io"
    """Network, file I/O - benefits from async/threads regardless of GIL."""

    CPU_BOUND = "cpu"
    """Computation - only benefits from threads if GIL-free."""

    MIXED = "mixed"
    """Both I/O and CPU - use adaptive strategy."""


@cache
def is_free_threaded() -> bool:
    """Check if running on a free-threaded (no-GIL) Python build.

    Returns:
        True if the GIL is disabled, False otherwise.

    Detection methods (in order):
    1. sys._is_gil_enabled() - Python 3.13+ direct API
    2. sysconfig Py_GIL_DISABLED - build-time flag
    3. PYTHON_GIL=0 environment variable
    """
    # Method 1: Direct API (Python 3.13+)
    if hasattr(sys, "_is_gil_enabled"):
        return not sys._is_gil_enabled()

    # Method 2: Build config
    try:
        import sysconfig
        gil_disabled = sysconfig.get_config_var("Py_GIL_DISABLED")
        if gil_disabled:
            return bool(int(gil_disabled))
    except (ImportError, ValueError, TypeError):
        pass

    # Method 3: Environment variable (runtime override)
    return os.environ.get("PYTHON_GIL", "1") == "0"


@cache
def cpu_count() -> int:
    """Get available CPU cores."""
    try:
        # Prefer len(os.sched_getaffinity(0)) for container-awareness
        return len(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        return os.cpu_count() or 4


def optimal_workers(workload: WorkloadType = WorkloadType.MIXED) -> int:
    """Get optimal worker count for given workload type.

    Args:
        workload: Type of work being parallelized.

    Returns:
        Recommended number of workers.

    Strategy:
    - IO_BOUND: High concurrency (4x CPU) - threads wait on I/O
    - CPU_BOUND: Match CPU count if free-threaded, else minimal
    - MIXED: Adaptive based on GIL state
    """
    cpus = cpu_count()
    free_threaded = is_free_threaded()

    if workload == WorkloadType.IO_BOUND:
        # I/O-bound: threads spend time waiting, high concurrency helps
        return cpus * 4

    elif workload == WorkloadType.CPU_BOUND:
        if free_threaded:
            # True parallelism: match CPU cores
            return cpus
        else:
            # GIL serializes: more threads = more overhead, no benefit
            return 2

    else:  # MIXED
        if free_threaded:
            # Can benefit from parallelism
            return cpus * 2
        else:
            # Conservative for GIL Python
            return cpus


@dataclass(frozen=True, slots=True)
class ParallelStats:
    """Statistics from parallel execution."""

    total_items: int
    workers_used: int
    elapsed_ms: float
    free_threaded: bool

    @property
    def items_per_second(self) -> float:
        if self.elapsed_ms <= 0:
            return 0
        return (self.total_items / self.elapsed_ms) * 1000

    @property
    def parallelism_effective(self) -> bool:
        """Was parallelism actually effective?"""
        # If free-threaded and multiple workers, yes
        return self.free_threaded and self.workers_used > 1


async def run_parallel[T](
    tasks: Sequence[Callable[[], T]],
    workload: WorkloadType = WorkloadType.MIXED,
    max_workers: int | None = None,
) -> tuple[list[T], ParallelStats]:
    """Run tasks in parallel with adaptive worker count.

    Automatically adjusts strategy based on:
    - Free-threading availability
    - Workload type
    - Task count

    Args:
        tasks: Sequence of zero-argument callables.
        workload: Type of work being done.
        max_workers: Override worker count (None = auto).

    Returns:
        Tuple of (results in order, execution stats).
    """
    import time

    if not tasks:
        return [], ParallelStats(0, 0, 0, is_free_threaded())

    # Determine workers
    workers = max_workers or optimal_workers(workload)
    workers = min(workers, len(tasks))  # Don't over-allocate

    start = time.perf_counter()

    # Single task: run directly (no thread overhead)
    if len(tasks) == 1:
        result = tasks[0]()
        elapsed = (time.perf_counter() - start) * 1000
        return [result], ParallelStats(1, 1, elapsed, is_free_threaded())

    # Multiple tasks: use thread pool
    # Note: We don't propagate context to avoid "already entered" errors
    # when running from async context. Each thread gets fresh context.
    loop = asyncio.get_event_loop()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            loop.run_in_executor(pool, task)
            for task in tasks
        ]
        results = await asyncio.gather(*futures, return_exceptions=True)

    elapsed = (time.perf_counter() - start) * 1000

    # Re-raise any exceptions
    for r in results:
        if isinstance(r, Exception):
            raise r

    return list(results), ParallelStats(
        total_items=len(tasks),
        workers_used=workers,
        elapsed_ms=elapsed,
        free_threaded=is_free_threaded(),
    )


async def run_parallel_async(
    coroutines: Sequence,
    max_concurrency: int | None = None,
) -> tuple[list, ParallelStats]:
    """Run async coroutines concurrently.

    For I/O-bound async work, asyncio.gather is optimal.
    This wrapper adds stats tracking.

    Args:
        coroutines: Async coroutines to run.
        max_concurrency: Limit concurrent coroutines (None = unlimited).

    Returns:
        Tuple of (results, stats).
    """
    import time

    if not coroutines:
        return [], ParallelStats(0, 0, 0, is_free_threaded())

    start = time.perf_counter()

    if max_concurrency and max_concurrency < len(coroutines):
        # Use semaphore for bounded concurrency
        sem = asyncio.Semaphore(max_concurrency)

        async def bounded(coro):
            async with sem:
                return await coro

        results = await asyncio.gather(
            *[bounded(c) for c in coroutines],
            return_exceptions=True,
        )
        workers = max_concurrency
    else:
        results = await asyncio.gather(*coroutines, return_exceptions=True)
        workers = len(coroutines)

    elapsed = (time.perf_counter() - start) * 1000

    for r in results:
        if isinstance(r, Exception):
            raise r

    return list(results), ParallelStats(
        total_items=len(coroutines),
        workers_used=workers,
        elapsed_ms=elapsed,
        free_threaded=is_free_threaded(),
    )


def run_cpu_bound[T](
    tasks: Sequence[Callable[[], T]],
    max_workers: int | None = None,
) -> list[T]:
    """Run CPU-bound tasks with optimal strategy.

    Uses ProcessPoolExecutor if GIL is enabled (true parallelism via processes).
    Uses ThreadPoolExecutor if free-threaded (true parallelism via threads).

    Note: ProcessPoolExecutor has serialization overhead. Only use for
    genuinely CPU-intensive tasks where the computation time exceeds
    the pickling cost.

    Args:
        tasks: Callables to run (must be picklable if using processes).
        max_workers: Override worker count.

    Returns:
        Results in order.
    """
    if not tasks:
        return []

    if len(tasks) == 1:
        return [tasks[0]()]

    workers = max_workers or cpu_count()
    workers = min(workers, len(tasks))

    if is_free_threaded():
        # Threads have true parallelism - lower overhead than processes
        with ThreadPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(lambda t: t(), tasks))
    else:
        # Need processes for true parallelism
        with ProcessPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(lambda t: t(), tasks))


def runtime_info() -> dict:
    """Get runtime parallelism info for diagnostics."""
    return {
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "free_threaded": is_free_threaded(),
        "cpu_count": cpu_count(),
        "optimal_workers": {
            "io_bound": optimal_workers(WorkloadType.IO_BOUND),
            "cpu_bound": optimal_workers(WorkloadType.CPU_BOUND),
            "mixed": optimal_workers(WorkloadType.MIXED),
        },
        "gil_status": "disabled" if is_free_threaded() else "enabled",
    }


def optimal_llm_workers(
    ollama_num_parallel: int | None = None,
    num_models: int = 2,
) -> int:
    """Get optimal worker count for LLM workloads.

    LLM inference is I/O-bound from the client's perspective:
    - Waiting for network I/O
    - Waiting for GPU/CPU inference on server

    The limit is typically the Ollama server's capacity, not the client.

    Args:
        ollama_num_parallel: Ollama's OLLAMA_NUM_PARALLEL setting.
            None = use default (4).
        num_models: Number of distinct models being used concurrently.
            E.g., synthesis + judge = 2.

    Returns:
        Recommended max_parallel_tasks for Naaru.

    Strategy:
        - Cap at ollama_num_parallel * num_models (server limit)
        - Don't exceed 4x CPU count (client-side limit)
        - Minimum of 4 for reasonable throughput
    """
    # Server-side limit
    ollama_parallel = ollama_num_parallel or 4
    server_limit = ollama_parallel * num_models

    # Client-side limit (I/O bound = high concurrency is fine)
    client_limit = cpu_count() * 4

    # Take the minimum, ensure at least 4
    return max(4, min(server_limit, client_limit))
