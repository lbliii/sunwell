"""Memory extractors for multi-topology memory.

RFC-025: Extracted from root simulacrum module.
"""

from sunwell.memory.simulacrum.extractors.extractor import (
    LearningExtractor,
    auto_extract_learnings,
    extract_user_facts,
    extract_user_facts_with_llm,
)
from sunwell.memory.simulacrum.extractors.facet_extractor import extract_facets_from_text
from sunwell.memory.simulacrum.extractors.spatial_extractor import SpatialExtractor
from sunwell.memory.simulacrum.extractors.structural_chunker import StructuralChunker
from sunwell.memory.simulacrum.extractors.topology_extractor import TopologyExtractor

__all__ = [
    "SpatialExtractor",
    "TopologyExtractor",
    "StructuralChunker",
    "extract_facets_from_text",
    "LearningExtractor",
    "extract_user_facts",
    "extract_user_facts_with_llm",
    "auto_extract_learnings",
]
