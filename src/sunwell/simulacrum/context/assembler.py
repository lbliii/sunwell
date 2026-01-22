"""ContextAssembler - Smart context window management.

The key innovation: never exceed context limits by intelligently selecting
what to include:

1. Always include: System prompt, recent turns, active learnings
2. Retrieve: Semantically relevant historical turns (RAG)
3. Summarize: Compress old context into summaries
4. Exclude: Dead ends, superseded information

This enables "infinite" conversations by keeping the active context
within model limits while preserving access to full history.
"""


from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sunwell.simulacrum.core.dag import ConversationDAG
from sunwell.simulacrum.core.turn import Learning, Turn, TurnType
from sunwell.types.memory import ContextBudget

if TYPE_CHECKING:
    from sunwell.embedding.protocol import EmbeddingProtocol
    from sunwell.models.protocol import ModelProtocol


@dataclass
class AssembledContext:
    """The final assembled context ready for model input."""

    system: str
    """System prompt."""

    messages: list[dict]
    """Messages in LLM format."""

    learnings: list[Learning]
    """Active learnings included."""

    retrieved_turns: list[Turn]
    """Turns retrieved via RAG."""

    recent_turns: list[Turn]
    """Recent conversation turns."""

    estimated_tokens: int
    """Estimated total tokens."""

    compression_applied: bool = False
    """Whether compression was needed."""

    def to_messages(self) -> list[dict]:
        """Convert to LLM messages format."""
        messages = []

        # System prompt with learnings
        system_parts = [self.system]
        if self.learnings:
            system_parts.append("\n\n## Key Context (from conversation history)")
            for l in self.learnings:
                system_parts.append(f"- [{l.category}] {l.fact}")

        messages.append({
            "role": "system",
            "content": "\n".join(system_parts),
        })

        # Retrieved historical turns as actual conversation messages
        # (Not as system context - small models ignore system messages)
        if self.retrieved_turns:
            for turn in self.retrieved_turns:
                messages.append(turn.to_message())

        # Recent conversation
        for turn in self.recent_turns:
            messages.append(turn.to_message())

        return messages


@dataclass
class ContextAssembler:
    """Assembles optimal context from conversation DAG.

    Smart context assembly:
    1. Always include system prompt + learnings
    2. Include recent turns (sliding window)
    3. Retrieve relevant historical turns (RAG)
    4. Compress if still over budget
    5. Never include dead ends or superseded info
    """

    dag: ConversationDAG
    """The conversation DAG to assemble from."""

    embedder: EmbeddingProtocol | None = None
    """Embedder for semantic retrieval."""

    summarizer: ModelProtocol | None = None
    """Model for compression/summarization."""

    budget: ContextBudget = field(default_factory=ContextBudget)
    """Token budget configuration."""

    # Embedding index for retrieval
    _turn_embeddings: dict[str, list[float]] = field(default_factory=dict)
    _initialized: bool = False

    async def initialize(self) -> None:
        """Build embedding index for retrieval."""
        if not self.embedder or self._initialized:
            return

        # Embed all turns for retrieval
        turns_to_embed = [
            t for t in self.dag.turns.values()
            if t.id not in self.dag.compressed
            and t.id not in self.dag.dead_ends
        ]

        if turns_to_embed:
            texts = [t.content for t in turns_to_embed]
            result = await self.embedder.embed(texts)

            for i, turn in enumerate(turns_to_embed):
                self._turn_embeddings[turn.id] = result.vectors[i].tolist()

        self._initialized = True

    async def assemble(
        self,
        query: str,
        system_prompt: str = "",
        recent_count: int = 10,
        retrieve_count: int = 5,
    ) -> AssembledContext:
        """Assemble context for a query.

        Args:
            query: The current user query (for relevance scoring).
            system_prompt: System instructions.
            recent_count: Number of recent turns to include.
            retrieve_count: Number of relevant turns to retrieve.

        Returns:
            Assembled context ready for model input.
        """
        if not self._initialized and self.embedder:
            await self.initialize()

        # 1. Get recent turns (always included)
        recent_turns = self.dag.get_recent_turns(recent_count)

        # 2. Get active learnings
        learnings = self.dag.get_active_learnings()

        # 3. Retrieve relevant historical turns (excluding recent)
        retrieved = []
        if self.embedder and self._turn_embeddings:
            retrieved = await self._retrieve_relevant(
                query,
                exclude={t.id for t in recent_turns},
                limit=retrieve_count,
            )

        # 4. Estimate tokens
        estimated = self._estimate_tokens(
            system_prompt, recent_turns, retrieved, learnings
        )

        # 5. Compress if over budget
        compression_applied = False
        if estimated > self.budget.available and self.summarizer:
            recent_turns, compression_applied = await self._compress(
                recent_turns, estimated - self.budget.available
            )

        return AssembledContext(
            system=system_prompt,
            messages=[],  # Built in to_messages()
            learnings=learnings,
            retrieved_turns=retrieved,
            recent_turns=recent_turns,
            estimated_tokens=estimated,
            compression_applied=compression_applied,
        )

    async def _retrieve_relevant(
        self,
        query: str,
        exclude: set[str],
        limit: int,
    ) -> list[Turn]:
        """Retrieve semantically relevant turns."""
        if not self.embedder or not self._turn_embeddings:
            return []

        # Embed query
        result = await self.embedder.embed([query])
        query_vec = result.vectors[0].tolist()

        # Score all turns
        scores = []
        for turn_id, turn_vec in self._turn_embeddings.items():
            if turn_id in exclude:
                continue
            if turn_id in self.dag.dead_ends:
                continue  # Never retrieve dead ends

            score = self._cosine_similarity(query_vec, turn_vec)
            scores.append((turn_id, score))

        # Sort by score and return top
        scores.sort(key=lambda x: x[1], reverse=True)

        return [
            self.dag.turns[tid]
            for tid, _ in scores[:limit]
            if tid in self.dag.turns
        ]

    async def _compress(
        self,
        turns: list[Turn],
        tokens_to_save: int,
    ) -> tuple[list[Turn], bool]:
        """Compress turns to fit budget.

        Strategy: Summarize older turns, keep recent ones verbatim.
        """
        if not self.summarizer or len(turns) < 5:
            return turns, False

        # Keep last 3 turns verbatim, compress the rest
        to_keep = turns[-3:]
        to_compress = turns[:-3]

        if not to_compress:
            return turns, False

        # Generate summary
        compress_text = "\n\n".join([
            f"{'User' if t.turn_type == TurnType.USER else 'Assistant'}: {t.content}"
            for t in to_compress
        ])

        summary_prompt = f"""Summarize this conversation excerpt in 2-3 sentences,
preserving key facts, decisions, and any code/technical details:

{compress_text}

Summary:"""

        result = await self.summarizer.generate(summary_prompt)

        # Create summary turn
        summary_turn = Turn(
            content=f"[Earlier context summary]: {result.content}",
            turn_type=TurnType.SUMMARY,
            parent_ids=tuple(t.id for t in to_compress),
        )

        # Mark originals as compressed
        for t in to_compress:
            self.dag.compressed.add(t.id)

        return [summary_turn] + to_keep, True

    def _estimate_tokens(
        self,
        system: str,
        recent: list[Turn],
        retrieved: list[Turn],
        learnings: list[Learning],
    ) -> int:
        """Rough token estimation (chars / 4)."""
        total = len(system) // 4
        total += sum(len(t.content) // 4 for t in recent)
        total += sum(len(t.content) // 4 for t in retrieved)
        total += sum(len(l.fact) // 4 for l in learnings)
        return total

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Cosine similarity between vectors."""
        dot = sum(x * y for x, y in zip(a, b, strict=False))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)
