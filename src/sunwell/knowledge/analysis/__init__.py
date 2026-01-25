"""Analysis module for project scanning and State DAG construction (RFC-100, RFC-103).

This module provides infrastructure for building State DAGs from existing projects,
enabling brownfield workflows where Sunwell can understand and improve existing codebases.

Two-DAG Architecture:
- State DAG: Scan existing project → show "what exists and its health"
- Execution DAG: Plan tasks → track progress → complete goal (existing Sunwell behavior)

The State DAG enables ~95% of real-world work (brownfield) vs just greenfield builds.

RFC-103 adds workspace-aware scanning:
- Auto-detect related source code repositories
- Enable drift detection between docs and source
- Cross-reference validation
"""

from sunwell.knowledge.analysis.source_context import SourceContext, SymbolInfo
from sunwell.knowledge.analysis.state_dag import (
    HealthProbeResult,
    StateDag,
    StateDagBuilder,
    StateDagEdge,
    StateDagNode,
    scan_project,
)
from sunwell.knowledge.analysis.workspace import (
    Workspace,
    WorkspaceConfig,
    WorkspaceDetector,
    WorkspaceLink,
    build_workspace,
    load_or_detect_workspace,
)

__all__ = [
    # State DAG (RFC-100)
    "HealthProbeResult",
    "StateDag",
    "StateDagBuilder",
    "StateDagEdge",
    "StateDagNode",
    "scan_project",
    # Workspace (RFC-103)
    "Workspace",
    "WorkspaceConfig",
    "WorkspaceDetector",
    "WorkspaceLink",
    "build_workspace",
    "load_or_detect_workspace",
    # Source Context (RFC-103)
    "SourceContext",
    "SymbolInfo",
]
