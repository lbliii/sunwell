"""Multi-topology memory (RFC-014).

RFC-025: Extracted from root simulacrum module.
"""

from sunwell.simulacrum.topology.facets import (
    ConfidenceLevel,
    ContentFacets,
    DiataxisType,
    FacetedIndex,
    FacetQuery,
    PersonaType,
    VerificationState,
)
from sunwell.simulacrum.topology.memory_node import MemoryNode
from sunwell.simulacrum.topology.spatial import (
    PositionType,
    SpatialContext,
    SpatialQuery,
    spatial_match,
)
from sunwell.simulacrum.topology.structural import (
    DocumentSection,
    DocumentTree,
    SectionType,
    infer_section_type,
)
from sunwell.simulacrum.topology.topology_base import (
    ConceptEdge,
    ConceptGraph,
    RelationType,
)
from sunwell.simulacrum.topology.unified_store import UnifiedMemoryStore

__all__ = [
    "SpatialContext",
    "SpatialQuery",
    "PositionType",
    "spatial_match",
    "ConceptGraph",
    "ConceptEdge",
    "RelationType",
    "DocumentTree",
    "DocumentSection",
    "SectionType",
    "infer_section_type",
    "ContentFacets",
    "FacetQuery",
    "FacetedIndex",
    "DiataxisType",
    "PersonaType",
    "VerificationState",
    "ConfidenceLevel",
    "MemoryNode",
    "UnifiedMemoryStore",
]
