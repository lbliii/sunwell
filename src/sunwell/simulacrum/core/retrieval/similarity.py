"""Similarity utilities for semantic retrieval."""


def cosine_similarity(
    a: tuple[float, ...],
    b: tuple[float, ...],
) -> float:
    """Compute cosine similarity between two vectors.

    Args:
        a: First vector
        b: Second vector

    Returns:
        Similarity score between 0.0 and 1.0
    """
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def keyword_similarity(query: str, fact: str) -> float:
    """Keyword-based similarity fallback when embeddings unavailable.

    Args:
        query: Query string
        fact: Fact string to match against

    Returns:
        Similarity score between 0.0 and 1.0
    """
    query_words = set(query.lower().split())
    fact_words = set(fact.lower().split())
    overlap = len(query_words & fact_words)
    if not query_words:
        return 0.0
    return overlap / len(query_words)
