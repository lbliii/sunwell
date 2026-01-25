"""Simple embedding implementations that don't require external APIs."""

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from sunwell.embedding.protocol import EmbeddingResult

# Pre-compiled regex for tokenization (avoid per-call compilation)
_WORD_PATTERN = re.compile(r"\b\w+\b")


@dataclass(slots=True)
class HashEmbedding:
    """Simple hash-based embedding for testing/development.

    NOT suitable for production - uses deterministic hashing
    to create pseudo-embeddings. Good for testing the retrieval
    pipeline without API costs.
    """

    _dimensions: int = 384

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed(
        self,
        texts: Sequence[str],
    ) -> EmbeddingResult:
        """Create hash-based embeddings."""
        vectors = np.zeros((len(texts), self._dimensions), dtype=np.float32)

        for i, text in enumerate(texts):
            vectors[i] = self._hash_to_vector(text)

        return EmbeddingResult(
            vectors=vectors,
            model="hash-embedding",
            dimensions=self._dimensions,
        )

    async def embed_single(self, text: str) -> NDArray[np.float32]:
        """Embed a single text."""
        return self._hash_to_vector(text)

    def _hash_to_vector(self, text: str) -> NDArray[np.float32]:
        """Convert text to a deterministic pseudo-embedding."""
        # Create a seed from the text
        text_hash = hashlib.sha256(text.encode()).digest()

        # Use the hash bytes to seed a random generator
        seed = int.from_bytes(text_hash[:4], "big")
        rng = np.random.default_rng(seed)

        # Generate a pseudo-random vector
        vector = rng.standard_normal(self._dimensions).astype(np.float32)

        # Normalize
        vector = vector / (np.linalg.norm(vector) + 1e-10)

        return vector


@dataclass(slots=True)
class TFIDFEmbedding:
    """TF-IDF based embedding for simple semantic similarity.

    Better than hash embedding for actual semantic matching,
    but still doesn't require external APIs.
    """

    _dimensions: int = 384
    _vocab: dict[str, int] | None = None

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed(
        self,
        texts: Sequence[str],
    ) -> EmbeddingResult:
        """Create TF-IDF-ish embeddings."""
        # Build vocabulary from all texts
        all_words: set[str] = set()
        for text in texts:
            all_words.update(self._tokenize(text))

        vocab = {word: i % self._dimensions for i, word in enumerate(sorted(all_words))}

        vectors = np.zeros((len(texts), self._dimensions), dtype=np.float32)

        for i, text in enumerate(texts):
            vectors[i] = self._text_to_vector(text, vocab)

        return EmbeddingResult(
            vectors=vectors,
            model="tfidf-embedding",
            dimensions=self._dimensions,
        )

    async def embed_single(self, text: str) -> NDArray[np.float32]:
        """Embed a single text."""
        vocab = {word: i % self._dimensions for i, word in enumerate(self._tokenize(text))}
        return self._text_to_vector(text, vocab)

    def _tokenize(self, text: str) -> list[str]:
        """Simple tokenization."""
        return _WORD_PATTERN.findall(text.lower())

    def _text_to_vector(self, text: str, vocab: dict[str, int]) -> NDArray[np.float32]:
        """Convert text to vector using vocabulary."""
        vector = np.zeros(self._dimensions, dtype=np.float32)
        words = self._tokenize(text)

        for word in words:
            if word in vocab:
                idx = vocab[word]
                vector[idx] += 1

        # Normalize
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm

        return vector
