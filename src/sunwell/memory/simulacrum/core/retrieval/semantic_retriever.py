"""Semantic retrieval for parallel memory access.

Supports hybrid search combining vector similarity (embeddings) with
BM25 keyword scoring for improved retrieval quality.

Extended with MIRA-inspired importance scoring that incorporates:
- Graph connectivity (hub score)
- Behavioral signals (access patterns, mentions)
- Temporal relevance (recency, deadlines)
"""

from typing import TYPE_CHECKING

from sunwell.foundation.threading import WorkloadType, optimal_workers, run_parallel
from sunwell.foundation.types.memory import MemoryRetrievalResult
from sunwell.memory.simulacrum.core.retrieval.importance import compute_importance
from sunwell.memory.simulacrum.core.retrieval.similarity import (
    bm25_score,
    hybrid_score,
    normalize_bm25,
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

    Supports hybrid search combining:
    - Vector similarity (semantic matching via embeddings)
    - BM25 scoring (lexical matching for exact terms)

    Hybrid search catches both semantic relationships ("auth" → "authentication")
    and exact term matches that embeddings might miss.
    """

    def __init__(
        self,
        dag: ConversationDAG,
        embedder: EmbeddingProtocol | None = None,
        episodes: list[Episode] | None = None,
        chunk_manager: ChunkManager | None = None,
        hybrid_weight: float = 0.7,
    ) -> None:
        """Initialize semantic retriever.

        Args:
            dag: Conversation DAG
            embedder: Optional embedder for semantic matching
            episodes: Optional list of episodes
            chunk_manager: Optional chunk manager for chunk retrieval
            hybrid_weight: Weight for vector score in hybrid search (0.0-1.0).
                BM25 weight = 1 - hybrid_weight. Default 0.7 (70% vector, 30% BM25).
        """
        self._dag = dag
        self._embedder = embedder
        self._episodes = episodes or []
        self._chunk_manager = chunk_manager
        self._hybrid_weight = hybrid_weight

    async def retrieve_parallel(
        self,
        query: str,
        include_learnings: bool = True,
        include_episodes: bool = True,
        include_recent_turns: bool = True,
        include_chunks: bool = True,
        limit_per_type: int = 10,
        hybrid_weight: float | None = None,
        activity_days: int = 0,
    ) -> MemoryRetrievalResult:
        """Parallel retrieval across memory types with importance scoring.

        Args:
            query: Query string for semantic matching
            include_learnings: Include learnings from DAG
            include_episodes: Include episodes (past sessions)
            include_recent_turns: Include recent conversation turns
            include_chunks: Include warm/cold chunks
            limit_per_type: Max items per memory type
            hybrid_weight: Override instance hybrid_weight for this query.
                0.0 = pure BM25, 1.0 = pure vector, None = use instance default.
            activity_days: Current cumulative activity day count for decay calculations.
                Pass 0 to disable activity-based decay (uses calendar time only).

        Returns:
            MemoryRetrievalResult with all retrieved items
        """
        weight = hybrid_weight if hybrid_weight is not None else self._hybrid_weight

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
            """Retrieve and score learnings using importance scoring."""
            if not include_learnings:
                return []

            learnings = self._dag.get_active_learnings()
            scored: list[tuple[Learning, float]] = []

            for learning in learnings:
                # First compute semantic similarity
                semantic_score = hybrid_score(
                    query=query,
                    document=learning.fact,
                    query_embedding=query_embedding,
                    doc_embedding=learning.embedding,
                    vector_weight=weight,
                )

                # Get inbound link count from learning graph (hub score)
                inbound_links = self._dag.get_inbound_link_count(learning.id)

                # Use full importance scoring with graph connectivity
                score = compute_importance(
                    learning=learning,
                    query_similarity=semantic_score,
                    activity_days=activity_days,
                    inbound_link_count=inbound_links,
                )

                if score > 0.3:
                    scored.append((learning, score))

            scored.sort(key=lambda x: -x[1])
            return scored[:limit_per_type]

        def get_episodes() -> list[tuple[Episode, float]]:
            """Retrieve and score episodes using BM25."""
            if not include_episodes:
                return []

            scored: list[tuple[Episode, float]] = []
            for ep in self._episodes:
                # Use BM25 for episodes (typically no embeddings)
                raw_score = bm25_score(query, ep.summary)
                score = normalize_bm25(raw_score)

                # Always include dead ends with boosted score
                if ep.outcome == "failed":
                    score = min(1.0, score + 0.3)

                if score > 0.2 or ep.outcome == "failed":
                    scored.append((ep, score))

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
            """Retrieve relevant chunks using hybrid search."""
            if not include_chunks or not self._chunk_manager:
                return []

            # Get all chunks and score them
            all_chunks = self._chunk_manager.get_all_chunks()
            scored: list[tuple[str, float]] = []

            for chunk in all_chunks:
                if chunk.summary:
                    text = chunk.summary.main_points
                    # Use BM25 for chunks (embeddings computed per-chunk is expensive)
                    raw_score = bm25_score(query, text)
                    score = normalize_bm25(raw_score)

                    if score > 0.2:
                        scored.append((text, score))

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
