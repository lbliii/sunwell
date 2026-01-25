"""Indexing response models (RFC-108)."""

from typing import Literal

from sunwell.interface.server.routes.models.base import CamelModel

IndexChunkType = Literal["function", "class", "module", "block", "prose", "scene"]


class IndexChunk(CamelModel):
    """A chunk from the index search."""

    id: str
    file_path: str
    start_line: int
    end_line: int
    content: str
    chunk_type: IndexChunkType
    name: str | None = None
    score: float


class IndexQueryResponse(CamelModel):
    """Result of an index query."""

    chunks: list[IndexChunk]
    fallback_used: bool
    query_time_ms: int
    total_chunks_searched: int
    error: str | None = None
