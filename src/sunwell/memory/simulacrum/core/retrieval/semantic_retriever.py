"""Semantic retrieval for parallel memory access."""

from typing import TYPE_CHECKING

from sunwell.foundation.threading import WorkloadType, optimal_workers, run_parallel
from sunwell.foundation.types.memory import MemoryRetrievalResult
from sunwell.memory.simulacrum.core.retrieval.similarity import (
    cosine_similarity,
    keyword_similarity,
)

if TYPE_CHECKING:
    from sunwell.foundation.types.memory import Episode
    from sunwell.knowledge.embedding.protocol import EmbeddingProtocol
    from sunwell.memory.simulacrum.core.dag import ConversationDAG
    from sunwell.memory.simulacrum.core.turn import Learning, Turn
    from sunwell.memory.simulacrum.hierarchical.chunk_manager import ChunkManager


class SemanticRetriever:
    """Parallel retrieval across memory types with free-threading awareness.

    Uses ThreadPoolExecutor with adaptive worker count based on GIL state
    for true parallel retrieval when running on Python 3.13+ free-threaded.
    """

    def __init__(
        self,
        dag: ConversationDAG,
        embedder: EmbeddingProtocol | None = None,
        episodes: list[Episode] | None = None,
        chunk_manager: ChunkManager | None = None,
    ) -> None:
        """Initialize semantic retriever.

        Args:
            dag: Conversation DAG
            embedder: Optional embedder for semantic matching
            episodes: Optional list of episodes
            chunk_manager: Optional chunk manager for chunk retrieval
        """
        self._dag = dag
        self._embedder = embedder
        self._episodes = episodes or []
        self._chunk_manager = chunk_manager

    async def retrieve_parallel(
        self,
        query: str,
        include_learnings: bool = True,
        include_episodes: bool = True,
        include_recent_turns: bool = True,
        include_chunks: bool = True,
        limit_per_type: int = 10,
    ) -> MemoryRetrievalResult:
        """Parallel retrieval across memory types.

        Args:
            query: Query string for semantic matching
            include_learnings: Include learnings from DAG
            include_episodes: Include episodes (past sessions)
            include_recent_turns: Include recent conversation turns
            include_chunks: Include warm/cold chunks
            limit_per_type: Max items per memory type

        Returns:
            MemoryRetrievalResult with all retrieved items
        """
        # Compute query embedding once
        query_embedding: tuple[float, ...] | None = None
        if self._embedder:
            try:
                result = await self._embedder.embed([query])
                query_embedding = tuple(result[0])
            except Exception:
                query_embedding = None

        # Define retrieval tasks as sync functions
        def get_learnings() -> list[tuple[Learning, float]]:
            """Retrieve and score learnings."""
            if not include_learnings:
                return []

            learnings = self._dag.get_active_learnings()
            scored: list[tuple[Learning, float]] = []

            for learning in learnings:
                if query_embedding and learning.embedding:
                    score = cosine_similarity(query_embedding, learning.embedding)
                else:
                    score = keyword_similarity(query, learning.fact)

                if score > 0.3:
                    scored.append((learning, score))

            scored.sort(key=lambda x: -x[1])
            return scored[:limit_per_type]

        def get_episodes() -> list[tuple[Episode, float]]:
            """Retrieve and score episodes."""
            if not include_episodes:
                return []

            scored: list[tuple[Episode, float]] = []
            for ep in self._episodes:
                # Simple keyword match for episodes
                score = keyword_similarity(query, ep.summary)
                if score > 0.2 or ep.outcome == "failed":  # Always include dead ends
                    # Boost failed episodes to avoid dead ends
                    if ep.outcome == "failed":
                        score += 0.3
                    scored.append((ep, min(1.0, score)))

            scored.sort(key=lambda x: -x[1])
            return scored[:limit_per_type]

        def get_recent_turns() -> list[tuple[Turn, float]]:
            """Retrieve recent turns."""
            if not include_recent_turns:
                return []

            turns = self._dag.get_recent_turns(limit_per_type)
            # Recent turns get relevance based on recency
            return [(turn, 1.0 - (i * 0.05)) for i, turn in enumerate(turns)]

        def get_chunks() -> list[tuple[str, float]]:
            """Retrieve relevant chunks."""
            if not include_chunks or not self._chunk_manager:
                return []

            # Get all chunks and score them
            all_chunks = self._chunk_manager.get_all_chunks()
            scored: list[tuple[str, float]] = []

            for chunk in all_chunks:
                if chunk.summary:
                    score = keyword_similarity(query, chunk.summary.main_points)
                    if score > 0.2:
                        content = chunk.summary.main_points
                        scored.append((content, score))

            scored.sort(key=lambda x: -x[1])
            return scored[:limit_per_type]

        # Get optimal worker count based on GIL state
        workers = optimal_workers(WorkloadType.IO_BOUND)

        # Run all retrieval tasks in parallel
        tasks = [get_learnings, get_episodes, get_recent_turns, get_chunks]
        results, stats = await run_parallel(tasks, WorkloadType.IO_BOUND, max_workers=workers)

        # Unpack results
        learnings_result, episodes_result, turns_result, chunks_result = results

        return MemoryRetrievalResult(
            learnings=learnings_result,
            episodes=episodes_result,
            turns=turns_result,
            code_chunks=chunks_result,
            focus_topics=query.split()[:3],
        )
