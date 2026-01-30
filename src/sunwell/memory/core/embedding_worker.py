"""Background embedding worker for non-blocking embedding computation.

Computes embeddings for learnings asynchronously without blocking the agent loop.
The worker processes a queue of learning IDs and updates them with computed embeddings.

Architecture:
- EmbeddingQueue: Thread-safe queue for learning IDs
- EmbeddingWorker: Background task that processes the queue
- Integration: SimulacrumStore/DAG queues learnings, worker updates them
"""

import asyncio
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.knowledge.embedding.protocol import EmbeddingProtocol
    from sunwell.memory.simulacrum.core.dag import ConversationDAG

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class EmbeddingQueue:
    """Thread-safe queue for learning IDs that need embeddings.

    Supports batching for efficient embedding computation.
    """

    _queue: list[str] = field(default_factory=list, init=False)
    """Queue of learning IDs pending embedding."""

    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    """Lock for thread-safe access."""

    _pending: set[str] = field(default_factory=set, init=False)
    """Set of IDs currently pending (for O(1) dedup)."""

    max_size: int = 1000
    """Maximum queue size to prevent unbounded growth."""

    def put(self, learning_id: str) -> bool:
        """Add a learning ID to the queue (thread-safe, O(1)).

        Args:
            learning_id: ID of learning that needs embedding

        Returns:
            True if added, False if already in queue or queue full
        """
        with self._lock:
            if learning_id in self._pending:
                return False
            if len(self._queue) >= self.max_size:
                logger.warning("Embedding queue full, dropping: %s", learning_id)
                return False
            self._queue.append(learning_id)
            self._pending.add(learning_id)
            return True

    def get_batch(self, max_batch: int = 10) -> list[str]:
        """Get a batch of learning IDs (thread-safe).

        Args:
            max_batch: Maximum IDs to return

        Returns:
            List of learning IDs (removes them from queue)
        """
        with self._lock:
            batch = self._queue[:max_batch]
            self._queue = self._queue[max_batch:]
            for lid in batch:
                self._pending.discard(lid)
            return batch

    def __len__(self) -> int:
        """Get queue length (thread-safe)."""
        with self._lock:
            return len(self._queue)

    def is_empty(self) -> bool:
        """Check if queue is empty (thread-safe)."""
        with self._lock:
            return len(self._queue) == 0


@dataclass(slots=True)
class EmbeddingWorker:
    """Background worker that computes embeddings for learnings.

    Runs as an async task, polling the queue and computing embeddings
    in batches for efficiency.

    Usage:
        worker = EmbeddingWorker(embedder, dag, queue)
        task = asyncio.create_task(worker.run())
        # ... later ...
        await worker.stop()
    """

    embedder: EmbeddingProtocol
    """Embedding provider (e.g., OpenAI, local model)."""

    dag: ConversationDAG
    """DAG containing learnings to update."""

    queue: EmbeddingQueue
    """Queue of learning IDs to process."""

    batch_size: int = 10
    """Number of learnings to embed per batch."""

    poll_interval: float = 1.0
    """Seconds to wait between queue polls when empty."""

    _running: bool = field(default=False, init=False)
    """Whether the worker is running."""

    _task: asyncio.Task | None = field(default=None, init=False)
    """The background task."""

    async def run(self) -> None:
        """Run the embedding worker loop.

        Continuously processes the queue until stopped.
        """
        self._running = True
        logger.debug("Embedding worker started")

        while self._running:
            try:
                await self._process_batch()
            except Exception as e:
                logger.warning("Embedding worker error: %s", e)
                await asyncio.sleep(self.poll_interval)

        logger.debug("Embedding worker stopped")

    async def _process_batch(self) -> int:
        """Process a batch of learnings from the queue.

        Returns:
            Number of learnings processed
        """
        batch = self.queue.get_batch(self.batch_size)

        if not batch:
            # Queue empty, wait before next poll
            await asyncio.sleep(self.poll_interval)
            return 0

        # Get learnings from DAG
        learnings_to_embed: list[tuple[str, str]] = []
        for learning_id in batch:
            learning = self.dag.learnings.get(learning_id)
            if learning and learning.embedding is None:
                learnings_to_embed.append((learning_id, learning.fact))

        if not learnings_to_embed:
            return 0

        # Compute embeddings in batch
        try:
            texts = [fact for _, fact in learnings_to_embed]
            result = await self.embedder.embed(texts)

            # Update learnings with embeddings
            for i, (learning_id, _) in enumerate(learnings_to_embed):
                learning = self.dag.learnings.get(learning_id)
                if learning:
                    embedding = tuple(result.vectors[i].tolist())
                    updated = learning.with_embedding(embedding)
                    self.dag.learnings[learning_id] = updated

            logger.debug("Computed embeddings for %d learnings", len(learnings_to_embed))
            return len(learnings_to_embed)

        except Exception as e:
            logger.warning("Failed to compute embeddings: %s", e)
            # Re-queue failed items for retry
            for learning_id, _ in learnings_to_embed:
                self.queue.put(learning_id)
            return 0

    async def stop(self) -> None:
        """Stop the worker gracefully."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def start(self) -> asyncio.Task:
        """Start the worker as a background task.

        Returns:
            The asyncio Task running the worker
        """
        self._task = asyncio.create_task(self.run())
        return self._task


# =============================================================================
# Factory Functions
# =============================================================================


def create_embedding_worker(
    embedder: EmbeddingProtocol,
    dag: ConversationDAG,
    queue: EmbeddingQueue | None = None,
    batch_size: int = 10,
    poll_interval: float = 1.0,
) -> EmbeddingWorker:
    """Create an embedding worker with sensible defaults.

    Args:
        embedder: Embedding provider
        dag: ConversationDAG to update
        queue: Optional existing queue (creates new if None)
        batch_size: Learnings per batch
        poll_interval: Seconds between polls

    Returns:
        Configured EmbeddingWorker
    """
    return EmbeddingWorker(
        embedder=embedder,
        dag=dag,
        queue=queue or EmbeddingQueue(),
        batch_size=batch_size,
        poll_interval=poll_interval,
    )


# =============================================================================
# Integration Helper
# =============================================================================


class EmbeddingQueueIntegration:
    """Integration helper for queuing learnings for embedding.

    Provides a simple interface for the learning extraction flow
    to queue learnings for background embedding.
    """

    def __init__(self, queue: EmbeddingQueue | None = None) -> None:
        """Initialize with optional existing queue."""
        self._queue = queue or EmbeddingQueue()
        self._on_queue_callbacks: list[Callable[[str], None]] = []

    @property
    def queue(self) -> EmbeddingQueue:
        """Get the embedding queue."""
        return self._queue

    def queue_for_embedding(self, learning_id: str) -> bool:
        """Queue a learning for embedding computation.

        Args:
            learning_id: ID of learning to embed

        Returns:
            True if queued successfully
        """
        added = self._queue.put(learning_id)
        if added:
            for callback in self._on_queue_callbacks:
                try:
                    callback(learning_id)
                except Exception as e:
                    logger.debug("Queue callback error: %s", e)
        return added

    def on_queued(self, callback: Callable[[str], None]) -> None:
        """Register a callback for when items are queued.

        Args:
            callback: Function called with learning_id when queued
        """
        self._on_queue_callbacks.append(callback)

    def pending_count(self) -> int:
        """Get count of learnings pending embedding."""
        return len(self._queue)
