"""Tool Orchestrator Shard - Pre-flight expertise fetching for Naaru (RFC-031).

Uses semantic retrieval to decide when/why/what expertise to fetch,
then passes enriched context to generation models.

Small models don't need tool awareness - they just receive the relevant
expertise baked into their prompt.
"""

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.core import Lens
    from sunwell.knowledge.embedding.protocol import EmbeddingProtocol


@dataclass(frozen=True, slots=True)
class RetrievedExpertise:
    """A piece of expertise retrieved for a task."""

    name: str
    content: str
    score: float  # Semantic similarity score
    source: str  # Where it came from (heuristic, skill, etc.)


@dataclass(frozen=True, slots=True)
class ToolShardResult:
    """Result from Tool Orchestrator Shard."""

    topics_detected: tuple[str, ...]
    expertise: tuple[RetrievedExpertise, ...]
    reasoning: str  # Explains why these topics were selected
    enriched_prompt: str
    latency_ms: int

    @property
    def fetched_expertise(self) -> bool:
        """Whether any expertise was fetched."""
        return len(self.expertise) > 0


class ToolOrchestratorShard:
    """Analyzes tasks and fetches expertise before generation.

    Uses semantic similarity to decide:
    - WHEN to fetch expertise (score > threshold)
    - WHY (similarity scores explain relevance)
    - WHAT (top-k results from retrieval)

    The generation model never needs tool awareness - it just receives
    an enriched prompt with relevant expertise baked in.
    """

    def __init__(
        self,
        lens: Lens,
        threshold: float = 0.5,
        top_k: int = 5,
        embedder: EmbeddingProtocol | None = None,
    ) -> None:
        """Initialize the Tool Orchestrator Shard.

        Args:
            lens: The expertise lens to retrieve from
            threshold: Minimum similarity score to include expertise
            top_k: Maximum number of expertise items to fetch
            embedder: Optional embedder for semantic retrieval (falls back to keywords)
        """
        self.lens = lens
        self.threshold = threshold
        self.top_k = top_k
        self._embedder = embedder
        self._expertise_embeddings: dict[str, list[float]] | None = None

    async def process(self, task: str) -> ToolShardResult:
        """Analyze task and fetch relevant expertise.

        Args:
            task: The task prompt to analyze

        Returns:
            ToolShardResult with enriched prompt and metadata
        """
        start = time.perf_counter()

        # Use semantic retrieval if embedder is configured, else keyword matching
        if self._embedder:
            expertise = await self._async_semantic_retrieve(task)
        else:
            expertise = self._keyword_retrieve(task)

        # Filter by threshold (semantic already filters, but keyword may not)
        relevant = [e for e in expertise if e.score >= self.threshold]

        # Build reasoning (explains why these were selected)
        if relevant:
            reasoning_lines = ["Expertise selected by semantic similarity:"]
            for e in relevant:
                reasoning_lines.append(f"  - {e.name}: {e.score:.0%} match")
        else:
            reasoning_lines = [f"No expertise above threshold ({self.threshold:.0%})"]
        reasoning = "\n".join(reasoning_lines)

        # Build enriched prompt
        enriched_prompt = self._build_enriched_prompt(task, relevant)

        latency = int((time.perf_counter() - start) * 1000)

        return ToolShardResult(
            topics_detected=tuple(e.name for e in relevant),
            expertise=tuple(relevant),
            reasoning=reasoning,
            enriched_prompt=enriched_prompt,
            latency_ms=latency,
        )

    def _retrieve_expertise(self, task: str) -> list[RetrievedExpertise]:
        """Retrieve relevant expertise using semantic similarity.

        Uses the lens's heuristics, anti-heuristics, and skills
        to find relevant guidance for the task.

        Falls back to keyword matching when embeddings are not configured.
        """
        # Use semantic retrieval if embedder is available
        if self._embedder and self._expertise_embeddings:
            return self._semantic_retrieve(task)

        # Fall back to keyword-based matching
        return self._keyword_retrieve(task)

    def _semantic_retrieve(self, task: str) -> list[RetrievedExpertise]:
        """Retrieve expertise using embedding similarity.

        Computes cosine similarity between task and expertise embeddings.
        """
        import math

        if not self._embedder or not self._expertise_embeddings:
            return []

        # This is sync context but we need to run async embed
        # For now, fall back to keyword if called from sync context
        # The caller (process) is async and can call _async_semantic_retrieve
        return self._keyword_retrieve(task)

    async def _async_semantic_retrieve(self, task: str) -> list[RetrievedExpertise]:
        """Async semantic retrieval with embedding computation."""
        import math

        if not self._embedder:
            return self._keyword_retrieve(task)

        # Build expertise embeddings on first call
        if self._expertise_embeddings is None:
            await self._build_expertise_embeddings()

        if not self._expertise_embeddings:
            return self._keyword_retrieve(task)

        # Embed the task
        result = await self._embedder.embed([task])
        task_vector = result.vectors[0].tolist()

        # Score each expertise item
        scored: list[tuple[str, str, str, float]] = []  # (name, content, source, score)

        for key, embedding in self._expertise_embeddings.items():
            # Cosine similarity
            dot = sum(a * b for a, b in zip(task_vector, embedding, strict=True))
            norm_task = math.sqrt(sum(a * a for a in task_vector))
            norm_exp = math.sqrt(sum(b * b for b in embedding))
            if norm_task > 0 and norm_exp > 0:
                score = dot / (norm_task * norm_exp)
            else:
                score = 0.0

            if score >= self.threshold:
                # Parse key back to name, content, source
                parts = key.split("|", 2)
                if len(parts) == 3:
                    name, source, content = parts
                    scored.append((name, content, source, score))

        # Sort by score and take top_k
        scored.sort(key=lambda x: x[3], reverse=True)

        return [
            RetrievedExpertise(name=name, content=content, source=source, score=score)
            for name, content, source, score in scored[: self.top_k]
        ]

    async def _build_expertise_embeddings(self) -> None:
        """Build embeddings for all expertise items in the lens."""
        if not self._embedder:
            return

        self._expertise_embeddings = {}
        texts_to_embed: list[tuple[str, str]] = []  # (key, text)

        # Collect heuristics
        for heuristic in self.lens.heuristics:
            text = f"{heuristic.name}: {heuristic.rule}"
            if heuristic.always:
                text += f" Always: {', '.join(heuristic.always)}"
            if heuristic.never:
                text += f" Never: {', '.join(heuristic.never)}"
            key = f"{heuristic.name}|heuristic|{heuristic.rule}"
            texts_to_embed.append((key, text))

        # Collect skills
        for skill in self.lens.skills:
            text = f"{skill.name}: {skill.description}"
            key = f"{skill.name}|skill|{skill.description}"
            texts_to_embed.append((key, text))

        if not texts_to_embed:
            return

        # Embed all at once
        texts = [t[1] for t in texts_to_embed]
        result = await self._embedder.embed(texts)

        # Store embeddings
        for (key, _), vector in zip(texts_to_embed, result.vectors, strict=True):
            self._expertise_embeddings[key] = vector.tolist()

    def _keyword_retrieve(self, task: str) -> list[RetrievedExpertise]:
        """Fallback: keyword-based expertise matching.

        Uses multiple signals to score relevance:
        1. Direct word overlap between task and heuristic name
        2. Topic keyword mapping (retry → error handling, etc.)
        3. Heuristic rule/always/never overlap with task
        """
        expertise: list[RetrievedExpertise] = []
        task_lower = task.lower()
        task_words = set(task_lower.split())

        # Topic keyword mapping - common coding topics to related terms
        topic_map = {
            # Task keywords → heuristic-related terms
            "retry": {"error", "exception", "fail", "handle", "recover"},
            "async": {"concurrent", "parallel", "await", "thread"},
            "cache": {"memory", "store", "performance", "memoize"},
            "test": {"verify", "assert", "check", "validate"},
            "api": {"interface", "contract", "endpoint", "rest"},
            "error": {"exception", "fail", "handle", "catch"},
            "type": {"contract", "signature", "annotation", "hint"},
            "log": {"debug", "trace", "monitor", "observe"},
            "config": {"setting", "option", "parameter", "env"},
            "decorator": {"wrap", "function", "pattern"},
        }

        # Expand task words with related terms
        expanded_task_words = set(task_words)
        for word in task_words:
            if word in topic_map:
                expanded_task_words.update(topic_map[word])

        # Score each heuristic
        for heuristic in self.lens.heuristics:
            score = 0.0

            # Check name overlap
            name_words = set(heuristic.name.lower().replace("-", " ").replace("_", " ").split())
            name_overlap = len(name_words & expanded_task_words)
            score += name_overlap * 0.3

            # Check rule overlap
            if heuristic.rule:
                rule_words = set(heuristic.rule.lower().split())
                rule_overlap = len(rule_words & expanded_task_words)
                score += min(rule_overlap * 0.1, 0.3)

            # Check always/never for overlap
            always_text = " ".join(heuristic.always) if heuristic.always else ""
            never_text = " ".join(heuristic.never) if heuristic.never else ""
            content_text = (always_text + " " + never_text).lower()
            content_words = set(content_text.split())
            content_overlap = len(content_words & expanded_task_words)
            score += min(content_overlap * 0.05, 0.2)

            # Boost for generic "good code" heuristics (always somewhat relevant)
            generic_keywords = {"type", "error", "test", "document", "name", "simple"}
            if name_words & generic_keywords:
                score += 0.2

            # Normalize to 0-1 range
            score = min(score, 1.0)

            if score > 0.1:  # Include if any relevance
                # Use to_prompt_fragment() to get formatted content
                expertise.append(RetrievedExpertise(
                    name=heuristic.name,
                    content=heuristic.to_prompt_fragment(),
                    score=score,
                    source="heuristic (keyword)",
                ))

        # Sort by score descending
        expertise.sort(key=lambda e: e.score, reverse=True)
        return expertise[:self.top_k]

    def _build_enriched_prompt(
        self,
        task: str,
        expertise: list[RetrievedExpertise],
    ) -> str:
        """Build enriched prompt with pre-fetched expertise.

        The model receives this instead of the raw task,
        with relevant expertise already included.
        """
        if not expertise:
            # No relevant expertise - just return task
            return task

        parts = [
            "## Expert Guidance",
            "",
            "Apply these best practices (ordered by relevance):",
            "",
        ]

        for e in expertise:
            parts.append(f"### {e.name} ({e.score:.0%} relevant)")
            parts.append("")
            parts.append(e.content)
            parts.append("")

        parts.extend([
            "---",
            "",
            "## Task",
            "",
            task,
        ])

        return "\n".join(parts)


# =============================================================================
# Convenience function for quick usage
# =============================================================================

async def prefetch_expertise(
    task: str,
    lens: Lens,
    threshold: float = 0.5,
    top_k: int = 5,
) -> ToolShardResult:
    """Convenience function to prefetch expertise for a task.

    Example:
        result = await prefetch_expertise(task, lens)
        response = await model.generate(result.enriched_prompt)
    """
    shard = ToolOrchestratorShard(lens, threshold=threshold, top_k=top_k)
    return await shard.process(task)
