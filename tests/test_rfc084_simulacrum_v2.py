"""Tests for RFC-084: Simulacrum v2 — Unified Memory Architecture.

Tests cover:
- HeuristicSummarizer (TF-IDF summarization, fact extraction)
- TopologyExtractor (Jaccard similarity, relationship detection)
- Auto-wiring (topology extraction, cold demotion, focus)
- StorageConfig new fields
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import pytest

from sunwell.memory.simulacrum.core.turn import Turn, TurnType
from sunwell.memory.simulacrum.core.store import SimulacrumStore, StorageConfig
from sunwell.memory.simulacrum.hierarchical.summarizer import HeuristicSummarizer
from sunwell.memory.simulacrum.extractors.topology_extractor import TopologyExtractor
from sunwell.memory.simulacrum.topology.topology_base import RelationType
from sunwell.memory.simulacrum.context.focus import Focus


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_turns() -> tuple[Turn, ...]:
    """Create sample turns for testing."""
    return tuple(
        Turn(
            content=f"Message {i}: This is test content about authentication and security.",
            turn_type=TurnType.USER if i % 2 == 0 else TurnType.ASSISTANT,
            timestamp=f"2026-01-21T10:00:{i:02d}",
        )
        for i in range(5)
    )


@pytest.fixture
def heuristic_summarizer() -> HeuristicSummarizer:
    """Create a HeuristicSummarizer instance."""
    return HeuristicSummarizer()


@pytest.fixture
def topology_extractor() -> TopologyExtractor:
    """Create a TopologyExtractor instance."""
    return TopologyExtractor()


@pytest.fixture
def temp_storage_path() -> Path:
    """Create a temporary directory for storage tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# =============================================================================
# HeuristicSummarizer Tests
# =============================================================================


class TestHeuristicSummarizer:
    """Tests for the HeuristicSummarizer class."""

    @pytest.mark.asyncio
    async def test_summarize_turns(
        self, heuristic_summarizer: HeuristicSummarizer, sample_turns: tuple[Turn, ...]
    ) -> None:
        """Test that summarize_turns produces non-empty output."""
        summary = await heuristic_summarizer.summarize_turns(sample_turns)
        assert summary
        assert isinstance(summary, str)
        assert len(summary) > 10

    @pytest.mark.asyncio
    async def test_summarize_empty_turns(
        self, heuristic_summarizer: HeuristicSummarizer
    ) -> None:
        """Test that empty turns returns empty string."""
        summary = await heuristic_summarizer.summarize_turns(())
        assert summary == ""

    @pytest.mark.asyncio
    async def test_extract_facts(
        self, heuristic_summarizer: HeuristicSummarizer
    ) -> None:
        """Test fact extraction from turns with clear facts."""
        turns = (
            Turn(
                content="My name is Alice and I am a developer.",
                turn_type=TurnType.USER,
            ),
            Turn(
                content="We use Python for backend development.",
                turn_type=TurnType.ASSISTANT,
            ),
            Turn(
                content="The database is PostgreSQL running on port 5432.",
                turn_type=TurnType.USER,
            ),
        )
        facts = await heuristic_summarizer.extract_facts(turns)
        assert isinstance(facts, list)
        # Should extract at least one fact
        assert len(facts) >= 1

    @pytest.mark.asyncio
    async def test_extract_themes(
        self, heuristic_summarizer: HeuristicSummarizer
    ) -> None:
        """Test theme extraction from summaries."""
        summaries = [
            "Discussion about authentication and security.",
            "Implemented OAuth2 authentication flow.",
            "Added JWT token validation for API security.",
        ]
        themes = await heuristic_summarizer.extract_themes(summaries)
        assert isinstance(themes, list)
        assert len(themes) <= 5

    @pytest.mark.asyncio
    async def test_generate_executive_summary(
        self, heuristic_summarizer: HeuristicSummarizer
    ) -> None:
        """Test executive summary generation."""
        summaries = [
            "We discussed the authentication system.",
            "The team decided to use OAuth2.",
            "Security requirements were reviewed.",
        ]
        exec_summary = await heuristic_summarizer.generate_executive_summary(summaries)
        assert isinstance(exec_summary, str)

    def test_split_sentences(
        self, heuristic_summarizer: HeuristicSummarizer
    ) -> None:
        """Test sentence splitting handles abbreviations."""
        text = "Dr. Smith uses file.py for testing. It works well."
        sentences = heuristic_summarizer._split_sentences(text)
        # Should not split on "Dr." or "file.py"
        assert len(sentences) == 2

    def test_stopwords_filtered(
        self, heuristic_summarizer: HeuristicSummarizer
    ) -> None:
        """Test that common stopwords are filtered."""
        assert "the" in heuristic_summarizer._stopwords
        assert "and" in heuristic_summarizer._stopwords
        assert "authentication" not in heuristic_summarizer._stopwords


# =============================================================================
# TopologyExtractor Tests
# =============================================================================


class TestTopologyExtractor:
    """Tests for the TopologyExtractor class."""

    def test_jaccard_similarity(
        self, topology_extractor: TopologyExtractor
    ) -> None:
        """Test Jaccard similarity calculation."""
        set_a = {"apple", "banana", "cherry"}
        set_b = {"banana", "cherry", "date"}
        similarity = topology_extractor._jaccard_similarity(set_a, set_b)
        # Intersection: {banana, cherry} = 2
        # Union: {apple, banana, cherry, date} = 4
        # Jaccard: 2/4 = 0.5
        assert similarity == 0.5

    def test_jaccard_similarity_empty(
        self, topology_extractor: TopologyExtractor
    ) -> None:
        """Test Jaccard with empty sets."""
        assert topology_extractor._jaccard_similarity(set(), set()) == 0.0
        assert topology_extractor._jaccard_similarity({"a"}, set()) == 0.0

    def test_tokenize(self, topology_extractor: TopologyExtractor) -> None:
        """Test tokenization."""
        text = "The quick brown fox jumps"
        tokens = topology_extractor._tokenize(text)
        # Short tokens (<=2 chars) filtered
        assert "The" not in tokens  # "the" lowercased, but "the" > 2 chars
        assert "quick" in tokens
        assert "fox" in tokens

    def test_is_elaboration(self, topology_extractor: TopologyExtractor) -> None:
        """Test elaboration detection."""
        source = "Specifically, the authentication uses JWT tokens."
        target = "The system uses authentication."
        assert topology_extractor._is_elaboration(source, target)

    def test_is_contradiction(self, topology_extractor: TopologyExtractor) -> None:
        """Test contradiction detection."""
        source = "However, the authentication system is not secure."
        target = "The authentication system works well."
        assert topology_extractor._is_contradiction(source, target)

    def test_extract_heuristic_relationships_relates_to(
        self, topology_extractor: TopologyExtractor
    ) -> None:
        """Test that similar content produces RELATES_TO edges."""
        # Use highly overlapping text to ensure Jaccard > 0.3
        edges = topology_extractor.extract_heuristic_relationships(
            source_id="chunk-1",
            source_text="authentication security tokens validation access control",
            candidate_ids=["chunk-2"],
            candidate_texts=["authentication security tokens validation system"],
        )
        # Should find RELATES_TO relationship due to Jaccard similarity
        relates_to_edges = [e for e in edges if e.relation == RelationType.RELATES_TO]
        assert len(relates_to_edges) >= 1
        assert relates_to_edges[0].confidence > 0.3

    def test_extract_heuristic_relationships_empty(
        self, topology_extractor: TopologyExtractor
    ) -> None:
        """Test with empty candidates."""
        edges = topology_extractor.extract_heuristic_relationships(
            source_id="chunk-1",
            source_text="Some content.",
            candidate_ids=[],
            candidate_texts=[],
        )
        assert edges == []

    def test_relates_to_threshold(self, topology_extractor: TopologyExtractor) -> None:
        """Test the RELATES_TO threshold constant."""
        assert topology_extractor.RELATES_TO_THRESHOLD == 0.3


# =============================================================================
# StorageConfig Tests
# =============================================================================


class TestStorageConfigRFC084:
    """Tests for RFC-084 additions to StorageConfig."""

    def test_auto_topology_default(self) -> None:
        """Test auto_topology defaults to True."""
        config = StorageConfig()
        assert config.auto_topology is True

    def test_topology_interval_default(self) -> None:
        """Test topology_interval defaults to 10."""
        config = StorageConfig()
        assert config.topology_interval == 10

    def test_auto_cold_demotion_default(self) -> None:
        """Test auto_cold_demotion defaults to True."""
        config = StorageConfig()
        assert config.auto_cold_demotion is True

    def test_warm_retention_days_default(self) -> None:
        """Test warm_retention_days defaults to 7."""
        config = StorageConfig()
        assert config.warm_retention_days == 7

    def test_max_warm_chunks_default(self) -> None:
        """Test max_warm_chunks defaults to 50."""
        config = StorageConfig()
        assert config.max_warm_chunks == 50

    def test_auto_summarize_default(self) -> None:
        """Test auto_summarize defaults to True."""
        config = StorageConfig()
        assert config.auto_summarize is True

    def test_config_customization(self) -> None:
        """Test that all new fields are customizable."""
        config = StorageConfig(
            auto_topology=False,
            topology_interval=20,
            auto_cold_demotion=False,
            warm_retention_days=14,
            max_warm_chunks=100,
            auto_summarize=False,
        )
        assert config.auto_topology is False
        assert config.topology_interval == 20
        assert config.auto_cold_demotion is False
        assert config.warm_retention_days == 14
        assert config.max_warm_chunks == 100
        assert config.auto_summarize is False


# =============================================================================
# Focus Integration Tests
# =============================================================================


class TestFocusIntegration:
    """Tests for Focus mechanism integration."""

    def test_focus_update_from_query(self) -> None:
        """Test focus updates from query content."""
        focus = Focus()
        new_topics = focus.update_from_query("Fix the authentication bug in the API")
        assert "auth" in focus.topics or "api" in focus.topics

    def test_focus_explicit_set(self) -> None:
        """Test explicit focus setting."""
        focus = Focus()
        focus.set_explicit("security", 1.0)
        assert "security" in focus.topics
        assert "security" in focus.explicit
        assert focus.topics["security"] == 1.0

    def test_focus_decay(self) -> None:
        """Test implicit topic decay."""
        focus = Focus()
        focus.update_from_query("Fix authentication")
        initial_weight = focus.topics.get("auth", 0)
        
        # Decay happens on next update
        focus.update_from_query("Something unrelated")
        
        if "auth" in focus.topics:
            assert focus.topics["auth"] < initial_weight


# =============================================================================
# SimulacrumStore Integration Tests
# =============================================================================


class TestSimulacrumStoreRFC084:
    """Tests for RFC-084 SimulacrumStore integration."""

    def test_store_has_focus(self, temp_storage_path: Path) -> None:
        """Test that store initializes focus mechanism."""
        store = SimulacrumStore(base_path=temp_storage_path)
        assert store.focus is not None

    def test_store_initializes_with_auto_wiring(
        self, temp_storage_path: Path
    ) -> None:
        """Test that store initializes auto-wiring when enabled."""
        config = StorageConfig(auto_topology=True, auto_summarize=True)
        store = SimulacrumStore(base_path=temp_storage_path, config=config)
        # Should have topology extractor initialized
        assert store._topology_extractor is not None

    def test_store_can_disable_auto_wiring(
        self, temp_storage_path: Path
    ) -> None:
        """Test that auto-wiring can be disabled."""
        config = StorageConfig(auto_topology=False)
        store = SimulacrumStore(base_path=temp_storage_path, config=config)
        assert store._topology_extractor is None


# =============================================================================
# Unified Simulacrum Alias Test
# =============================================================================


class TestSimulacrumAlias:
    """Test that Simulacrum is aliased to SimulacrumStore."""

    def test_simulacrum_is_simulacrum_store(self) -> None:
        """Test that Simulacrum is SimulacrumStore."""
        from sunwell.memory.simulacrum.core import Simulacrum, SimulacrumStore
        assert Simulacrum is SimulacrumStore

    def test_legacy_simulacrum_available(self) -> None:
        """Test that LegacySimulacrum is still importable."""
        from sunwell.memory.simulacrum.core import LegacySimulacrum
        assert LegacySimulacrum is not None
