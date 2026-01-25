"""Hierarchical memory (RFC-013).

RFC-025: Extracted from root simulacrum module.
"""

from sunwell.memory.simulacrum.hierarchical.chunk_manager import ChunkManager
from sunwell.memory.simulacrum.hierarchical.chunks import Chunk, ChunkSummary, ChunkType
from sunwell.memory.simulacrum.hierarchical.config import DEFAULT_CHUNK_CONFIG, ChunkConfig
from sunwell.memory.simulacrum.hierarchical.ctf import (
    CTFDecoder,
    CTFEncoder,
    decode_chunk_summaries,
    encode_chunk_summaries,
)
from sunwell.memory.simulacrum.hierarchical.summarizer import Summarizer

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
