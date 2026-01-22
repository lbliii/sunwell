"""Ollama embedding provider for local, free semantic embeddings.

Uses Ollama's native /api/embed endpoint (not OpenAI-compatible).
Requires: ollama serve running locally with an embedding model pulled.

Recommended models:
- all-minilm (384 dims, fast, good quality)
- embeddinggemma (768 dims, Google)
- qwen3-embedding (1024 dims, high quality)
"""


from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from sunwell.core.errors import ErrorCode, SunwellError
from sunwell.embedding.protocol import EmbeddingResult

if TYPE_CHECKING:
    import httpx

# Known embedding model dimensions (fallback if not auto-detected)
MODEL_DIMENSIONS: dict[str, int] = {
    "all-minilm": 384,
    "all-minilm:latest": 384,
    "all-minilm:l6-v2": 384,
    "nomic-embed-text": 768,
    "nomic-embed-text:latest": 768,
    "embeddinggemma": 768,
    "embeddinggemma:latest": 768,
    "mxbai-embed-large": 1024,
    "mxbai-embed-large:latest": 1024,
    "qwen3-embedding": 1024,
    "qwen3-embedding:latest": 1024,
}


@dataclass
class OllamaEmbedding:
    """Ollama embedding provider implementing EmbeddingProtocol.

    Provides local, free semantic embeddings using Ollama's embedding models.
    No API costs, runs entirely on your machine.

    Usage:
        embedder = OllamaEmbedding(model="all-minilm")
        result = await embedder.embed(["Hello world", "Another text"])
        # result.vectors shape: (2, 384)

    Requirements:
        - Ollama running: ollama serve
        - Model pulled: ollama pull all-minilm
    """

    model: str = "all-minilm"
    base_url: str = "http://localhost:11434"
    max_chars_per_text: int = 512  # Truncate long texts to ~128 tokens (safer for small models)
    max_batch_chars: int = 4000  # Batch if total chars exceed this (conservative)
    _dimensions: int | None = field(default=None, init=False)
    _client: httpx.AsyncClient | None = field(default=None, init=False)

    @property
    def dimensions(self) -> int:
        """Return embedding dimensions for this model."""
        if self._dimensions is not None:
            return self._dimensions

        # Try known models first
        if self.model in MODEL_DIMENSIONS:
            return MODEL_DIMENSIONS[self.model]

        # Default fallback (will be corrected on first embed call)
        return 384

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            try:
                import httpx
            except ImportError as e:
                raise ImportError(
                    "httpx not installed. Run: pip install httpx"
                ) from e
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client

    async def embed(
        self,
        texts: Sequence[str],
    ) -> EmbeddingResult:
        """Embed one or more texts using Ollama.

        Args:
            texts: Sequence of strings to embed.

        Returns:
            EmbeddingResult with L2-normalized vectors.

        Raises:
            RuntimeError: If Ollama is not running or model not available.
        """
        if not texts:
            return EmbeddingResult(
                vectors=np.array([], dtype=np.float32).reshape(0, self.dimensions),
                model=f"ollama/{self.model}",
                dimensions=self.dimensions,
            )

        # Truncate long texts to fit model context window
        truncated = [
            t[:self.max_chars_per_text] if len(t) > self.max_chars_per_text else t
            for t in texts
        ]

        # Check if we need to batch
        total_chars = sum(len(t) for t in truncated)
        if total_chars > self.max_batch_chars:
            return await self._embed_batched(truncated)

        return await self._embed_single_batch(truncated)

    async def _embed_single_batch(
        self,
        texts: list[str],
    ) -> EmbeddingResult:
        """Embed a single batch of texts."""
        client = await self._get_client()

        # Ollama /api/embed accepts single string or array
        payload = {
            "model": self.model,
            "input": texts if len(texts) > 1 else texts[0],
        }

        response = await client.post(
            f"{self.base_url}/api/embed",
            json=payload,
        )

        if response.status_code != 200:
            # Capture actual error from Ollama
            try:
                error_body = response.json().get("error", response.text)
            except Exception:
                error_body = response.text

            raise SunwellError(
                code=ErrorCode.MODEL_PROVIDER_UNAVAILABLE,
                context={
                    "model": self.model,
                    "provider": "ollama",
                    "detail": f"Ollama error ({response.status_code}): {error_body}",
                    "num_texts": len(texts),
                },
            )

        data = response.json()
        embeddings = data.get("embeddings", [])

        if not embeddings:
            raise SunwellError(
                code=ErrorCode.MODEL_RESPONSE_INVALID,
                context={
                    "model": self.model,
                    "provider": "ollama",
                    "detail": f"No embeddings returned for model '{self.model}'",
                },
            )

        # Convert to numpy array
        vectors = np.array(embeddings, dtype=np.float32)

        # Handle single text case (Ollama returns nested array)
        if vectors.ndim == 1:
            vectors = vectors.reshape(1, -1)

        # Update dimensions from actual response
        self._dimensions = vectors.shape[1]

        return EmbeddingResult(
            vectors=vectors,
            model=f"ollama/{self.model}",
            dimensions=self._dimensions,
        )

    async def _embed_batched(
        self,
        texts: list[str],
    ) -> EmbeddingResult:
        """Embed texts in batches to avoid context length limits."""
        all_vectors = []
        batch: list[str] = []
        batch_chars = 0

        for text in texts:
            text_chars = len(text)

            # If adding this text would exceed limit, process current batch
            if batch and batch_chars + text_chars > self.max_batch_chars:
                result = await self._embed_single_batch(batch)
                all_vectors.append(result.vectors)
                batch = []
                batch_chars = 0

            batch.append(text)
            batch_chars += text_chars

        # Process final batch
        if batch:
            result = await self._embed_single_batch(batch)
            all_vectors.append(result.vectors)

        # Concatenate all vectors
        vectors = np.vstack(all_vectors)

        return EmbeddingResult(
            vectors=vectors,
            model=f"ollama/{self.model}",
            dimensions=vectors.shape[1],
        )

    async def embed_single(self, text: str) -> NDArray[np.float32]:
        """Embed a single text. Convenience method.

        Args:
            text: String to embed.

        Returns:
            1D numpy array of embedding values.
        """
        result = await self.embed([text])
        return result.vectors[0]

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> OllamaEmbedding:
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args) -> None:
        """Async context manager exit."""
        await self.close()
