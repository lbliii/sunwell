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
    >>> mirror = MirrorHandler(workspace=Path("."))
    >>> source = await mirror.introspect_source("sunwell.tools.executor")
    >>> patterns = await mirror.analyze_patterns(scope="session", focus="latency")

    # Phase 5: Model-aware routing
    >>> best_model = mirror.select_model_for_task("introspect_source")
"""

from sunwell.mirror.analysis import (
    FailureAnalyzer,
    analyze_errors,
    analyze_latency,
    analyze_tool_usage,
)
from sunwell.mirror.handler import MirrorHandler
from sunwell.mirror.introspection import (
    SourceIntrospector,
    # Lens introspection functions
    lens_get_all,
    lens_get_framework,
    lens_get_heuristics,
    lens_get_personas,
    lens_get_validators,
    # Simulacrum introspection functions
    simulacrum_get_all,
    simulacrum_get_context,
    simulacrum_get_dead_ends,
    simulacrum_get_focus,
    simulacrum_get_learnings,
    # Execution introspection functions
    execution_get_error_summary,
    execution_get_errors,
    execution_get_recent_tool_calls,
    execution_get_stats,
)
from sunwell.mirror.model_tracker import ModelPerformanceEntry, ModelPerformanceTracker
from sunwell.mirror.proposals import (
    Proposal,
    ProposalManager,
    ProposalStatus,
    ProposalType,
)
from sunwell.mirror.router import (
    TASK_CATEGORY_MAP,
    ModelRouter,
    ModelRoutingConfig,
    get_all_task_categories,
    get_tools_for_category,
)
from sunwell.mirror.safety import SafetyChecker, SafetyPolicy, validate_diff_safety
from sunwell.mirror.tools import MIRROR_TOOL_TRUST, MIRROR_TOOLS, get_mirror_tools_for_trust

__all__ = [
    # Source Introspection (class - has internal state)
    "SourceIntrospector",
    # Lens Introspection (module functions)
    "lens_get_all",
    "lens_get_framework",
    "lens_get_heuristics",
    "lens_get_personas",
    "lens_get_validators",
    # Simulacrum Introspection (module functions)
    "simulacrum_get_all",
    "simulacrum_get_context",
    "simulacrum_get_dead_ends",
    "simulacrum_get_focus",
    "simulacrum_get_learnings",
    # Execution Introspection (module functions)
    "execution_get_error_summary",
    "execution_get_errors",
    "execution_get_recent_tool_calls",
    "execution_get_stats",
    # Pattern Analysis (module functions)
    "analyze_errors",
    "analyze_latency",
    "analyze_tool_usage",
    # Failure Analysis (frozen dataclass)
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
