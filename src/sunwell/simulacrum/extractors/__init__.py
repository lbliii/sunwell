"""Memory extractors for multi-topology memory.

RFC-025: Extracted from root simulacrum module.
"""

from sunwell.simulacrum.extractors.spatial_extractor import SpatialExtractor
from sunwell.simulacrum.extractors.topology_extractor import TopologyExtractor
from sunwell.simulacrum.extractors.structural_chunker import StructuralChunker
from sunwell.simulacrum.extractors.facet_extractor import FacetExtractor
from sunwell.simulacrum.extractors.extractor import (
    LearningExtractor,
    extract_user_facts,
    extract_user_facts_with_llm,
    auto_extract_learnings,
)

__all__ = [
    "SpatialExtractor",
    "TopologyExtractor",
    "StructuralChunker",
    "FacetExtractor",
    "LearningExtractor",
    "extract_user_facts",
    "extract_user_facts_with_llm",
    "auto_extract_learnings",
]
