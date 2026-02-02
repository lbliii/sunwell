"""Project Intelligence - RFC-045: The Persistent Codebase Mind.

Project Intelligence transforms Sunwell from a stateless code assistant into
a persistent codebase mind that remembers decisions, understands relationships,
and learns preferences.

Components:
- Decision Memory: Architectural decisions with rationale
- Codebase Graph: Semantic understanding of code structure
- Pattern Learning: User/project style preferences
- Failure Memory: What didn't work and why
- Cross-Session Continuity: Persistent context across sessions

See: RFC-045-project-intelligence.md
"""

from sunwell.knowledge.codebase.advisor import (
    ComplexityEstimate,
    ExecutionOrder,
    FocusedContext,
    ImpactScope,
    TaskAdvice,
    TaskGraphAdvisor,
    TaskType,
)
from sunwell.knowledge.codebase.algorithms import (
    FanMetrics,
    GraphAlgorithms,
    SubgraphResult,
)
from sunwell.knowledge.codebase.codebase import (
    CodebaseAnalyzer,
    CodebaseGraph,
    CodeLocation,
    CodePath,
    EdgeType,
    NodeType,
    StructuralEdge,
    StructuralNode,
)
from sunwell.knowledge.codebase.context import (
    ProjectContext,
    ProjectIntelligence,
)
from sunwell.knowledge.codebase.decisions import (
    Decision,
    DecisionMemory,
    RejectedOption,
)
from sunwell.knowledge.codebase.extractor import IntelligenceExtractor
from sunwell.knowledge.codebase.failures import (
    FailedApproach,
    FailureMemory,
)
from sunwell.knowledge.codebase.patterns import (
    PatternProfile,
    learn_from_acceptance,
    learn_from_edit,
    learn_from_rejection,
)

__all__ = [
    # Decision Memory
    "Decision",
    "DecisionMemory",
    "RejectedOption",
    # Failure Memory
    "FailedApproach",
    "FailureMemory",
    # Pattern Learning
    "PatternProfile",
    "learn_from_edit",
    "learn_from_rejection",
    "learn_from_acceptance",
    # Codebase Graph
    "CodebaseGraph",
    "CodebaseAnalyzer",
    "CodeLocation",
    "CodePath",
    # Structural Graph Types
    "NodeType",
    "EdgeType",
    "StructuralNode",
    "StructuralEdge",
    # Graph Algorithms
    "GraphAlgorithms",
    "FanMetrics",
    "SubgraphResult",
    # Task Graph Advisor
    "TaskGraphAdvisor",
    "TaskType",
    "TaskAdvice",
    "ComplexityEstimate",
    "ImpactScope",
    "FocusedContext",
    "ExecutionOrder",
    # Context
    "ProjectContext",
    "ProjectIntelligence",
    # Extraction
    "IntelligenceExtractor",
]
