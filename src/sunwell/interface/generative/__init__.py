"""Interface domain - CLI, Server, UI primitives, Generative Interface.

RFC-138: Module Architecture Consolidation

This domain consolidates all user-facing modules:
- CLI: Command-line interface
- Server: HTTP API for Studio
- Surface: UI primitives
- Generative: LLM-driven interaction routing (RFC-075)

This module provides an LLM-driven system that analyzes user goals and
manifests the appropriate interaction type (workspace, view, action, or conversation).

Key components:
- IntentPipeline: Two-step classification + response (RECOMMENDED)
- IntentClassifier: Structured routing decisions
- ResponseGenerator: Route-aware response generation
- InteractionRouter: Routes intents to appropriate handlers
- ActionExecutor: Executes actions against data providers
- ViewRenderer: Renders views for calendar, lists, notes, etc.

Usage (recommended):
    >>> from sunwell.interface.generative import IntentPipeline
    >>> pipeline = IntentPipeline.create(model)
    >>> analysis = await pipeline.analyze("build a chat app")
"""

from sunwell.interface.generative.block_actions import BlockActionExecutor, BlockActionResult
from sunwell.interface.generative.classifier import ClassificationResult, IntentClassifier
from sunwell.interface.generative.executor import ActionExecutor, ActionResult
from sunwell.interface.generative.pipeline import IntentPipeline, analyze_with_pipeline
from sunwell.interface.generative.responder import ResponseGenerator
from sunwell.interface.generative.router import (
    ActionOutput,
    ConversationOutput,
    HybridOutput,
    InteractionRouter,
    ViewOutput,
    WorkspaceOutput,
)
from sunwell.interface.generative.types import (
    ActionSpec,
    IntentAnalysis,
    InteractionType,
    Serializable,
    ViewSpec,
)
from sunwell.interface.generative.views import ViewRenderer

__all__ = [
    # Types
    "ActionSpec",
    "IntentAnalysis",
    "InteractionType",
    "Serializable",
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
    # Executors and Renderers
    "ActionExecutor",
    "ActionResult",
    "BlockActionExecutor",
    "BlockActionResult",
    "ViewRenderer",
]
