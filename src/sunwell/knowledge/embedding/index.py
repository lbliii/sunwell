"""In-memory vector index implementation."""

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from sunwell.knowledge.embedding.protocol import SearchResult


@dataclass(slots=True)
class InMemoryIndex:
    """Simple in-memory vector index using NumPy.

    Best for:
    - Development and testing
    - Small lenses (< 1000 components)
    - Scenarios where persistence isn't critical

    For production with larger lenses, consider FAISS.

    Performance notes:
    - Vectors stored in list, materialized to array lazily on search (O(n) add, not O(n²))
    - O(1) id lookups via _id_to_idx mapping
    """

    _dimensions: int

    # Pending vectors (list-based for O(1) append)
    _vectors_list: list[NDArray[np.float32]] = field(default_factory=list, init=False)
    # Materialized array (built lazily on search)
    _vectors_array: NDArray[np.float32] | None = field(default=None, init=False)
    # Dirty flag for lazy materialization
    _dirty: bool = field(default=False, init=False)
    # Core data
    _ids: list[str] = field(default_factory=list, init=False)
    _metadata: list[dict] = field(default_factory=list, init=False)
    # O(1) id→index lookup
    _id_to_idx: dict[str, int] = field(default_factory=dict, init=False)

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @property
    def count(self) -> int:
        return len(self._ids)

    def _materialize(self) -> None:
        """Build the contiguous array from pending vectors if dirty."""
        if not self._dirty:
            return
        if self._vectors_list:
            self._vectors_array = np.vstack(self._vectors_list)
        else:
            self._vectors_array = None
        self._dirty = False

    def add(
        self,
        id: str,
        vector: NDArray[np.float32],
        metadata: dict | None = None,
    ) -> None:
        """Add a single vector to the index."""
        if vector.shape[0] != self._dimensions:
            raise ValueError(f"Expected {self._dimensions} dims, got {vector.shape[0]}")

        self._id_to_idx[id] = len(self._ids)
        self._ids.append(id)
        self._metadata.append(metadata or {})
        self._vectors_list.append(vector.reshape(1, -1))
        self._dirty = True

    def add_batch(
        self,
        ids: Sequence[str],
        vectors: NDArray[np.float32],
        metadata: Sequence[dict] | None = None,
    ) -> None:
        """Add multiple vectors to the index."""
        if vectors.shape[1] != self._dimensions:
            raise ValueError(f"Expected {self._dimensions} dims, got {vectors.shape[1]}")

        start_idx = len(self._ids)
        for i, id_ in enumerate(ids):
            self._id_to_idx[id_] = start_idx + i

        self._ids.extend(ids)
        self._metadata.extend(metadata or [{} for _ in ids])
        self._vectors_list.append(vectors)
        self._dirty = True

    def search(
        self,
        query_vector: NDArray[np.float32],
        top_k: int = 5,
        threshold: float | None = None,
    ) -> list[SearchResult]:
        """Search for similar vectors using cosine similarity."""
        if len(self._ids) == 0:
            return []

        # Materialize array if needed
        self._materialize()
        if self._vectors_array is None:
            return []

        # Normalize for cosine similarity
        query_norm = query_vector / (np.linalg.norm(query_vector) + 1e-10)
        norms = np.linalg.norm(self._vectors_array, axis=1, keepdims=True) + 1e-10
        vectors_norm = self._vectors_array / norms

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
        """Delete a vector by ID. O(1) lookup, O(n) compaction."""
        idx = self._id_to_idx.pop(id, None)
        if idx is None:
            return False

        # Remove from lists
        self._ids.pop(idx)
        self._metadata.pop(idx)

        # Update indices for all items after the deleted one
        for id_, i in self._id_to_idx.items():
            if i > idx:
                self._id_to_idx[id_] = i - 1

        # Materialize and delete from array
        self._materialize()
        if self._vectors_array is not None:
            self._vectors_array = np.delete(self._vectors_array, idx, axis=0)
            if len(self._vectors_array) == 0:
                self._vectors_array = None
            # Rebuild vectors_list from array
            if self._vectors_array is not None:
                self._vectors_list = [self._vectors_array]
            else:
                self._vectors_list = []
            self._dirty = False

        return True

    def clear(self) -> None:
        """Remove all vectors from the index."""
        self._vectors_array = None
        self._vectors_list.clear()
        self._dirty = False
        self._ids.clear()
        self._metadata.clear()
        self._id_to_idx.clear()

    def save(self, path: str | Path) -> None:
        """Persist the index to disk."""
        p = Path(path)
        p.mkdir(parents=True, exist_ok=True)

        # Materialize before saving
        self._materialize()
        if self._vectors_array is not None:
            np.save(p / "vectors.npy", self._vectors_array)

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
        # Rebuild id→index mapping
        index._id_to_idx = {id_: i for i, id_ in enumerate(index._ids)}

        vectors_path = p / "vectors.npy"
        if vectors_path.exists():
            index._vectors_array = np.load(vectors_path)
            index._vectors_list = [index._vectors_array]
            index._dirty = False

        return index
