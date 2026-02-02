"""Tests for RFC-013 Hierarchical Memory and CTF."""

import pytest
from sunwell.memory.simulacrum.core.turn import Turn, TurnType
from sunwell.memory.simulacrum.hierarchical.ctf import CTFEncoder, CTFDecoder
from sunwell.memory.simulacrum.hierarchical.chunks import Chunk, ChunkType
from sunwell.memory.simulacrum.hierarchical.chunk_manager import ChunkManager
from sunwell.memory.simulacrum.hierarchical.config import ChunkConfig
from pathlib import Path

def test_ctf_encoding_decoding():
    """Test that CTF can round-trip turns correctly."""
    turns = (
        Turn(content="hello world", turn_type=TurnType.USER, timestamp="2026-01-15T10:00:00"),
        Turn(content="hi there\nwith newline", turn_type=TurnType.ASSISTANT, timestamp="2026-01-15T10:00:01", model="gpt-4o"),
    )
    
    encoded = CTFEncoder.encode_turns(turns)
    assert "#CTF v1" in encoded
    assert "user\thello world" in encoded
    assert "assistant\thi there␊with newline" in encoded
    
    decoded = CTFDecoder.decode_turns(encoded)
    assert len(decoded) == 2
    assert decoded[0].content == "hello world"
    assert decoded[1].content == "hi there\nwith newline"
    assert decoded[1].model == "gpt-4o"

def test_token_estimation():
    """Test Turn's token estimation logic."""
    turn = Turn(content="This is a test of five words.", turn_type=TurnType.USER)
    # 7 words * 1.3 = 9.1 -> 9 tokens
    assert turn.token_count == 9

from sunwell.memory.simulacrum.hierarchical.summarizer import Summarizer

@pytest.mark.asyncio
async def test_summarizer_heuristic():
    """Test heuristic summarization."""
    summarizer = Summarizer()
    turns = (
        Turn(content="I want to build a new app", turn_type=TurnType.USER),
        Turn(content="Sure, what kind of app?", turn_type=TurnType.ASSISTANT),
    )
    
    summary = await summarizer.summarize_turns(turns)
    assert "Discussion starting with: I want to build a new app" in summary

@pytest.mark.asyncio
async def test_chunk_manager_archival(tmp_path):
    """Test demoting to cold tier and expanding from archive."""
    manager = ChunkManager(base_path=tmp_path)
    
    turns = (
        Turn(content="archived turn", turn_type=TurnType.USER),
    )
    
    chunk_id = "cold-chunk"
    chunk = Chunk(
        id=chunk_id,
        chunk_type=ChunkType.MICRO,
        turn_range=(0, 1),
        turns=turns
    )
    
    manager._chunks[chunk_id] = chunk
    
    # Demote to macro
    manager.demote_to_macro(chunk_id)
    
    macro_chunk = manager._chunks[chunk_id]
    assert macro_chunk.turns is None
    assert macro_chunk.content_ctf is None
    assert macro_chunk.content_ref is not None
    assert macro_chunk.content_ref.endswith(".json.gz")
    
    # Expand from archive
    expanded = manager.expand_chunk(chunk_id)
    assert len(expanded.turns) == 1
    assert expanded.turns[0].content == "archived turn"

def test_chunk_manager_stats(tmp_path):
    """Test storage statistics reporting."""
    manager = ChunkManager(base_path=tmp_path)
    manager._chunks["c1"] = Chunk(id="c1", chunk_type=ChunkType.MICRO, turn_range=(0, 1), turns=(), token_count=10)
    manager._chunks["c2"] = Chunk(id="c2", chunk_type=ChunkType.MICRO, turn_range=(1, 2), content_ctf="...", token_count=20)
    
    stats = manager.stats
    assert stats["total_chunks"] == 2
    assert stats["micro_chunks"] == 1
    assert stats["total_tokens"] == 30
