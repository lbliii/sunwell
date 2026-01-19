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

**Import Guidelines:**

Import directly from subpackages for clarity:

```python
# Preferred: Explicit subpackage imports
from sunwell.simulacrum.core import SimulacrumStore, Turn, ConversationDAG
from sunwell.simulacrum.manager import SimulacrumManager
from sunwell.simulacrum.topology import UnifiedMemoryStore, MemoryNode
from sunwell.simulacrum.hierarchical import ChunkManager, Chunk
from sunwell.simulacrum.context import ContextAssembler, Focus
from sunwell.simulacrum.extractors import SpatialExtractor
from sunwell.simulacrum.parallel import ParallelRetriever
```

**Subpackages:**
- `core/` - Core abstractions (store, dag, turn, memory, Simulacrum)
- `hierarchical/` - RFC-013 hierarchical memory (chunks, chunk_manager, ctf, summarizer)
- `topology/` - RFC-014 multi-topology memory (spatial, structural, facets, unified_store)
- `extractors/` - Memory extractors (spatial, topology, structural, facet, learning)
- `context/` - Context assembly and focus management
- `parallel/` - Parallel retrieval across multiple memory stores
- `manager/` - Multi-simulacrum management (spawning, lifecycle, archiving)
"""

# Only export the most commonly used items for convenience
# All other items should be imported from their subpackages

from sunwell.simulacrum.core import (
    ConversationDAG,
    Learning,
    Simulacrum,
    SimulacrumStore,
    StorageConfig,
    Turn,
    TurnType,
)
from sunwell.simulacrum.manager import (
    SimulacrumManager,
    SimulacrumMetadata,
)

__all__ = [
    # Core (most commonly used)
    "Simulacrum",
    "SimulacrumStore",
    "StorageConfig",
    "Turn",
    "TurnType",
    "Learning",
    "ConversationDAG",

    # Multi-simulacrum management (commonly used)
    "SimulacrumManager",
    "SimulacrumMetadata",
]
