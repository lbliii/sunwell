"""Request types for Agent execution (RFC-MEMORY).

Defines RunOptions — execution configuration for Agent.run().

NOTE: RunRequest was REMOVED in RFC-MEMORY. Use SessionContext instead:
    - SessionContext: All session state (goal, workspace, options)
    - PersistentMemory: Unified memory facade
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.convergence import ConvergenceConfig
    from sunwell.core.lens import Lens


@dataclass(frozen=True, slots=True)
class RunOptions:
    """Execution options for Agent.run().

    Controls behavior during execution:
    - Trust level for tool execution
    - Timeout limits
    - Validation and convergence settings
    - Learning persistence
    """

    trust: str = "workspace"
    """Tool trust level: 'read_only', 'workspace', 'shell'."""

    timeout_seconds: int = 300
    """Maximum execution time in seconds."""

    converge: bool = False
    """Enable convergence loop (RFC-123)."""

    convergence_config: "ConvergenceConfig | None" = None
    """Configuration for convergence behavior."""

    validate: bool = True
    """Run validation gates after execution."""

    persist_learnings: bool = True
    """Save learnings to memory after execution."""

    auto_fix: bool = True
    """Automatically attempt to fix validation failures."""

    model: str | None = None
    """Override model name for this run."""

    lens: "Lens | None" = None
    """Lens to apply during execution."""
