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

from sunwell.intelligence.codebase import (
    CodebaseAnalyzer,
    CodebaseGraph,
    CodeLocation,
    CodePath,
)
from sunwell.intelligence.context import (
    ProjectContext,
    ProjectIntelligence,
)
from sunwell.intelligence.decisions import (
    Decision,
    DecisionMemory,
    RejectedOption,
)
from sunwell.intelligence.extractor import IntelligenceExtractor
from sunwell.intelligence.failures import (
    FailedApproach,
    FailureMemory,
)
from sunwell.intelligence.patterns import (
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
    # Context
    "ProjectContext",
    "ProjectIntelligence",
    # Extraction
    "IntelligenceExtractor",
]
