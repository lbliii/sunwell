"""Protocol definitions for dependency injection and testing.

RFC-025: Protocol Layer - Enables dependency injection and testability.

Type definitions moved to sunwell.contracts; re-exported here
for backward compatibility.
"""

# Re-export serialization protocols from contracts
from sunwell.contracts.serialization import (
    DictSerializable,
    Embeddable,
    Promptable,
    Saveable,
    Serializable,
)

# Re-export execution protocols from contracts
from sunwell.contracts.execution import (
    ChatSessionProtocol,
    ConsoleProtocol,
    MemoryStoreProtocol,
    ParallelExecutorProtocol,
    ToolExecutorProtocol,
    ToolResult,
    WorkerProtocol,
)

# Re-export model types that were previously imported here
from sunwell.contracts.model import Tool, ToolCall

# NOTE: MessageBus and NaaruRegion were previously re-exported here
# for WorkerProtocol backward compat. Consumers should now import
# MessageBus/NaaruRegion directly from sunwell.planning.naaru.core.bus.
