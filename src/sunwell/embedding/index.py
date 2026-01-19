"""In-memory vector index implementation."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from sunwell.embedding.protocol import SearchResult


@dataclass
class InMemoryIndex:
    """Simple in-memory vector index using NumPy.

    Best for:
    - Development and testing
    - Small lenses (< 1000 components)
    - Scenarios where persistence isn't critical

    For production with larger lenses, consider FAISS.
    """

    _dimensions: int

    _vectors: NDArray[np.float32] | None = field(default=None, init=False)
    _ids: list[str] = field(default_factory=list, init=False)
    _metadata: list[dict] = field(default_factory=list, init=False)

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @property
    def count(self) -> int:
        return len(self._ids)

    def add(
        self,
        id: str,
        vector: NDArray[np.float32],
        metadata: dict | None = None,
    ) -> None:
        """Add a single vector to the index."""
        if vector.shape[0] != self._dimensions:
            raise ValueError(f"Expected {self._dimensions} dims, got {vector.shape[0]}")

        if self._vectors is None:
            self._vectors = vector.reshape(1, -1)
        else:
            self._vectors = np.vstack([self._vectors, vector])

        self._ids.append(id)
        self._metadata.append(metadata or {})

    def add_batch(
        self,
        ids: Sequence[str],
        vectors: NDArray[np.float32],
        metadata: Sequence[dict] | None = None,
    ) -> None:
        """Add multiple vectors to the index."""
        if vectors.shape[1] != self._dimensions:
            raise ValueError(f"Expected {self._dimensions} dims, got {vectors.shape[1]}")

        if self._vectors is None:
            self._vectors = vectors
        else:
            self._vectors = np.vstack([self._vectors, vectors])

        self._ids.extend(ids)
        self._metadata.extend(metadata or [{} for _ in ids])

    def search(
        self,
        query_vector: NDArray[np.float32],
        top_k: int = 5,
        threshold: float | None = None,
    ) -> list[SearchResult]:
        """Search for similar vectors using cosine similarity."""
        if self._vectors is None or len(self._ids) == 0:
            return []

        # Normalize for cosine similarity
        query_norm = query_vector / (np.linalg.norm(query_vector) + 1e-10)
        norms = np.linalg.norm(self._vectors, axis=1, keepdims=True) + 1e-10
        vectors_norm = self._vectors / norms

        # Compute similarities
        similarities = np.dot(vectors_norm, query_norm)

        # Get top-k indices
        if threshold is not None:
            mask = similarities >= threshold
            indices = np.where(mask)[0]
            if len(indices) == 0:
                return []
            # Sort by similarity descending, take top_k
            sorted_idx = np.argsort(similarities[indices])[::-1][:top_k]
            indices = indices[sorted_idx]
        else:
            indices = np.argsort(similarities)[::-1][:top_k]

        return [
            SearchResult(
                id=self._ids[i],
                score=float(similarities[i]),
                metadata=self._metadata[i],
            )
            for i in indices
        ]

    def delete(self, id: str) -> bool:
        """Delete a vector by ID."""
        try:
            idx = self._ids.index(id)
            self._ids.pop(idx)
            self._metadata.pop(idx)
            if self._vectors is not None:
                self._vectors = np.delete(self._vectors, idx, axis=0)
                if len(self._vectors) == 0:
                    self._vectors = None
            return True
        except ValueError:
            return False

    def clear(self) -> None:
        """Remove all vectors from the index."""
        self._vectors = None
        self._ids.clear()
        self._metadata.clear()

    def save(self, path: str | Path) -> None:
        """Persist the index to disk."""
        p = Path(path)
        p.mkdir(parents=True, exist_ok=True)

        if self._vectors is not None:
            np.save(p / "vectors.npy", self._vectors)

        with open(p / "metadata.json", "w") as f:
            json.dump(
                {"ids": self._ids, "metadata": self._metadata, "dims": self._dimensions},
                f,
            )

    @classmethod
    def load(cls, path: str | Path) -> InMemoryIndex:
        """Load an index from disk."""
        p = Path(path)

        with open(p / "metadata.json") as f:
            data = json.load(f)

        index = cls(_dimensions=data["dims"])
        index._ids = data["ids"]
        index._metadata = data["metadata"]

        vectors_path = p / "vectors.npy"
        if vectors_path.exists():
            index._vectors = np.load(vectors_path)

        return index
