"""Semantic tool retrieval using embeddings.

Provides semantic similarity-based tool retrieval by embedding tool
descriptions and matching against user queries. Integrates with
the existing embedding infrastructure.

This module adds a semantic signal to MultiSignalToolSelector,
complementing the DAG-based workflow knowledge with semantic understanding.
"""

import asyncio
import logging
import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from sunwell.knowledge.embedding import InMemoryIndex, create_embedder
from sunwell.knowledge.embedding.protocol import EmbeddingProtocol
from sunwell.memory.simulacrum.core.retrieval.similarity import (
    bm25_score,
    normalize_bm25,
)

if TYPE_CHECKING:
    from sunwell.models import Tool

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ToolEmbeddingIndex:
    """Semantic index for tool retrieval using embeddings.

    Embeds tool names and descriptions, then uses hybrid search
    (semantic + keyword) to find relevant tools for a query.

    Features:
    - Lazy initialization (embeddings computed on first query)
    - Hybrid scoring (semantic + BM25 keyword matching)
    - Thread-safe with caching
    - Uses existing embedding infrastructure

    Attributes:
        embedder: Embedding provider (auto-detected if None)
        vector_weight: Weight for vector similarity vs BM25 (0.0-1.0)
        _index: Internal vector index
        _tool_texts: Cached tool description texts
        _initialized: Whether index has been built
    """

    embedder: EmbeddingProtocol | None = None
    vector_weight: float = 0.7  # 70% semantic, 30% BM25

    # Internal state
    _index: InMemoryIndex | None = field(default=None, init=False)
    _tool_texts: dict[str, str] = field(default_factory=dict, init=False)
    _initialized: bool = field(default=False, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def _get_embedder(self) -> EmbeddingProtocol:
        """Get or create embedder instance."""
        if self.embedder is None:
            self.embedder = create_embedder(prefer_local=True, fallback=True)
        return self.embedder

    def _build_tool_text(self, tool: "Tool") -> str:
        """Build searchable text from tool definition.

        Combines name, description, and parameter names for rich matching.

        Args:
            tool: Tool definition

        Returns:
            Combined text for embedding
        """
        parts = [tool.name]

        # Add description if available
        description = getattr(tool, "description", None)
        if description:
            parts.append(description)

        # Add parameter names for better matching
        parameters = getattr(tool, "parameters", None)
        if parameters:
            props = parameters.get("properties", {})
            param_names = list(props.keys())
            if param_names:
                parts.append(f"Parameters: {', '.join(param_names)}")

        return " ".join(parts)

    async def _build_index(self, tools: "tuple[Tool, ...]") -> None:
        """Build the embedding index from tools.

        Args:
            tools: Available tool definitions
        """
        if not tools:
            return

        embedder = self._get_embedder()

        # Build text representations
        tool_names: list[str] = []
        tool_texts: list[str] = []

        for tool in tools:
            text = self._build_tool_text(tool)
            tool_names.append(tool.name)
            tool_texts.append(text)
            self._tool_texts[tool.name] = text

        # Embed all tools in batch
        try:
            result = await embedder.embed(tool_texts)
            vectors = result.vectors

            # Create index
            self._index = InMemoryIndex(_dimensions=result.dimensions)

            # Add all vectors
            metadata = [{"text": text} for text in tool_texts]
            self._index.add_batch(tool_names, vectors, metadata)

            logger.debug(
                "Built tool embedding index: %d tools, %d dimensions",
                len(tool_names),
                result.dimensions,
            )
        except Exception as e:
            logger.warning("Failed to build tool embedding index: %s", e)
            self._index = None

    def initialize(self, tools: "tuple[Tool, ...]") -> None:
        """Initialize the index with tools (synchronous wrapper).

        Thread-safe: Uses lock to prevent concurrent initialization.

        Args:
            tools: Available tool definitions
        """
        with self._lock:
            if self._initialized:
                return

            # Run async embedding in sync context
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Already in async context, create task
                    asyncio.create_task(self._build_index(tools))
                else:
                    loop.run_until_complete(self._build_index(tools))
            except RuntimeError:
                # No event loop, create new one
                asyncio.run(self._build_index(tools))

            self._initialized = True

    async def initialize_async(self, tools: "tuple[Tool, ...]") -> None:
        """Initialize the index with tools (async version).

        Thread-safe: Uses lock to prevent concurrent initialization.

        Args:
            tools: Available tool definitions
        """
        with self._lock:
            if self._initialized:
                return

            await self._build_index(tools)
            self._initialized = True

    async def get_semantic_scores(
        self,
        query: str,
        tool_names: frozenset[str],
        top_k: int = 20,
    ) -> dict[str, float]:
        """Get semantic relevance scores for tools.

        Uses hybrid search combining:
        - Semantic similarity (embedding cosine distance)
        - BM25 keyword matching

        Args:
            query: User query
            tool_names: Set of tool names to score
            top_k: Maximum number of tools to return scores for

        Returns:
            Dict mapping tool name to relevance score (0.0-1.0)
        """
        if not self._initialized or self._index is None:
            return {}

        if not query.strip():
            return {}

        embedder = self._get_embedder()

        try:
            # Embed query
            query_embedding = await embedder.embed_single(query)

            # Search index
            results = self._index.search(query_embedding, top_k=top_k)

            # Build scores with hybrid approach
            scores: dict[str, float] = {}

            for result in results:
                if result.id not in tool_names:
                    continue

                # Get tool text for BM25
                tool_text = self._tool_texts.get(result.id, result.id)

                # Compute BM25 component
                bm25 = bm25_score(query, tool_text, avg_doc_length=50.0)
                bm25_norm = normalize_bm25(bm25, max_score=5.0)

                # Combine vector similarity with BM25
                # result.score is already cosine similarity (0-1)
                vector_score = max(0.0, result.score)
                hybrid = self.vector_weight * vector_score + (1 - self.vector_weight) * bm25_norm

                scores[result.id] = hybrid

            return scores

        except Exception as e:
            logger.warning("Semantic tool search failed: %s", e)
            return {}

    def get_semantic_scores_sync(
        self,
        query: str,
        tool_names: frozenset[str],
        top_k: int = 20,
    ) -> dict[str, float]:
        """Synchronous wrapper for get_semantic_scores.

        Args:
            query: User query
            tool_names: Set of tool names to score
            top_k: Maximum number of tools to return scores for

        Returns:
            Dict mapping tool name to relevance score (0.0-1.0)
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Can't run sync in async context easily
                # Return empty scores (semantic scoring disabled)
                return {}
            return loop.run_until_complete(
                self.get_semantic_scores(query, tool_names, top_k)
            )
        except RuntimeError:
            return asyncio.run(self.get_semantic_scores(query, tool_names, top_k))

    def boost_by_semantic_relevance(
        self,
        ranked_tools: list[str],
        semantic_scores: dict[str, float],
        boost_threshold: float = 0.3,
        boost_weight: int = 40,
    ) -> list[str]:
        """Re-rank tools by combining existing rank with semantic scores.

        Tools with high semantic relevance get boosted in the ranking.

        Args:
            ranked_tools: Tools in current rank order
            semantic_scores: Semantic relevance scores per tool
            boost_threshold: Minimum score to apply boost
            boost_weight: Score points to add for semantic match

        Returns:
            Re-ranked tool list
        """
        if not semantic_scores:
            return ranked_tools

        # Assign position-based scores (higher position = lower score)
        scored: list[tuple[float, str]] = []

        for i, tool in enumerate(ranked_tools):
            # Base score from position (inverse rank)
            base_score = len(ranked_tools) - i

            # Add semantic boost if above threshold
            semantic = semantic_scores.get(tool, 0.0)
            if semantic >= boost_threshold:
                # Scale boost by semantic score
                boost = boost_weight * semantic
                base_score += boost

            scored.append((base_score, tool))

        # Sort by combined score descending
        scored.sort(key=lambda x: (-x[0], x[1]))

        return [tool for _, tool in scored]

    def reset(self) -> None:
        """Reset the index (call if tools change)."""
        with self._lock:
            self._index = None
            self._tool_texts.clear()
            self._initialized = False
