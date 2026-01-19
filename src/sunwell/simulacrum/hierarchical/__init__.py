"""Hierarchical memory (RFC-013).

RFC-025: Extracted from root simulacrum module.
"""

from sunwell.simulacrum.hierarchical.chunks import Chunk, ChunkType, ChunkSummary
from sunwell.simulacrum.hierarchical.config import ChunkConfig, DEFAULT_CHUNK_CONFIG
from sunwell.simulacrum.hierarchical.chunk_manager import ChunkManager
from sunwell.simulacrum.hierarchical.ctf import (
    CTFEncoder,
    CTFDecoder,
    encode_chunk_summaries,
    decode_chunk_summaries,
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
