"""Planning context retrieval for RFC-122: Compound Learning."""

from typing import TYPE_CHECKING

from sunwell.memory.simulacrum.core.planning_context import PlanningContext
from sunwell.memory.simulacrum.core.retrieval.similarity import (
    cosine_similarity,
    keyword_similarity,
)

if TYPE_CHECKING:
    from sunwell.foundation.types.memory import Episode
    from sunwell.knowledge.embedding.protocol import EmbeddingProtocol
    from sunwell.memory.simulacrum.core.dag import ConversationDAG
    from sunwell.memory.simulacrum.core.turn import Learning


class PlanningRetriever:
    """Retrieves categorized knowledge for planning tasks (RFC-122).

    Uses semantic matching to find relevant learnings and episodes,
    categorizing them for injection into HarmonicPlanner via Convergence.
    """

    def __init__(
        self,
        dag: ConversationDAG,
        embedder: EmbeddingProtocol | None = None,
        episodes: list[Episode] | None = None,
    ) -> None:
        """Initialize planning retriever.

        Args:
            dag: Conversation DAG containing learnings
            embedder: Optional embedder for semantic matching
            episodes: Optional list of episodes for dead-end detection
        """
        self._dag = dag
        self._embedder = embedder
        self._episodes = episodes or []

    async def retrieve(
        self,
        goal: str,
        limit_per_category: int = 5,
    ) -> PlanningContext:
        """Retrieve all relevant knowledge for planning a task.

        Uses semantic matching against learnings stored in DAG.
        Returns categorized results for injection into HarmonicPlanner.

        Args:
            goal: Task description to match against
            limit_per_category: Max items per category

        Returns:
            PlanningContext with categorized learnings
        """
        # Get all learnings from the DAG
        learnings = self._dag.get_active_learnings()

        # Compute goal embedding using embedder
        goal_embedding: tuple[float, ...] | None = None
        if self._embedder:
            try:
                embedding_result = await self._embedder.embed([goal])
                goal_embedding = tuple(embedding_result[0])
            except Exception:
                goal_embedding = None

        # Score all learnings by relevance
        scored: list[tuple[float, Learning]] = []

        for learning in learnings:
            if goal_embedding and learning.embedding:
                similarity = cosine_similarity(goal_embedding, learning.embedding)
            else:
                # Fallback: keyword matching
                similarity = keyword_similarity(goal, learning.fact)

            # Boost by confidence and usage
            boost = learning.confidence * (1.0 + 0.05 * min(learning.use_count, 10))
            final_score = similarity * boost

            if final_score > 0.3:
                scored.append((final_score, learning))

        # Sort by score
        scored.sort(key=lambda x: -x[0])

        # Categorize
        facts: list[Learning] = []
        constraints: list[Learning] = []
        dead_ends: list[Learning] = []
        templates: list[Learning] = []
        heuristics: list[Learning] = []
        patterns: list[Learning] = []

        for _score, learning in scored:
            if learning.category == "fact" and len(facts) < limit_per_category or learning.category == "preference" and len(facts) < limit_per_category:
                facts.append(learning)
            elif learning.category == "constraint" and len(constraints) < limit_per_category:
                constraints.append(learning)
            elif learning.category == "dead_end" and len(dead_ends) < limit_per_category:
                dead_ends.append(learning)
            elif learning.category == "template" and len(templates) < limit_per_category:
                templates.append(learning)
            elif learning.category == "heuristic" and len(heuristics) < limit_per_category:
                heuristics.append(learning)
            elif learning.category == "pattern" and len(patterns) < limit_per_category:
                patterns.append(learning)

        # RFC-022: Include episodes for learning from past sessions
        failed_episodes = [ep for ep in self._episodes if ep.outcome == "failed"][:limit_per_category]
        dead_end_summaries = tuple(ep.summary for ep in failed_episodes)

        return PlanningContext(
            facts=tuple(facts),
            constraints=tuple(constraints),
            dead_ends=tuple(dead_ends),
            templates=tuple(templates),
            heuristics=tuple(heuristics),
            patterns=tuple(patterns),
            goal=goal,
            episodes=tuple(failed_episodes),
            dead_end_summaries=dead_end_summaries,
        )
