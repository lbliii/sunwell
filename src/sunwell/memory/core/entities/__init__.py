"""Entity extraction and management system (Phase 1: Foundation).

Provides entity extraction, resolution, and storage for
entity-aware retrieval and co-occurrence analysis.

Part of Hindsight-inspired memory enhancements.
"""

from sunwell.memory.core.entities.extractor import (
    LLMEntityExtractor,
    PatternEntityExtractor,
    get_entity_extractor,
)
from sunwell.memory.core.entities.integration import (
    EntityIntegration,
    create_entity_integration,
)
from sunwell.memory.core.entities.resolver import DEFAULT_ALIASES, EntityResolver
from sunwell.memory.core.entities.store import EntityStore
from sunwell.memory.core.entities.types import (
    Entity,
    EntityMention,
    EntityType,
    ExtractionResult,
)

__all__ = [
    # Types
    "Entity",
    "EntityMention",
    "EntityType",
    "ExtractionResult",
    # Extraction
    "PatternEntityExtractor",
    "LLMEntityExtractor",
    "get_entity_extractor",
    # Resolution
    "EntityResolver",
    "DEFAULT_ALIASES",
    # Storage
    "EntityStore",
    # Integration
    "EntityIntegration",
    "create_entity_integration",
]
