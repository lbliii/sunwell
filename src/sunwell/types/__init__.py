"""Type definitions - single source of truth for all shared types.

This package consolidates duplicate type definitions across the codebase.
All imports should come from here.
"""

from sunwell.types.core import (
    Severity,
    Tier,
    ValidationMethod,
    IntentCategory,
    SemanticVersion,
    LensReference,
    Confidence,
    ErrorCategory,
    ValidationExecutionError,
    ModelError,
    LensResolutionError,
)

from sunwell.types.config import (
    NaaruConfig,
    ModelConfig,
    EmbeddingConfig,
)

from sunwell.types.memory import (
    ContextBudget,
    MemoryRetrievalResult,
    RetrievalResult,  # Alias for backward compatibility
)

from sunwell.types.routing import (
    RoutingTier,
)

from sunwell.types.protocol import (
    ConsoleProtocol,
    ChatSessionProtocol,
    MemoryStoreProtocol,
    ToolExecutorProtocol,
    ParallelExecutorProtocol,
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
