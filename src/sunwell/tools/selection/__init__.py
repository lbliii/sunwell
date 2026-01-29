"""Tool selection module for intelligent progressive tool disclosure.

This module provides multi-signal tool selection that combines:
1. DAG-based workflow knowledge (tool progressions)
2. Learned patterns from LearningStore
3. Progressive trust from ProgressivePolicy
4. Project type filtering
5. Lens tool profiles
6. Dead end avoidance
7. Semantic relevance (embedding-based retrieval)
8. Plan-then-execute (heuristic tool planning)
9. Tool rationale validation (post-selection)

The goal is to dramatically reduce tool count for small models while
maintaining full capabilities for large models.
"""

from sunwell.tools.selection.embedding import ToolEmbeddingIndex
from sunwell.tools.selection.graph import (
    DEFAULT_TOOL_DAG,
    ToolDAG,
    ToolDAGError,
    ToolNode,
)
from sunwell.tools.selection.planner import (
    ToolPlan,
    ToolPlanner,
    plan_heuristic,
)
from sunwell.tools.selection.rationale import (
    RationaleStrength,
    ToolRationale,
    ToolRationaleValidator,
    generate_heuristic_rationale,
)
from sunwell.tools.selection.selector import (
    MultiSignalToolSelector,
    SelectionTrace,
    ToolScore,
)

__all__ = [
    # DAG
    "ToolDAG",
    "ToolNode",
    "ToolDAGError",
    "DEFAULT_TOOL_DAG",
    # Selector
    "MultiSignalToolSelector",
    "SelectionTrace",
    "ToolScore",
    # Embedding
    "ToolEmbeddingIndex",
    # Planning
    "ToolPlan",
    "ToolPlanner",
    "plan_heuristic",
    # Rationale
    "RationaleStrength",
    "ToolRationale",
    "ToolRationaleValidator",
    "generate_heuristic_rationale",
]
