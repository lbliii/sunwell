"""Planning domain - Intent routing, reasoning, coordination, skills.

Key components:
- Naaru: Coordinated multi-model intelligence (the main entry point)
- UnifiedRouter: Intent-aware cognitive routing
- Reasoner: LLM-driven judgment for decisions
- Skill/SkillGraph: Agent skills integration
- LensManager: Lens discovery and loading

For advanced usage, import from subpackages directly:
    from sunwell.planning.naaru import ArtifactExecutor, ExecutionPlan
    from sunwell.planning.skills import SkillCompiler, SkillLibrary
    from sunwell.planning.routing import RoutingExemplar, ConfidenceRubric

RFC-138: Module Architecture Consolidation
"""

# === Primary Entry Points ===
# === Lens Management ===
from sunwell.planning.lens import (
    LensIndex,
    LensIndexEntry,
    LensManager,
)

# === Common Config Helpers ===
from sunwell.planning.naaru import (
    AgentResult,
    Naaru,
    NaaruConfig,
    Task,
    TaskStatus,
    create_auto_config,
    create_balanced_config,
    create_minimal_config,
)
from sunwell.planning.reasoning import (
    DecisionType,
    FastClassifier,
    ReasonedDecision,
    Reasoner,
)
from sunwell.planning.routing import (
    Complexity,
    Intent,
    RoutingDecision,
    UnifiedRouter,
)

# === Skills ===
from sunwell.planning.skills import (
    Skill,
    SkillCompiler,
    SkillGraph,
    SkillResult,
)

__all__ = [
    # === Primary API ===
    "Naaru",
    "NaaruConfig",
    "Task",
    "TaskStatus",
    "AgentResult",
    # === Routing ===
    "UnifiedRouter",
    "RoutingDecision",
    "Intent",
    "Complexity",
    # === Reasoning ===
    "Reasoner",
    "ReasonedDecision",
    "DecisionType",
    "FastClassifier",
    # === Skills ===
    "Skill",
    "SkillGraph",
    "SkillResult",
    "SkillCompiler",
    # === Lens ===
    "LensManager",
    "LensIndex",
    "LensIndexEntry",
    # === Config Helpers ===
    "create_auto_config",
    "create_balanced_config",
    "create_minimal_config",
]
