"""Knowledge domain - Codebase understanding and analysis.

Key components:
- Workspace: Project workspace detection and configuration
- IndexingService: Continuous semantic indexing for RAG
- ProjectIntelligence: Codebase intelligence and pattern learning
- ProjectRegistry: Project management and resolution
- create_embedder: Vector search and embedding

For advanced usage, import from subpackages directly:
    from sunwell.knowledge.analysis import StateDag, SourceContext
    from sunwell.knowledge.codebase import DecisionMemory, FailureMemory
    from sunwell.knowledge.bootstrap import BootstrapOrchestrator

RFC-138: Module Architecture Consolidation
"""

# === Primary Entry Points ===

# Workspace detection and scanning
from sunwell.knowledge.analysis import (
    Workspace,
    WorkspaceConfig,
    scan_project,
    build_workspace,
)

# Codebase intelligence (RFC-045)
from sunwell.knowledge.codebase import (
    ProjectIntelligence,
    CodebaseAnalyzer,
    DecisionMemory,
)

# Indexing and RAG (RFC-108)
from sunwell.knowledge.indexing import (
    IndexingService,
    SmartContext,
    create_smart_context,
)

# Project management (RFC-117)
from sunwell.knowledge.project import (
    Project,
    ProjectRegistry,
    ProjectManifest,
    resolve_project,
    analyze_project,
)

# Embedding
from sunwell.knowledge.embedding import (
    EmbeddingProtocol,
    create_embedder,
    SearchResult,
)

# Environment discovery (RFC-104)
from sunwell.knowledge.environment import (
    UserEnvironment,
    load_environment,
    discover_roots,
)

__all__ = [
    # === Workspace ===
    "Workspace",
    "WorkspaceConfig",
    "scan_project",
    "build_workspace",
    # === Intelligence ===
    "ProjectIntelligence",
    "CodebaseAnalyzer",
    "DecisionMemory",
    # === Indexing ===
    "IndexingService",
    "SmartContext",
    "create_smart_context",
    # === Project ===
    "Project",
    "ProjectRegistry",
    "ProjectManifest",
    "resolve_project",
    "analyze_project",
    # === Embedding ===
    "EmbeddingProtocol",
    "create_embedder",
    "SearchResult",
    # === Environment ===
    "UserEnvironment",
    "load_environment",
    "discover_roots",
]
