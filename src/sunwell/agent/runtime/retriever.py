"""Expertise retriever for semantic search over lens heuristics."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.core.models.heuristic import Heuristic
    from sunwell.foundation.core.lens import Lens
    from sunwell.knowledge.embedding.protocol import EmbeddingProtocol


@dataclass(slots=True)
class ExpertiseRetriever:
    """Retrieves relevant heuristics from a lens using semantic search.
    
    Uses embeddings to find heuristics that match a query semantically,
    enabling on-demand expertise retrieval during agent execution.
    """

    lens: Lens
    embedder: EmbeddingProtocol
    top_k: int = 5

    _initialized: bool = field(default=False, init=False)
    _heuristic_embeddings: dict[str, list[float]] = field(default_factory=dict, init=False)

    async def initialize(self) -> None:
        """Pre-compute embeddings for all heuristics in the lens."""
        if self._initialized:
            return

        # Embed all heuristics
        heuristic_texts = []
        heuristic_names = []

        for heuristic in self.lens.heuristics:
            # Create searchable text from heuristic
            text_parts = [heuristic.name]
            if heuristic.description:
                text_parts.append(heuristic.description)
            if heuristic.examples:
                text_parts.extend(heuristic.examples)

            text = "\n".join(text_parts)
            heuristic_texts.append(text)
            heuristic_names.append(heuristic.name)

        if heuristic_texts:
            # Batch embed all heuristics
            results = await self.embedder.embed(heuristic_texts)
            for name, embedding in zip(heuristic_names, results.embeddings):
                self._heuristic_embeddings[name] = embedding

        self._initialized = True

    async def retrieve(self, query: str) -> list[Heuristic]:
        """Retrieve top-k most relevant heuristics for a query.
        
        Args:
            query: Search query
            
        Returns:
            List of heuristics ordered by relevance (most relevant first)
        """
        if not self._initialized:
            await self.initialize()

        if not self.lens.heuristics:
            return []

        # Embed the query
        query_result = await self.embedder.embed([query])
        if not query_result.embeddings:
            return []

        query_embedding = query_result.embeddings[0]

        # Compute similarity scores
        scores: list[tuple[float, Heuristic]] = []

        for heuristic in self.lens.heuristics:
            if heuristic.name not in self._heuristic_embeddings:
                continue

            heuristic_embedding = self._heuristic_embeddings[heuristic.name]

            # Cosine similarity
            similarity = self._cosine_similarity(query_embedding, heuristic_embedding)
            scores.append((similarity, heuristic))

        # Sort by similarity (descending) and return top-k
        scores.sort(key=lambda x: x[0], reverse=True)
        return [heuristic for _, heuristic in scores[:self.top_k]]

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if len(a) != len(b):
            return 0.0

        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5

        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0

        return dot_product / (norm_a * norm_b)
