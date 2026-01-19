"""Adaptive Agent — Signal-Driven Execution (RFC-042).

Makes all advanced features automatic by default. The agent uses cheap signals
to decide when to apply expensive techniques. Users just say what they want;
the infrastructure figures out how.

Key components:
- Event streaming for live progress updates
- Validation gates at runnable milestones
- Signal-based routing (complexity, confidence, error type)
- Iterative DAG expansion with intra-session learning
- Simulacrum integration for cross-session memory

Example:
    >>> from sunwell.adaptive import AdaptiveAgent
    >>> agent = AdaptiveAgent(model=my_model)
    >>> async for event in agent.run("Build a Flask forum app"):
    ...     print(event)
"""

from sunwell.adaptive.agent import AdaptiveAgent, TaskGraph, run_adaptive
from sunwell.adaptive.budget import AdaptiveBudget, CostEstimate
from sunwell.adaptive.events import AgentEvent, EventType
from sunwell.adaptive.fixer import FixResult, FixStage
from sunwell.adaptive.gates import GateDetector, GateResult, GateType, ValidationGate
from sunwell.adaptive.learning import Learning, LearningExtractor, LearningStore
from sunwell.adaptive.renderer import (
    JSONRenderer,
    QuietRenderer,
    RendererConfig,
    RichRenderer,
    create_renderer,
)
from sunwell.adaptive.signals import (
    AdaptiveSignals,
    ErrorSignals,
    TaskSignals,
    extract_signals,
)
from sunwell.adaptive.toolchain import LanguageToolchain, detect_toolchain
from sunwell.adaptive.validation import Artifact, ValidationRunner, ValidationStage

__all__ = [
    # Agent
    "AdaptiveAgent",
    "TaskGraph",
    "run_adaptive",
    # Budget
    "AdaptiveBudget",
    "CostEstimate",
    # Events
    "AgentEvent",
    "EventType",
    # Fixer
    "FixStage",
    "FixResult",
    # Gates
    "GateType",
    "ValidationGate",
    "GateResult",
    "GateDetector",
    # Learning
    "Learning",
    "LearningExtractor",
    "LearningStore",
    # Renderer
    "RichRenderer",
    "QuietRenderer",
    "JSONRenderer",
    "RendererConfig",
    "create_renderer",
    # Signals
    "AdaptiveSignals",
    "ErrorSignals",
    "extract_signals",
    "TaskSignals",
    # Toolchains
    "LanguageToolchain",
    "detect_toolchain",
    # Validation
    "Artifact",
    "ValidationRunner",
    "ValidationStage",
]
