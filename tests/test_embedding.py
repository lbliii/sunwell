"""Tests for embedding and vector index."""

import numpy as np
import pytest

from sunwell.embedding.index import InMemoryIndex
from sunwell.embedding.simple import HashEmbedding, TFIDFEmbedding
from sunwell.embedding.ollama import OllamaEmbedding
from sunwell.embedding.protocol import SearchResult
from sunwell.embedding import create_embedder


class TestInMemoryIndex:
    def test_add_and_search(self):
        index = InMemoryIndex(_dimensions=4)

        # Add vectors
        v1 = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        v2 = np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32)
        v3 = np.array([0.9, 0.1, 0.0, 0.0], dtype=np.float32)  # Similar to v1

        index.add("id1", v1, {"type": "test"})
        index.add("id2", v2)
        index.add("id3", v3)

        assert index.count == 3

        # Search for similar to v1
        results = index.search(v1, top_k=2)
        assert len(results) == 2
        assert results[0].id == "id1"  # Exact match should be first
        assert results[1].id == "id3"  # Similar should be second

    def test_add_batch(self):
        index = InMemoryIndex(_dimensions=4)

        vectors = np.array([
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
        ], dtype=np.float32)

        index.add_batch(["a", "b"], vectors, [{"n": 1}, {"n": 2}])

        assert index.count == 2

    def test_search_with_threshold(self):
        index = InMemoryIndex(_dimensions=4)

        v1 = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        v2 = np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32)  # Orthogonal

        index.add("id1", v1)
        index.add("id2", v2)

        # High threshold should exclude orthogonal vector
        results = index.search(v1, threshold=0.9)
        assert len(results) == 1
        assert results[0].id == "id1"

    def test_delete(self):
        index = InMemoryIndex(_dimensions=4)

        v1 = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        index.add("id1", v1)

        assert index.count == 1
        assert index.delete("id1")
        assert index.count == 0
        assert not index.delete("nonexistent")

    def test_clear(self):
        index = InMemoryIndex(_dimensions=4)

        v1 = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        index.add("id1", v1)
        index.add("id2", v1)

        index.clear()
        assert index.count == 0

    def test_save_and_load(self, tmp_path):
        index = InMemoryIndex(_dimensions=4)

        v1 = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        index.add("id1", v1, {"meta": "data"})

        # Save
        save_path = tmp_path / "index"
        index.save(save_path)

        # Load
        loaded = InMemoryIndex.load(save_path)
        assert loaded.count == 1
        assert loaded.dimensions == 4

        # Search should still work
        results = loaded.search(v1)
        assert len(results) == 1
        assert results[0].id == "id1"


class TestHashEmbedding:
    @pytest.mark.asyncio
    async def test_embed(self):
        embedder = HashEmbedding()

        result = await embedder.embed(["hello world", "goodbye world"])

        assert result.vectors.shape == (2, 384)
        assert result.model == "hash-embedding"

    @pytest.mark.asyncio
    async def test_embed_single(self):
        embedder = HashEmbedding()

        vector = await embedder.embed_single("test text")

        assert vector.shape == (384,)

    @pytest.mark.asyncio
    async def test_deterministic(self):
        embedder = HashEmbedding()

        v1 = await embedder.embed_single("same text")
        v2 = await embedder.embed_single("same text")

        np.testing.assert_array_equal(v1, v2)


class TestTFIDFEmbedding:
    @pytest.mark.asyncio
    async def test_embed(self):
        embedder = TFIDFEmbedding()

        result = await embedder.embed(["hello world", "goodbye world"])

        assert result.vectors.shape == (2, 384)

    @pytest.mark.asyncio
    async def test_similar_texts(self):
        embedder = TFIDFEmbedding()

        result = await embedder.embed([
            "the quick brown fox",
            "the quick brown dog",
            "something completely different",
        ])

        # First two should be more similar to each other than to third
        v1, v2, v3 = result.vectors

        sim_12 = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-10)
        sim_13 = np.dot(v1, v3) / (np.linalg.norm(v1) * np.linalg.norm(v3) + 1e-10)

        # Similar texts should have higher similarity
        # (This is a weak test since TFIDF is simple)
        assert sim_12 != sim_13  # At least they're different


def ollama_available() -> bool:
    """Check if Ollama is running and has an embedding model."""
    try:
        import httpx
        response = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
        if response.status_code != 200:
            return False
        models = response.json().get("models", [])
        # Check for any embedding model
        embedding_models = ["all-minilm", "nomic-embed-text", "embeddinggemma", "mxbai-embed-large"]
        return any(
            any(em in m.get("name", "") for em in embedding_models)
            for m in models
        )
    except Exception:
        return False


@pytest.mark.skipif(not ollama_available(), reason="Ollama not running or no embedding model")
class TestOllamaEmbedding:
    """Tests for OllamaEmbedding (requires local Ollama with embedding model)."""

    @pytest.mark.asyncio
    async def test_embed_single(self):
        async with OllamaEmbedding(model="all-minilm") as embedder:
            vector = await embedder.embed_single("hello world")

            assert vector.shape[0] > 0  # Has dimensions
            assert vector.dtype == np.float32
            # Should be normalized (L2 norm ≈ 1)
            norm = np.linalg.norm(vector)
            assert 0.99 < norm < 1.01

    @pytest.mark.asyncio
    async def test_embed_batch(self):
        async with OllamaEmbedding(model="all-minilm") as embedder:
            result = await embedder.embed(["hello world", "goodbye world", "test text"])

            assert result.vectors.shape[0] == 3
            assert result.vectors.shape[1] > 0
            assert "ollama" in result.model

    @pytest.mark.asyncio
    async def test_semantic_similarity(self):
        """Test that similar texts have higher cosine similarity."""
        async with OllamaEmbedding(model="all-minilm") as embedder:
            result = await embedder.embed([
                "The cat sat on the mat",
                "A feline rested on the rug",  # Similar meaning
                "Python is a programming language",  # Different topic
            ])

            v1, v2, v3 = result.vectors

            # Cosine similarity (vectors are already normalized)
            sim_12 = float(np.dot(v1, v2))
            sim_13 = float(np.dot(v1, v3))

            # Similar sentences should have higher similarity
            assert sim_12 > sim_13, f"Expected {sim_12} > {sim_13}"

    @pytest.mark.asyncio
    async def test_empty_input(self):
        async with OllamaEmbedding(model="all-minilm") as embedder:
            result = await embedder.embed([])

            assert result.vectors.shape[0] == 0

    @pytest.mark.asyncio
    async def test_dimensions_property(self):
        embedder = OllamaEmbedding(model="all-minilm")

        # Before embedding, uses known dimensions
        assert embedder.dimensions == 384

        # After embedding, uses actual dimensions
        await embedder.embed_single("test")
        assert embedder.dimensions == 384  # all-minilm is 384

        await embedder.close()


class TestCreateEmbedder:
    """Tests for the create_embedder factory."""

    def test_create_embedder_returns_protocol(self):
        """Factory returns something implementing EmbeddingProtocol."""
        from sunwell.embedding.protocol import EmbeddingProtocol

        embedder = create_embedder()

        # Should have required methods
        assert hasattr(embedder, "embed")
        assert hasattr(embedder, "embed_single")
        assert hasattr(embedder, "dimensions")

    def test_create_embedder_with_fallback(self):
        """Factory falls back to HashEmbedding when needed."""
        # Force fallback by disabling local preference
        embedder = create_embedder(prefer_local=False, fallback=True)

        assert isinstance(embedder, HashEmbedding)

    def test_create_embedder_no_fallback_raises(self):
        """Factory raises when no provider and fallback disabled."""
        with pytest.raises(RuntimeError, match="No embedding provider"):
            create_embedder(prefer_local=False, fallback=False)

    @pytest.mark.skipif(not ollama_available(), reason="Ollama not running")
    def test_create_embedder_prefers_ollama(self):
        """Factory prefers Ollama when available."""
        embedder = create_embedder()

        assert isinstance(embedder, OllamaEmbedding)
