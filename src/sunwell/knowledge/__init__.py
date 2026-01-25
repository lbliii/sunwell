"""Knowledge domain - Codebase understanding and analysis.

This domain consolidates all modules that help understand code, projects, and workspaces.

RFC-138: Module Architecture Consolidation

Key components:
- Analysis: State DAG construction, workspace scanning, source context
- Codebase Intelligence: Decision memory, failure tracking, pattern learning
- Indexing: Continuous semantic indexing for RAG
- Project Management: Project registry, resolution, manifest, signals
- Embedding: Vector search and embedding protocols
- Navigation: Table of contents generation
- Bootstrap: Day-1 intelligence from Git history
- Workspace: Workspace detection and codebase indexing
- Environment: Environment discovery and model detection
- Extraction: Content extraction utilities

Example:
    >>> from sunwell.knowledge import scan_project, ProjectIntelligence
    >>> from sunwell.knowledge import IndexingService, create_smart_context
    >>> from sunwell.knowledge import resolve_project, ProjectRegistry
"""

# Analysis (State DAG, workspace scanning)
from sunwell.knowledge.analysis import (
    HealthProbeResult,
    SourceContext,
    StateDag,
    StateDagBuilder,
    StateDagEdge,
    StateDagNode,
    SymbolInfo,
    Workspace,
    WorkspaceConfig,
    WorkspaceDetector,
    WorkspaceLink,
    add_link,
    build_workspace,
    load_or_detect_workspace,
    remove_link,
    scan_project,
)

# Codebase Intelligence (RFC-045)
from sunwell.knowledge.codebase import (
    CodebaseAnalyzer,
    CodebaseGraph,
    CodeLocation,
    CodePath,
    Decision,
    DecisionMemory,
    FailedApproach,
    FailureMemory,
    IntelligenceExtractor,
    PatternProfile,
    ProjectContext,
    ProjectIntelligence,
    RejectedOption,
    learn_from_acceptance,
    learn_from_edit,
    learn_from_rejection,
)

# Indexing (RFC-108)
from sunwell.knowledge.indexing import (
    AutoFeatures,
    ContextResult,
    IndexMetrics,
    IndexState,
    IndexStatus,
    IndexingService,
    PROJECT_MARKERS,
    ProjectType,
    SmartContext,
    create_smart_context,
    detect_auto_features,
    detect_file_type,
    detect_project_type,
    estimate_goal_complexity,
    get_priority_files,
)

# Project Management (RFC-117, RFC-079)
from sunwell.knowledge.project import (
    AgentConfig,
    DevCommand,
    GitStatus,
    InferredGoal,
    ManifestError,
    PipelineStep,
    Prerequisite,
    PreviewType,
    Project,
    ProjectAnalysis,
    ProjectManifest,
    ProjectRegistry,
    ProjectResolutionError,
    ProjectResolver,
    ProjectSignals,
    ProjectType,
    ProjectValidationError,
    RegistryError,
    Serializable,
    SubProject,
    SuggestedAction,
    WorkspaceType,
    WORKSPACE_PRIMARIES,
    analyze_project,
    create_manifest,
    detect_sub_projects,
    gather_project_signals,
    init_project,
    invalidate_cache,
    is_monorepo,
    load_cached_analysis,
    load_manifest,
    resolve_project,
    save_manifest,
    validate_not_sunwell_repo,
    validate_workspace,
)

# Embedding
from sunwell.knowledge.embedding import (
    EmbeddingProtocol,
    EmbeddingResult,
    HashEmbedding,
    InMemoryIndex,
    MODEL_DIMENSIONS,
    OllamaEmbedding,
    SearchResult,
    TFIDFEmbedding,
    create_embedder,
)

# Navigation (RFC-124)
from sunwell.knowledge.navigation import (
    GeneratorConfig,
    NavigationResult,
    NavigatorConfig,
    ProjectToc,
    TocGenerator,
    TocNavigator,
    TocNode,
)

# Bootstrap (RFC-050)
from sunwell.knowledge.bootstrap import (
    BootstrapDecision,
    BootstrapOrchestrator,
    BootstrapPatterns,
    BootstrapResult,
    BootstrapStatus,
    CodeEvidence,
    ConfigEvidence,
    DocEvidence,
    GitEvidence,
    IncrementalBootstrap,
    OwnershipDomain,
    OwnershipMap,
)

# Workspace (RFC-024, RFC-043)
# Note: Workspace, WorkspaceConfig, WorkspaceDetector are exported from analysis.workspace
# For workspace package versions, import directly: from sunwell.knowledge.workspace import ...
from sunwell.knowledge.workspace import (
    CodebaseIndexer,
    DEFAULT_TRUST,
    ResolutionSource,
    WorkspaceResult,
    default_config_root,
    default_workspace_root,
    ensure_workspace_exists,
    format_resolution_message,
    resolve_trust_level,
    resolve_workspace,
)

# Environment (RFC-104)
from sunwell.knowledge.environment import (
    Pattern,
    ProjectEntry,
    ProjectRoot,
    UserEnvironment,
    add_reference,
    check_reference_health,
    clear_cache,
    create_project_entry_from_path,
    discover_projects_in_root,
    discover_roots,
    environment_exists,
    export_environment,
    extract_patterns,
    find_similar_references,
    get_environment_age,
    get_environment_path,
    get_patterns_for_project,
    get_reference_for_new_project,
    import_environment,
    list_references,
    load_environment,
    remove_reference,
    reset_environment,
    save_environment,
    suggest_patterns_for_new_project,
    suggest_references,
)

# Extraction
from sunwell.knowledge.extraction import (
    ExtractedFact,
    SquashResult,
    extract_goal_with_squash,
    section_aware_extract,
    squash_extract,
)

__all__ = [
    # Analysis
    "HealthProbeResult",
    "SourceContext",
    "StateDag",
    "StateDagBuilder",
    "StateDagEdge",
    "StateDagNode",
    "SymbolInfo",
    "Workspace",
    "WorkspaceConfig",
    "WorkspaceDetector",
    "WorkspaceLink",
    "add_link",
    "build_workspace",
    "load_or_detect_workspace",
    "remove_link",
    "scan_project",
    # Codebase Intelligence
    "CodebaseAnalyzer",
    "CodebaseGraph",
    "CodeLocation",
    "CodePath",
    "Decision",
    "DecisionMemory",
    "FailedApproach",
    "FailureMemory",
    "IntelligenceExtractor",
    "PatternProfile",
    "ProjectContext",
    "ProjectIntelligence",
    "RejectedOption",
    "learn_from_acceptance",
    "learn_from_edit",
    "learn_from_rejection",
    # Indexing
    "AutoFeatures",
    "ContextResult",
    "IndexMetrics",
    "IndexState",
    "IndexStatus",
    "IndexingService",
    "PROJECT_MARKERS",
    "ProjectType",
    "SmartContext",
    "create_smart_context",
    "detect_auto_features",
    "detect_file_type",
    "detect_project_type",
    "estimate_goal_complexity",
    "get_priority_files",
    # Project Management
    "AgentConfig",
    "DevCommand",
    "GitStatus",
    "InferredGoal",
    "ManifestError",
    "PipelineStep",
    "Prerequisite",
    "PreviewType",
    "Project",
    "ProjectAnalysis",
    "ProjectManifest",
    "ProjectRegistry",
    "ProjectResolutionError",
    "ProjectResolver",
    "ProjectSignals",
    "ProjectType",
    "ProjectValidationError",
    "RegistryError",
    "Serializable",
    "SubProject",
    "SuggestedAction",
    "WorkspaceType",
    "WORKSPACE_PRIMARIES",
    "analyze_project",
    "create_manifest",
    "detect_sub_projects",
    "gather_project_signals",
    "init_project",
    "invalidate_cache",
    "is_monorepo",
    "load_cached_analysis",
    "load_manifest",
    "resolve_project",
    "save_manifest",
    "validate_not_sunwell_repo",
    "validate_workspace",
    # Embedding
    "EmbeddingProtocol",
    "EmbeddingResult",
    "HashEmbedding",
    "InMemoryIndex",
    "MODEL_DIMENSIONS",
    "OllamaEmbedding",
    "SearchResult",
    "TFIDFEmbedding",
    "create_embedder",
    # Navigation
    "GeneratorConfig",
    "NavigationResult",
    "NavigatorConfig",
    "ProjectToc",
    "TocGenerator",
    "TocNavigator",
    "TocNode",
    # Bootstrap
    "BootstrapDecision",
    "BootstrapOrchestrator",
    "BootstrapPatterns",
    "BootstrapResult",
    "BootstrapStatus",
    "CodeEvidence",
    "ConfigEvidence",
    "DocEvidence",
    "GitEvidence",
    "IncrementalBootstrap",
    "OwnershipDomain",
    "OwnershipMap",
    # Workspace (RFC-024, RFC-043)
    "CodebaseIndexer",
    "DEFAULT_TRUST",
    "ResolutionSource",
    "WorkspaceResult",
    "default_config_root",
    "default_workspace_root",
    "ensure_workspace_exists",
    "format_resolution_message",
    "resolve_trust_level",
    "resolve_workspace",
    # Environment
    "Pattern",
    "ProjectEntry",
    "ProjectRoot",
    "UserEnvironment",
    "add_reference",
    "check_reference_health",
    "clear_cache",
    "create_project_entry_from_path",
    "discover_projects_in_root",
    "discover_roots",
    "environment_exists",
    "export_environment",
    "extract_patterns",
    "find_similar_references",
    "get_environment_age",
    "get_environment_path",
    "get_patterns_for_project",
    "get_reference_for_new_project",
    "import_environment",
    "list_references",
    "load_environment",
    "remove_reference",
    "reset_environment",
    "save_environment",
    "suggest_patterns_for_new_project",
    "suggest_references",
    # Extraction
    "ExtractedFact",
    "SquashResult",
    "extract_goal_with_squash",
    "section_aware_extract",
    "squash_extract",
]
