"""Type definitions - single source of truth for all shared types.

This package consolidates duplicate type definitions across the codebase.
All imports should come from here.
"""

from sunwell.foundation.types.config import (
    EmbeddingConfig,
    ModelConfig,
    NaaruConfig,
)
from sunwell.foundation.types.core import (
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
from sunwell.foundation.types.memory import (
    ContextBudget,
    MemoryRetrievalResult,
)
from sunwell.foundation.types.model_size import ModelSize
from sunwell.foundation.types.naaru_api import (
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
from sunwell.foundation.types.protocol import (
    ChatSessionProtocol,
    ConsoleProtocol,
    DictSerializable,
    Embeddable,
    MemoryStoreProtocol,
    ParallelExecutorProtocol,
    Promptable,
    Saveable,
    Serializable,
    ToolExecutorProtocol,
    WorkerProtocol,
)
from sunwell.foundation.types.routing import (
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
    "Serializable",
    "DictSerializable",
    "Promptable",
    "Embeddable",
    "Saveable",
    "ConsoleProtocol",
    "ChatSessionProtocol",
    "MemoryStoreProtocol",
    "ToolExecutorProtocol",
    "ParallelExecutorProtocol",
    "WorkerProtocol",
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
