"""Shared contracts: protocols, types, and dataclasses.

This module is Layer 0 — it may only import from stdlib.
All other sunwell modules may import from here.

The purpose of this module is to break circular dependencies by providing
a single home for the protocol definitions and shared types that multiple
modules need. Each protocol was previously defined inside the module that
implements it, which forced every *consumer* to import from that module,
creating bidirectional dependencies.

Migration note: All types re-exported from their original locations for
backward compatibility. New code should import from sunwell.contracts.
"""

# Serialization protocols
# Domain types and protocols
from sunwell.contracts.domain import (
    Domain,
    DomainType,
    DomainValidator,
    ValidationResult,
)

# Event types
from sunwell.contracts.events import (
    AgentEvent,
    EventEmitter,
    EventType,
    EventUIHints,
    GateSummary,
    TaskSummary,
)

# Execution protocols
from sunwell.contracts.execution import (
    ChatSessionProtocol,
    ConsoleProtocol,
    MemoryStoreProtocol,
    ParallelExecutorProtocol,
    ToolExecutorProtocol,
    ToolResult,
    WorkerProtocol,
)

# Fount protocol
from sunwell.contracts.fount import FountProtocol

# Model types and protocol
from sunwell.contracts.model import (
    GenerateOptions,
    GenerateResult,
    Message,
    ModelProtocol,
    TokenUsage,
    Tool,
    ToolCall,
)
from sunwell.contracts.serialization import (
    DictSerializable,
    Embeddable,
    Promptable,
    Saveable,
    Serializable,
)

__all__ = [
    # Serialization
    "Serializable",
    "DictSerializable",
    "Promptable",
    "Embeddable",
    "Saveable",
    # Model
    "ModelProtocol",
    "Message",
    "Tool",
    "ToolCall",
    "GenerateOptions",
    "GenerateResult",
    "TokenUsage",
    # Events
    "EventType",
    "AgentEvent",
    "EventUIHints",
    "EventEmitter",
    "TaskSummary",
    "GateSummary",
    # Execution
    "ConsoleProtocol",
    "ChatSessionProtocol",
    "MemoryStoreProtocol",
    "ToolExecutorProtocol",
    "ToolResult",
    "ParallelExecutorProtocol",
    "WorkerProtocol",
    # Fount
    "FountProtocol",
    # Domain
    "DomainType",
    "ValidationResult",
    "DomainValidator",
    "Domain",
]
