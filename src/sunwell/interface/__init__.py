"""Generative Interface — LLM-Driven Interaction Routing (RFC-075).

This module provides an LLM-driven system that analyzes user goals and
manifests the appropriate interaction type (workspace, view, action, or conversation).

Key components:
- IntentPipeline: Two-step classification + response (RECOMMENDED)
- IntentClassifier: Structured routing decisions
- ResponseGenerator: Route-aware response generation
- IntentAnalyzer: Legacy single-prompt approach (deprecated)
- InteractionRouter: Routes intents to appropriate handlers
- ActionExecutor: Executes actions against data providers
- ViewRenderer: Renders views for calendar, lists, notes, etc.

Usage (recommended):
    >>> from sunwell.interface import IntentPipeline
    >>> pipeline = IntentPipeline.create(model)
    >>> analysis = await pipeline.analyze("build a chat app")
"""

from sunwell.interface.analyzer import IntentAnalyzer
from sunwell.interface.block_actions import BlockActionExecutor, BlockActionResult
from sunwell.interface.classifier import ClassificationResult, IntentClassifier
from sunwell.interface.executor import ActionExecutor, ActionResult
from sunwell.interface.pipeline import IntentPipeline, analyze_with_pipeline
from sunwell.interface.responder import ResponseGenerator
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
    "ClassificationResult",
    # Router
    "ActionOutput",
    "ConversationOutput",
    "HybridOutput",
    "InteractionRouter",
    "ViewOutput",
    "WorkspaceOutput",
    # Pipeline (RECOMMENDED)
    "IntentPipeline",
    "IntentClassifier",
    "ResponseGenerator",
    "analyze_with_pipeline",
    # Legacy Components
    "IntentAnalyzer",
    "ActionExecutor",
    "ActionResult",
    "BlockActionExecutor",
    "BlockActionResult",
    "ViewRenderer",
]
