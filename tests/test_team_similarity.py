"""Unit tests for team similarity matching.

These tests help debug the failing team intelligence tests.
"""

from pathlib import Path

import pytest

from sunwell.features.team.store import TeamKnowledgeStore


class TestSimilarityMatching:
    """Test the _similar() method used for contradiction detection."""

    def test_exact_match(self):
        """Test exact string matches."""
        store = TeamKnowledgeStore(Path("/tmp/test"))
        assert store._similar("MySQL", "MySQL") is True
        assert store._similar("PostgreSQL", "PostgreSQL") is True

    def test_partial_match(self):
        """Test partial matches with shared words."""
        store = TeamKnowledgeStore(Path("/tmp/test"))
        # "MySQL database" should match "MySQL" (high overlap)
        assert store._similar("MySQL database", "MySQL") is True
        assert store._similar("use MySQL", "MySQL") is True
        assert store._similar("PostgreSQL database", "PostgreSQL") is True

    def test_low_overlap(self):
        """Test strings with low overlap don't match."""
        store = TeamKnowledgeStore(Path("/tmp/test"))
        assert store._similar("MySQL", "PostgreSQL") is False
        assert store._similar("Redis caching", "MySQL database") is False

    def test_threshold_boundary(self):
        """Test similarity threshold boundaries."""
        store = TeamKnowledgeStore(Path("/tmp/test"))
        # 50% overlap should match (1 word overlap out of 2 total words)
        assert store._similar("a b", "a") is True  # 1/2 = 0.5
        # Below 50% should not match
        assert store._similar("a b c", "d e") is False  # 0/5 = 0.0
        assert store._similar("a b", "a c") is False  # 1/3 = 0.333 < 0.5

    def test_case_insensitive(self):
        """Test that matching is case-insensitive."""
        store = TeamKnowledgeStore(Path("/tmp/test"))
        assert store._similar("MySQL", "mysql") is True
        assert store._similar("PostgreSQL", "POSTGRESQL") is True

    def test_empty_strings(self):
        """Test handling of empty strings."""
        store = TeamKnowledgeStore(Path("/tmp/test"))
        assert store._similar("", "") is False  # No overlap possible
        assert store._similar("MySQL", "") is False

    def test_single_word_match(self):
        """Test single word matching."""
        store = TeamKnowledgeStore(Path("/tmp/test"))
        # Single word should match itself
        assert store._similar("Redis", "Redis") is True
        # Single word in phrase should match if >= 50% overlap
        # "use Redis caching" vs "Redis" = 1/3 = 0.333 < 0.5, so should not match
        assert store._similar("use Redis caching", "Redis") is False
        # But "Redis caching" vs "Redis" = 1/2 = 0.5, so should match
        assert store._similar("Redis caching", "Redis") is True


class TestContradictionDetection:
    """Test contradiction detection logic."""

    @pytest.mark.asyncio
    async def test_contradiction_exact_match(self, tmp_path):
        """Test contradiction detection with exact match."""
        store = TeamKnowledgeStore(tmp_path)
        
        # Create decision rejecting MySQL
        await store.create_decision(
            category="database",
            question="Which database?",
            choice="PostgreSQL",
            rationale="Better features",
            author="test@example.com",
            rejected=[("MySQL", "Licensing")],
            auto_commit=False,
        )
        
        # Check if MySQL contradicts
        conflict = await store.check_contradiction("MySQL", "database")
        assert conflict is not None
        assert conflict.choice == "PostgreSQL"

    @pytest.mark.asyncio
    async def test_contradiction_partial_match(self, tmp_path):
        """Test contradiction detection with partial match."""
        store = TeamKnowledgeStore(tmp_path)
        
        await store.create_decision(
            category="database",
            question="Which database?",
            choice="PostgreSQL",
            rationale="Better features",
            author="test@example.com",
            rejected=[("MySQL", "Licensing")],
            auto_commit=False,
        )
        
        # "MySQL database" should match rejected "MySQL"
        conflict = await store.check_contradiction("MySQL database", "database")
        assert conflict is not None
        assert conflict.choice == "PostgreSQL"

    @pytest.mark.asyncio
    async def test_no_contradiction(self, tmp_path):
        """Test that non-rejected choices don't trigger contradiction."""
        store = TeamKnowledgeStore(tmp_path)
        
        await store.create_decision(
            category="database",
            question="Which database?",
            choice="PostgreSQL",
            rationale="Better features",
            author="test@example.com",
            rejected=[("MySQL", "Licensing")],
            auto_commit=False,
        )
        
        # PostgreSQL should not contradict
        conflict = await store.check_contradiction("PostgreSQL", "database")
        assert conflict is None
