"""File locking for multi-instance coordination (RFC-051).

Advisory file locks prevent simultaneous file access across worker processes.
Uses flock() for cross-process safety on the same machine.
"""

import asyncio
import contextlib
import fcntl
import os
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class FileLock:
    """An acquired file lock."""

    path: Path
    """The file path being locked."""

    lock_file: Path
    """The lock file path."""

    fd: int
    """File descriptor for the lock."""


class FileLockManager:
    """Manages advisory file locks for coordinating access.

    Uses flock() for advisory locking — works across processes on same machine.
    Handles stale lock cleanup for crashed workers.
    Includes deadlock prevention via sorted acquisition order.

    Example:
        manager = FileLockManager(root / ".sunwell" / "locks")

        # Acquire single lock
        lock = await manager.acquire(Path("src/auth.py"), timeout=30.0)
        try:
            # ... do work ...
        finally:
            await manager.release(lock)

        # Or acquire multiple locks (deadlock-safe)
        locks = await manager.acquire_all([Path("a.py"), Path("b.py")])
        try:
            # ... do work ...
        finally:
            await manager.release_all(locks)

    Deadlock Prevention:
        - Locks are always acquired in sorted path order
        - Timeout prevents indefinite waiting
        - Stale lock detection cleans up crashed workers
    """

    def __init__(
        self,
        locks_dir: Path,
        stale_threshold_seconds: float = 60.0,
        max_retry_attempts: int = 100,
    ):
        """Initialize lock manager.

        Args:
            locks_dir: Directory to store lock files
            stale_threshold_seconds: Lock considered stale after this duration
            max_retry_attempts: Maximum retry attempts before giving up
        """
        self.locks_dir = Path(locks_dir)
        self.locks_dir.mkdir(parents=True, exist_ok=True)
        self.stale_threshold_seconds = stale_threshold_seconds
        self.max_retry_attempts = max_retry_attempts
        self._held_locks: dict[Path, FileLock] = {}

    def _lock_path(self, file_path: Path) -> Path:
        """Get lock file path for a given source file.

        Flattens path: src/auth.py → src_auth.py.lock
        """
        flat_name = str(file_path).replace("/", "_").replace("\\", "_")
        return self.locks_dir / "files" / f"{flat_name}.lock"

    def is_locked(self, file_path: Path) -> bool:
        """Check if a file is locked by another process.

        Non-blocking check using LOCK_NB.
        Also cleans up stale locks from crashed workers.

        Args:
            file_path: The file to check

        Returns:
            True if locked by another process
        """
        lock_path = self._lock_path(file_path)

        if not lock_path.exists():
            return False

        # Check for stale lock (file older than threshold)
        if self._is_stale_lock(lock_path):
            self._cleanup_stale_lock(lock_path)
            return False

        try:
            fd = os.open(str(lock_path), os.O_RDONLY)
            try:
                # Try non-blocking lock
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                # Got lock → file was not locked
                fcntl.flock(fd, fcntl.LOCK_UN)
                return False
            except BlockingIOError:
                # Could not get lock → file is locked
                return True
            finally:
                os.close(fd)
        except FileNotFoundError:
            return False

    def _is_stale_lock(self, lock_path: Path) -> bool:
        """Check if a lock file is stale (no active holder).

        A lock is stale if:
        1. The lock file exists but no process holds flock on it
        2. AND it's older than stale_threshold_seconds
        """
        try:
            mtime = lock_path.stat().st_mtime
            age = time.time() - mtime
            return age > self.stale_threshold_seconds
        except FileNotFoundError:
            return False

    def _cleanup_stale_lock(self, lock_path: Path) -> None:
        """Remove a stale lock file."""
        try:
            # Double-check we can acquire the lock (no active holder)
            fd = os.open(str(lock_path), os.O_RDONLY)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(fd, fcntl.LOCK_UN)
                # Successfully locked → no holder → safe to delete
                lock_path.unlink(missing_ok=True)
            except BlockingIOError:
                # Active holder exists, not stale
                pass
            finally:
                os.close(fd)
        except FileNotFoundError:
            pass

    async def acquire(
        self,
        file_path: Path,
        timeout: float = 30.0,
    ) -> FileLock:
        """Acquire lock on a file with timeout.

        Includes deadlock prevention:
        - Timeout to prevent indefinite waiting
        - Stale lock cleanup before retrying
        - Maximum retry attempts

        Args:
            file_path: The file to lock
            timeout: Maximum time to wait for lock

        Returns:
            FileLock object

        Raises:
            TimeoutError: If lock cannot be acquired within timeout
        """
        lock_path = self._lock_path(file_path)
        lock_path.parent.mkdir(parents=True, exist_ok=True)

        # Create or open lock file
        fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR)

        start = asyncio.get_event_loop().time()
        attempts = 0

        while attempts < self.max_retry_attempts:
            attempts += 1
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                # Got the lock - update mtime to indicate active lock
                os.utime(lock_path, None)
                lock = FileLock(path=file_path, lock_file=lock_path, fd=fd)
                self._held_locks[file_path] = lock
                return lock
            except BlockingIOError:
                # Lock held by another process
                elapsed = asyncio.get_event_loop().time() - start
                if elapsed > timeout:
                    os.close(fd)
                    raise TimeoutError(
                        f"Timeout acquiring lock for {file_path} after {attempts} attempts"
                    ) from None

                # Check for stale lock and clean up if needed
                if self._is_stale_lock(lock_path):
                    self._cleanup_stale_lock(lock_path)

                # Exponential backoff with jitter to reduce contention
                import random
                backoff = min(0.5, 0.05 * (2 ** min(attempts, 5)))
                jitter = random.uniform(0, backoff * 0.5)
                await asyncio.sleep(backoff + jitter)

        # Exceeded max retry attempts
        os.close(fd)
        raise TimeoutError(
            f"Max retry attempts ({self.max_retry_attempts}) exceeded for {file_path}"
        )

    async def acquire_all(
        self,
        file_paths: list[Path],
        timeout: float = 30.0,
    ) -> list[FileLock]:
        """Acquire locks on multiple files.

        Acquires in sorted order to prevent deadlocks.
        If any lock fails, releases all acquired locks.

        Args:
            file_paths: Files to lock
            timeout: Maximum time to wait for each lock

        Returns:
            List of FileLock objects

        Raises:
            TimeoutError: If any lock cannot be acquired
        """
        # Sort to prevent deadlocks
        sorted_paths = sorted(file_paths, key=str)
        acquired: list[FileLock] = []

        try:
            for path in sorted_paths:
                lock = await self.acquire(path, timeout=timeout)
                acquired.append(lock)
            return acquired
        except Exception:
            # Release all on failure
            await self.release_all(acquired)
            raise

    async def release(self, lock: FileLock) -> None:
        """Release a file lock.

        Args:
            lock: The lock to release
        """
        if lock.path in self._held_locks:
            del self._held_locks[lock.path]

        try:
            fcntl.flock(lock.fd, fcntl.LOCK_UN)
            os.close(lock.fd)
        except OSError:
            pass  # Already closed or invalid

    async def release_all(self, locks: list[FileLock]) -> None:
        """Release multiple locks.

        Args:
            locks: List of locks to release
        """
        for lock in locks:
            with contextlib.suppress(Exception):
                await self.release(lock)
