"""Tests for Phase 1.1: Entity Extraction System.

Tests pattern-based entity extraction, resolution, and storage.
"""

import tempfile
from pathlib import Path

import pytest

from sunwell.memory.core.entities import (
    DEFAULT_ALIASES,
    Entity,
    EntityResolver,
    EntityStore,
    EntityType,
    PatternEntityExtractor,
)


class TestPatternEntityExtractor:
    """Test pattern-based entity extraction."""

    def setup_method(self):
        """Set up test fixtures."""
        self.extractor = PatternEntityExtractor()

    def test_extract_file_paths(self):
        """Test extraction of file paths."""
        text = "Edit the file `src/main.py` and update `config.yaml`"
        result = self.extractor.extract(text, learning_id="test_1")

        assert len(result.entities) >= 2
        file_entities = [e for e in result.entities if e.entity_type == EntityType.FILE]
        assert len(file_entities) >= 2

        file_names = [e.canonical_name for e in file_entities]
        assert "src/main.py" in file_names
        assert "config.yaml" in file_names

    def test_extract_technologies(self):
        """Test extraction of technology names."""
        text = "Use React with TypeScript and PostgreSQL database"
        result = self.extractor.extract(text)

        tech_entities = [e for e in result.entities if e.entity_type == EntityType.TECH]
        assert len(tech_entities) >= 3

        tech_names = [e.canonical_name for e in tech_entities]
        assert "React" in tech_names
        assert "TypeScript" in tech_names
        assert "PostgreSQL" in tech_names

    def test_extract_code_symbols(self):
        """Test extraction of code symbols."""
        text = "Define class UserModel and method authenticate()"
        result = self.extractor.extract(text)

        symbol_entities = [e for e in result.entities if e.entity_type == EntityType.SYMBOL]
        assert len(symbol_entities) >= 2

        symbol_names = [e.canonical_name for e in symbol_entities]
        assert "UserModel" in symbol_names
        assert "authenticate" in symbol_names

    def test_extract_concepts(self):
        """Test extraction of multi-word concepts."""
        text = "Implement Memory System with Entity Graph and Semantic Search"
        result = self.extractor.extract(text)

        concept_entities = [e for e in result.entities if e.entity_type == EntityType.CONCEPT]
        # Should find multi-word concepts
        assert len(concept_entities) > 0

    def test_no_duplicates(self):
        """Test that duplicate entities are not extracted."""
        text = "Use React and React hooks and React components"
        result = self.extractor.extract(text)

        # Should only have one React entity
        tech_entities = [e for e in result.entities if e.canonical_name == "React"]
        assert len(tech_entities) == 1

    def test_mentions_created(self):
        """Test that mentions are created with learning ID."""
        text = "Use React with TypeScript"
        result = self.extractor.extract(text, learning_id="learning_123")

        assert len(result.mentions) > 0
        for mention in result.mentions:
            assert mention.learning_id == "learning_123"
            assert mention.entity_id
            assert mention.confidence > 0

    def test_empty_text(self):
        """Test extraction from empty text."""
        result = self.extractor.extract("")
        assert len(result.entities) == 0
        assert len(result.mentions) == 0


class TestEntityResolver:
    """Test entity resolution and normalization."""

    def setup_method(self):
        """Set up test fixtures."""
        self.resolver = EntityResolver(DEFAULT_ALIASES)

    def test_exact_match(self):
        """Test exact name matching."""
        entity1 = Entity(
            entity_id="id1",
            canonical_name="React",
            entity_type=EntityType.TECH,
        )

        result = self.resolver.resolve("React", [entity1])
        assert result == entity1

    def test_alias_match(self):
        """Test matching via aliases."""
        entity1 = Entity(
            entity_id="id1",
            canonical_name="ReactJS",
            entity_type=EntityType.TECH,
            aliases=("React", "react.js"),
        )

        result = self.resolver.resolve("React", [entity1])
        assert result == entity1

    def test_user_alias_match(self):
        """Test user-defined alias matching."""
        resolver = EntityResolver({"py": "Python"})

        entity1 = Entity(
            entity_id="id1",
            canonical_name="Python",
            entity_type=EntityType.TECH,
        )

        result = resolver.resolve("py", [entity1])
        assert result == entity1

    def test_levenshtein_match(self):
        """Test fuzzy matching with Levenshtein distance."""
        entity1 = Entity(
            entity_id="id1",
            canonical_name="PostgreSQL",
            entity_type=EntityType.TECH,
        )

        # Should match with 1-2 character difference
        result = self.resolver.resolve("Postgresql", [entity1])
        assert result == entity1

    def test_no_match(self):
        """Test when no match is found."""
        entity1 = Entity(
            entity_id="id1",
            canonical_name="React",
            entity_type=EntityType.TECH,
        )

        result = self.resolver.resolve("Angular", [entity1])
        assert result is None

    def test_merge_entities(self):
        """Test merging two entities."""
        entity1 = Entity(
            entity_id="id1",
            canonical_name="React",
            entity_type=EntityType.TECH,
            aliases=("ReactJS",),
            mention_count=5,
        )

        entity2 = Entity(
            entity_id="id2",
            canonical_name="react.js",
            entity_type=EntityType.TECH,
            mention_count=3,
        )

        merged = self.resolver.merge_entities(entity1, entity2)

        assert merged.entity_id == entity1.entity_id
        assert merged.canonical_name == entity1.canonical_name
        assert "react.js" in merged.aliases
        assert "ReactJS" in merged.aliases
        assert merged.mention_count == 8  # 5 + 3


class TestEntityStore:
    """Test entity storage with SQLite."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_entities.db"
        self.store = EntityStore(self.db_path)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_add_entity(self):
        """Test adding an entity."""
        entity = Entity(
            entity_id="test_1",
            canonical_name="React",
            entity_type=EntityType.TECH,
        )

        added = self.store.add_entity(entity)
        assert added is True

        # Try adding again (should fail - duplicate)
        added_again = self.store.add_entity(entity)
        assert added_again is False

    def test_get_entity(self):
        """Test retrieving an entity."""
        entity = Entity(
            entity_id="test_1",
            canonical_name="React",
            entity_type=EntityType.TECH,
            aliases=("ReactJS",),
        )

        self.store.add_entity(entity)
        retrieved = self.store.get_entity("test_1")

        assert retrieved is not None
        assert retrieved.entity_id == entity.entity_id
        assert retrieved.canonical_name == entity.canonical_name
        assert retrieved.entity_type == entity.entity_type
        assert "ReactJS" in retrieved.aliases

    def test_get_entities_by_type(self):
        """Test filtering entities by type."""
        tech1 = Entity(entity_id="t1", canonical_name="React", entity_type=EntityType.TECH)
        tech2 = Entity(entity_id="t2", canonical_name="Python", entity_type=EntityType.TECH)
        file1 = Entity(entity_id="f1", canonical_name="main.py", entity_type=EntityType.FILE)

        self.store.add_entity(tech1)
        self.store.add_entity(tech2)
        self.store.add_entity(file1)

        tech_entities = self.store.get_entities_by_type(EntityType.TECH)
        assert len(tech_entities) == 2

        file_entities = self.store.get_entities_by_type(EntityType.FILE)
        assert len(file_entities) == 1

    def test_entity_learning_links(self):
        """Test linking entities to learnings."""
        from sunwell.memory.core.entities.types import EntityMention

        entity = Entity(entity_id="e1", canonical_name="React", entity_type=EntityType.TECH)
        self.store.add_entity(entity)

        mention = EntityMention(
            learning_id="l1",
            entity_id="e1",
            mention_text="React",
            confidence=0.9,
        )

        added = self.store.add_mention(mention)
        assert added is True

        # Check entity mention count was incremented
        updated_entity = self.store.get_entity("e1")
        assert updated_entity.mention_count == 1

        # Get learnings for entity
        learning_ids = self.store.get_learnings_by_entity("e1")
        assert "l1" in learning_ids

        # Get entities for learning
        entities = self.store.get_entities_for_learning("l1")
        assert len(entities) == 1
        assert entities[0].entity_id == "e1"

    def test_cooccurrence_tracking(self):
        """Test co-occurrence tracking between entities."""
        entity1 = Entity(entity_id="e1", canonical_name="React", entity_type=EntityType.TECH)
        entity2 = Entity(entity_id="e2", canonical_name="TypeScript", entity_type=EntityType.TECH)

        self.store.add_entity(entity1)
        self.store.add_entity(entity2)

        # Record co-occurrence
        self.store.update_cooccurrence("e1", "e2")
        self.store.update_cooccurrence("e1", "e2")  # Twice

        # Get co-occurring entities
        cooccurring = self.store.get_cooccurring_entities("e1", min_count=2, limit=10)

        assert len(cooccurring) == 1
        assert cooccurring[0][0].entity_id == "e2"
        assert cooccurring[0][1] == 2  # Count

    def test_stats(self):
        """Test entity store statistics."""
        tech1 = Entity(entity_id="t1", canonical_name="React", entity_type=EntityType.TECH)
        tech2 = Entity(entity_id="t2", canonical_name="Python", entity_type=EntityType.TECH)

        self.store.add_entity(tech1)
        self.store.add_entity(tech2)

        stats = self.store.stats()

        assert stats["total_entities"] == 2
        assert stats["by_type"]["tech"] == 2


class TestEntityIntegration:
    """Integration tests for entity extraction workflow."""

    def test_end_to_end_extraction(self):
        """Test complete extraction workflow."""
        extractor = PatternEntityExtractor()

        text = "Use React with TypeScript to build the main.py component"
        result = extractor.extract(text, learning_id="l1")

        # Should extract multiple entity types
        assert len(result.entities) >= 3
        assert result.extraction_mode == "pattern"

        # Check entity types are diverse
        entity_types = {e.entity_type for e in result.entities}
        assert EntityType.TECH in entity_types
        assert EntityType.FILE in entity_types

    def test_extraction_with_storage(self):
        """Test extraction and storage together."""
        temp_dir = tempfile.mkdtemp()
        try:
            db_path = Path(temp_dir) / "test.db"
            store = EntityStore(db_path)
            extractor = PatternEntityExtractor()

            text = "Use React hooks in the UserProfile component"
            result = extractor.extract(text, learning_id="l1")

            # Store entities
            for entity in result.entities:
                store.add_entity(entity)

            # Store mentions
            for mention in result.mentions:
                store.add_mention(mention)

            # Verify storage
            assert store.count_entities() == len(result.entities)

            # Check mentions are linked
            entities_for_learning = store.get_entities_for_learning("l1")
            assert len(entities_for_learning) == len(result.entities)

        finally:
            import shutil
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
