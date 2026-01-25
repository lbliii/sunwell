"""Resource governance for multi-instance coordination (RFC-051).

Manages shared resources across worker processes:
1. LLM API rate limiting
2. Memory usage tracking
3. Worker count recommendations
"""

import asyncio
import fcntl
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ResourceLimits:
    """Resource limits for parallel execution."""

    max_concurrent_llm_calls: int = 2
    """Maximum concurrent LLM API calls (for rate limiting)."""

    max_memory_per_worker_mb: int = 2048
    """Maximum memory per worker process."""

    max_total_memory_mb: int = 8192
    """Maximum total memory for all workers."""

    llm_requests_per_minute: int = 60
    """LLM API rate limit."""


class ResourceGovernor:
    """Manages shared resources across worker processes.

    Controls:
    1. LLM API rate limiting
    2. Memory usage tracking
    3. Disk I/O throttling (future)

    Example:
        governor = ResourceGovernor(limits, root)

        # Acquire LLM slot before making API call
        async with governor.llm_slot():
            response = await llm.generate(prompt)

        # Check memory before starting worker
        if governor.check_memory():
            worker.start()
    """

    def __init__(self, limits: ResourceLimits, root: Path):
        """Initialize resource governor.

        Args:
            limits: Resource limits configuration
            root: Project root directory
        """
        self.limits = limits
        self.root = Path(root)

        # Semaphore file for LLM concurrency
        self._resources_dir = root / ".sunwell" / "resources"
        self._resources_dir.mkdir(parents=True, exist_ok=True)
        self._llm_semaphore_path = self._resources_dir / "llm_semaphore"
        self._llm_lock_path = self._resources_dir / "llm_semaphore.lock"

    @asynccontextmanager
    async def llm_slot(self) -> AsyncIterator[None]:
        """Acquire a slot for LLM API call.

        Blocks if max_concurrent_llm_calls exceeded.

        Example:
            async with governor.llm_slot():
                response = await llm.generate(prompt)
        """
        await self._acquire_llm_slot()
        try:
            yield
        finally:
            await self._release_llm_slot()

    async def _acquire_llm_slot(self) -> None:
        """Acquire LLM semaphore slot with proper locking.

        Uses flock to ensure atomic read-modify-write.
        """
        while True:
            # Acquire exclusive lock for atomic operation
            fd = os.open(str(self._llm_lock_path), os.O_CREAT | os.O_RDWR)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX)

                count = self._read_llm_count()
                if count < self.limits.max_concurrent_llm_calls:
                    self._write_llm_count(count + 1)
                    return
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)

            # Slot not available, wait and retry
            await asyncio.sleep(0.1)

    async def _release_llm_slot(self) -> None:
        """Release LLM semaphore slot with proper locking."""
        fd = os.open(str(self._llm_lock_path), os.O_CREAT | os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            count = self._read_llm_count()
            self._write_llm_count(max(0, count - 1))
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def _read_llm_count(self) -> int:
        """Read current LLM slot count."""
        if not self._llm_semaphore_path.exists():
            return 0
        try:
            return int(self._llm_semaphore_path.read_text().strip())
        except (ValueError, FileNotFoundError):
            return 0

    def _write_llm_count(self, count: int) -> None:
        """Write LLM slot count atomically."""
        tmp = self._llm_semaphore_path.with_suffix(".tmp")
        tmp.write_text(str(count))
        tmp.rename(self._llm_semaphore_path)

    def check_memory(self) -> bool:
        """Check if memory usage is within limits.

        Returns:
            True if memory is within limits
        """
        try:
            import psutil

            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024

            return memory_mb < self.limits.max_memory_per_worker_mb
        except ImportError:
            # psutil not available, assume OK
            return True

    def get_recommended_workers(self) -> int:
        """Recommend number of workers based on available resources.

        Considers:
        - CPU cores
        - Available memory
        - LLM rate limits

        Returns:
            Recommended number of workers
        """
        try:
            import psutil

            cpu_cores = psutil.cpu_count() or 4
            available_memory_mb = psutil.virtual_memory().available / 1024 / 1024

            # One worker per core, max
            by_cpu = cpu_cores

            # Memory: each worker needs ~2GB
            by_memory = int(available_memory_mb / self.limits.max_memory_per_worker_mb)

            # LLM: don't exceed rate limits
            by_llm = self.limits.max_concurrent_llm_calls

            return max(1, min(by_cpu, by_memory, by_llm))

        except ImportError:
            # psutil not available, default to conservative
            return min(4, self.limits.max_concurrent_llm_calls)

    def reset(self) -> None:
        """Reset all resource tracking.

        Call this when starting fresh or recovering from errors.
        """
        self._write_llm_count(0)
