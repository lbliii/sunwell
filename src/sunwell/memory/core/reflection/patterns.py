"""Pattern detection for reflection system.

Groups related learnings by theme using semantic similarity
and keyword clustering.

Part of Phase 3: Reflection System.
"""

import logging
from collections import defaultdict
from typing import TYPE_CHECKING

from sunwell.memory.core.reflection.types import PatternCluster

if TYPE_CHECKING:
    from sunwell.knowledge.embedding.protocol import EmbeddingProtocol
    from sunwell.memory.simulacrum.core.turn import Learning

logger = logging.getLogger(__name__)


class PatternDetector:
    """Detects patterns and clusters related learnings.

    Uses semantic similarity (if embeddings available) or
    keyword-based clustering to group related learnings.
    """

    def __init__(self, embedder: EmbeddingProtocol | None = None):
        """Initialize pattern detector.

        Args:
            embedder: Optional embedder for semantic clustering
        """
        self._embedder = embedder

    async def cluster_learnings(
        self,
        learnings: list[Learning],
        min_cluster_size: int = 3,
        similarity_threshold: float = 0.7,
    ) -> list[PatternCluster]:
        """Cluster learnings by theme.

        Args:
            learnings: List of learnings to cluster
            min_cluster_size: Minimum learnings per cluster
            similarity_threshold: Similarity threshold for clustering

        Returns:
            List of PatternCluster instances
        """
        if not learnings:
            return []

        # Try semantic clustering if embedder available
        if self._embedder:
            clusters = await self._semantic_clustering(
                learnings,
                similarity_threshold,
            )
        else:
            # Fall back to keyword clustering
            clusters = self._keyword_clustering(learnings)

        # Filter by minimum size
        return [c for c in clusters if len(c) >= min_cluster_size]

    async def _semantic_clustering(
        self,
        learnings: list[Learning],
        threshold: float,
    ) -> list[PatternCluster]:
        """Cluster learnings using semantic similarity.

        Uses a simple greedy clustering algorithm:
        1. Start with first learning as cluster seed
        2. Add similar learnings (cosine > threshold)
        3. Repeat with remaining learnings

        Args:
            learnings: List of learnings
            threshold: Similarity threshold

        Returns:
            List of clusters
        """
        from sunwell.memory.simulacrum.core.retrieval.similarity import cosine_similarity

        # Get embeddings for all learnings
        learning_embeddings = {}
        for learning in learnings:
            if learning.embedding:
                learning_embeddings[learning.id] = learning.embedding
            else:
                # Generate embedding if needed
                try:
                    emb = await self._embedder.embed([learning.fact])
                    learning_embeddings[learning.id] = tuple(emb[0])
                except Exception as e:
                    logger.debug(f"Failed to embed learning {learning.id}: {e}")

        # Greedy clustering
        clusters: list[PatternCluster] = []
        remaining = set(learning_embeddings.keys())

        while remaining:
            # Start new cluster with first remaining learning
            seed_id = next(iter(remaining))
            remaining.remove(seed_id)

            cluster = PatternCluster(
                theme="",  # Will be set later
                learning_ids=[seed_id],
            )

            seed_embedding = learning_embeddings[seed_id]

            # Find similar learnings
            for learning_id in list(remaining):
                learning_embedding = learning_embeddings[learning_id]
                similarity = cosine_similarity(seed_embedding, learning_embedding)

                if similarity >= threshold:
                    cluster.add_learning(learning_id)
                    remaining.remove(learning_id)

            # Extract theme from cluster (use most common words)
            cluster.theme = self._extract_theme_from_cluster(
                [l for l in learnings if l.id in cluster.learning_ids]
            )

            # Calculate coherence (average pairwise similarity)
            if len(cluster) > 1:
                similarities = []
                for i, id1 in enumerate(cluster.learning_ids):
                    for id2 in cluster.learning_ids[i + 1 :]:
                        sim = cosine_similarity(
                            learning_embeddings[id1],
                            learning_embeddings[id2],
                        )
                        similarities.append(sim)
                cluster.coherence_score = sum(similarities) / len(similarities) if similarities else 0.0
            else:
                cluster.coherence_score = 1.0

            clusters.append(cluster)

        return clusters

    def _keyword_clustering(self, learnings: list[Learning]) -> list[PatternCluster]:
        """Cluster learnings using keyword overlap.

        Simple heuristic clustering based on common keywords.

        Args:
            learnings: List of learnings

        Returns:
            List of clusters
        """
        # Extract keywords from each learning
        learning_keywords: dict[str, set[str]] = {}
        for learning in learnings:
            keywords = self._extract_keywords(learning.fact)
            learning_keywords[learning.id] = keywords

        # Group by common keywords
        keyword_to_learnings: dict[str, list[str]] = defaultdict(list)
        for learning_id, keywords in learning_keywords.items():
            for keyword in keywords:
                keyword_to_learnings[keyword].append(learning_id)

        # Create clusters from keyword groups
        clusters: list[PatternCluster] = []
        processed = set()

        # Sort keywords by frequency
        sorted_keywords = sorted(
            keyword_to_learnings.items(),
            key=lambda x: len(x[1]),
            reverse=True,
        )

        for keyword, learning_ids in sorted_keywords:
            # Skip if most learnings already processed
            unprocessed = [lid for lid in learning_ids if lid not in processed]
            if len(unprocessed) < 2:
                continue

            cluster = PatternCluster(
                theme=keyword,
                learning_ids=unprocessed,
                coherence_score=0.5,  # Heuristic
            )
            clusters.append(cluster)

            # Mark as processed
            processed.update(unprocessed)

        return clusters

    def _extract_keywords(self, text: str) -> set[str]:
        """Extract keywords from text.

        Simple extraction: words > 4 chars, not common stopwords.

        Args:
            text: Text to extract keywords from

        Returns:
            Set of keywords
        """
        # Common stopwords
        stopwords = {
            "that", "this", "with", "from", "have", "will",
            "would", "could", "should", "their", "there", "where",
            "which", "when", "what", "about", "after", "before",
            "because", "being", "between", "during", "through",
        }

        # Extract words
        words = text.lower().split()
        keywords = set()

        for word in words:
            # Remove punctuation
            word = word.strip(".,!?;:()[]{}\"'")

            # Keep if > 4 chars and not stopword
            if len(word) > 4 and word not in stopwords:
                keywords.add(word)

        return keywords

    def _extract_theme_from_cluster(self, learnings: list[Learning]) -> str:
        """Extract a theme from a cluster of learnings.

        Uses most common keywords as theme.

        Args:
            learnings: List of learnings in cluster

        Returns:
            Theme string
        """
        # Count keyword frequency
        keyword_freq: dict[str, int] = defaultdict(int)
        for learning in learnings:
            keywords = self._extract_keywords(learning.fact)
            for keyword in keywords:
                keyword_freq[keyword] += 1

        # Get top 2-3 keywords
        if not keyword_freq:
            return "general"

        sorted_keywords = sorted(
            keyword_freq.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        top_keywords = [k for k, _ in sorted_keywords[:3]]
        return " ".join(top_keywords)
