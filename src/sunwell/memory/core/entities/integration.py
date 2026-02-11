"""Integration module for entity extraction in learning workflow.

Provides automatic entity extraction when learnings are added,
with optional LLM-based extraction for ambiguous cases.

Part of Phase 1: Foundation.
"""

import logging
from typing import TYPE_CHECKING

from sunwell.memory.core.entities.extractor import get_entity_extractor
from sunwell.memory.core.entities.resolver import DEFAULT_ALIASES, EntityResolver
from sunwell.memory.core.entities.store import EntityStore

if TYPE_CHECKING:
    from pathlib import Path

    from sunwell.agent.learning.learning import Learning
    from sunwell.knowledge.embedding.protocol import EmbeddingProtocol

logger = logging.getLogger(__name__)


class EntityIntegration:
    """Integrates entity extraction into learning workflow.

    Automatically extracts entities from learnings and stores them
    for entity-aware retrieval and co-occurrence analysis.
    """

    def __init__(
        self,
        entity_store_path: Path,
        extraction_mode: str = "pattern",
        embedder: EmbeddingProtocol | None = None,
        user_aliases: dict[str, str] | None = None,
    ):
        """Initialize entity integration.

        Args:
            entity_store_path: Path to entity store database
            extraction_mode: "pattern" (default) or "llm"
            embedder: Optional embedder for LLM extraction
            user_aliases: Optional user-defined alias mappings
        """
        self.entity_store = EntityStore(entity_store_path)
        self.extractor = get_entity_extractor(extraction_mode, embedder)
        self.resolver = EntityResolver(user_aliases or DEFAULT_ALIASES)

        # Load existing entities into resolver cache
        self._warm_resolver_cache()

    def _warm_resolver_cache(self) -> None:
        """Load existing entities into resolver cache."""
        from sunwell.memory.core.entities.types import EntityType

        for entity_type in EntityType:
            entities = self.entity_store.get_entities_by_type(entity_type)
            for entity in entities:
                self.resolver.add_entity(entity)

    async def process_learning(self, learning: Learning) -> int:
        """Process a learning to extract and store entities.

        Args:
            learning: Learning to process

        Returns:
            Number of entities extracted and linked
        """
        # Extract entities
        result = self.extractor.extract(learning.fact, learning.id)
        if not result:
            return 0

        entities_linked = 0

        # Process each extracted entity
        for entity in result.entities:
            # Resolve to canonical entity (or keep if novel)
            existing_entities = self.entity_store.get_entities_by_type(entity.entity_type)
            resolved = self.resolver.resolve(entity.canonical_name, existing_entities)

            if resolved:
                # Use existing entity
                entity_to_use = resolved.with_mention()
                # Update mention count
                self.entity_store.add_entity(entity_to_use)
            else:
                # Add new entity
                self.entity_store.add_entity(entity)
                self.resolver.add_entity(entity)
                entity_to_use = entity

            # Link to learning
            for mention in result.mentions:
                if mention.entity_id == entity.entity_id:
                    # Update mention with resolved entity ID
                    mention.entity_id = entity_to_use.entity_id
                    self.entity_store.add_mention(mention)
                    entities_linked += 1

        # Update co-occurrence for entity pairs in this learning
        entity_ids = [e.entity_id for e in result.entities]
        for i, id1 in enumerate(entity_ids):
            for id2 in entity_ids[i + 1 :]:
                self.entity_store.update_cooccurrence(id1, id2)

        return entities_linked

    def get_stats(self) -> dict:
        """Get entity extraction statistics.

        Returns:
            Dict with entity stats
        """
        return self.entity_store.stats()


# Factory function for easy instantiation
def create_entity_integration(
    workspace: Path,
    extraction_mode: str = "pattern",
    embedder: EmbeddingProtocol | None = None,
    user_aliases: dict[str, str] | None = None,
) -> EntityIntegration:
    """Create entity integration for a workspace.

    Args:
        workspace: Project workspace root
        extraction_mode: "pattern" (default) or "llm"
        embedder: Optional embedder for LLM extraction
        user_aliases: Optional user-defined alias mappings

    Returns:
        EntityIntegration instance
    """
    from pathlib import Path

    memory_dir = Path(workspace) / ".sunwell" / "memory"
    entity_store_path = memory_dir / "entities.db"
    return EntityIntegration(entity_store_path, extraction_mode, embedder, user_aliases)
