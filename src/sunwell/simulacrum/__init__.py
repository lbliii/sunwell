"""Simulacrum - Portable problem-solving context across models.

Your simulacrum travels with you:
- Switch from GPT-4 to Claude mid-conversation
- Learnings, dead ends, and context persist
- Smart retrieval keeps context within window limits
- Resume any session from any model

Memory Architecture (inspired by human cognition):
- Working Memory: Current conversation, recent turns
- Long-term Memory: Learnings, facts, patterns (persist forever)
- Episodic Memory: Past sessions, attempts, dead ends
- Semantic Memory: Codebase, docs, references (RAG)
- Procedural Memory: Skills, workflows, heuristics (from Lens)

Hierarchical Memory (RFC-013):
- HOT: Last 2 micro-chunks with full content
- WARM: CTF-encoded chunks with summaries and embeddings
- COLD: Macro-chunk summaries, full content archived
- Progressive compression: 10 → 25 → 100 turn consolidation

Multi-Topology Memory (RFC-014):
- Spatial: Position-aware retrieval (file, line, section)
- Topological: Concept graph relationships (contradicts, elaborates)
- Structural: Document hierarchy awareness
- Multi-Faceted: Cross-dimensional filtering (diataxis, persona)
- Unified Store: Hybrid queries across all dimensions

Key innovations:
- Model-agnostic: same simulacrum works with any LLM
- Content-addressable: hash-based deduplication
- Multi-memory: different retention/retrieval per type
- Smart assembly: never exceed token limits
- Provenance: track where every insight came from
"""

from sunwell.simulacrum.turn import Turn, TurnType, Learning
from sunwell.simulacrum.dag import ConversationDAG
from sunwell.simulacrum.context import ContextAssembler
from sunwell.simulacrum.store import SimulacrumStore, StorageConfig
from sunwell.simulacrum.memory import (
    MemoryType,
    WorkingMemory,
    LongTermMemory,
    EpisodicMemory,
    SemanticMemory,
    ProceduralMemory,
)
from sunwell.simulacrum.core import Simulacrum
from sunwell.simulacrum.focus import Focus, FocusFilter
from sunwell.simulacrum.parallel import ParallelRetriever
from sunwell.types.memory import RetrievalResult

# RFC-013: Hierarchical Memory exports
from sunwell.simulacrum.chunks import Chunk, ChunkType, ChunkSummary
from sunwell.simulacrum.config import ChunkConfig, DEFAULT_CHUNK_CONFIG
from sunwell.simulacrum.chunk_manager import ChunkManager
from sunwell.simulacrum.ctf import CTFEncoder, CTFDecoder, encode_chunk_summaries, decode_chunk_summaries
from sunwell.simulacrum.summarizer import Summarizer

# RFC-014: Multi-Topology Memory exports
from sunwell.simulacrum.spatial import SpatialContext, SpatialQuery, PositionType, spatial_match
from sunwell.simulacrum.topology import ConceptGraph, ConceptEdge, RelationType
from sunwell.simulacrum.structural import DocumentTree, DocumentSection, SectionType, infer_section_type
from sunwell.simulacrum.facets import (
    ContentFacets,
    FacetQuery,
    FacetedIndex,
    DiataxisType,
    PersonaType,
    VerificationState,
    ConfidenceLevel,
)
from sunwell.simulacrum.memory_node import MemoryNode
from sunwell.simulacrum.unified_store import UnifiedMemoryStore
from sunwell.simulacrum.spatial_extractor import SpatialExtractor
from sunwell.simulacrum.facet_extractor import FacetExtractor
from sunwell.simulacrum.topology_extractor import TopologyExtractor
from sunwell.simulacrum.structural_chunker import StructuralChunker
from sunwell.simulacrum.memory_tools import MemoryToolHandler, MEMORY_TOOLS
from sunwell.simulacrum.unified_context import UnifiedContextAssembler, UnifiedContext
from sunwell.types.memory import ContextBudget
from sunwell.simulacrum.manager import (
    SimulacrumManager,
    SimulacrumMetadata,
    SimulacrumToolHandler,
    SIMULACRUM_TOOLS,
    SpawnPolicy,
    LifecyclePolicy,
    ArchiveMetadata,
)

__all__ = [
    # Core
    "Simulacrum",
    "Turn",
    "TurnType",
    "Learning",
    
    # Memory types
    "MemoryType",
    "WorkingMemory",
    "LongTermMemory", 
    "EpisodicMemory",
    "SemanticMemory",
    "ProceduralMemory",
    
    # Focus/Attention
    "Focus",
    "FocusFilter",
    
    # Parallel Retrieval
    "ParallelRetriever",
    "RetrievalResult",
    
    # RFC-013: Hierarchical Memory
    "Chunk",
    "ChunkType",
    "ChunkSummary",
    "ChunkConfig",
    "DEFAULT_CHUNK_CONFIG",
    "ChunkManager",
    "Summarizer",
    
    # RFC-013: Compact Turn Format (CTF)
    "CTFEncoder",
    "CTFDecoder",
    "encode_chunk_summaries",
    "decode_chunk_summaries",
    
    # RFC-014: Spatial Memory
    "SpatialContext",
    "SpatialQuery",
    "PositionType",
    "spatial_match",
    "SpatialExtractor",
    
    # RFC-014: Topological Memory
    "ConceptGraph",
    "ConceptEdge",
    "RelationType",
    "TopologyExtractor",
    
    # RFC-014: Structural Memory
    "DocumentTree",
    "DocumentSection",
    "SectionType",
    "infer_section_type",
    "StructuralChunker",
    
    # RFC-014: Multi-Faceted Memory
    "ContentFacets",
    "FacetQuery",
    "FacetedIndex",
    "DiataxisType",
    "PersonaType",
    "VerificationState",
    "ConfidenceLevel",
    "FacetExtractor",
    
    # RFC-014: Unified Memory
    "MemoryNode",
    "UnifiedMemoryStore",
    
    # RFC-014: Memory Tools
    "MemoryToolHandler",
    "MEMORY_TOOLS",
    
    # Storage
    "ConversationDAG",
    "ContextAssembler",
    "SimulacrumStore",
    "StorageConfig",
    
    # RFC-014: Unified Context Assembly
    "UnifiedContextAssembler",
    "UnifiedContext",
    "ContextBudget",
    
    # RFC-014: Multi-Simulacrum Management
    "SimulacrumManager",
    "SimulacrumMetadata",
    "SimulacrumToolHandler",
    "SIMULACRUM_TOOLS",
    "SpawnPolicy",
    "LifecyclePolicy",
    "ArchiveMetadata",
]
