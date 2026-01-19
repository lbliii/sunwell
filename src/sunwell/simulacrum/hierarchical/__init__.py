"""Hierarchical memory (RFC-013).

RFC-025: Extracted from root simulacrum module.
"""

from sunwell.simulacrum.hierarchical.chunk_manager import ChunkManager
from sunwell.simulacrum.hierarchical.chunks import Chunk, ChunkSummary, ChunkType
from sunwell.simulacrum.hierarchical.config import DEFAULT_CHUNK_CONFIG, ChunkConfig
from sunwell.simulacrum.hierarchical.ctf import (
    CTFDecoder,
    CTFEncoder,
    decode_chunk_summaries,
    encode_chunk_summaries,
)
from sunwell.simulacrum.hierarchical.summarizer import Summarizer

__all__ = [
    "Chunk",
    "ChunkType",
    "ChunkSummary",
    "ChunkConfig",
    "DEFAULT_CHUNK_CONFIG",
    "ChunkManager",
    "CTFEncoder",
    "CTFDecoder",
    "encode_chunk_summaries",
    "decode_chunk_summaries",
    "Summarizer",
]
