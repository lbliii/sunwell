"""Generative Interface — LLM-Driven Interaction Routing (RFC-075).

This module provides an LLM-driven system that analyzes user goals and
manifests the appropriate interaction type (workspace, view, action, or conversation).

Key components:
- IntentAnalyzer: LLM-based intent classification
- InteractionRouter: Routes intents to appropriate handlers
- ActionExecutor: Executes actions against data providers
- ViewRenderer: Renders views for calendar, lists, notes, etc.
"""

from sunwell.interface.analyzer import IntentAnalyzer
from sunwell.interface.block_actions import BlockActionExecutor, BlockActionResult
from sunwell.interface.executor import ActionExecutor, ActionResult
from sunwell.interface.router import (
    ActionOutput,
    ConversationOutput,
    HybridOutput,
    InteractionRouter,
    ViewOutput,
    WorkspaceOutput,
)
from sunwell.interface.types import (
    ActionSpec,
    IntentAnalysis,
    InteractionType,
    ViewSpec,
)
from sunwell.interface.views import ViewRenderer

__all__ = [
    # Types
    "ActionSpec",
    "IntentAnalysis",
    "InteractionType",
    "ViewSpec",
    # Router
    "ActionOutput",
    "ConversationOutput",
    "HybridOutput",
    "InteractionRouter",
    "ViewOutput",
    "WorkspaceOutput",
    # Components
    "IntentAnalyzer",
    "ActionExecutor",
    "ActionResult",
    "BlockActionExecutor",
    "BlockActionResult",
    "ViewRenderer",
]
