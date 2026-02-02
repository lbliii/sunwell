"""Manages hierarchical chunking of conversation history.

RFC-013: Hierarchical Memory with Progressive Compression

This module implements the three-tier memory pyramid by granularity:
- MICRO: Full JSON content, last 2 micro-chunks (~10 turns, instant access)
- MESO: CTF-encoded chunks with summaries and embeddings (~25 turns)
- MACRO: Summaries only, full content archived (~100 turns, expandable on demand)

Key features:
- Micro-chunks (10 turns) → Meso-chunks (25 turns) → Macro-chunks (100 turns)
- Automatic summarization and fact extraction
- Embedding-based semantic retrieval
- Token-budgeted context window assembly
"""

import gzip
import hashlib
import json
import logging
import math
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sunwell.foundation.utils import safe_json_dump, safe_json_load
from sunwell.memory.simulacrum.hierarchical.chunks import Chunk, ChunkSummary, ChunkType
from sunwell.memory.simulacrum.hierarchical.config import ChunkConfig
from sunwell.memory.simulacrum.hierarchical.ctf import CTFDecoder, CTFEncoder

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from sunwell.knowledge.embedding.protocol import EmbeddingProtocol
    from sunwell.memory.simulacrum.core.turn import Turn
    from sunwell.memory.simulacrum.hierarchical.summarizer import Summarizer


@dataclass(slots=True)
class ChunkManager:
    """Orchestrates the lifecycle of conversation chunks across tiers.

    Responsibilities:
    - Creating micro-chunks from recent turns
    - Consolidating chunks into meso/macro levels
    - Managing micro/meso/macro storage tiers
    - Handling chunk retrieval and expansion
    - Semantic search via embeddings
    """

    base_path: Path
    config: ChunkConfig = field(default_factory=ChunkConfig)

    # Optional dependencies for processing
    summarizer: Summarizer | None = None
    embedder: EmbeddingProtocol | None = None

    # RFC-045: Intelligence extraction callback
    _demotion_callback: Any | None = None
    """Callback to call when chunks are demoted (for intelligence extraction)."""

    # Internal state
    _chunks: dict[str, Chunk] = field(default_factory=dict)
    _turn_count: int = 0
    _pending_turns: list[Turn] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Ensure chunk storage structure exists and load existing chunks."""
        self.base_path = Path(self.base_path)
        self._ensure_dirs()
        self._load_existing_chunks()

    def _ensure_dirs(self) -> None:
        """Create tier-specific storage directories."""
        (self.base_path / "micro").mkdir(parents=True, exist_ok=True)
        (self.base_path / "meso").mkdir(parents=True, exist_ok=True)
        (self.base_path / "macro").mkdir(parents=True, exist_ok=True)
        (self.base_path / "archive").mkdir(parents=True, exist_ok=True)

    def _load_existing_chunks(self) -> None:
        """Load chunk metadata from disk on initialization."""
        for tier in ["micro", "meso", "macro"]:
            tier_path = self.base_path / tier
            for chunk_file in tier_path.glob("*.json"):
                data = safe_json_load(chunk_file)
                if data is None:
                    continue
                try:
                    chunk = self._deserialize_chunk(data)
                    self._chunks[chunk.id] = chunk
                    if chunk.turn_range[1] > self._turn_count:
                        self._turn_count = chunk.turn_range[1]
                except (KeyError, TypeError):
                    logger.debug("Skipping malformed chunk: %s", chunk_file)
                    continue

    # === Turn Ingestion ===

    async def add_turns(self, turns: Sequence[Turn]) -> list[str]:
        """Add turns and trigger chunking logic."""
        new_ids = []
        for turn in turns:
            self._turn_count += 1
            self._pending_turns.append(turn)

            if self._turn_count % self.config.micro_chunk_size == 0:
                chunk_id = await self._create_micro_chunk()
                new_ids.append(chunk_id)
                self._maybe_demote_micro_chunks()

                if self._turn_count % self.config.mini_chunk_interval == 0:
                    mini_id = await self._consolidate_mini_chunk()
                    if mini_id:
                        new_ids.append(mini_id)

                if self._turn_count % self.config.macro_chunk_interval == 0:
                    macro_id = await self._consolidate_macro_chunk()
                    if macro_id:
                        new_ids.append(macro_id)

        return new_ids

    async def _create_micro_chunk(self) -> str:
        """Create a micro-chunk from pending turns."""
        turns = tuple(self._pending_turns)
        self._pending_turns = []

        start = self._turn_count - len(turns)
        end = self._turn_count

        summary = ""
        if self.config.auto_summarize and self.summarizer:
            summary = await self.summarizer.summarize_turns(turns)

        key_facts = ()
        if self.config.auto_extract_facts and self.summarizer:
            facts = await self.summarizer.extract_facts(turns)
            key_facts = tuple(facts)

        embedding = None
        if self.config.auto_embed and self.embedder:
            text_to_embed = summary or self._turns_to_text(turns)
            result = await self.embedder.embed([text_to_embed])
            if result.vectors is not None and len(result.vectors) > 0:
                embedding = tuple(result.vectors[0].tolist())

        chunk = Chunk(
            id=self._generate_chunk_id("micro", start, end),
            chunk_type=ChunkType.MICRO,
            turn_range=(start, end),
            turns=turns,
            summary=summary,
            token_count=sum(t.token_count for t in turns),
            embedding=embedding,
            timestamp_start=turns[0].timestamp if turns else "",
            timestamp_end=turns[-1].timestamp if turns else "",
            key_facts=key_facts,
        )

        self._chunks[chunk.id] = chunk
        self._save_chunk(chunk, tier="micro")
        return chunk.id

    # === Tier Management ===

    def _maybe_demote_micro_chunks(self) -> None:
        """Demote oldest micro chunks to meso tier."""
        micro_chunks = self._get_micro_chunks()
        micro_chunks.sort(key=lambda c: c.turn_range[0])

        while len(micro_chunks) > self.config.hot_chunks:
            oldest = micro_chunks.pop(0)
            self.demote_to_meso(oldest.id)

    def demote_to_meso(self, chunk_id: str) -> str:
        """Demote a micro chunk to meso tier using CTF encoding."""
        chunk = self._chunks.get(chunk_id)
        if not chunk or chunk.turns is None:
            return chunk_id

        # RFC-045: Callback handled by SimulacrumStore._on_chunk_demotion
        # This method is synchronous; async callback is handled upstream

        ctf_content = CTFEncoder.encode_turns(chunk.turns)
        meso_chunk = replace(chunk, turns=None, content_ctf=ctf_content)

        self._chunks[chunk_id] = meso_chunk
        self._save_chunk(meso_chunk, tier="meso")
        (self.base_path / "micro" / f"{chunk_id}.json").unlink(missing_ok=True)

        return chunk_id

    def set_demotion_callback(self, callback: Callable[[Chunk, str], None]) -> None:
        """Set callback for chunk demotion (RFC-045).

        Args:
            callback: Async function(chunk: Chunk, new_tier: str) -> None
        """
        self._demotion_callback = callback

    def demote_to_macro(self, chunk_id: str) -> str:
        """Demote a meso chunk to macro tier, archiving content."""
        chunk = self._chunks.get(chunk_id)
        if not chunk:
            return chunk_id

        # RFC-045: Callback handled by SimulacrumStore._on_chunk_demotion
        # This method is synchronous; async callback is handled upstream

        archive_ref = None
        if self.config.archive_cold_content:
            archive_ref = self._archive_chunk(chunk)

        macro_chunk = replace(chunk, turns=None, content_ctf=None, content_ref=archive_ref)
        self._chunks[chunk_id] = macro_chunk
        self._save_chunk(macro_chunk, tier="macro")
        (self.base_path / "meso" / f"{chunk_id}.json").unlink(missing_ok=True)

        return chunk_id

    def _archive_chunk(self, chunk: Chunk) -> str:
        """Compress and save full chunk content to archive."""
        data = self._serialize_chunk(chunk)
        archive_ref = f"{chunk.id}.json.gz"
        archive_path = self.base_path / "archive" / archive_ref

        with gzip.open(archive_path, "wt", encoding="utf-8") as f:
            json.dump(data, f)

        return archive_ref

    # === Consolidation ===

    async def _consolidate_mini_chunk(self) -> str | None:
        """Consolidate micro-chunks into a mini-chunk."""
        micro_chunks = [c for c in self._chunks.values() if c.chunk_type == ChunkType.MICRO and c.parent_chunk_id is None]
        needed = self.config.mini_chunk_interval // self.config.micro_chunk_size
        if len(micro_chunks) < needed:
            return None

        recent = micro_chunks[-needed:]
        summaries = [c.summary for c in recent if c.summary]
        combined_summary = ""
        themes = ()
        key_facts = set()

        if self.summarizer:
            combined_summary = await self.summarizer.summarize_turns([t for c in recent for t in (c.turns or ())])
            themes = tuple(await self.summarizer.extract_themes(summaries))
            for c in recent:
                key_facts.update(c.key_facts)

        start = recent[0].turn_range[0]
        end = recent[-1].turn_range[1]

        mini_chunk = Chunk(
            id=self._generate_chunk_id("mini", start, end),
            chunk_type=ChunkType.MINI,
            turn_range=(start, end),
            summary=combined_summary,
            token_count=sum(c.token_count for c in recent),
            timestamp_start=recent[0].timestamp_start,
            timestamp_end=recent[-1].timestamp_end,
            themes=themes,
            key_facts=tuple(key_facts),
            child_chunk_ids=tuple(c.id for c in recent),
        )

        self._chunks[mini_chunk.id] = mini_chunk
        self._save_chunk(mini_chunk, tier="meso")
        for c in recent:
            self._chunks[c.id] = replace(c, parent_chunk_id=mini_chunk.id)

        return mini_chunk.id

    async def _consolidate_macro_chunk(self) -> str | None:
        """Consolidate mini-chunks into a macro-chunk."""
        mini_chunks = [c for c in self._chunks.values() if c.chunk_type == ChunkType.MINI and c.parent_chunk_id is None]
        needed = self.config.macro_chunk_interval // self.config.mini_chunk_interval
        if len(mini_chunks) < needed:
            return None

        recent = mini_chunks[-needed:]
        summaries = [c.summary for c in recent if c.summary]
        exec_summary = ""
        themes = set()
        key_facts = set()

        if self.summarizer:
            exec_summary = await self.summarizer.generate_executive_summary(summaries)
            for c in recent:
                themes.update(c.themes)
                key_facts.update(c.key_facts)

        start = recent[0].turn_range[0]
        end = recent[-1].turn_range[1]

        macro_chunk = Chunk(
            id=self._generate_chunk_id("macro", start, end),
            chunk_type=ChunkType.MACRO,
            turn_range=(start, end),
            summary=exec_summary,
            token_count=sum(c.token_count for c in recent),
            timestamp_start=recent[0].timestamp_start,
            timestamp_end=recent[-1].timestamp_end,
            themes=tuple(themes),
            key_facts=tuple(key_facts),
            child_chunk_ids=tuple(c.id for c in recent),
        )

        self._chunks[macro_chunk.id] = macro_chunk
        self._save_chunk(macro_chunk, tier="macro")
        for c in recent:
            self._chunks[c.id] = replace(c, parent_chunk_id=macro_chunk.id)

        return macro_chunk.id

    # === Retrieval ===

    async def get_relevant_chunks(self, query: str, limit: int = 5, include_hot: bool = True) -> list[Chunk]:
        """Retrieve relevant chunks using embeddings."""
        if not self.embedder:
            return list(self._chunks.values())[-limit:]

        result = await self.embedder.embed([query])
        if result.vectors is None or len(result.vectors) == 0:
            return list(self._chunks.values())[-limit:]
        query_embedding = tuple(result.vectors[0].tolist())

        scored = []
        for chunk in self._chunks.values():
            if not include_hot and chunk.turns is not None:
                continue
            if chunk.embedding:
                score = self._cosine_similarity(query_embedding, chunk.embedding)
                scored.append((score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:limit]]

    def get_context_window(self, max_tokens: int, query: str | None = None) -> list[Chunk | ChunkSummary]:
        """Build context window within token budget (sync version).

        Note: For semantic retrieval, use get_context_window_async() instead.
        """
        context: list[Chunk | ChunkSummary] = []
        token_budget = max_tokens

        # Include micro chunks (most recent with full turns)
        for chunk in self._get_micro_chunks():
            if chunk.token_count <= token_budget:
                context.append(chunk)
                token_budget -= chunk.token_count

        # Include macro summaries for older content
        macro_chunks = [c for c in self._chunks.values() if c.chunk_type == ChunkType.MACRO]
        for chunk in macro_chunks:
            if not chunk.summary:
                continue
            summary_tokens = int(len(chunk.summary.split()) * 1.3)
            if summary_tokens <= token_budget:
                context.append(ChunkSummary(
                    chunk_id=chunk.id, chunk_type=chunk.chunk_type, turn_range=chunk.turn_range,
                    summary=chunk.summary, themes=chunk.themes, token_count=summary_tokens,
                    embedding=chunk.embedding,
                ))
                token_budget -= summary_tokens

        return context

    async def get_context_window_async(
        self,
        max_tokens: int,
        query: str | None = None,
        semantic_limit: int = 5,
    ) -> list[Chunk | ChunkSummary]:
        """Build context window with semantic retrieval (async version).

        Strategy:
        1. Always include MICRO chunks (most recent turns)
        2. If query provided, use semantic search to find relevant meso chunks
        3. Expand meso chunks from CTF to include their content
        4. Fill remaining budget with macro summaries
        """
        context: list[Chunk | ChunkSummary] = []
        seen_ids: set[str] = set()
        token_budget = max_tokens

        # 1. MICRO chunks (most recent, full turns)
        for chunk in self._get_micro_chunks():
            if chunk.token_count <= token_budget:
                context.append(chunk)
                seen_ids.add(chunk.id)
                token_budget -= chunk.token_count

        # 2. Semantic retrieval for query
        if query and self.embedder:
            relevant = await self.get_relevant_chunks(query, limit=semantic_limit)
            for chunk in relevant:
                if chunk.id in seen_ids:
                    continue

                # Expand warm chunks to get content back
                expanded = self.expand_chunk(chunk.id)
                if expanded.token_count <= token_budget:
                    context.append(expanded)
                    seen_ids.add(chunk.id)
                    token_budget -= expanded.token_count

        # 3. Macro summaries for high-level context
        macro_chunks = [c for c in self._chunks.values() if c.chunk_type == ChunkType.MACRO]
        for chunk in macro_chunks:
            if chunk.id in seen_ids or not chunk.summary:
                continue
            summary_tokens = int(len(chunk.summary.split()) * 1.3)
            if summary_tokens <= token_budget:
                context.append(ChunkSummary(
                    chunk_id=chunk.id, chunk_type=chunk.chunk_type, turn_range=chunk.turn_range,
                    summary=chunk.summary, themes=chunk.themes, token_count=summary_tokens,
                    embedding=chunk.embedding,
                ))
                seen_ids.add(chunk.id)
                token_budget -= summary_tokens

        # Sort by turn range to maintain chronological order
        context.sort(key=lambda c: c.turn_range[0] if hasattr(c, "turn_range") else 0)
        return context

    def expand_chunk(self, chunk_id: str) -> Chunk:
        """Expand compressed chunk to full turns."""
        chunk = self._chunks.get(chunk_id)
        if not chunk: raise KeyError(chunk_id)
        if chunk.turns is not None: return chunk
        if chunk.content_ctf:
            return replace(chunk, turns=tuple(CTFDecoder.decode_turns(chunk.content_ctf)))
        if chunk.content_ref:
            return self._load_from_archive(chunk.content_ref)
        return chunk

    def _load_from_archive(self, archive_ref: str) -> Chunk:
        """Load chunk from archive."""
        archive_path = self.base_path / "archive" / archive_ref
        with gzip.open(archive_path, "rt", encoding="utf-8") as f:
            data = json.load(f)
        return self._deserialize_chunk(data)

    # === Chunk Accessors ===

    def get_chunk(self, chunk_id: str) -> Chunk | None:
        """Get a chunk by ID."""
        return self._chunks.get(chunk_id)

    def get_all_chunks(self) -> list[Chunk]:
        """Get all chunks."""
        return list(self._chunks.values())

    def _get_micro_chunks(self) -> list[Chunk]:
        """Get chunks in micro tier (have full turns)."""
        return [c for c in self._chunks.values() if c.turns is not None]

    def _get_meso_chunks(self) -> list[Chunk]:
        """Get chunks in meso tier (CTF-encoded, no full turns)."""
        return [c for c in self._chunks.values() if c.turns is None and c.content_ctf is not None]

    def _get_archived_chunks(self) -> list[Chunk]:
        """Get chunks in macro tier (summary only, archived)."""
        return [c for c in self._chunks.values() if c.turns is None and c.content_ctf is None]

    def _get_macro_chunks(self) -> list[Chunk]:
        """Get all macro-level chunks."""
        return [c for c in self._chunks.values() if c.chunk_type == ChunkType.MACRO]

    def _get_recent_chunks(self, limit: int) -> list[Chunk]:
        """Get the most recent chunks by turn range."""
        chunks = list(self._chunks.values())
        chunks.sort(key=lambda c: c.turn_range[1], reverse=True)
        return chunks[:limit]

    # === Utilities ===

    def _cosine_similarity(self, a: tuple[float, ...], b: tuple[float, ...]) -> float:
        dot = sum(x * y for x, y in zip(a, b, strict=False))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0

    def _generate_chunk_id(self, prefix: str, start: int, end: int) -> str:
        content = f"{prefix}:{start}:{end}:{time.time()}"
        return f"{prefix}_{hashlib.blake2b(content.encode(), digest_size=6).hexdigest()}"

    def _turns_to_text(self, turns: tuple[Turn, ...]) -> str:
        return "\n".join(f"{t.turn_type.value}: {t.content[:500]}" for t in turns)

    def _save_chunk(self, chunk: Chunk, tier: str) -> None:
        path = self.base_path / tier / f"{chunk.id}.json"
        if not safe_json_dump(self._serialize_chunk(chunk), path):
            logger.error("Failed to save chunk %s to %s", chunk.id, path)

    def _serialize_chunk(self, chunk: Chunk) -> dict:
        data = {
            "id": chunk.id, "chunk_type": chunk.chunk_type.value, "turn_range": list(chunk.turn_range),
            "summary": chunk.summary, "token_count": chunk.token_count, "timestamp_start": chunk.timestamp_start,
            "timestamp_end": chunk.timestamp_end, "themes": list(chunk.themes), "key_facts": list(chunk.key_facts),
            "parent_chunk_id": chunk.parent_chunk_id, "child_chunk_ids": list(chunk.child_chunk_ids),
            "content_ctf": chunk.content_ctf, "content_ref": chunk.content_ref,
        }
        if chunk.embedding: data["embedding"] = list(chunk.embedding)
        if chunk.turns:
            data["turns"] = [{"content": t.content, "turn_type": t.turn_type.value, "timestamp": t.timestamp, "model": t.model} for t in chunk.turns]
        return data

    def _deserialize_chunk(self, data: dict) -> Chunk:
        from sunwell.memory.simulacrum.core.turn import Turn, TurnType
        turns = tuple(Turn(content=t["content"], turn_type=TurnType(t["turn_type"]), timestamp=t["timestamp"], model=t.get("model")) for t in data.get("turns", [])) if "turns" in data else None
        return Chunk(
            id=data["id"], chunk_type=ChunkType(data["chunk_type"]), turn_range=tuple(data["turn_range"]),
            turns=turns, content_ctf=data.get("content_ctf"), content_ref=data.get("content_ref"),
            summary=data.get("summary", ""), token_count=data.get("token_count", 0),
            embedding=tuple(data["embedding"]) if "embedding" in data else None,
            timestamp_start=data.get("timestamp_start", ""), timestamp_end=data.get("timestamp_end", ""),
            themes=tuple(data.get("themes", [])), key_facts=tuple(data.get("key_facts", [])),
            parent_chunk_id=data.get("parent_chunk_id"), child_chunk_ids=tuple(data.get("child_chunk_ids", [])),
        )

    @property
    def stats(self) -> dict:
        """Get statistics about chunk storage."""
        micro = self._get_micro_chunks()
        meso = self._get_meso_chunks()
        archived = self._get_archived_chunks()

        return {
            "total_chunks": len(self._chunks),
            "micro_chunks": len(micro),
            "meso_chunks": len(meso),
            "macro_chunks": len(self._get_macro_chunks()),
            "archived_chunks": len(archived),
            "total_turns": self._turn_count,
            "micro_tokens": sum(c.token_count for c in micro),
            "total_tokens": sum(c.token_count for c in self._chunks.values()),
        }

    def cleanup_expired_archives(self) -> int:
        """Delete archived chunks older than retention limit."""
        if self.config.cold_retention_days <= 0:
            return 0

        count = 0
        now = time.time()
        retention_secs = self.config.cold_retention_days * 86400

        archive_dir = self.base_path / "archive"
        for archive_file in archive_dir.glob("*.jsonl.gz"):
            if now - archive_file.stat().st_mtime > retention_secs:
                archive_file.unlink()
                count += 1

        return count
