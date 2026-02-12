"""Planning context retrieval for RFC-122: Compound Learning.

Extended with MIRA-inspired importance scoring that incorporates:
- Graph connectivity (hub score from learning relationships)
- Behavioral signals (access patterns, mentions)
- Temporal relevance (recency, deadlines)

Phase 1 Enhancement: Optional cross-encoder reranking for improved accuracy.
Phase 2 Enhancement: Entity-aware retrieval with co-occurrence expansion.

The learning graph tracks how learnings relate to each other:
- Learnings with many inbound references are "hub" knowledge
- Hub score boosts importance during retrieval
"""

from typing import TYPE_CHECKING

from sunwell.memory.simulacrum.core.planning_context import PlanningContext
from sunwell.memory.simulacrum.core.retrieval.importance import compute_importance
from sunwell.memory.simulacrum.core.retrieval.similarity import hybrid_score

if TYPE_CHECKING:
    from sunwell.foundation.types.memory import Episode
    from sunwell.knowledge.embedding.protocol import EmbeddingProtocol
    from sunwell.memory.core.entities import PatternEntityExtractor
    from sunwell.memory.core.reranking import CrossEncoderReranker
    from sunwell.memory.simulacrum.core.dag import ConversationDAG
    from sunwell.memory.simulacrum.core.turn import Learning
    from sunwell.memory.simulacrum.topology.entity_graph_builder import EntityGraphBuilder


class PlanningRetriever:
    """Retrieves categorized knowledge for planning tasks (RFC-122).

    Uses semantic matching to find relevant learnings and episodes,
    categorizing them for injection into HarmonicPlanner via Convergence.

    Phase 1 Enhancement: Optional cross-encoder reranking for improved accuracy.
    """

    def __init__(
        self,
        dag: ConversationDAG,
        embedder: EmbeddingProtocol | None = None,
        episodes: list[Episode] | None = None,
        reranker: CrossEncoderReranker | None = None,
        entity_extractor: PatternEntityExtractor | None = None,
        entity_graph_builder: EntityGraphBuilder | None = None,
    ) -> None:
        """Initialize planning retriever.

        Args:
            dag: Conversation DAG containing learnings
            embedder: Optional embedder for semantic matching
            episodes: Optional list of episodes for dead-end detection
            reranker: Optional cross-encoder reranker (Phase 1)
            entity_extractor: Optional entity extractor (Phase 2)
            entity_graph_builder: Optional entity graph builder (Phase 2)
        """
        self._dag = dag
        self._embedder = embedder
        self._episodes = episodes or []
        self._reranker = reranker
        self._entity_extractor = entity_extractor
        self._entity_graph_builder = entity_graph_builder

    async def retrieve(
        self,
        goal: str,
        limit_per_category: int = 5,
        activity_days: int = 0,
    ) -> PlanningContext:
        """Retrieve all relevant knowledge for planning a task.

        Uses importance scoring against learnings stored in DAG.
        Returns categorized results for injection into HarmonicPlanner.

        Args:
            goal: Task description to match against
            limit_per_category: Max items per category
            activity_days: Current cumulative activity day count for decay calculations.
                Pass 0 to disable activity-based decay (uses calendar time only).

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
            # Compute semantic similarity using hybrid scoring (vector + BM25)
            similarity = hybrid_score(
                query=goal,
                document=learning.fact,
                query_embedding=goal_embedding,
                doc_embedding=learning.embedding,
            )

            # Get inbound link count from learning graph (hub score)
            inbound_links = self._dag.get_inbound_link_count(learning.id)

            # Use full importance scoring with graph connectivity
            final_score = compute_importance(
                learning=learning,
                query_similarity=similarity,
                activity_days=activity_days,
                inbound_link_count=inbound_links,
            )

            if final_score > 0.3:
                scored.append((final_score, learning))

        # Sort by score
        scored.sort(key=lambda x: -x[0])

        # Phase 1: Optional cross-encoder reranking
        if self._reranker and self._reranker.config.enabled:
            # Rerank with cross-encoder for improved accuracy
            import asyncio

            # Calculate how many candidates to rerank
            rerank_limit = limit_per_category * 6  # 6 categories
            candidates_to_rerank = scored[: rerank_limit * self._reranker.config.overretrieve_multiplier]

            if len(candidates_to_rerank) >= self._reranker.config.min_candidates_for_reranking:
                # Rerank asynchronously
                reranked = await self._reranker.rerank(
                    goal,
                    candidates_to_rerank,
                    rerank_limit,
                )
                # Update scored list with reranked results
                scored = reranked

        # Categorize
        facts: list[Learning] = []
        constraints: list[Learning] = []
        dead_ends: list[Learning] = []
        templates: list[Learning] = []
        heuristics: list[Learning] = []
        patterns: list[Learning] = []

        for _score, learning in scored:
            cat = learning.category
            if cat in ("fact", "preference") and len(facts) < limit_per_category:
                facts.append(learning)
            elif cat == "constraint" and len(constraints) < limit_per_category:
                constraints.append(learning)
            elif cat == "dead_end" and len(dead_ends) < limit_per_category:
                dead_ends.append(learning)
            elif cat == "template" and len(templates) < limit_per_category:
                templates.append(learning)
            elif cat == "heuristic" and len(heuristics) < limit_per_category:
                heuristics.append(learning)
            elif cat == "pattern" and len(patterns) < limit_per_category:
                patterns.append(learning)

        # RFC-022: Include episodes for learning from past sessions
        failed_episodes = [
            ep for ep in self._episodes if ep.outcome == "failed"
        ][:limit_per_category]
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

    async def retrieve_with_entities(
        self,
        goal: str,
        limit_per_category: int = 5,
        activity_days: int = 0,
        entity_boost: float = 0.15,
        cooccurrence_depth: int = 2,
        cooccurrence_decay: float = 0.5,
    ) -> PlanningContext:
        """Retrieve knowledge with entity-aware boosting (Phase 2).

        Enhances retrieval with entity understanding:
        1. Extract entities from goal
        2. Standard hybrid retrieval
        3. Boost scores for entity overlap
        4. Expand via co-occurrence graph
        5. Merge and return top-k

        Args:
            goal: Task description to match against
            limit_per_category: Max items per category
            activity_days: Current cumulative activity day count
            entity_boost: Score boost per matching entity (default 0.15)
            cooccurrence_depth: Depth for co-occurrence expansion (default 2)
            cooccurrence_decay: Score decay per hop (default 0.5)

        Returns:
            PlanningContext with entity-boosted learnings
        """
        # If no entity support, fall back to standard retrieval
        if not self._entity_extractor or not self._entity_graph_builder:
            return await self.retrieve(goal, limit_per_category, activity_days)

        # 1. Extract entities from goal
        goal_entities = self._entity_extractor.extract(goal)
        goal_entity_ids = [e.entity_id for e in goal_entities.entities]

        if not goal_entity_ids:
            # No entities in goal, use standard retrieval
            return await self.retrieve(goal, limit_per_category, activity_days)

        # 2. Standard hybrid retrieval (with overretrieve for boosting)
        learnings = self._dag.get_active_learnings()
        goal_embedding: tuple[float, ...] | None = None
        if self._embedder:
            try:
                embedding_result = await self._embedder.embed([goal])
                goal_embedding = tuple(embedding_result[0])
            except Exception:
                goal_embedding = None

        scored: list[tuple[float, Learning]] = []

        for learning in learnings:
            # Base similarity score
            similarity = hybrid_score(
                query=goal,
                document=learning.fact,
                query_embedding=goal_embedding,
                doc_embedding=learning.embedding,
            )

            # Get inbound link count from learning graph
            inbound_links = self._dag.get_inbound_link_count(learning.id)

            # Base importance score
            base_score = compute_importance(
                learning=learning,
                query_similarity=similarity,
                activity_days=activity_days,
                inbound_link_count=inbound_links,
            )

            # 3. Entity overlap boosting
            learning_entities = self._entity_graph_builder.get_entities_by_learning(learning.id)
            learning_entity_ids = [e.id for e in learning_entities]
            entity_overlap = set(goal_entity_ids) & set(learning_entity_ids)

            # Boost score for each overlapping entity
            if entity_overlap:
                boost = len(entity_overlap) * entity_boost
                final_score = base_score + boost
            else:
                final_score = base_score

            if final_score > 0.3:
                scored.append((final_score, learning))

        # 4. Co-occurrence expansion (depth=2 hops, decay=0.5)
        expanded_learnings = await self._expand_via_cooccurrence(
            goal_entity_ids,
            cooccurrence_depth,
            cooccurrence_decay,
            activity_days,
        )

        # Add expanded learnings with decayed scores
        for score, learning in expanded_learnings:
            # Only add if not already in scored
            if learning not in [l for _, l in scored]:
                scored.append((score, learning))

        # Sort by score
        scored.sort(key=lambda x: -x[0])

        # Phase 1: Optional cross-encoder reranking
        if self._reranker and self._reranker.config.enabled:
            import asyncio

            rerank_limit = limit_per_category * 6
            candidates_to_rerank = scored[: rerank_limit * self._reranker.config.overretrieve_multiplier]

            if len(candidates_to_rerank) >= self._reranker.config.min_candidates_for_reranking:
                reranked = await self._reranker.rerank(
                    goal,
                    candidates_to_rerank,
                    rerank_limit,
                )
                scored = reranked

        # Categorize
        facts: list[Learning] = []
        constraints: list[Learning] = []
        dead_ends: list[Learning] = []
        templates: list[Learning] = []
        heuristics: list[Learning] = []
        patterns: list[Learning] = []

        for _score, learning in scored:
            cat = learning.category
            if cat in ("fact", "preference") and len(facts) < limit_per_category:
                facts.append(learning)
            elif cat == "constraint" and len(constraints) < limit_per_category:
                constraints.append(learning)
            elif cat == "dead_end" and len(dead_ends) < limit_per_category:
                dead_ends.append(learning)
            elif cat == "template" and len(templates) < limit_per_category:
                templates.append(learning)
            elif cat == "heuristic" and len(heuristics) < limit_per_category:
                heuristics.append(learning)
            elif cat == "pattern" and len(patterns) < limit_per_category:
                patterns.append(learning)

        # Include episodes
        failed_episodes = [
            ep for ep in self._episodes if ep.outcome == "failed"
        ][:limit_per_category]
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

    async def _expand_via_cooccurrence(
        self,
        entity_ids: list[str],
        depth: int,
        decay: float,
        activity_days: int,
    ) -> list[tuple[float, Learning]]:
        """Expand retrieval via entity co-occurrence graph.

        Args:
            entity_ids: Starting entity IDs
            depth: Maximum depth (number of hops)
            decay: Score decay per hop
            activity_days: Current activity days for importance scoring

        Returns:
            List of (score, learning) tuples from expanded entities
        """
        if not self._entity_graph_builder or depth <= 0:
            return []

        expanded_entities: set[str] = set(entity_ids)
        frontier = set(entity_ids)
        current_decay = decay

        # BFS expansion through co-occurrence graph
        for _ in range(depth):
            next_frontier = set()
            for entity_id in frontier:
                # Get co-occurring entities (min weight=2)
                cooccurring = self._entity_graph_builder.get_cooccurring_entities(
                    entity_id,
                    min_weight=2,
                    limit=5,  # Top 5 per entity
                )
                for entity_node, _weight in cooccurring:
                    if entity_node.id not in expanded_entities:
                        next_frontier.add(entity_node.id)
                        expanded_entities.add(entity_node.id)

            frontier = next_frontier
            current_decay *= decay
            if not frontier:
                break

        # Get learnings for expanded entities
        expanded_learnings: list[tuple[float, Learning]] = []
        for entity_id in expanded_entities:
            if entity_id not in entity_ids:  # Don't duplicate original entities
                entity_node = self._entity_graph_builder.unified_store.get_node(entity_id)
                if entity_node and hasattr(entity_node, "related_learnings"):
                    for learning_id in entity_node.related_learnings:
                        learning = self._dag.find_learning(learning_id)
                        if learning:
                            # Score with decay and importance
                            base_score = current_decay * 0.5  # Base score for expanded
                            inbound_links = self._dag.get_inbound_link_count(learning.id)
                            importance = compute_importance(
                                learning=learning,
                                query_similarity=0.0,  # No direct similarity
                                activity_days=activity_days,
                                inbound_link_count=inbound_links,
                            )
                            final_score = base_score * importance
                            if final_score > 0.2:
                                expanded_learnings.append((final_score, learning))

        return expanded_learnings
