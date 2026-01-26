"""Enhanced context assembly using RFC-014 multi-topology memory.

Replaces traditional RAG with a unified query across:
- Spatial: "What's near this code location?"
- Topological: "What concepts relate to this?"
- Structural: "What's in this document section?"
- Faceted: "Give me tutorial content for novices"
- Temporal: "Recent conversation history"
"""


from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sunwell.foundation.types.memory import ContextBudget
from sunwell.memory.simulacrum.core.dag import ConversationDAG
from sunwell.memory.simulacrum.core.turn import Learning, Turn
from sunwell.memory.simulacrum.topology.facets import DiataxisType, FacetQuery, PersonaType
from sunwell.memory.simulacrum.topology.memory_node import MemoryNode
from sunwell.memory.simulacrum.topology.spatial import SpatialQuery
from sunwell.memory.simulacrum.topology.topology_base import RelationType
from sunwell.memory.simulacrum.topology.unified_store import UnifiedMemoryStore

if TYPE_CHECKING:
    from sunwell.knowledge.codebase.context import ProjectContext
    from sunwell.knowledge.embedding.protocol import EmbeddingProtocol


@dataclass(slots=True)
class UnifiedContext:
    """Context assembled from multi-topology memory."""

    system: str
    """System prompt."""

    messages: list[dict]
    """Messages in LLM format."""

    # Separated by source for transparency
    recent_turns: list[Turn]
    """Recent conversation turns."""

    memory_nodes: list[tuple[MemoryNode, float]]
    """Retrieved memory nodes with relevance scores."""

    learnings: list[Learning]
    """Active learnings included."""

    # Stats
    estimated_tokens: int
    retrieval_sources: dict[str, int]
    """Which topology sources contributed how much."""

    def to_messages(self) -> list[dict]:
        """Convert to LLM messages format."""
        messages = []

        # System prompt with learnings and memory context
        system_parts = [self.system]

        # Add learnings
        if self.learnings:
            system_parts.append("\n\n## Key Learnings")
            for l in self.learnings:
                system_parts.append(f"- [{l.category}] {l.fact}")

        # Add memory context (from unified store)
        if self.memory_nodes:
            system_parts.append("\n\n## Relevant Memory")
            for node, _score in self.memory_nodes[:10]:  # Top 10
                # Include spatial context if available
                context_parts = []
                if node.spatial and node.spatial.file_path:
                    context_parts.append(f"[{node.spatial.file_path}]")
                if node.facets and node.facets.diataxis_type:
                    context_parts.append(f"({node.facets.diataxis_type.value})")

                prefix = " ".join(context_parts)
                if prefix:
                    system_parts.append(f"- {prefix}: {node.content[:300]}...")
                else:
                    system_parts.append(f"- {node.content[:300]}...")

        # RFC-045: Add project intelligence context
        if self.intelligence_context:
            system_parts.append(self.intelligence_context)

        messages.append({
            "role": "system",
            "content": "\n".join(system_parts),
        })

        # Recent conversation
        for turn in self.recent_turns:
            messages.append(turn.to_message())

        return messages


@dataclass(slots=True)
class UnifiedContextAssembler:
    """Assembles context using RFC-014 multi-topology memory.

    Key improvements over simple RAG:
    1. Spatial awareness: Knows WHERE information came from
    2. Conceptual relationships: Follows concept graph edges
    3. Structural context: Understands document hierarchy
    4. Faceted filtering: Matches user persona/needs
    5. Temporal recency: Balances old vs new information
    """

    dag: ConversationDAG
    """Conversation history."""

    store: UnifiedMemoryStore | None = None
    """Multi-topology memory store."""

    embedder: EmbeddingProtocol | None = None
    """Embedder for semantic queries."""

    project_context: ProjectContext | None = None
    """RFC-045: Project intelligence context."""

    budget: ContextBudget = field(default_factory=ContextBudget)
    """Token budget configuration."""

    async def assemble(
        self,
        query: str,
        system_prompt: str = "",
        recent_count: int = 10,
        *,
        # Multi-topology query options
        spatial_query: SpatialQuery | None = None,
        facet_query: FacetQuery | None = None,
        follow_relations: list[RelationType] | None = None,
        persona: PersonaType | None = None,
        diataxis_type: DiataxisType | None = None,
    ) -> UnifiedContext:
        """Assemble context from multi-topology memory.

        Args:
            query: Current user query
            system_prompt: System instructions
            recent_count: Recent turns to include
            spatial_query: Optional spatial constraints (e.g., "in file X")
            facet_query: Optional facet constraints
            follow_relations: If set, follow these relation types in concept graph
            persona: Target persona for content filtering
            diataxis_type: Target Diataxis type for content filtering

        Returns:
            UnifiedContext ready for model input.
        """
        # 1. Get recent turns (always included)
        recent_turns = self.dag.get_recent_turns(recent_count)

        # 2. Get active learnings
        learnings = self.dag.get_active_learnings()

        # 3. Multi-topology memory retrieval
        memory_nodes: list[tuple[MemoryNode, float]] = []
        retrieval_sources: dict[str, int] = {}

        if self.store:
            # Build facet query from convenience args
            effective_facet_query = facet_query
            if persona or diataxis_type:
                effective_facet_query = FacetQuery(
                    diataxis_type=diataxis_type,
                    persona=persona,
                )

            # Unified query across all topologies
            memory_nodes = self.store.query(
                text_query=query,
                spatial_query=spatial_query,
                facet_query=effective_facet_query,
                limit=20,
            )

            # Track which sources contributed
            for node, _ in memory_nodes:
                if node.spatial:
                    retrieval_sources["spatial"] = retrieval_sources.get("spatial", 0) + 1
                if node.facets:
                    retrieval_sources["facets"] = retrieval_sources.get("facets", 0) + 1
                if node.section:
                    retrieval_sources["structural"] = retrieval_sources.get("structural", 0) + 1
                if node.outgoing_edges:
                    retrieval_sources["topological"] = retrieval_sources.get("topological", 0) + 1

            # Follow concept graph relations if requested
            if follow_relations and memory_nodes:
                # Get related concepts for top results
                top_node_ids = [n.id for n, _ in memory_nodes[:5]]
                for node_id in top_node_ids:
                    for rel_type in follow_relations:
                        related = self.store.query(
                            relationship_from=node_id,
                            relationship_type=rel_type,
                            limit=3,
                        )
                        for r_node, score in related:
                            if r_node.id not in {n.id for n, _ in memory_nodes}:
                                # Discount related nodes slightly
                                memory_nodes.append((r_node, score * 0.8))
                                retrieval_sources["topological"] = retrieval_sources.get("topological", 0) + 1

        # RFC-045: Add project intelligence (decisions, failures, patterns)
        intelligence_context = ""
        if self.project_context:
            intelligence_parts = []
            # Find relevant decisions
            relevant_decisions = await self.project_context.decisions.find_relevant_decisions(
                query, top_k=3
            )
            if relevant_decisions:
                intelligence_parts.append("\n\n## 📋 Relevant Architectural Decisions")
                for decision in relevant_decisions:
                    intelligence_parts.append(
                        f"- [{decision.category}] {decision.question} → {decision.choice}"
                    )
                    if decision.rationale:
                        intelligence_parts.append(f"  Rationale: {decision.rationale}")
                    if decision.rejected:
                        rejected_str = ", ".join(r.option for r in decision.rejected)
                        intelligence_parts.append(f"  Rejected: {rejected_str}")

            # Check for similar failures
            similar_failures = await self.project_context.failures.check_similar_failures(
                query, top_k=2
            )
            if similar_failures:
                intelligence_parts.append("\n\n## ⚠️ Similar Past Failures")
                for failure in similar_failures:
                    intelligence_parts.append(
                        f"- {failure.error_type}: {failure.description}"
                    )
                    intelligence_parts.append(f"  Error: {failure.error_message}")
                    if failure.root_cause:
                        intelligence_parts.append(f"  Root cause: {failure.root_cause}")

            if intelligence_parts:
                intelligence_context = "\n".join(intelligence_parts)

        # 4. Estimate tokens
        estimated = self._estimate_tokens(
            system_prompt, recent_turns, memory_nodes, learnings
        )

        return UnifiedContext(
            system=system_prompt,
            messages=[],  # Built in to_messages()
            recent_turns=recent_turns,
            memory_nodes=memory_nodes,
            learnings=learnings,
            estimated_tokens=estimated,
            retrieval_sources=retrieval_sources,
            intelligence_context=intelligence_context,
        )

    async def assemble_for_code_task(
        self,
        query: str,
        file_path: str,
        system_prompt: str = "",
    ) -> UnifiedContext:
        """Specialized assembly for code-related tasks.

        Automatically includes:
        - Spatial context from same file/module
        - Related concepts from code graph
        - HOW-TO content from documentation
        """
        # Build spatial query for the current file/module
        spatial_query = SpatialQuery(
            file_pattern=file_path,
        )

        # Build facet query for actionable content (HOW-TO is preferred for code tasks)
        facet_query = FacetQuery(
            diataxis_type=DiataxisType.HOWTO,
        )

        return await self.assemble(
            query=query,
            system_prompt=system_prompt,
            spatial_query=spatial_query,
            facet_query=facet_query,
            follow_relations=[RelationType.ELABORATES, RelationType.DEPENDS_ON],
        )

    async def assemble_for_learning(
        self,
        query: str,
        system_prompt: str = "",
        persona: PersonaType = PersonaType.NOVICE,
    ) -> UnifiedContext:
        """Specialized assembly for learning/onboarding tasks.

        Automatically includes:
        - Tutorial content
        - Explanation content
        - Content appropriate for the persona
        """
        # Note: FacetQuery only supports single values, so we filter for TUTORIAL
        # For multi-type filtering, we'd need to extend FacetQuery or do post-filtering
        facet_query = FacetQuery(
            diataxis_type=DiataxisType.TUTORIAL,
            persona=persona,
        )

        return await self.assemble(
            query=query,
            system_prompt=system_prompt,
            facet_query=facet_query,
            follow_relations=[RelationType.ELABORATES, RelationType.SUMMARIZES],
        )

    def _estimate_tokens(
        self,
        system: str,
        recent: list[Turn],
        memory: list[tuple[MemoryNode, float]],
        learnings: list[Learning],
    ) -> int:
        """Rough token estimation (chars / 4)."""
        total = len(system) // 4
        total += sum(len(t.content) // 4 for t in recent)
        total += sum(len(n.content) // 4 for n, _ in memory)
        total += sum(len(l.fact) // 4 for l in learnings)
        return total
