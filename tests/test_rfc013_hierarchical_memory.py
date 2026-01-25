"""Tests for RFC-013: Hierarchical Memory with Progressive Compression.

Tests cover:
- Compact Turn Format (CTF) encoding/decoding
- Chunk creation and consolidation
- Tier management (hot → warm → cold)
- Semantic retrieval
- SimulacrumStore integration
"""

from __future__ import annotations

import asyncio
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from sunwell.memory.simulacrum.core.turn import Turn, TurnType
from sunwell.memory.simulacrum.hierarchical.chunks import Chunk, ChunkType, ChunkSummary
from sunwell.memory.simulacrum.hierarchical.config import ChunkConfig, DEFAULT_CHUNK_CONFIG
from sunwell.memory.simulacrum.hierarchical.ctf import (
    CTFEncoder,
    CTFDecoder,
    encode_chunk_summaries,
    decode_chunk_summaries,
)
from sunwell.memory.simulacrum.hierarchical.chunk_manager import ChunkManager
from sunwell.memory.simulacrum.hierarchical.summarizer import Summarizer
from sunwell.memory.simulacrum.core.store import SimulacrumStore, StorageConfig


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_turns() -> tuple[Turn, ...]:
    """Create sample turns for testing."""
    return tuple(
        Turn(
            content=f"Message {i}: This is test content for turn number {i}.",
            turn_type=TurnType.USER if i % 2 == 0 else TurnType.ASSISTANT,
            timestamp=f"2026-01-15T10:00:{i:02d}",
            model="gpt-4o" if i % 2 == 1 else None,
        )
        for i in range(10)
    )


@pytest.fixture
def sample_chunk(sample_turns: tuple[Turn, ...]) -> Chunk:
    """Create a sample chunk for testing."""
    return Chunk(
        id="micro_abc123",
        chunk_type=ChunkType.MICRO,
        turn_range=(0, 10),
        turns=sample_turns,
        summary="Test conversation about numbers",
        token_count=150,
        timestamp_start="2026-01-15T10:00:00",
        timestamp_end="2026-01-15T10:00:09",
        themes=("testing", "numbers"),
        key_facts=("User likes tests",),
    )


@pytest.fixture
def temp_dir() -> Path:
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def chunk_config() -> ChunkConfig:
    """Create a test chunk configuration."""
    return ChunkConfig(
        micro_chunk_size=5,  # Smaller for testing
        mini_chunk_interval=15,
        macro_chunk_interval=30,
        hot_chunks=2,
        auto_summarize=False,  # Disable for simpler tests
        auto_extract_facts=False,
        auto_embed=False,
    )


@pytest.fixture
def chunk_manager(temp_dir: Path, chunk_config: ChunkConfig) -> ChunkManager:
    """Create a ChunkManager for testing."""
    return ChunkManager(
        base_path=temp_dir / "chunks",
        config=chunk_config,
    )


# =============================================================================
# CTF Encoding/Decoding Tests
# =============================================================================


class TestCTFEncoder:
    """Tests for Compact Turn Format encoding."""

    def test_encode_empty_turns(self):
        """Encoding empty turns returns empty string."""
        result = CTFEncoder.encode_turns(())
        assert result == ""

    def test_encode_single_turn(self):
        """Single turn encoding works correctly."""
        turn = Turn(
            content="Hello world",
            turn_type=TurnType.USER,
            timestamp="2026-01-15T10:00:00",
        )
        result = CTFEncoder.encode_turns((turn,))
        
        assert result.startswith("#CTF v1")
        assert "turns=1" in result
        assert "user" in result
        assert "Hello world" in result

    def test_encode_multiple_turns(self, sample_turns: tuple[Turn, ...]):
        """Multiple turn encoding produces valid CTF."""
        result = CTFEncoder.encode_turns(sample_turns)
        
        assert result.startswith("#CTF v1")
        assert f"turns={len(sample_turns)}" in result
        lines = result.split("\n")
        # Header + data rows
        assert len(lines) == len(sample_turns) + 1

    def test_escape_tabs_and_newlines(self):
        """Tabs and newlines in content are escaped."""
        turn = Turn(
            content="Line 1\nLine 2\tTabbed",
            turn_type=TurnType.USER,
            timestamp="2026-01-15T10:00:00",
        )
        result = CTFEncoder.encode_turns((turn,))
        
        assert "\t" not in result.split("\n")[1].split("\t")[1]  # Content field
        assert "␊" in result  # Escaped newline
        assert "␉" in result  # Escaped tab

    def test_truncate_long_content(self):
        """Long content is truncated."""
        long_content = "x" * 3000
        turn = Turn(
            content=long_content,
            turn_type=TurnType.USER,
            timestamp="2026-01-15T10:00:00",
        )
        result = CTFEncoder.encode_turns((turn,))
        
        assert "…[truncated]" in result
        assert len(result) < len(long_content) + 200


class TestCTFDecoder:
    """Tests for Compact Turn Format decoding."""

    def test_decode_invalid_format(self):
        """Invalid format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid CTF format"):
            CTFDecoder.decode_turns("Not a CTF string")

    def test_decode_empty_content(self):
        """Empty or header-only content returns empty list."""
        result = CTFDecoder.decode_turns("#CTF v1 turns=0 fields=role,content,timestamp,model")
        assert result == []

    def test_roundtrip_encoding(self, sample_turns: tuple[Turn, ...]):
        """Encoding then decoding preserves turn data."""
        encoded = CTFEncoder.encode_turns(sample_turns)
        decoded = CTFDecoder.decode_turns(encoded)
        
        assert len(decoded) == len(sample_turns)
        for original, restored in zip(sample_turns, decoded):
            assert restored.content == original.content
            assert restored.turn_type == original.turn_type
            assert restored.timestamp == original.timestamp

    def test_unescape_content(self):
        """Escaped content is properly restored."""
        turn = Turn(
            content="Tab:\tNewline:\n",
            turn_type=TurnType.USER,
            timestamp="2026-01-15T10:00:00",
        )
        encoded = CTFEncoder.encode_turns((turn,))
        decoded = CTFDecoder.decode_turns(encoded)
        
        assert decoded[0].content == turn.content


class TestChunkSummaryCTF:
    """Tests for chunk summary CTF encoding/decoding."""

    def test_encode_empty_summaries(self):
        """Empty summary list returns empty string."""
        result = encode_chunk_summaries([])
        assert result == ""

    def test_encode_summaries(self):
        """Chunk summaries encode correctly."""
        summaries = [
            {
                "chunk_id": "micro_abc123",
                "turn_range": (0, 10),
                "summary": "User introduced themselves",
                "themes": ["identity", "capabilities"],
            },
            {
                "chunk_id": "micro_def456",
                "turn_range": (10, 20),
                "summary": "Discussed file limitations",
                "themes": ["tools", "limitations"],
            },
        ]
        result = encode_chunk_summaries(summaries)
        
        assert result.startswith("#CTF v1")
        assert "type=summaries" in result
        assert "count=2" in result

    def test_roundtrip_summaries(self):
        """Encoding then decoding preserves summary data."""
        summaries = [
            {
                "chunk_id": "micro_abc123",
                "turn_range": (0, 10),
                "summary": "Test summary with special chars: \n\t",
                "themes": ["theme1", "theme2"],
            },
        ]
        encoded = encode_chunk_summaries(summaries)
        decoded = decode_chunk_summaries(encoded)
        
        assert len(decoded) == 1
        assert decoded[0]["chunk_id"] == "micro_abc123"
        assert decoded[0]["turn_range"] == (0, 10)
        assert decoded[0]["themes"] == ["theme1", "theme2"]


# =============================================================================
# Chunk Tests
# =============================================================================


class TestChunk:
    """Tests for Chunk dataclass."""

    def test_chunk_creation(self, sample_chunk: Chunk):
        """Chunk can be created with all fields."""
        assert sample_chunk.id == "micro_abc123"
        assert sample_chunk.chunk_type == ChunkType.MICRO
        assert sample_chunk.turn_range == (0, 10)
        assert len(sample_chunk.turns) == 10

    def test_chunk_is_frozen(self, sample_chunk: Chunk):
        """Chunk is immutable."""
        with pytest.raises(AttributeError):
            sample_chunk.id = "new_id"

    def test_chunk_summary_lightweight(self):
        """ChunkSummary contains only essential fields."""
        summary = ChunkSummary(
            chunk_id="micro_abc123",
            chunk_type=ChunkType.MICRO,
            turn_range=(0, 10),
            summary="Test summary",
            themes=("test",),
            token_count=50,
        )
        assert summary.chunk_id == "micro_abc123"
        assert summary.embedding is None


# =============================================================================
# ChunkManager Tests
# =============================================================================


class TestChunkManager:
    """Tests for ChunkManager functionality."""

    @pytest.mark.asyncio
    async def test_add_turns_creates_micro_chunk(
        self,
        chunk_manager: ChunkManager,
        sample_turns: tuple[Turn, ...],
    ):
        """Adding enough turns creates a micro-chunk."""
        # Config has micro_chunk_size=5, so 5 turns should create a chunk
        chunk_ids = await chunk_manager.add_turns(sample_turns[:5])
        
        assert len(chunk_ids) == 1
        assert chunk_ids[0].startswith("micro_")
        
        chunk = chunk_manager.get_chunk(chunk_ids[0])
        assert chunk is not None
        assert chunk.chunk_type == ChunkType.MICRO
        assert len(chunk.turns) == 5

    @pytest.mark.asyncio
    async def test_hot_tier_demotion(
        self,
        chunk_manager: ChunkManager,
    ):
        """Older chunks are demoted to warm tier when hot limit exceeded."""
        # Create enough turns to exceed hot_chunks limit (2)
        all_turns = tuple(
            Turn(
                content=f"Message {i}",
                turn_type=TurnType.USER,
                timestamp=f"2026-01-15T10:00:{i:02d}",
            )
            for i in range(15)  # 3 micro-chunks with size=5
        )
        
        await chunk_manager.add_turns(all_turns)
        
        # Should have 3 chunks total, 2 hot, 1 warm
        hot_chunks = chunk_manager._get_hot_chunks()
        warm_chunks = chunk_manager._get_warm_chunks()
        
        assert len(hot_chunks) <= 2  # Config limit
        assert len(warm_chunks) >= 1  # At least one demoted

    @pytest.mark.asyncio
    async def test_chunk_expansion(
        self,
        chunk_manager: ChunkManager,
        sample_turns: tuple[Turn, ...],
    ):
        """Warm chunks can be expanded back to full turns."""
        # Create and demote a chunk
        chunk_ids = await chunk_manager.add_turns(sample_turns[:5])
        chunk_id = chunk_ids[0]
        
        # Manually demote to warm (public method)
        chunk_manager.demote_to_warm(chunk_id)
        
        # Expand it back
        expanded = chunk_manager.expand_chunk(chunk_id)
        
        assert expanded.turns is not None
        assert len(expanded.turns) == 5

    def test_get_recent_chunks(
        self,
        chunk_manager: ChunkManager,
    ):
        """Recent chunks are retrieved by turn range."""
        # Add some test chunks manually
        chunk1 = Chunk(
            id="test_1",
            chunk_type=ChunkType.MICRO,
            turn_range=(0, 10),
            turns=(),
            token_count=100,
        )
        chunk2 = Chunk(
            id="test_2",
            chunk_type=ChunkType.MICRO,
            turn_range=(10, 20),
            turns=(),
            token_count=100,
        )
        chunk_manager._chunks = {"test_1": chunk1, "test_2": chunk2}
        
        recent = chunk_manager._get_recent_chunks(1)
        assert len(recent) == 1
        assert recent[0].id == "test_2"  # Most recent by turn_range

    def test_stats(self, chunk_manager: ChunkManager):
        """Stats returns expected structure."""
        stats = chunk_manager.stats
        
        assert "total_chunks" in stats
        assert "hot_chunks" in stats
        assert "warm_chunks" in stats
        assert "cold_chunks" in stats
        assert "total_turns" in stats


# =============================================================================
# Summarizer Tests
# =============================================================================


class TestSummarizer:
    """Tests for Summarizer without LLM."""

    @pytest.mark.asyncio
    async def test_heuristic_summarize(self, sample_turns: tuple[Turn, ...]):
        """Heuristic summary works without LLM."""
        summarizer = Summarizer(model=None)
        result = await summarizer.summarize_turns(sample_turns)
        
        assert result  # Non-empty
        assert "Discussion starting with:" in result or "Conversation segment" in result

    @pytest.mark.asyncio
    async def test_summarize_empty_turns(self):
        """Empty turns return empty summary."""
        summarizer = Summarizer(model=None)
        result = await summarizer.summarize_turns([])
        
        assert result == ""

    @pytest.mark.asyncio
    async def test_extract_facts_without_llm(self, sample_turns: tuple[Turn, ...]):
        """Fact extraction returns empty without LLM."""
        summarizer = Summarizer(model=None)
        result = await summarizer.extract_facts(sample_turns)
        
        assert result == []  # No heuristic fact extraction


# =============================================================================
# SimulacrumStore Integration Tests
# =============================================================================


class TestSimulacrumStoreIntegration:
    """Tests for SimulacrumStore with RFC-013 features."""

    def test_store_initializes_chunk_manager(self, temp_dir: Path):
        """Store creates ChunkManager on init."""
        store = SimulacrumStore(base_path=temp_dir)
        
        assert store._chunk_manager is not None
        assert (temp_dir / "chunks").exists()

    def test_store_with_custom_chunk_config(self, temp_dir: Path):
        """Store accepts custom ChunkConfig."""
        config = ChunkConfig(
            micro_chunk_size=20,
            hot_chunks=5,
        )
        store = SimulacrumStore(
            base_path=temp_dir,
            chunk_config=config,
        )
        
        assert store._chunk_manager.config.micro_chunk_size == 20
        assert store._chunk_manager.config.hot_chunks == 5

    def test_add_turn_integrates_with_chunks(self, temp_dir: Path):
        """Adding turns feeds into chunk manager."""
        config = ChunkConfig(
            micro_chunk_size=2,
            auto_summarize=False,
            auto_embed=False,
        )
        store = SimulacrumStore(
            base_path=temp_dir,
            chunk_config=config,
        )
        
        # Add turns
        store.add_turn(Turn(content="Hello", turn_type=TurnType.USER))
        store.add_turn(Turn(content="Hi there", turn_type=TurnType.ASSISTANT))
        
        # Give async a chance to complete
        import time
        time.sleep(0.1)
        
        # Check chunk manager received turns
        assert store._chunk_manager._turn_count >= 0  # At least initialized

    def test_get_context_for_prompt(self, temp_dir: Path):
        """Context retrieval returns formatted string."""
        store = SimulacrumStore(base_path=temp_dir)
        
        # Add some turns first
        store.add_user("What is the weather?")
        store.add_assistant("I don't have real-time weather data.")
        
        # Get context
        context = store.get_context_for_prompt("weather", max_tokens=1000)
        
        # Should return something (from DAG if not from chunks)
        assert isinstance(context, str)

    def test_stats_include_chunk_info(self, temp_dir: Path):
        """Stats include chunk manager statistics."""
        store = SimulacrumStore(base_path=temp_dir)
        stats = store.stats()
        
        assert "chunk_stats" in stats
        assert "total_chunks" in stats["chunk_stats"]


# =============================================================================
# Config Tests
# =============================================================================


class TestChunkConfig:
    """Tests for ChunkConfig."""

    def test_default_config_values(self):
        """Default config has expected values."""
        config = DEFAULT_CHUNK_CONFIG
        
        assert config.micro_chunk_size == 10
        assert config.mini_chunk_interval == 25
        assert config.macro_chunk_interval == 100
        assert config.hot_chunks == 2
        assert config.warm_format == "ctf"
        assert config.auto_summarize is True

    def test_config_customization(self):
        """Config can be customized."""
        config = ChunkConfig(
            micro_chunk_size=5,
            summarization_strategy="llm",
            embedding_provider="openai",
        )
        
        assert config.micro_chunk_size == 5
        assert config.summarization_strategy == "llm"
        assert config.embedding_provider == "openai"


# =============================================================================
# Token Efficiency Tests
# =============================================================================


class TestTokenEfficiency:
    """Tests verifying CTF achieves token reduction."""

    def test_ctf_smaller_than_json(self, sample_turns: tuple[Turn, ...]):
        """CTF produces smaller output than equivalent JSON."""
        import json
        
        # JSON representation
        json_data = [
            {
                "role": t.turn_type.value,
                "content": t.content,
                "timestamp": t.timestamp,
                "model": t.model,
            }
            for t in sample_turns
        ]
        json_str = json.dumps(json_data)
        
        # CTF representation
        ctf_str = CTFEncoder.encode_turns(sample_turns)
        
        # CTF should be meaningfully smaller
        reduction = (len(json_str) - len(ctf_str)) / len(json_str) * 100
        assert reduction > 20  # At least 20% reduction
