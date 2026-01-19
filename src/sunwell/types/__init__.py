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
    ErrorCategory,
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
    RetrievalResult,  # Alias for backward compatibility
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
    "ErrorCategory",
    "ValidationExecutionError",
    "ModelError",
    "LensResolutionError",
    # Config types
    "NaaruConfig",
    "ModelConfig",
    "EmbeddingConfig",
    # Memory types
    "ContextBudget",
    "MemoryRetrievalResult",
    "RetrievalResult",  # Alias for backward compatibility
    # Routing types
    "RoutingTier",
    # Protocols (RFC-025)
    "ConsoleProtocol",
    "ChatSessionProtocol",
    "MemoryStoreProtocol",
    "ToolExecutorProtocol",
    "ParallelExecutorProtocol",
]
