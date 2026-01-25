"""Embedding and vector search for expertise retrieval."""

from sunwell.embedding.index import InMemoryIndex, SearchResult
from sunwell.embedding.ollama import MODEL_DIMENSIONS, OllamaEmbedding
from sunwell.embedding.protocol import EmbeddingProtocol, EmbeddingResult
from sunwell.embedding.simple import HashEmbedding, TFIDFEmbedding

__all__ = [
    "EmbeddingProtocol",
    "EmbeddingResult",
    "InMemoryIndex",
    "SearchResult",
    "HashEmbedding",
    "TFIDFEmbedding",
    "OllamaEmbedding",
    "create_embedder",
]


def create_embedder(
    prefer_local: bool = True,
    fallback: bool = True,
) -> EmbeddingProtocol:
    """Create the best available embedder.

    Checks for local Ollama embedding models first, falls back to HashEmbedding
    for development/testing if none available.

    Args:
        prefer_local: If True, prefer Ollama over cloud APIs (default: True)
        fallback: If True, fall back to HashEmbedding when nothing else available

    Returns:
        An embedder implementing EmbeddingProtocol.

    Raises:
        RuntimeError: If no embedder available and fallback=False.

    Usage:
        embedder = create_embedder()  # Auto-detects best option
        result = await embedder.embed(["hello world"])
    """
    if prefer_local:
        ollama_model = _detect_ollama_embedding_model()
        if ollama_model:
            return OllamaEmbedding(model=ollama_model)

    if fallback:
        return HashEmbedding()

    raise RuntimeError(
        "No embedding provider available. "
        "Install an embedding model: ollama pull all-minilm"
    )


def _detect_ollama_embedding_model() -> str | None:
    """Check if Ollama is running and has an embedding model.

    Returns:
        Model name if available, None otherwise.
    """
    try:
        import httpx

        response = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
        if response.status_code != 200:
            return None

        models = response.json().get("models", [])

        # Check for embedding models in preference order
        for model in models:
            name = model.get("name", "")
            # Check if any known embedding model matches
            for em in MODEL_DIMENSIONS:
                if em in name:
                    return name
        return None
    except Exception:
        return None
