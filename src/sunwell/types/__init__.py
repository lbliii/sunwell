"""Type definitions - single source of truth for all shared types.

This package consolidates duplicate type definitions across the codebase.
All imports should come from here.
"""

from sunwell.types.config import (
    EmbeddingConfig,
    ModelConfig,
    NaaruConfig,
)
from sunwell.types.core import (
    Confidence,
    IntentCategory,
    LensReference,
    LensResolutionError,
    ModelError,
    SemanticVersion,
    Severity,
    Tier,
    ValidationExecutionError,
    ValidationMethod,
)
from sunwell.types.memory import (
    ContextBudget,
    MemoryRetrievalResult,
)
from sunwell.types.model_size import ModelSize
from sunwell.types.naaru_api import (
    CONVERGENCE_SLOTS,
    SLOT_TTL_SECONDS,
    CompositionSpec,
    ConversationMessage,
    NaaruError,
    NaaruEvent,
    NaaruEventType,
    ProcessInput,
    ProcessMode,
    ProcessOutput,
    RoutingDecision,
    get_slot_ttl,
)
from sunwell.types.protocol import (
    ChatSessionProtocol,
    ConsoleProtocol,
    MemoryStoreProtocol,
    ParallelExecutorProtocol,
    ToolExecutorProtocol,
)
from sunwell.types.routing import (
    RoutingTier,
)

__all__ = [
    # Core types
    "Severity",
    "Tier",
    "ValidationMethod",
    "IntentCategory",
    "SemanticVersion",
    "LensReference",
    "Confidence",
    "ValidationExecutionError",
    "ModelError",
    "LensResolutionError",
    # Config types
    "NaaruConfig",
    "ModelConfig",
    "EmbeddingConfig",
    "ModelSize",
    # Memory types
    "ContextBudget",
    "MemoryRetrievalResult",
    # Routing types
    "RoutingTier",
    # Protocols (RFC-025)
    "ConsoleProtocol",
    "ChatSessionProtocol",
    "MemoryStoreProtocol",
    "ToolExecutorProtocol",
    "ParallelExecutorProtocol",
    # Naaru API types (RFC-083)
    "CompositionSpec",
    "ConversationMessage",
    "NaaruError",
    "NaaruEvent",
    "NaaruEventType",
    "ProcessInput",
    "ProcessMode",
    "ProcessOutput",
    "RoutingDecision",
    "CONVERGENCE_SLOTS",
    "SLOT_TTL_SECONDS",
    "get_slot_ttl",
]
