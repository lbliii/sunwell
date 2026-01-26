"""Knowledge domain - Codebase understanding and analysis.

Key components:
- Workspace: Project workspace detection and configuration
- IndexingService: Continuous semantic indexing for RAG
- ProjectIntelligence: Codebase intelligence and pattern learning
- ProjectRegistry: Project management and resolution
- create_embedder: Vector search and embedding

For advanced usage, import from subpackages directly:
    from sunwell.knowledge.analysis import StateDag, SourceContext
    from sunwell.knowledge.codebase import FailedApproach, learn_from_edit
    from sunwell.knowledge.bootstrap import BootstrapOrchestrator

RFC-138: Module Architecture Consolidation
"""

# === Primary Entry Points ===

# Workspace detection and scanning
from sunwell.knowledge.analysis import (
    Workspace,
    WorkspaceConfig,
    build_workspace,
    scan_project,
)

# Question answering and context enrichment (RFC-135)
from sunwell.knowledge.answering import (
    AnswerResult,
    answer_question,
    answer_question_simple,
    enrich_context_for_goal,
)

# Codebase intelligence (RFC-045)
from sunwell.knowledge.codebase import (
    CodebaseAnalyzer,
    DecisionMemory,
    FailureMemory,
    PatternProfile,
    ProjectIntelligence,
)

# Embedding
from sunwell.knowledge.embedding import (
    EmbeddingProtocol,
    SearchResult,
    create_embedder,
)

# Environment discovery (RFC-104)
from sunwell.knowledge.environment import (
    UserEnvironment,
    discover_roots,
    load_environment,
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
    ProjectManifest,
    ProjectRegistry,
    analyze_project,
    resolve_project,
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
    "FailureMemory",
    "PatternProfile",
    # === Indexing ===
    "IndexingService",
    "SmartContext",
    "create_smart_context",
    # === Question Answering (RFC-135) ===
    "AnswerResult",
    "answer_question",
    "answer_question_simple",
    "enrich_context_for_goal",
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
