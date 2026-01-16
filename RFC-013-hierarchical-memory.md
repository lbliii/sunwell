# RFC-013: Hierarchical Memory with Progressive Compression

**Status:** Implemented  
**Author:** Sunwell Contributors  
**Created:** 2026-01-15  
**Updated:** 2026-01-15  
**Related:** [RFC-012: Tool Calling](./RFC-012-tool-calling.md), [HeadspaceStore](./src/sunwell/headspace/store.py)

---

## Summary

Replace turn-count-based storage demotion with a **hierarchical chunking system** that progressively compresses conversation history. Introduces TOON (Token-Oriented Object Notation) for warm/cold storage to reduce token costs when feeding history to LLMs.

**Key insight:** 10-turn micro-chunks with auto-summarization provide better memory efficiency than waiting for 100 turns. Hierarchical consolidation (10 → 25 → 100) enables graduated compression while preserving retrievability.

---

## Motivation

### Current State: Flat Turn Storage

Today, HeadspaceStore uses simple thresholds:

```python
class StorageConfig:
    hot_max_turns: int = 100          # Demote after 100 turns
    warm_max_age_hours: int = 24 * 7  # Move to cold after 1 week
```

**Problems:**

1. **Turn count ignores token cost** — A 10-token turn equals a 2000-token turn
2. **All-or-nothing compression** — No gradual degradation
3. **No summarization** — Old context is either full or gone
4. **Inefficient retrieval** — Must scan all turns for relevance
5. **JSON overhead** — Repeated structure bloats token usage when re-feeding to LLM

### Evidence from Real Sessions

Analysis of the `writer` session (26 turns) shows:

```json
{
  "token_count": 0,    // Not tracked!
  "learnings": 0,      // Not extracted
  "compressed": 0      // Nothing demoted yet
}
```

User repeatedly asked the LLM to recall information. The system retrieved relevant turns, but:
- No summarization of older context
- No automatic learning extraction
- Token costs unknown

---

## Design

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         HIERARCHICAL MEMORY PYRAMID                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   HOT TIER (last 20 turns)                                                   │
│   ├── Full JSON content                                                      │
│   ├── Instant access                                                         │
│   └── 2 micro-chunks max                                                     │
│                                                                              │
│   WARM TIER (turns 20-100)                                                   │
│   ├── CTF-encoded chunks (Compact Turn Format)                               │
│   ├── Per-chunk summaries                                                    │
│   ├── Embeddings for retrieval                                               │
│   └── Mini-chunk consolidations every 25 turns                               │
│                                                                              │
│   COLD TIER (100+ turns)                                                     │
│   ├── Macro-chunk summaries only                                             │
│   ├── Key facts extracted to learnings                                       │
│   ├── Embeddings preserved                                                   │
│   └── Full content archived (expandable on demand)                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1. Chunk Types

```python
# src/sunwell/headspace/chunks.py

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class ChunkType(Enum):
    """Granularity levels in the memory pyramid."""
    MICRO = "micro"   # 10 turns
    MINI = "mini"     # 25 turns (2-3 micro-chunks consolidated)
    MACRO = "macro"   # 100 turns (4 mini-chunks consolidated)


@dataclass(frozen=True, slots=True)
class Chunk:
    """A compressed unit of conversation history."""
    
    id: str
    chunk_type: ChunkType
    turn_range: tuple[int, int]  # (start_turn, end_turn)
    
    # Content (mutually exclusive based on tier)
    turns: tuple["Turn", ...] | None = None  # HOT: full turns
    content_ctf: str | None = None           # WARM: CTF-encoded
    content_ref: str | None = None           # COLD: reference to archive
    
    # Always present
    summary: str = ""
    token_count: int = 0
    embedding: tuple[float, ...] | None = None
    
    # Metadata
    timestamp_start: str = ""
    timestamp_end: str = ""
    themes: tuple[str, ...] = ()
    key_facts: tuple[str, ...] = ()
    
    # Hierarchy
    parent_chunk_id: str | None = None       # For mini/macro chunks
    child_chunk_ids: tuple[str, ...] = ()    # Chunks this consolidates


@dataclass(frozen=True, slots=True)
class ChunkSummary:
    """Lightweight summary for retrieval without loading full chunk."""
    
    chunk_id: str
    chunk_type: ChunkType
    turn_range: tuple[int, int]
    summary: str
    themes: tuple[str, ...]
    token_count: int
    embedding: tuple[float, ...] | None = None
```

### 2. Chunking Configuration

```python
# src/sunwell/headspace/config.py

@dataclass
class ChunkConfig:
    """Configuration for hierarchical chunking."""
    
    # Chunk sizes
    micro_chunk_size: int = 10
    """Turns per micro-chunk."""
    
    mini_chunk_interval: int = 25
    """Consolidate micro-chunks every N turns."""
    
    macro_chunk_interval: int = 100
    """Major consolidation every N turns."""
    
    # Hot tier limits
    hot_chunks: int = 2
    """Keep last N micro-chunks in hot tier (full JSON)."""
    
    hot_max_tokens: int = 50_000
    """Alternative: demote when hot tier exceeds token budget."""
    
    # Format preferences
    warm_format: Literal["json", "ctf"] = "ctf"
    """Storage format for warm tier. CTF = Compact Turn Format."""
    
    cold_format: Literal["ctf", "summary_only"] = "summary_only"
    """Storage format for cold tier."""
    
    # Auto-processing
    auto_summarize: bool = True
    """Generate summaries when chunking."""
    
    auto_extract_facts: bool = True
    """Extract key facts to learnings."""
    
    auto_embed: bool = True
    """Generate embeddings for retrieval."""
    
    # Retention
    archive_cold_content: bool = True
    """Keep full content in archive (expandable on demand)."""
    
    cold_retention_days: int = 90
    """Delete archived content after N days (0 = forever)."""


# Default configuration
DEFAULT_CHUNK_CONFIG = ChunkConfig()
```

### 3. Chunk Manager

```python
# src/sunwell/headspace/chunk_manager.py

from dataclasses import replace
from pathlib import Path

from sunwell.headspace.chunks import Chunk, ChunkType, ChunkSummary
from sunwell.headspace.config import ChunkConfig
from sunwell.headspace.turn import Turn
from sunwell.headspace.ctf import CTFEncoder, CTFDecoder


@dataclass
class ChunkManager:
    """Manages hierarchical chunking of conversation history.
    
    Responsibilities:
    - Create micro-chunks every N turns
    - Consolidate into mini/macro chunks on schedule
    - Convert between formats (JSON ↔ TOON)
    - Generate summaries and embeddings
    - Handle retrieval across tiers
    """
    
    base_path: Path
    config: ChunkConfig = field(default_factory=ChunkConfig)
    
    # Injected dependencies
    summarizer: "Summarizer | None" = None
    embedder: "Embedder | None" = None
    
    # State
    _chunks: dict[str, Chunk] = field(default_factory=dict)
    _turn_count: int = 0
    
    def __post_init__(self) -> None:
        self._ensure_dirs()
    
    def _ensure_dirs(self) -> None:
        """Create chunk storage directories."""
        (self.base_path / "hot").mkdir(parents=True, exist_ok=True)
        (self.base_path / "warm").mkdir(parents=True, exist_ok=True)
        (self.base_path / "cold").mkdir(parents=True, exist_ok=True)
        (self.base_path / "archive").mkdir(parents=True, exist_ok=True)
    
    # === Chunk Creation ===
    
    def add_turns(self, turns: list[Turn]) -> list[str]:
        """Add turns and create chunks as needed.
        
        Returns IDs of any new chunks created.
        """
        new_chunk_ids = []
        
        for turn in turns:
            self._turn_count += 1
            
            # Check if we need to create a micro-chunk
            if self._turn_count % self.config.micro_chunk_size == 0:
                chunk_id = self._create_micro_chunk()
                new_chunk_ids.append(chunk_id)
                
                # Check for mini-chunk consolidation
                if self._turn_count % self.config.mini_chunk_interval == 0:
                    mini_id = self._consolidate_mini_chunk()
                    if mini_id:
                        new_chunk_ids.append(mini_id)
                
                # Check for macro-chunk consolidation
                if self._turn_count % self.config.macro_chunk_interval == 0:
                    macro_id = self._consolidate_macro_chunk()
                    if macro_id:
                        new_chunk_ids.append(macro_id)
        
        return new_chunk_ids
    
    def _create_micro_chunk(self) -> str:
        """Create a micro-chunk from the last N turns."""
        # Get turns for this chunk
        start = self._turn_count - self.config.micro_chunk_size
        end = self._turn_count
        turns = self._get_turns_range(start, end)
        
        # Calculate token count
        token_count = sum(t.token_count for t in turns)
        
        # Generate summary if enabled
        summary = ""
        if self.config.auto_summarize and self.summarizer:
            summary = self.summarizer.summarize_turns(turns)
        
        # Generate embedding if enabled
        embedding = None
        if self.config.auto_embed and self.embedder:
            embedding = self.embedder.embed(summary or self._turns_to_text(turns))
        
        # Extract key facts if enabled
        key_facts = ()
        if self.config.auto_extract_facts and self.summarizer:
            key_facts = tuple(self.summarizer.extract_facts(turns))
        
        chunk = Chunk(
            id=self._generate_chunk_id("micro", start, end),
            chunk_type=ChunkType.MICRO,
            turn_range=(start, end),
            turns=tuple(turns),
            summary=summary,
            token_count=token_count,
            embedding=embedding,
            timestamp_start=turns[0].timestamp if turns else "",
            timestamp_end=turns[-1].timestamp if turns else "",
            key_facts=key_facts,
        )
        
        self._chunks[chunk.id] = chunk
        self._save_chunk(chunk, tier="hot")
        
        # Demote older chunks if over limit
        self._maybe_demote_hot_chunks()
        
        return chunk.id
    
    def _consolidate_mini_chunk(self) -> str | None:
        """Consolidate recent micro-chunks into a mini-chunk."""
        # Find micro-chunks to consolidate
        micro_chunks = self._get_recent_micro_chunks(
            count=self.config.mini_chunk_interval // self.config.micro_chunk_size
        )
        
        if len(micro_chunks) < 2:
            return None
        
        # Merge summaries
        combined_summary = self._merge_summaries([c.summary for c in micro_chunks])
        
        # Extract themes across chunks
        themes = self._extract_themes(micro_chunks)
        
        # Combine key facts (deduplicated)
        all_facts = set()
        for c in micro_chunks:
            all_facts.update(c.key_facts)
        
        # Generate consolidated embedding
        embedding = None
        if self.config.auto_embed and self.embedder:
            embedding = self.embedder.embed(combined_summary)
        
        start = micro_chunks[0].turn_range[0]
        end = micro_chunks[-1].turn_range[1]
        
        mini_chunk = Chunk(
            id=self._generate_chunk_id("mini", start, end),
            chunk_type=ChunkType.MINI,
            turn_range=(start, end),
            summary=combined_summary,
            token_count=sum(c.token_count for c in micro_chunks),
            embedding=embedding,
            timestamp_start=micro_chunks[0].timestamp_start,
            timestamp_end=micro_chunks[-1].timestamp_end,
            themes=tuple(themes),
            key_facts=tuple(all_facts),
            child_chunk_ids=tuple(c.id for c in micro_chunks),
        )
        
        self._chunks[mini_chunk.id] = mini_chunk
        self._save_chunk(mini_chunk, tier="warm")
        
        return mini_chunk.id
    
    def _consolidate_macro_chunk(self) -> str | None:
        """Consolidate mini-chunks into a macro-chunk."""
        # Find mini-chunks to consolidate
        mini_chunks = self._get_recent_mini_chunks(
            count=self.config.macro_chunk_interval // self.config.mini_chunk_interval
        )
        
        if len(mini_chunks) < 2:
            return None
        
        # High-level summary
        executive_summary = self._generate_executive_summary(mini_chunks)
        
        # Consolidated themes
        all_themes = set()
        for c in mini_chunks:
            all_themes.update(c.themes)
        
        # Key facts (promote to learnings)
        all_facts = set()
        for c in mini_chunks:
            all_facts.update(c.key_facts)
        
        # Archive underlying content if configured
        if self.config.archive_cold_content:
            self._archive_chunks(mini_chunks)
        
        start = mini_chunks[0].turn_range[0]
        end = mini_chunks[-1].turn_range[1]
        
        macro_chunk = Chunk(
            id=self._generate_chunk_id("macro", start, end),
            chunk_type=ChunkType.MACRO,
            turn_range=(start, end),
            summary=executive_summary,
            token_count=sum(c.token_count for c in mini_chunks),
            timestamp_start=mini_chunks[0].timestamp_start,
            timestamp_end=mini_chunks[-1].timestamp_end,
            themes=tuple(all_themes),
            key_facts=tuple(all_facts),
            child_chunk_ids=tuple(c.id for c in mini_chunks),
        )
        
        self._chunks[macro_chunk.id] = macro_chunk
        self._save_chunk(macro_chunk, tier="cold")
        
        return macro_chunk.id
    
    # === Tier Management ===
    
    def _maybe_demote_hot_chunks(self) -> None:
        """Demote oldest hot chunks to warm tier."""
        hot_chunks = self._get_hot_chunks()
        
        while len(hot_chunks) > self.config.hot_chunks:
            oldest = hot_chunks.pop(0)
            self._demote_to_warm(oldest)
    
    def _demote_to_warm(self, chunk: Chunk) -> None:
        """Convert chunk to warm tier format."""
        if self.config.warm_format == "ctf":
            # Convert turns to CTF format (Compact Turn Format)
            ctf_content = CTFEncoder.encode_turns(chunk.turns)
            
            # Use dataclasses.replace() for immutable update
            warm_chunk = replace(
                chunk,
                turns=None,  # Clear full turns
                content_ctf=ctf_content,
            )
        else:
            warm_chunk = chunk
        
        self._chunks[chunk.id] = warm_chunk
        self._move_chunk(chunk.id, from_tier="hot", to_tier="warm")
    
    # === Retrieval ===
    
    def get_relevant_chunks(
        self,
        query: str,
        limit: int = 5,
        include_hot: bool = True,
    ) -> list[Chunk]:
        """Retrieve chunks most relevant to query.
        
        Uses embedding similarity for semantic search.
        Falls back to recency-based retrieval if no embedder configured.
        """
        if not self.embedder:
            # Explicit warning so users know semantic search is disabled
            import warnings
            warnings.warn(
                "ChunkManager: No embedder configured. "
                "Falling back to recency-based retrieval. "
                "Set auto_embed=True and provide an embedder for semantic search.",
                UserWarning,
                stacklevel=2,
            )
            return self._get_recent_chunks(limit)
        
        query_embedding = self.embedder.embed(query)
        
        # Score all chunks by similarity
        scored = []
        for chunk in self._chunks.values():
            if chunk.embedding:
                score = self._cosine_similarity(query_embedding, chunk.embedding)
                scored.append((score, chunk))
        
        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)
        
        return [chunk for _, chunk in scored[:limit]]
    
    def expand_chunk(self, chunk_id: str) -> Chunk:
        """Expand a compressed chunk to full content.
        
        For warm tier: decode CTF back to turns
        For cold tier: load from archive
        """
        chunk = self._chunks.get(chunk_id)
        if not chunk:
            raise KeyError(f"Chunk not found: {chunk_id}")
        
        if chunk.turns:
            # Already expanded
            return chunk
        
        if chunk.content_ctf:
            # Decode CTF (Compact Turn Format)
            turns = CTFDecoder.decode_turns(chunk.content_ctf)
            # Use dataclasses.replace() for immutable frozen dataclass
            return replace(chunk, turns=tuple(turns))
        
        if chunk.content_ref:
            # Load from archive
            return self._load_from_archive(chunk.content_ref)
        
        raise ValueError(f"Cannot expand chunk {chunk_id}: no content source")
    
    def _load_from_archive(self, archive_ref: str) -> Chunk:
        """Load full chunk content from cold archive.
        
        Archive format: YYYY-MM-DD.jsonl.zst (zstd-compressed JSONL)
        """
        import json
        
        archive_path = self.base_path / "archive" / archive_ref
        
        # Try zstd first, fall back to gzip
        if archive_path.with_suffix(".jsonl.zst").exists():
            try:
                import zstd
                with open(archive_path.with_suffix(".jsonl.zst"), "rb") as f:
                    data = json.loads(zstd.decompress(f.read()))
            except ImportError:
                raise RuntimeError("zstd required for archive retrieval")
        elif archive_path.with_suffix(".jsonl.gz").exists():
            import gzip
            with gzip.open(archive_path.with_suffix(".jsonl.gz"), "rt") as f:
                data = json.load(f)
        else:
            raise FileNotFoundError(f"Archive not found: {archive_ref}")
        
        # Reconstruct chunk from archived data
        from sunwell.headspace.turn import Turn, TurnType
        
        turns = tuple(
            Turn(
                content=t["content"],
                turn_type=TurnType(t["turn_type"]),
                timestamp=t["timestamp"],
                parent_ids=tuple(t.get("parent_ids", [])),
            )
            for t in data.get("turns", [])
        )
        
        return Chunk(
            id=data["chunk_id"],
            chunk_type=ChunkType(data["chunk_type"]),
            turn_range=tuple(data["turn_range"]),
            turns=turns,
            summary=data.get("summary", ""),
            token_count=data.get("token_count", 0),
            timestamp_start=data.get("timestamp_start", ""),
            timestamp_end=data.get("timestamp_end", ""),
            themes=tuple(data.get("themes", [])),
            key_facts=tuple(data.get("key_facts", [])),
        )
    
    def get_context_window(
        self,
        max_tokens: int,
        query: str | None = None,
    ) -> list[Chunk | Turn]:
        """Build context window within token budget.
        
        Strategy:
        1. Always include hot tier (most recent)
        2. Add relevant warm chunks by similarity
        3. Add macro summaries for broad context
        """
        context = []
        token_budget = max_tokens
        
        # 1. Hot tier first (always included)
        for chunk in self._get_hot_chunks():
            if chunk.token_count <= token_budget:
                context.append(chunk)
                token_budget -= chunk.token_count
        
        # 2. Relevant warm chunks
        if query and token_budget > 0:
            relevant = self.get_relevant_chunks(query, limit=3, include_hot=False)
            for chunk in relevant:
                if chunk.token_count <= token_budget:
                    context.append(chunk)
                    token_budget -= chunk.token_count
        
        # 3. Macro summaries for broad context (cheap)
        for chunk in self._get_macro_chunks():
            summary_tokens = len(chunk.summary.split()) * 1.3  # Rough estimate
            if summary_tokens <= token_budget:
                context.append(ChunkSummary(
                    chunk_id=chunk.id,
                    chunk_type=chunk.chunk_type,
                    turn_range=chunk.turn_range,
                    summary=chunk.summary,
                    themes=chunk.themes,
                    token_count=int(summary_tokens),
                ))
                token_budget -= summary_tokens
        
        return context
    
    # === Helper Methods ===
    
    def _generate_chunk_id(self, prefix: str, start: int, end: int) -> str:
        """Generate unique chunk ID."""
        import hashlib
        content = f"{prefix}:{start}:{end}:{self._turn_count}"
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    def _cosine_similarity(
        self,
        a: tuple[float, ...],
        b: tuple[float, ...],
    ) -> float:
        """Compute cosine similarity between embeddings."""
        import math
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0
    
    # ... additional helper methods
```

### 4. Compact Turn Format (CTF)

CTF is a **simple, line-oriented format** designed specifically for Sunwell's warm-tier storage. It eliminates JSON overhead by using a header + TSV structure.

**Design goals:**
- Zero external dependencies
- Human-readable for debugging
- 30-50% token reduction vs JSON
- Trivial to implement and test

```python
# src/sunwell/headspace/ctf.py

"""Compact Turn Format (CTF) - Token-efficient storage for conversation turns.

CTF uses a header-based schema followed by tab-separated values.
This eliminates repeated keys and JSON syntax overhead.

JSON (~18 tokens per turn):
[
  {"role": "user", "content": "hello", "timestamp": "2026-01-15T10:00:00"},
  {"role": "assistant", "content": "hi there", "timestamp": "2026-01-15T10:00:01"}
]

CTF (~10 tokens per turn):
#CTF v1 turns=2 fields=role,content,timestamp,model
user	hello	2026-01-15T10:00:00	-
assistant	hi there	2026-01-15T10:00:01	gpt-4o

Token savings: ~40% for typical conversation data.
"""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.headspace.turn import Turn

# Field separator (tab) and record separator (newline)
FIELD_SEP = "\t"
RECORD_SEP = "\n"
NULL_VALUE = "-"
CTF_VERSION = "1"


class CTFEncoder:
    """Encode turns to Compact Turn Format."""
    
    @staticmethod
    def encode_turns(turns: tuple["Turn", ...]) -> str:
        """Convert turns to CTF format.
        
        Achieves ~40% token reduction for typical conversation data.
        """
        if not turns:
            return ""
        
        fields = ["role", "content", "timestamp", "model"]
        
        # Header line
        header = f"#CTF v{CTF_VERSION} turns={len(turns)} fields={','.join(fields)}"
        
        # Data lines
        lines = [header]
        for turn in turns:
            # Escape content: replace tabs/newlines, truncate if needed
            content = CTFEncoder._escape_content(turn.content)
            
            row = FIELD_SEP.join([
                turn.turn_type.value,
                content,
                turn.timestamp,
                turn.model or NULL_VALUE,
            ])
            lines.append(row)
        
        return RECORD_SEP.join(lines)
    
    @staticmethod
    def _escape_content(content: str, max_len: int = 2000) -> str:
        """Escape and truncate content for CTF storage."""
        # Truncate long content
        if len(content) > max_len:
            content = content[:max_len] + "…[truncated]"
        
        # Replace field/record separators
        content = content.replace("\t", "␉").replace("\n", "␊")
        
        return content


class CTFDecoder:
    """Decode turns from Compact Turn Format."""
    
    @staticmethod
    def decode_turns(ctf_content: str) -> list["Turn"]:
        """Parse CTF back to Turn objects."""
        from sunwell.headspace.turn import Turn, TurnType
        
        if not ctf_content or not ctf_content.startswith("#CTF"):
            raise ValueError("Invalid CTF format: missing header")
        
        lines = ctf_content.strip().split(RECORD_SEP)
        if len(lines) < 2:
            return []
        
        # Parse header
        header = lines[0]
        # Extract field order from header
        fields_match = header.split("fields=")
        if len(fields_match) < 2:
            raise ValueError("Invalid CTF header: missing fields")
        fields = fields_match[1].split(",")
        
        # Parse data rows
        turns = []
        for line in lines[1:]:
            if not line.strip():
                continue
            
            values = line.split(FIELD_SEP)
            if len(values) < len(fields):
                continue  # Skip malformed rows
            
            # Build turn from fields
            data = dict(zip(fields, values))
            
            # Unescape content
            content = CTFDecoder._unescape_content(data.get("content", ""))
            
            turns.append(Turn(
                content=content,
                turn_type=TurnType(data.get("role", "user")),
                timestamp=data.get("timestamp", ""),
                model=data.get("model") if data.get("model") != NULL_VALUE else None,
            ))
        
        return turns
    
    @staticmethod
    def _unescape_content(content: str) -> str:
        """Restore escaped content."""
        return content.replace("␉", "\t").replace("␊", "\n")


def encode_chunk_summaries(summaries: list[dict]) -> str:
    """Encode chunk summaries to CTF."""
    if not summaries:
        return ""
    
    fields = ["chunk_id", "turn_range", "summary", "themes"]
    header = f"#CTF v{CTF_VERSION} type=summaries count={len(summaries)} fields={','.join(fields)}"
    
    lines = [header]
    for s in summaries:
        row = FIELD_SEP.join([
            s.get("chunk_id", ""),
            s.get("turn_range", ""),
            CTFEncoder._escape_content(s.get("summary", "")),
            "|".join(s.get("themes", [])),
        ])
        lines.append(row)
    
    return RECORD_SEP.join(lines)


def decode_chunk_summaries(ctf_content: str) -> list[dict]:
    """Decode chunk summaries from CTF."""
    if not ctf_content or not ctf_content.startswith("#CTF"):
        return []
    
    lines = ctf_content.strip().split(RECORD_SEP)
    summaries = []
    
    for line in lines[1:]:
        if not line.strip():
            continue
        values = line.split(FIELD_SEP)
        if len(values) >= 4:
            summaries.append({
                "chunk_id": values[0],
                "turn_range": values[1],
                "summary": CTFDecoder._unescape_content(values[2]),
                "themes": values[3].split("|") if values[3] else [],
            })
    
    return summaries
```

**Why CTF over external formats:**

| Aspect | JSON | MessagePack | CTF |
|--------|------|-------------|-----|
| Dependencies | stdlib | `msgpack` | None |
| Token efficiency | Baseline | ~30% smaller | ~40% smaller |
| Human-readable | ✅ | ❌ | ✅ |
| Debug-friendly | ✅ | ❌ | ✅ |
| Complexity | N/A | Serialization | ~100 LOC |

**Token comparison example:**

```
# JSON: 47 tokens
[{"role":"user","content":"How do I use the CLI?","timestamp":"2026-01-15T10:00:00","model":null},{"role":"assistant","content":"Run sunwell --help","timestamp":"2026-01-15T10:00:01","model":"gpt-4o"}]

# CTF: 28 tokens
#CTF v1 turns=2 fields=role,content,timestamp,model
user	How do I use the CLI?	2026-01-15T10:00:00	-
assistant	Run sunwell --help	2026-01-15T10:00:01	gpt-4o
```

### 5. Summarization Service

```python
# src/sunwell/headspace/summarizer.py

from dataclasses import dataclass
from sunwell.headspace.turn import Turn
from sunwell.models.protocol import ModelProtocol


@dataclass
class Summarizer:
    """Generate summaries and extract facts from turns.
    
    Uses LLM for intelligent summarization.
    Falls back to heuristics if no model available.
    """
    
    model: ModelProtocol | None = None
    
    async def summarize_turns(self, turns: tuple[Turn, ...]) -> str:
        """Generate a concise summary of turns."""
        if not turns:
            return ""
        
        if self.model:
            return await self._llm_summarize(turns)
        else:
            return self._heuristic_summarize(turns)
    
    async def _llm_summarize(self, turns: tuple[Turn, ...]) -> str:
        """Use LLM to generate summary."""
        conversation = "\n".join(
            f"{t.turn_type.value}: {t.content[:500]}"
            for t in turns
        )
        
        prompt = f"""Summarize this conversation segment in 2-3 sentences.
Focus on: key topics discussed, decisions made, information shared.

Conversation:
{conversation}

Summary:"""
        
        result = await self.model.generate(prompt)
        return result.text.strip()
    
    def _heuristic_summarize(self, turns: tuple[Turn, ...]) -> str:
        """Simple heuristic summary without LLM."""
        user_turns = [t for t in turns if t.turn_type.value == "user"]
        
        if not user_turns:
            return "Assistant responses only"
        
        # Extract key phrases from user messages
        topics = []
        for turn in user_turns[:3]:  # First 3 user messages
            # Take first sentence or first 50 chars
            first_sentence = turn.content.split('.')[0][:50]
            topics.append(first_sentence)
        
        return f"Discussion of: {'; '.join(topics)}"
    
    async def extract_facts(self, turns: tuple[Turn, ...]) -> list[str]:
        """Extract key facts that should be remembered."""
        if not self.model:
            return []
        
        conversation = "\n".join(
            f"{t.turn_type.value}: {t.content[:300]}"
            for t in turns
        )
        
        prompt = f"""Extract key facts from this conversation that should be remembered.
Return as a list, one fact per line. Only include concrete, reusable information.
Examples: user preferences, project names, technical decisions, constraints mentioned.

Conversation:
{conversation}

Key facts (one per line):"""
        
        result = await self.model.generate(prompt)
        
        # Parse facts from response
        facts = []
        for line in result.text.strip().split("\n"):
            line = line.strip().lstrip("- •")
            if line and len(line) > 5:
                facts.append(line)
        
        return facts[:10]  # Cap at 10 facts per chunk
    
    async def extract_themes(self, chunks: list) -> list[str]:
        """Identify themes across multiple chunks."""
        if not self.model:
            return []
        
        summaries = "\n".join(c.summary for c in chunks if c.summary)
        
        prompt = f"""Identify 3-5 main themes from these conversation summaries.
Return as a list of single words or short phrases.

Summaries:
{summaries}

Themes:"""
        
        result = await self.model.generate(prompt)
        
        themes = []
        for line in result.text.strip().split("\n"):
            theme = line.strip().lstrip("- •").lower()
            if theme and len(theme) < 30:
                themes.append(theme)
        
        return themes[:5]
    
    async def generate_executive_summary(self, chunks: list) -> str:
        """Generate high-level summary for macro-chunk."""
        if not self.model:
            summaries = [c.summary for c in chunks if c.summary]
            return " | ".join(summaries[:3])
        
        summaries = "\n".join(
            f"- {c.summary}" for c in chunks if c.summary
        )
        
        prompt = f"""Create a high-level executive summary (3-4 sentences) of this extended conversation.
Focus on: main accomplishments, key decisions, important context for future reference.

Segment summaries:
{summaries}

Executive summary:"""
        
        result = await self.model.generate(prompt)
        return result.text.strip()
```

### 6. Updated HeadspaceStore Integration

```python
# src/sunwell/headspace/store.py (updated)

from sunwell.headspace.chunk_manager import ChunkManager
from sunwell.headspace.config import ChunkConfig


@dataclass
class HeadspaceStore:
    """Persistent conversation memory with hierarchical chunking.
    
    Updated to use ChunkManager for progressive compression.
    """
    
    base_path: Path
    config: StorageConfig = field(default_factory=StorageConfig)
    chunk_config: ChunkConfig = field(default_factory=ChunkConfig)
    
    # Components
    _chunk_manager: ChunkManager | None = field(default=None, init=False)
    _hot_dag: ConversationDAG = field(default_factory=ConversationDAG)
    
    def __post_init__(self) -> None:
        self.base_path = Path(self.base_path)
        self._ensure_dirs()
        self._chunk_manager = ChunkManager(
            base_path=self.base_path / "chunks",
            config=self.chunk_config,
        )
    
    def add_turn(self, turn: Turn) -> str:
        """Add a turn to hot storage and chunk manager."""
        turn_id = self._hot_dag.add_turn(turn)
        
        # Update token count if not set
        if turn.token_count == 0:
            turn = self._estimate_token_count(turn)
        
        # Feed to chunk manager for hierarchical processing
        if self._chunk_manager:
            self._chunk_manager.add_turns([turn])
        
        return turn_id
    
    def get_context_for_prompt(
        self,
        query: str,
        max_tokens: int = 4000,
    ) -> str:
        """Get relevant context for a prompt, within token budget."""
        if not self._chunk_manager:
            # Fall back to simple retrieval
            return self._simple_context(query, max_tokens)
        
        context_items = self._chunk_manager.get_context_window(
            max_tokens=max_tokens,
            query=query,
        )
        
        # Format for prompt
        parts = []
        for item in context_items:
            if isinstance(item, Chunk) and item.turns:
                # Full turns
                for turn in item.turns:
                    parts.append(f"{turn.turn_type.value}: {turn.content}")
            elif isinstance(item, ChunkSummary):
                # Summary only
                parts.append(f"[Earlier: {item.summary}]")
            elif hasattr(item, 'summary'):
                parts.append(f"[Context: {item.summary}]")
        
        return "\n\n".join(parts)
    
    def _estimate_token_count(self, turn: Turn) -> Turn:
        """Estimate token count for a turn."""
        # Rough estimate: ~1.3 tokens per word
        word_count = len(turn.content.split())
        estimated = int(word_count * 1.3)
        
        return Turn(
            content=turn.content,
            turn_type=turn.turn_type,
            timestamp=turn.timestamp,
            parent_ids=turn.parent_ids,
            token_count=estimated,
            model=turn.model,
            confidence=turn.confidence,
            tags=turn.tags,
        )
```

---

## Storage Layout

```
.sunwell/memory/
├── sessions/                    # Named session metadata
│   ├── writer.json
│   └── writer_dag.json
│
├── chunks/                      # Hierarchical chunk storage
│   ├── hot/                     # Full JSON, last 2 micro-chunks
│   │   ├── micro_abc123.json
│   │   └── micro_def456.json
│   │
│   ├── warm/                    # CTF-encoded, summaries
│   │   ├── micro_111222.ctf     # Compact Turn Format
│   │   ├── micro_333444.ctf
│   │   └── mini_555666.json     # Consolidated summary
│   │
│   ├── cold/                    # Summaries + embeddings only
│   │   └── macro_777888.json
│   │
│   └── archive/                 # Full content backup
│       └── 2026-01-15.jsonl.zst
│
├── embeddings/                  # Vector storage for retrieval
│   └── chunks.npy
│
└── learnings/                   # Auto-extracted facts
    └── session_writer.json
```

---

## CTF (Compact Turn Format) Specification

CTF is a simple, zero-dependency format for token-efficient turn storage.

### Design Principles

1. **Header declares schema** — Field names appear once, not per-record
2. **Tab-separated values** — Clean delimiter, rare in natural text
3. **Human-readable** — Debug without special tools
4. **Escape conventions** — Handle embedded tabs/newlines safely

### Format Grammar

```
CTF_FILE    := HEADER NEWLINE (DATA_ROW NEWLINE)*
HEADER      := "#CTF v" VERSION " " METADATA
METADATA    := KEY "=" VALUE (" " KEY "=" VALUE)*
DATA_ROW    := FIELD (TAB FIELD)*
FIELD       := ESCAPED_TEXT
```

### Turn Encoding Example

**JSON** (verbose, ~47 tokens):
```json
[
  {"role": "user", "content": "who are you", "timestamp": "2026-01-15T16:20:06", "model": null},
  {"role": "assistant", "content": "I'm an AI...", "timestamp": "2026-01-15T16:20:09", "model": "gpt-4o"}
]
```

**CTF** (compact, ~28 tokens):
```
#CTF v1 turns=2 fields=role,content,timestamp,model
user	who are you	2026-01-15T16:20:06	-
assistant	I'm an AI language model...	2026-01-15T16:20:09	gpt-4o
```

**Token savings**: ~40% reduction for typical turn data.

### Escape Conventions

| Character | Escaped As | Notes |
|-----------|------------|-------|
| Tab (`\t`) | `␉` (U+2409) | Field separator |
| Newline (`\n`) | `␊` (U+240A) | Record separator |
| Null/None | `-` | Null marker |

### Chunk Summary Encoding

```
#CTF v1 type=summaries count=2 fields=chunk_id,turn_range,summary,themes
micro_abc123	0-10	User introduced themselves as lb	identity|capabilities
micro_def456	10-20	Tested file creation limitations	tools|limitations
```

### Versioning

Version `1` is the initial specification. Future versions may add:
- Binary content encoding (base64 field prefix)
- Compression hints in header
- Checksum validation

---

## Retrieval Strategy

### Query Flow

```
User query: "What did we discuss about file saving?"
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. EMBED QUERY                                               │
│    query_vec = embed("What did we discuss about file...")    │
└─────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. SEARCH HOT TIER (always included)                         │
│    → Last 20 turns, full content                             │
└─────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. SEARCH WARM SUMMARIES                                     │
│    → cosine_sim(query_vec, chunk.embedding)                  │
│    → Return top-3 relevant chunks                            │
└─────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. EXPAND IF NEEDED                                          │
│    → Decode CTF → full turns (on demand)                     │
└─────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. ADD MACRO SUMMARIES                                       │
│    → Include executive summaries for broad context           │
└─────────────────────────────────────────────────────────────┘
                    │
                    ▼
              CONTEXT WINDOW
```

---

## Implementation Plan

### Phase 1: Foundation (Week 1)

- [ ] Add `Chunk`, `ChunkType`, `ChunkSummary` types
- [ ] Create `ChunkConfig` with defaults
- [ ] Implement basic `ChunkManager` without summarization
- [ ] Add token counting to `Turn` (fix the zeros)

**Exit criteria**: Micro-chunks created every 10 turns, stored as JSON.

### Phase 2: CTF Integration (Week 2)

- [ ] Create `src/sunwell/headspace/ctf.py` module (~100 LOC)
- [ ] Implement `CTFEncoder.encode_turns()` with escaping
- [ ] Implement `CTFDecoder.decode_turns()` with validation
- [ ] Add warm tier demotion with CTF conversion
- [ ] Benchmark token savings vs JSON (target: >30%)
- [ ] Add unit tests for edge cases (tabs, newlines, Unicode)

**Exit criteria**: Warm tier uses CTF, achieves >30% token reduction, all tests pass.

### Phase 3: Summarization (Week 3)

- [ ] Implement `Summarizer` with LLM integration
- [ ] Add heuristic fallback for no-model scenarios
- [ ] Generate summaries on micro-chunk creation
- [ ] Extract key facts to learnings

**Exit criteria**: Every chunk has auto-generated summary.

### Phase 4: Hierarchical Consolidation (Week 4)

- [ ] Implement mini-chunk consolidation (every 25 turns)
- [ ] Implement macro-chunk consolidation (every 100 turns)
- [ ] Add theme extraction across chunks
- [ ] Generate executive summaries

**Exit criteria**: Full pyramid operational with 10 → 25 → 100 consolidation.

### Phase 5: Embedding-Based Retrieval (Week 5)

- [ ] Add embedding generation on chunk creation
- [ ] Implement `get_relevant_chunks()` with cosine similarity
- [ ] Implement `get_context_window()` with token budgeting
- [ ] Add lazy chunk expansion

**Exit criteria**: Semantic retrieval returns relevant historical context.

### Phase 6: Archive & Cleanup (Week 6)

- [ ] Implement cold tier archival (zstd compression)
- [ ] Add `expand_chunk()` for archive retrieval
- [ ] Implement retention policies
- [ ] Add storage statistics and monitoring

**Exit criteria**: Complete lifecycle: hot → warm → cold → archive.

---

## Configuration Reference

```yaml
# ~/.sunwell/config.yaml

memory:
  # Chunk sizes
  micro_chunk_size: 10
  mini_chunk_interval: 25
  macro_chunk_interval: 100
  
  # Hot tier
  hot_chunks: 2              # Keep last 2 micro-chunks hot
  hot_max_tokens: 50000      # Alternative: token budget
  
  # Formats
  warm_format: ctf           # ctf | json (CTF = Compact Turn Format)
  cold_format: summary_only  # summary_only | ctf
  
  # Auto-processing
  auto_summarize: true
  auto_extract_facts: true
  auto_embed: true
  
  # Cost optimization
  summarization_strategy: heuristic  # heuristic | llm | local
  summarization_model: null          # Override model for summarization
  defer_summarization: true          # Summarize only on demotion
  
  # Embeddings
  embedding_provider: local          # local | openai
  embedding_model: all-MiniLM-L6-v2  # For local provider
  
  # Retention
  archive_cold_content: true
  cold_retention_days: 90    # 0 = forever
```

---

## Benchmarks (Expected)

| Metric | Current | With RFC-013 |
|--------|---------|--------------|
| Token cost for 100-turn context | ~15,000 | ~6,000 (60% reduction) |
| Storage for 1000 turns | ~2MB JSON | ~800KB (CTF + compression) |
| Retrieval latency (semantic) | N/A | <100ms |
| Context quality (relevance) | Recency only | Semantic + recency |

---

## Cost Analysis: Summarization Trade-offs

### LLM Summarization Costs

Summarization uses LLM calls, which have their own token costs. The system must ensure **compression savings exceed summarization costs**.

**Per 100 turns (10 micro-chunks):**

| Operation | Input Tokens | Output Tokens | Cost (GPT-4o) |
|-----------|--------------|---------------|---------------|
| 10× micro summaries | ~5,000 | ~500 | ~$0.015 |
| 4× mini consolidations | ~400 | ~200 | ~$0.002 |
| 1× macro summary | ~200 | ~100 | ~$0.001 |
| **Total** | ~5,600 | ~800 | **~$0.018** |

**Break-even analysis:**
- If 100 turns = 15,000 tokens at $0.01/1K = $0.15 per context window
- Compressed to 6,000 tokens = $0.06 per context window
- Savings per query: $0.09
- Break-even: 1 query (summarization cost << savings)

**Recommendation**: Summarization ROI is positive after **first retrieval**. For sessions with repeated context needs, savings compound quickly.

### Strategies to Reduce Summarization Cost

```python
@dataclass
class ChunkConfig:
    # ...existing fields...
    
    # Cost optimization
    summarization_strategy: Literal["llm", "heuristic", "local"] = "heuristic"
    """
    - llm: Use main model (best quality, highest cost)
    - heuristic: Rule-based extraction (free, lower quality)
    - local: Use local model like T5-small (free, good quality)
    """
    
    summarization_model: str | None = None
    """Override model for summarization. Use cheaper model than main chat."""
    
    defer_summarization: bool = True
    """Generate summaries only when chunk is demoted to warm tier."""
```

**Heuristic summarization** (default, zero cost):

```python
def _heuristic_summarize(self, turns: tuple[Turn, ...]) -> str:
    """Extract key phrases without LLM."""
    user_turns = [t for t in turns if t.turn_type.value == "user"]
    
    # First user message often states intent
    if user_turns:
        first_msg = user_turns[0].content[:100]
        return f"User request: {first_msg.split('.')[0]}"
    
    return f"Conversation segment ({len(turns)} turns)"
```

### Embedding Costs

| Provider | Model | Dimensions | Cost/1K tokens |
|----------|-------|------------|----------------|
| OpenAI | text-embedding-3-small | 1536 | $0.00002 |
| OpenAI | text-embedding-3-large | 3072 | $0.00013 |
| Local | sentence-transformers | 384 | Free |

**Recommendation**: Default to local embeddings (`sentence-transformers/all-MiniLM-L6-v2`) for zero-cost operation. OpenAI for higher quality when API key available.

---

## Open Questions

1. **Summarization model**: Should we use the same model as chat, or a smaller/cheaper model for summarization?
   
   **Proposal**: Default to same model, add `summarization_model` config override.

2. **Embedding provider**: Which embedding model? OpenAI `text-embedding-3-small` vs local alternatives?
   
   **Proposal**: Abstract via `EmbeddingProtocol`, default to OpenAI if API key available.

3. **TOON adoption**: Use TOON for warm tier only, or also for feeding context to LLM?
   
   **Proposal**: TOON for storage, convert to natural language for LLM context.

4. **Fact extraction accuracy**: How to validate auto-extracted facts?
   
   **Proposal**: Mark as `auto_extracted`, allow user confirmation via `/learn` command.

---

## References

### Sunwell
- [RFC-012: Tool Calling](./RFC-012-tool-calling.md)
- [HeadspaceStore Implementation](./src/sunwell/headspace/store.py)
- [Turn dataclass](./src/sunwell/headspace/turn.py)

### Related Work
- [MessagePack](https://msgpack.org/) — Binary serialization (alternative considered)
- [tiktoken](https://github.com/openai/tiktoken) — Accurate token counting for OpenAI models
- [sentence-transformers](https://www.sbert.net/) — Local embedding models

### Compression Techniques
- [zstd](https://github.com/facebook/zstd) — Fast compression for cold storage
- [Content-addressable storage](https://en.wikipedia.org/wiki/Content-addressable_storage) — Turn deduplication strategy

---

## Changelog

| Date | Change |
|:-----|:-------|
| 2026-01-15 | Initial draft |
| 2026-01-15 | Added TOON encoder/decoder specification |
| 2026-01-15 | Added hierarchical consolidation (10 → 25 → 100) |
| 2026-01-15 | Added summarization service design |
| 2026-01-15 | Added retrieval strategy with embedding search |
| 2026-01-15 | **Breaking**: Replaced TOON with CTF (Compact Turn Format) — zero dependencies |
| 2026-01-15 | Added cost analysis for LLM summarization trade-offs |
| 2026-01-15 | Added `_load_from_archive()` implementation |
| 2026-01-15 | Fixed frozen dataclass mutation (use `dataclasses.replace()`) |
| 2026-01-15 | Added explicit warning for missing embedder fallback |
| 2026-01-15 | Added configurable summarization strategy (heuristic/llm/local) |
| 2026-01-15 | Added local embedding provider option (sentence-transformers) |