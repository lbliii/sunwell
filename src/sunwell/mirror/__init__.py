"""Mirror Neurons - Self-Introspection and Self-Programming Toolkit.

RFC-015: Gives Sunwell the ability to examine and improve itself.

Mirror neurons in the brain fire both when performing an action AND
when observing that action. This module gives Sunwell similar capabilities:

1. **Introspect** - Examine its own code, configuration, and behavior
2. **Analyze** - Detect patterns and diagnose issues
3. **Propose** - Generate improvement proposals
4. **Apply** - Make changes with safety guardrails
5. **Learn** - Persist insights for future sessions
6. **Route** - Select optimal models per task category (Phase 5)

Example:
    >>> from sunwell.mirror import MirrorHandler
    >>> mirror = MirrorHandler(sunwell_root=Path("."))
    >>> source = await mirror.introspect_source("sunwell.tools.executor")
    >>> patterns = await mirror.analyze_patterns(scope="session", focus="latency")
    
    # Phase 5: Model-aware routing
    >>> best_model = mirror.select_model_for_task("introspect_source")
"""

from sunwell.mirror.introspection import (
    SourceIntrospector,
    LensIntrospector,
    SimulacrumIntrospector,
    ExecutionIntrospector,
)
from sunwell.mirror.analysis import (
    PatternAnalyzer,
    FailureAnalyzer,
)
from sunwell.mirror.proposals import (
    Proposal,
    ProposalStatus,
    ProposalType,
    ProposalManager,
)
from sunwell.mirror.handler import MirrorHandler
from sunwell.mirror.tools import MIRROR_TOOLS, MIRROR_TOOL_TRUST, get_mirror_tools_for_trust
from sunwell.mirror.model_tracker import ModelPerformanceTracker, ModelPerformanceEntry
from sunwell.mirror.router import (
    ModelRouter,
    ModelRoutingConfig,
    TASK_CATEGORY_MAP,
    get_all_task_categories,
    get_tools_for_category,
)
from sunwell.mirror.safety import SafetyChecker, SafetyPolicy, validate_diff_safety

__all__ = [
    # Introspection
    "SourceIntrospector",
    "LensIntrospector",
    "SimulacrumIntrospector",
    "ExecutionIntrospector",
    # Analysis
    "PatternAnalyzer",
    "FailureAnalyzer",
    # Proposals
    "Proposal",
    "ProposalStatus",
    "ProposalType",
    "ProposalManager",
    # Handler
    "MirrorHandler",
    # Tools
    "MIRROR_TOOLS",
    "MIRROR_TOOL_TRUST",
    "get_mirror_tools_for_trust",
    # Model Routing (Phase 5)
    "ModelPerformanceTracker",
    "ModelPerformanceEntry",
    "ModelRouter",
    "ModelRoutingConfig",
    "TASK_CATEGORY_MAP",
    "get_all_task_categories",
    "get_tools_for_category",
    # Safety
    "SafetyChecker",
    "SafetyPolicy",
    "validate_diff_safety",
]
