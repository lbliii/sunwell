"""Context assembly for prompt building with token budgets."""

from typing import TYPE_CHECKING, Any

from sunwell.memory.simulacrum.hierarchical.chunks import Chunk, ChunkSummary

if TYPE_CHECKING:
    from sunwell.memory.simulacrum.core.dag import ConversationDAG
    from sunwell.memory.simulacrum.hierarchical.chunk_manager import ChunkManager


class ContextAssembler:
    """Assembles context for prompts using hierarchical chunking.

    Uses progressive compression (hot/warm/cold tiers) to build
    optimal context within token budget.
    """

    def __init__(
        self,
        dag: ConversationDAG,
        chunk_manager: ChunkManager | None = None,
        focus: Any | None = None,
    ) -> None:
        """Initialize context assembler.

        Args:
            dag: Conversation DAG
            chunk_manager: Optional chunk manager for hierarchical retrieval
            focus: Optional focus mechanism for weighted retrieval
        """
        self._dag = dag
        self._chunk_manager = chunk_manager
        self._focus = focus

    def get_context_for_prompt(
        self,
        query: str,
        max_tokens: int = 4000,
    ) -> str:
        """Get relevant context for a prompt, within token budget.

        Uses hierarchical chunking and semantic search to build
        an optimal context window.

        Args:
            query: The query/prompt to find relevant context for
            max_tokens: Maximum tokens to include in context

        Returns:
            Formatted context string for inclusion in prompts
        """
        if not self._chunk_manager:
            # Fall back to simple retrieval
            return self._simple_context(query, max_tokens)

        context_items = self._chunk_manager.get_context_window(
            max_tokens=max_tokens,
            query=query,
        )

        # Format for prompt
        parts: list[str] = []
        for item in context_items:
            if isinstance(item, Chunk) and item.turns:
                # Full turns from hot tier
                for turn in item.turns:
                    parts.append(f"{turn.turn_type.value}: {turn.content}")
            elif isinstance(item, ChunkSummary):
                # Summary from cold tier
                parts.append(f"[Earlier context: {item.summary}]")
            elif hasattr(item, 'summary') and item.summary:
                parts.append(f"[Context: {item.summary}]")

        return "\n\n".join(parts)

    async def get_context_for_prompt_async(
        self,
        query: str,
        max_tokens: int = 4000,
    ) -> str:
        """Get relevant context for a prompt with semantic retrieval.

        Async version that uses embedding-based semantic search to find
        relevant chunks from warm storage, not just recent turns.

        Args:
            query: The query/prompt to find relevant context for
            max_tokens: Maximum tokens to include in context

        Returns:
            Formatted context string for inclusion in prompts
        """
        if not self._chunk_manager:
            return self._simple_context(query, max_tokens)

        # Use async method with semantic retrieval
        context_items = await self._chunk_manager.get_context_window_async(
            max_tokens=max_tokens,
            query=query,
            semantic_limit=5,
        )

        # Format for prompt
        parts: list[str] = []
        for item in context_items:
            if isinstance(item, Chunk) and item.turns:
                # Full turns from hot or expanded warm tier
                for turn in item.turns:
                    parts.append(f"{turn.turn_type.value}: {turn.content}")
            elif isinstance(item, ChunkSummary):
                # Summary from cold tier
                parts.append(f"[Earlier context: {item.summary}]")
            elif hasattr(item, "summary") and item.summary:
                parts.append(f"[Context: {item.summary}]")

        return "\n\n".join(parts)

    def get_context_for_prompt_weighted(
        self,
        query: str,
        max_tokens: int = 4000,
    ) -> str:
        """Get context with focus-weighted retrieval (RFC-084).

        Uses the focus mechanism to weight chunk relevance based on
        topic tracking across the conversation.

        Args:
            query: Query string
            max_tokens: Maximum tokens to include

        Returns:
            Formatted context string
        """
        if not self._chunk_manager:
            return self._simple_context(query, max_tokens)

        # Update focus from query
        if self._focus:
            self._focus.update_from_query(query)

        # Get context items
        context_items = self._chunk_manager.get_context_window(
            max_tokens=max_tokens,
            query=query,
        )

        # If we have focus, apply weighting
        if self._focus and self._focus.topics:
            from sunwell.memory.simulacrum.context.focus import FocusFilter
            focus_filter = FocusFilter(self._focus)

            # Score and reorder by focus relevance
            scored_items: list[tuple[float, Any]] = []
            for item in context_items:
                if hasattr(item, "turns") and item.turns:
                    # Score based on turns content
                    turns_scored = focus_filter.filter_turns(list(item.turns), min_relevance=0.0)
                    if turns_scored:
                        avg_score = sum(s for _, s in turns_scored) / len(turns_scored)
                    else:
                        avg_score = 0.5
                    scored_items.append((avg_score, item))
                elif hasattr(item, "summary") and item.summary:
                    # Score based on summary
                    tags = focus_filter._extract_tags(item.summary)
                    score = self._focus.matches(tags)
                    scored_items.append((score, item))
                else:
                    scored_items.append((0.5, item))

            # Sort by score descending
            scored_items.sort(key=lambda x: x[0], reverse=True)
            context_items = [item for _, item in scored_items]

        # Format for prompt
        parts: list[str] = []
        for item in context_items:
            if isinstance(item, Chunk) and item.turns:
                for turn in item.turns:
                    parts.append(f"{turn.turn_type.value}: {turn.content}")
            elif isinstance(item, ChunkSummary):
                parts.append(f"[Earlier context: {item.summary}]")
            elif hasattr(item, "summary") and item.summary:
                parts.append(f"[Context: {item.summary}]")

        return "\n\n".join(parts)

    def assemble_messages(
        self,
        query: str,
        system_prompt: str = "",
        max_tokens: int = 4000,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Assemble messages for LLM using hierarchical context.

        Uses progressive compression (hot/warm/cold tiers) to build
        optimal context within token budget.

        Args:
            query: Current user query
            system_prompt: System prompt to include
            max_tokens: Token budget for context

        Returns:
            Tuple of (messages, stats) where:
            - messages: List of message dicts for LLM
            - stats: Dict with retrieval statistics
        """
        messages: list[dict[str, Any]] = []
        stats = {
            "retrieved_chunks": 0,
            "hot_turns": 0,
            "warm_summaries": 0,
            "cold_summaries": 0,
            "compression_applied": False,
        }

        # 1. System prompt with learnings
        system_parts = [system_prompt] if system_prompt else []

        # Add learnings from DAG
        learnings = self._dag.get_active_learnings()
        if learnings:
            system_parts.append("\n\n## Key Context (from conversation history)")
            for learning in learnings:
                system_parts.append(f"- [{learning.category}] {learning.fact}")

        if system_parts:
            messages.append({
                "role": "system",
                "content": "\n".join(system_parts),
            })

        # 2. Get context from hierarchical chunks
        if self._chunk_manager:
            context_items = self._chunk_manager.get_context_window(
                max_tokens=max_tokens,
                query=query,
            )

            stats["retrieved_chunks"] = len(context_items)

            for item in context_items:
                if isinstance(item, Chunk) and item.turns:
                    # HOT tier: full turns as messages
                    stats["hot_turns"] += len(item.turns)
                    for turn in item.turns:
                        messages.append(turn.to_message())
                elif isinstance(item, ChunkSummary):
                    # COLD tier: summary only
                    stats["cold_summaries"] += 1
                    stats["compression_applied"] = True
                    messages.append({
                        "role": "assistant",
                        "content": f"[Earlier context: {item.summary}]",
                    })
                elif hasattr(item, 'summary') and item.summary:
                    # WARM tier: has summary
                    stats["warm_summaries"] += 1
                    messages.append({
                        "role": "assistant",
                        "content": f"[Context: {item.summary}]",
                    })
        else:
            # Fallback: recent turns from DAG
            recent = self._dag.get_recent_turns(10)
            stats["hot_turns"] = len(recent)
            for turn in recent:
                messages.append(turn.to_message())

        return messages, stats

    def _simple_context(self, query: str, max_tokens: int) -> str:
        """Simple context retrieval without ChunkManager.

        Falls back to recent turns from DAG.
        """
        recent = self._dag.get_recent_turns(20)

        parts = []
        token_count = 0

        for turn in reversed(recent):
            turn_tokens = turn.token_count or len(turn.content.split())
            if token_count + turn_tokens > max_tokens:
                break
            parts.append(f"{turn.turn_type.value}: {turn.content}")
            token_count += turn_tokens

        parts.reverse()
        return "\n\n".join(parts)
