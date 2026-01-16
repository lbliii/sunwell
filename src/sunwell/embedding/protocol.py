"""Embedding protocol for vector operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence, runtime_checkable

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class EmbeddingResult:
    """Result from embedding operation."""

    vectors: NDArray[np.float32]  # Shape: (n_texts, embedding_dim)
    model: str
    dimensions: int


@runtime_checkable
class EmbeddingProtocol(Protocol):
    """Protocol for embedding providers.

    Implementations: OpenAI, local sentence-transformers, etc.
    """

    @property
    def dimensions(self) -> int:
        """The embedding dimensions."""
        ...

    async def embed(
        self,
        texts: Sequence[str],
    ) -> EmbeddingResult:
        """Embed one or more texts."""
        ...

    async def embed_single(self, text: str) -> NDArray[np.float32]:
        """Embed a single text. Convenience method."""
        ...


@dataclass(frozen=True, slots=True)
class SearchResult:
    """A single search result from vector index."""

    id: str
    score: float
    metadata: dict


@runtime_checkable
class VectorIndexProtocol(Protocol):
    """Protocol for vector index backends.

    Implementations:
    - InMemoryIndex: NumPy-based, for development/small lenses
    - FAISSIndex: For large-scale production
    """

    @property
    def dimensions(self) -> int:
        """The embedding dimensions this index was built for."""
        ...

    @property
    def count(self) -> int:
        """Number of vectors in the index."""
        ...

    def add(
        self,
        id: str,
        vector: NDArray[np.float32],
        metadata: dict | None = None,
    ) -> None:
        """Add a single vector to the index."""
        ...

    def add_batch(
        self,
        ids: Sequence[str],
        vectors: NDArray[np.float32],
        metadata: Sequence[dict] | None = None,
    ) -> None:
        """Add multiple vectors to the index."""
        ...

    def search(
        self,
        query_vector: NDArray[np.float32],
        top_k: int = 5,
        threshold: float | None = None,
    ) -> list[SearchResult]:
        """Search for similar vectors."""
        ...

    def delete(self, id: str) -> bool:
        """Delete a vector by ID. Returns True if found and deleted."""
        ...

    def clear(self) -> None:
        """Remove all vectors from the index."""
        ...
