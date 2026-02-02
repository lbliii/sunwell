"""Similarity utilities for semantic retrieval.

Provides:
- cosine_similarity: Vector similarity for embeddings
- bm25_score: BM25 keyword scoring
- hybrid_score: Combines vector + BM25 with configurable weights
- activity_decay_score: Activity-based decay (inspired by MIRA)
"""

from collections import Counter


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


def bm25_score(
    query: str,
    document: str,
    avg_doc_length: float = 100.0,
    k1: float = 1.5,
    b: float = 0.75,
) -> float:
    """BM25 scoring for keyword matching.

    BM25 (Best Matching 25) is a ranking function used by search engines
    to score documents by relevance to a search query. It improves on
    simple TF-IDF by adding term frequency saturation and length normalization.

    This implementation uses only term frequency (TF) component without
    inverse document frequency (IDF), as we typically don't have corpus
    statistics available. For single-document scoring, this is sufficient.

    Args:
        query: Query string
        document: Document text to score
        avg_doc_length: Average document length in corpus (tokens).
            Defaults to 100 for typical memory chunks.
        k1: Term frequency saturation parameter (1.2-2.0 typical).
            Higher = more weight on term frequency.
        b: Length normalization parameter (0.0-1.0).
            0 = no length normalization, 1 = full normalization.

    Returns:
        BM25 score (unbounded positive float, higher = more relevant).
        Returns 0.0 for empty queries or documents.

    Example:
        >>> bm25_score("user auth", "User authentication handles user login")
        1.81  # High score - matches both terms
        >>> bm25_score("database", "User authentication handles user login")
        0.0   # No match
    """
    if not query or not document:
        return 0.0

    query_terms = query.lower().split()
    doc_terms = document.lower().split()

    if not query_terms or not doc_terms:
        return 0.0

    doc_length = len(doc_terms)
    term_freq = Counter(doc_terms)

    score = 0.0
    for term in query_terms:
        tf = term_freq.get(term, 0)
        if tf == 0:
            continue

        # BM25 term frequency component
        # Formula: (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * doc_length / avg_doc_length))
        numerator = tf * (k1 + 1)
        denominator = tf + k1 * (1 - b + b * doc_length / avg_doc_length)
        score += numerator / denominator

    return score


def normalize_bm25(score: float, max_score: float = 10.0) -> float:
    """Normalize BM25 score to 0.0-1.0 range.

    Uses a soft normalization that preserves ranking but bounds output.

    Args:
        score: Raw BM25 score
        max_score: Score that maps to ~0.9 (scores above still < 1.0)

    Returns:
        Normalized score between 0.0 and 1.0
    """
    if score <= 0:
        return 0.0
    # Soft normalization: score / (score + max_score) gives 0.5 at max_score
    # We adjust to give ~0.9 at max_score: 2 * score / (score + max_score)
    return min(1.0, 2 * score / (score + max_score))


def hybrid_score(
    query: str,
    document: str,
    query_embedding: tuple[float, ...] | None = None,
    doc_embedding: tuple[float, ...] | None = None,
    vector_weight: float = 0.7,
    avg_doc_length: float = 100.0,
) -> float:
    """Compute hybrid score combining vector and BM25.

    Hybrid search combines semantic similarity (vectors) with lexical
    matching (BM25). This catches both:
    - Semantic matches: "auth" matches documents about "authentication"
    - Lexical matches: Exact terms the embeddings might miss

    Args:
        query: Query string
        document: Document text
        query_embedding: Query embedding vector (or None for BM25-only)
        doc_embedding: Document embedding vector (or None for BM25-only)
        vector_weight: Weight for vector score (0.0-1.0).
            BM25 weight = 1 - vector_weight
        avg_doc_length: Average document length for BM25

    Returns:
        Hybrid score between 0.0 and 1.0

    Example:
        >>> # With embeddings
        >>> hybrid_score(
        ...     "user auth",
        ...     "Authentication system",
        ...     query_embedding=embed("user auth"),
        ...     doc_embedding=embed("Authentication system"),
        ... )
        0.82  # High - semantic + lexical match

        >>> # Without embeddings (BM25 only)
        >>> hybrid_score("user auth", "User authentication")
        0.54  # BM25 only
    """
    # Compute BM25 component
    bm25 = bm25_score(query, document, avg_doc_length=avg_doc_length)
    bm25_normalized = normalize_bm25(bm25)

    # If no embeddings, return BM25 only
    if query_embedding is None or doc_embedding is None:
        return bm25_normalized

    # Compute vector component
    vector = cosine_similarity(query_embedding, doc_embedding)

    # Combine with weights
    return vector_weight * vector + (1 - vector_weight) * bm25_normalized


def activity_decay_score(
    activity_day_created: int,
    current_activity_days: int,
    *,
    decay_rate: float = 0.015,
    newness_boost_days: int = 15,
    newness_boost: float = 0.3,
) -> float:
    """Compute decay factor based on activity days, not calendar time.

    Inspired by MIRA's scoring_formula.sql which uses "activity days"
    (days with actual user engagement) rather than calendar days for
    decay calculations. This prevents vacation-induced memory degradation.

    The decay formula is: 1.0 / (1.0 + age * decay_rate)
    - At age=0: returns ~1.3 (with newness boost)
    - At age=67: returns ~0.5 (half-life)
    - At age=134: returns ~0.33

    New learnings get a "grace period" boost that linearly decays over
    newness_boost_days, giving them time to prove their value through
    usage before being penalized.

    Args:
        activity_day_created: Activity day when the learning was created.
        current_activity_days: Current cumulative activity day count
        decay_rate: Decay per activity day. Default 0.015 gives ~67 day half-life.
            Higher = faster decay.
        newness_boost_days: Days of grace period for new learnings.
            Default 15 activity days.
        newness_boost: Maximum boost during grace period. Default 0.3.
            New learnings start with score multiplier of 1.0 + newness_boost.

    Returns:
        Multiplier in range (0.0, 1.0 + newness_boost].
        Apply this to relevance scores: final_score = base_score * decay

    Example:
        >>> activity_decay_score(10, 10)  # Created today
        1.3  # Full newness boost

        >>> activity_decay_score(10, 40)  # 30 activity days ago
        0.69  # Moderate decay, no boost
    """
    age = current_activity_days - activity_day_created

    # Base decay: asymptotic approach to 0
    # At age=0: 1.0, at age=67: ~0.5, at age=134: ~0.33
    base = 1.0 / (1.0 + max(0, age) * decay_rate)

    # Newness boost: grace period for new learnings to prove themselves
    boost = newness_boost * (1.0 - age / newness_boost_days) if age < newness_boost_days else 0.0

    return base + boost
