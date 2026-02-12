"""Main reflection engine for Phase 3: Reflection System.

Synthesizes higher-order insights from learnings by:
1. Clustering related learnings by theme
2. Analyzing causality (WHY patterns exist)
3. Generating reflections and mental models

Part of Hindsight-inspired memory enhancements.
"""

import hashlib
import logging
from typing import TYPE_CHECKING

from sunwell.memory.core.reflection.causality import CausalityAnalyzer
from sunwell.memory.core.reflection.patterns import PatternDetector
from sunwell.memory.core.reflection.types import MentalModel, Reflection

if TYPE_CHECKING:
    from sunwell.knowledge.embedding.protocol import EmbeddingProtocol
    from sunwell.memory.simulacrum.core.turn import Learning

logger = logging.getLogger(__name__)


class Reflector:
    """Main reflection engine.

    Synthesizes higher-order insights from learnings:
    - Reflections: WHY patterns and constraints exist
    - Mental models: Coherent understanding of topics
    """

    def __init__(self, embedder: EmbeddingProtocol | None = None):
        """Initialize reflector.

        Args:
            embedder: Optional embedder for semantic analysis
        """
        self._embedder = embedder
        self._pattern_detector = PatternDetector(embedder)
        self._causality_analyzer = CausalityAnalyzer(embedder)

    async def reflect_on_constraints(
        self,
        constraints: list[Learning],
        min_cluster_size: int = 3,
    ) -> list[Reflection]:
        """Analyze WHY constraints exist together.

        Example Input:
        - "Don't use global state in components"
        - "Avoid side effects in render"
        - "Use hooks for state management"

        Output:
        Reflection(
            theme="React functional programming",
            causality="These stem from React's declarative rendering model",
            summary="Functional purity enables predictable re-renders"
        )

        Args:
            constraints: List of constraint learnings
            min_cluster_size: Minimum learnings per cluster

        Returns:
            List of Reflection instances
        """
        if not constraints:
            return []

        # 1. Cluster related constraints
        clusters = await self._pattern_detector.cluster_learnings(
            constraints,
            min_cluster_size=min_cluster_size,
            similarity_threshold=0.7,
        )

        logger.info(f"Found {len(clusters)} constraint clusters")

        # 2. Generate reflection for each cluster
        reflections = []
        for cluster in clusters:
            # Get learnings in cluster
            cluster_learnings = [
                l for l in constraints if l.id in cluster.learning_ids
            ]

            # Analyze causality
            causality, summary = await self._causality_analyzer.analyze_causality(
                cluster_learnings,
                cluster.theme,
            )

            # Create reflection
            reflection_id = self._generate_reflection_id(cluster.theme)
            reflection = Reflection(
                id=reflection_id,
                theme=cluster.theme,
                causality=causality,
                summary=summary,
                source_learning_ids=tuple(cluster.learning_ids),
                confidence=cluster.coherence_score,
            )

            reflections.append(reflection)

        return reflections

    async def reflect_on_category(
        self,
        learnings: list[Learning],
        category: str,
        min_cluster_size: int = 3,
    ) -> list[Reflection]:
        """Generate reflections for any category of learnings.

        More general version of reflect_on_constraints.

        Args:
            learnings: List of learnings
            category: Category name (for logging)
            min_cluster_size: Minimum learnings per cluster

        Returns:
            List of Reflection instances
        """
        if not learnings:
            return []

        # Cluster and reflect
        clusters = await self._pattern_detector.cluster_learnings(
            learnings,
            min_cluster_size=min_cluster_size,
            similarity_threshold=0.6,  # Lower threshold for general categories
        )

        logger.info(f"Found {len(clusters)} {category} clusters")

        reflections = []
        for cluster in clusters:
            cluster_learnings = [l for l in learnings if l.id in cluster.learning_ids]
            causality, summary = await self._causality_analyzer.analyze_causality(
                cluster_learnings,
                cluster.theme,
            )

            reflection_id = self._generate_reflection_id(f"{category}_{cluster.theme}")
            reflection = Reflection(
                id=reflection_id,
                theme=f"{category}: {cluster.theme}",
                causality=causality,
                summary=summary,
                source_learning_ids=tuple(cluster.learning_ids),
                confidence=cluster.coherence_score,
            )
            reflections.append(reflection)

        return reflections

    async def build_mental_model(
        self,
        topic: str,
        learnings: list[Learning],
        reflections: list[Reflection] | None = None,
    ) -> MentalModel:
        """Build a mental model for a topic.

        Mental models synthesize multiple learnings into a single
        coherent view, saving tokens and providing better context.

        Args:
            topic: Topic name
            learnings: Relevant learnings about this topic
            reflections: Optional reflections to incorporate

        Returns:
            MentalModel instance
        """
        # Extract principles, patterns, and anti-patterns
        principles = self._causality_analyzer.extract_principles(learnings)
        patterns = self._causality_analyzer.extract_patterns(learnings)
        anti_patterns = self._causality_analyzer.extract_anti_patterns(learnings)

        # Incorporate reflections if available
        if reflections:
            for reflection in reflections:
                # Add reflection causality as a principle
                principles.append(reflection.causality)

        # Calculate confidence (average of source learning confidences)
        if learnings:
            avg_confidence = sum(l.confidence for l in learnings) / len(learnings)
        else:
            avg_confidence = 0.5

        # Create mental model
        model_id = self._generate_model_id(topic)
        mental_model = MentalModel(
            id=model_id,
            topic=topic,
            core_principles=tuple(principles),
            key_patterns=tuple(patterns),
            anti_patterns=tuple(anti_patterns),
            confidence=avg_confidence,
            source_learning_count=len(learnings),
        )

        return mental_model

    async def update_mental_model(
        self,
        existing_model: MentalModel,
        new_learnings: list[Learning],
    ) -> MentalModel:
        """Update an existing mental model with new learnings.

        Args:
            existing_model: Existing mental model
            new_learnings: New learnings to incorporate

        Returns:
            Updated MentalModel
        """
        from datetime import datetime

        # Extract new principles, patterns, anti-patterns
        new_principles = self._causality_analyzer.extract_principles(new_learnings)
        new_patterns = self._causality_analyzer.extract_patterns(new_learnings)
        new_anti_patterns = self._causality_analyzer.extract_anti_patterns(new_learnings)

        # Merge with existing (deduplicate)
        all_principles = set(existing_model.core_principles) | set(new_principles)
        all_patterns = set(existing_model.key_patterns) | set(new_patterns)
        all_anti_patterns = set(existing_model.anti_patterns) | set(new_anti_patterns)

        # Update confidence (weighted average)
        total_count = existing_model.source_learning_count + len(new_learnings)
        new_avg_confidence = sum(l.confidence for l in new_learnings) / len(new_learnings) if new_learnings else 0
        updated_confidence = (
            existing_model.confidence * existing_model.source_learning_count
            + new_avg_confidence * len(new_learnings)
        ) / total_count

        # Create updated model
        return MentalModel(
            id=existing_model.id,
            topic=existing_model.topic,
            core_principles=tuple(all_principles),
            key_patterns=tuple(all_patterns),
            anti_patterns=tuple(all_anti_patterns),
            confidence=updated_confidence,
            source_learning_count=total_count,
            created_at=existing_model.created_at,
            last_updated=datetime.now().isoformat(),
        )

    def _generate_reflection_id(self, theme: str) -> str:
        """Generate stable ID for a reflection.

        Args:
            theme: Reflection theme

        Returns:
            Reflection ID
        """
        content = f"reflection:{theme}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _generate_model_id(self, topic: str) -> str:
        """Generate stable ID for a mental model.

        Args:
            topic: Model topic

        Returns:
            Model ID
        """
        content = f"mental_model:{topic}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def estimate_token_savings(
        self,
        mental_model: MentalModel,
        replaced_learning_count: int,
        avg_learning_tokens: int = 50,
    ) -> dict:
        """Estimate token savings from using a mental model.

        Args:
            mental_model: The mental model
            replaced_learning_count: Number of learnings this replaces
            avg_learning_tokens: Average tokens per learning

        Returns:
            Dict with token savings metrics
        """
        model_tokens = mental_model.estimate_token_count()
        individual_tokens = replaced_learning_count * avg_learning_tokens
        savings = individual_tokens - model_tokens
        savings_percent = (savings / individual_tokens * 100) if individual_tokens > 0 else 0

        return {
            "mental_model_tokens": model_tokens,
            "individual_learning_tokens": individual_tokens,
            "token_savings": savings,
            "savings_percent": savings_percent,
            "replaced_learning_count": replaced_learning_count,
        }
