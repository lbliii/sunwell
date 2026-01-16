"""RAG over expertise graph - retrieves relevant lens components."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sunwell.core.lens import Lens
from sunwell.core.heuristic import Heuristic
from sunwell.core.persona import Persona
from sunwell.core.validator import HeuristicValidator
from sunwell.embedding.protocol import EmbeddingProtocol
from sunwell.embedding.index import InMemoryIndex

if TYPE_CHECKING:
    from sunwell.routing.cognitive_router import RoutingDecision


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    """Result from expertise retrieval."""

    heuristics: tuple[Heuristic, ...]
    personas: tuple[Persona, ...]
    validators: tuple[HeuristicValidator, ...]
    relevance_scores: dict[str, float]  # component_name → score


@dataclass
class ExpertiseRetriever:
    """RAG over the expertise graph.

    On lens load:
    1. Embed each component's description and triggers
    2. Build vector index

    On query:
    1. Embed the task prompt
    2. Retrieve top-k relevant components
    3. Return selected heuristics, validators, personas
    """

    lens: Lens
    embedder: EmbeddingProtocol
    top_k: int = 5
    relevance_threshold: float = 0.3

    _index: InMemoryIndex | None = field(default=None, init=False)
    _component_map: dict[str, object] = field(default_factory=dict, init=False)
    _initialized: bool = field(default=False, init=False)

    async def initialize(self) -> None:
        """Build the vector index from lens components."""
        # Collect all embeddable components
        components: list[tuple[str, str, object]] = []  # (id, text, obj)

        # Heuristics
        for h in self.lens.heuristics:
            text = h.to_embedding_text()
            components.append((f"heuristic:{h.name}", text, h))

        # Personas
        for p in self.lens.personas:
            text = p.to_embedding_text()
            components.append((f"persona:{p.name}", text, p))

        # Heuristic validators
        for v in self.lens.heuristic_validators:
            text = v.to_embedding_text()
            components.append((f"validator:{v.name}", text, v))

        if not components:
            self._initialized = True
            return

        # Embed all components
        texts = [text for _, text, _ in components]
        embeddings = await self.embedder.embed(texts)

        # Build index
        self._index = InMemoryIndex(_dimensions=self.embedder.dimensions)

        ids = [id for id, _, _ in components]
        metadata = [{"type": id.split(":")[0]} for id in ids]

        self._index.add_batch(ids, embeddings.vectors, metadata)

        # Build component map for retrieval
        for id, _, obj in components:
            self._component_map[id] = obj

        self._initialized = True

    async def retrieve(
        self,
        query: str,
        *,
        top_k: int | None = None,
    ) -> RetrievalResult:
        """Retrieve relevant components for a query."""
        if not self._initialized:
            await self.initialize()

        if not self._index or self._index.count == 0:
            # No index, return all heuristics (fallback)
            return RetrievalResult(
                heuristics=self.lens.heuristics,
                personas=(),
                validators=(),
                relevance_scores={},
            )

        # Embed query
        query_embedding = await self.embedder.embed_single(query)

        # Search
        k = top_k or self.top_k
        results = self._index.search(
            query_embedding,
            top_k=k,
            threshold=self.relevance_threshold,
        )

        # Categorize results
        heuristics: list[Heuristic] = []
        personas: list[Persona] = []
        validators: list[HeuristicValidator] = []
        scores: dict[str, float] = {}

        for result in results:
            component = self._component_map.get(result.id)
            if component is None:
                continue

            scores[result.id] = result.score

            if result.id.startswith("heuristic:"):
                heuristics.append(component)  # type: ignore
            elif result.id.startswith("persona:"):
                personas.append(component)  # type: ignore
            elif result.id.startswith("validator:"):
                validators.append(component)  # type: ignore

        return RetrievalResult(
            heuristics=tuple(heuristics),
            personas=tuple(personas),
            validators=tuple(validators),
            relevance_scores=scores,
        )

    async def retrieve_with_routing(
        self,
        query: str,
        routing: "RoutingDecision",
    ) -> RetrievalResult:
        """Retrieve with routing hints from CognitiveRouter (RFC-020).
        
        The routing decision provides:
        - focus: Terms to boost in the query for better relevance
        - top_k: Adjusted retrieval count based on task complexity
        - threshold: Adjusted relevance threshold
        
        Args:
            query: The original task/query
            routing: RoutingDecision from CognitiveRouter
            
        Returns:
            RetrievalResult with routing-optimized heuristics
        """
        # Boost query with focus terms
        focus_str = " ".join(routing.focus) if routing.focus else ""
        boosted_query = f"{query} {focus_str}".strip()
        
        # Use routing-adjusted parameters
        return await self.retrieve(
            boosted_query,
            top_k=routing.top_k,
        )
    
    def get_stats(self) -> dict:
        """Get retriever statistics."""
        return {
            "initialized": self._initialized,
            "index_size": self._index.count if self._index else 0,
            "heuristic_count": len(self.lens.heuristics),
            "persona_count": len(self.lens.personas),
            "validator_count": len(self.lens.heuristic_validators),
        }
