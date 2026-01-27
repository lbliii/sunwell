"""Workflow Module — Autonomous Workflow Execution (RFC-086).

This module provides:
- WorkflowEngine: Procedural workflow executor with checkpoints
- IntentRouter: Natural language → workflow selection
- WorkflowState: State persistence across sessions
"""

from sunwell.features.workflow.engine import WorkflowEngine, WorkflowResult
from sunwell.features.workflow.router import IntentRouter
from sunwell.features.workflow.state import WorkflowState, WorkflowStateManager
from sunwell.features.workflow.types import (
    Intent,
    IntentCategory,
    WorkflowChain,
    WorkflowExecution,
    WorkflowStep,
    WorkflowStepResult,
    WorkflowTier,
)

__all__ = [
    # Engine
    "WorkflowEngine",
    "WorkflowResult",
    # Router
    "IntentRouter",
    # State
    "WorkflowState",
    "WorkflowStateManager",
    # Types
    "Intent",
    "IntentCategory",
    "WorkflowChain",
    "WorkflowExecution",
    "WorkflowStep",
    "WorkflowStepResult",
    "WorkflowTier",
]
