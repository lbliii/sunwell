"""Configuration for hierarchical chunking and memory management."""


from dataclasses import dataclass
from typing import Literal


@dataclass
class ChunkConfig:
    """Configuration for hierarchical conversation chunking.

    Implements RFC-013: Hierarchical Memory with Progressive Compression.
    """

    # Chunk sizes
    micro_chunk_size: int = 10
    """Number of turns per micro-chunk."""

    mini_chunk_interval: int = 25
    """Consolidate micro-chunks every N turns."""

    macro_chunk_interval: int = 100
    """Major consolidation every N turns."""

    # Hot tier limits
    hot_chunks: int = 2
    """Number of micro-chunks to keep in hot tier (full JSON)."""

    hot_max_tokens: int = 50_000
    """Maximum tokens allowed in hot tier before demotion."""

    # Format preferences
    warm_format: Literal["json", "ctf"] = "ctf"
    """Storage format for warm tier. CTF = Compact Turn Format."""

    cold_format: Literal["ctf", "summary_only"] = "summary_only"
    """Storage format for cold tier (summaries or full content)."""

    # Auto-processing
    auto_summarize: bool = True
    """Generate summaries automatically when chunking."""

    auto_extract_facts: bool = True
    """Extract key facts to learnings automatically."""

    auto_embed: bool = True
    """Generate embeddings for retrieval automatically."""

    # Cost optimization (RFC-013 addition)
    summarization_strategy: Literal["llm", "heuristic", "local"] = "heuristic"
    """
    Strategy for generating summaries:
    - llm: Use main model (best quality, highest cost)
    - heuristic: Rule-based extraction (free, lower quality)
    - local: Use local model like T5-small (free, good quality)
    """

    summarization_model: str | None = None
    """Override model for summarization. Use cheaper model than main chat."""

    defer_summarization: bool = True
    """Generate summaries only when chunk is demoted to warm tier."""

    # Embedding configuration (RFC-013 addition)
    embedding_provider: Literal["local", "openai"] = "local"
    """Embedding provider: local (sentence-transformers) or openai."""

    embedding_model: str = "all-MiniLM-L6-v2"
    """Model for local embedding provider."""

    # Retention and Archiving
    archive_cold_content: bool = True
    """Keep full content in archive even when demoted to cold tier."""

    cold_retention_days: int = 90
    """Days to keep archived content (0 = forever)."""


# Default configuration instance
DEFAULT_CHUNK_CONFIG = ChunkConfig()
