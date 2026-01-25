# src/sunwell/simulacrum/memory_node.py
"""Unified memory node combining all topology dimensions.

A single unit of memory with:
- Content (text, code, etc.)
- Temporal position (RFC-013 chunk)
- Spatial position (where in document/code)
- Structural context (document hierarchy)
- Faceted tags (multi-dimensional)
- Graph edges (relationships to other nodes)

Part of RFC-014: Multi-Topology Memory.
"""


from dataclasses import dataclass, field
from datetime import datetime

from sunwell.simulacrum.hierarchical.chunks import Chunk
from sunwell.simulacrum.topology.facets import ContentFacets
from sunwell.simulacrum.topology.spatial import SpatialContext
from sunwell.simulacrum.topology.structural import DocumentSection
from sunwell.simulacrum.topology.topology_base import ConceptEdge


@dataclass(slots=True)
class MemoryNode:
    """Unified memory node combining all topology dimensions.

    A single unit of memory with:
    - Content (text, code, etc.)
    - Temporal position (RFC-013 chunk)
    - Spatial position (where in document/code)
    - Structural context (document hierarchy)
    - Faceted tags (multi-dimensional)
    - Graph edges (relationships to other nodes)
    """

    id: str
    """Unique identifier."""

    content: str
    """The actual content."""

    # === Temporal (RFC-013) ===
    chunk: Chunk | None = None
    """RFC-013 chunk data (turn-based chunking)."""

    # === Spatial ===
    spatial: SpatialContext | None = None
    """Position context (file, line, section path)."""

    # === Structural ===
    section: DocumentSection | None = None
    """Document section context."""

    # === Multi-Faceted ===
    facets: ContentFacets | None = None
    """Cross-dimensional tags."""

    # === Topological ===
    outgoing_edges: list[ConceptEdge] = field(default_factory=list)
    """Relationships where this node is source."""

    incoming_edges: list[ConceptEdge] = field(default_factory=list)
    """Relationships where this node is target."""

    # === Metadata ===
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # === Retrieval ===
    embedding: tuple[float, ...] | None = None
    """Vector embedding for semantic search."""

    def summary(self) -> str:
        """Generate human-readable summary."""
        parts = []

        if self.spatial:
            parts.append(str(self.spatial))

        if self.section:
            parts.append(f"[{self.section.section_type.value}]")

        if self.facets and self.facets.diataxis_type:
            parts.append(f"({self.facets.diataxis_type.value})")

        parts.append(self.content[:100] + "..." if len(self.content) > 100 else self.content)

        return " ".join(parts)

    def to_dict(self) -> dict:
        """Serialize node for storage."""
        return {
            "id": self.id,
            "content": self.content,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            # Spatial
            "spatial": {
                "position_type": self.spatial.position_type.value,
                "file_path": self.spatial.file_path,
                "section_path": list(self.spatial.section_path),
                "heading_level": self.spatial.heading_level,
                "line_range": list(self.spatial.line_range),
                "module_path": self.spatial.module_path,
                "class_name": self.spatial.class_name,
                "function_name": self.spatial.function_name,
                "scope_depth": self.spatial.scope_depth,
                "url": self.spatial.url,
                "anchor": self.spatial.anchor,
            } if self.spatial else None,
            # Facets
            "facets": {
                "diataxis_type": self.facets.diataxis_type.value if self.facets and self.facets.diataxis_type else None,
                "primary_persona": self.facets.primary_persona.value if self.facets and self.facets.primary_persona else None,
                "secondary_personas": [p.value for p in self.facets.secondary_personas] if self.facets else [],
                "verification_state": self.facets.verification_state.value if self.facets else None,
                "confidence": self.facets.confidence.value if self.facets else None,
                "domain_tags": list(self.facets.domain_tags) if self.facets else [],
                "is_time_sensitive": self.facets.is_time_sensitive if self.facets else False,
                "last_verified": self.facets.last_verified if self.facets else None,
                "source_type": self.facets.source_type if self.facets else None,
                "source_authority": self.facets.source_authority if self.facets else 1.0,
            } if self.facets else None,
            # Embedding
            "embedding": list(self.embedding) if self.embedding else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> MemoryNode:
        """Deserialize node from storage."""
        from sunwell.simulacrum.topology.facets import (
            ConfidenceLevel,
            ContentFacets,
            DiataxisType,
            PersonaType,
            VerificationState,
        )
        from sunwell.simulacrum.topology.spatial import PositionType, SpatialContext

        # Reconstruct spatial
        spatial = None
        if data.get("spatial"):
            s = data["spatial"]
            spatial = SpatialContext(
                position_type=PositionType(s["position_type"]),
                file_path=s.get("file_path"),
                section_path=tuple(s.get("section_path", [])),
                heading_level=s.get("heading_level", 0),
                line_range=tuple(s.get("line_range", (0, 0))),
                module_path=s.get("module_path"),
                class_name=s.get("class_name"),
                function_name=s.get("function_name"),
                scope_depth=s.get("scope_depth", 0),
                url=s.get("url"),
                anchor=s.get("anchor"),
            )

        # Reconstruct facets
        facets = None
        if data.get("facets"):
            f_data = data["facets"]
            facets = ContentFacets(
                diataxis_type=DiataxisType(f_data["diataxis_type"]) if f_data.get("diataxis_type") else None,
                primary_persona=PersonaType(f_data["primary_persona"]) if f_data.get("primary_persona") else None,
                secondary_personas=tuple(PersonaType(p) for p in f_data.get("secondary_personas", [])),
                verification_state=VerificationState(f_data["verification_state"]) if f_data.get("verification_state") else VerificationState.UNVERIFIED,
                confidence=ConfidenceLevel(f_data["confidence"]) if f_data.get("confidence") else ConfidenceLevel.MODERATE,
                domain_tags=tuple(f_data.get("domain_tags", [])),
                is_time_sensitive=f_data.get("is_time_sensitive", False),
                last_verified=f_data.get("last_verified"),
                source_type=f_data.get("source_type"),
                source_authority=f_data.get("source_authority", 1.0),
            )

        # Reconstruct embedding
        embedding = None
        if data.get("embedding"):
            embedding = tuple(data["embedding"])

        return cls(
            id=data["id"],
            content=data["content"],
            spatial=spatial,
            facets=facets,
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            embedding=embedding,
        )
