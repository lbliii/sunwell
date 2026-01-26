"""Request types for Agent execution (RFC-MEMORY).

Defines RunOptions — execution configuration for Agent.run().

NOTE: RunRequest was REMOVED in RFC-MEMORY. Use SessionContext instead:
    - SessionContext: All session state (goal, workspace, options)
    - PersistentMemory: Unified memory facade

RFC-137 adds model delegation options for cost optimization:
    - enable_delegation: Turn on smart-to-dumb delegation
    - smart_model / delegation_model: Configure the model pair
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.agent.convergence import ConvergenceConfig
    from sunwell.foundation.core.lens import Lens
    from sunwell.models import ModelProtocol


@dataclass(frozen=True, slots=True)
class RunOptions:
    """Execution options for Agent.run().

    Controls behavior during execution:
    - Trust level for tool execution
    - Timeout limits
    - Validation and convergence settings
    - Learning persistence
    - Model delegation (RFC-137)

    Example with delegation:
        >>> options = RunOptions(
        ...     enable_delegation=True,
        ...     smart_model="claude-3-opus-20240229",  # or model instance
        ...     delegation_model="claude-3-haiku-20240307",
        ...     delegation_threshold_tokens=3000,
        ... )
    """

    trust: str = "workspace"
    """Tool trust level: 'read_only', 'workspace', 'shell'."""

    timeout_seconds: int = 300
    """Maximum execution time in seconds."""

    converge: bool = False
    """Enable convergence loop (RFC-123)."""

    convergence_config: ConvergenceConfig | None = None
    """Configuration for convergence behavior."""

    validate: bool = True
    """Run validation gates after execution."""

    persist_learnings: bool = True
    """Save learnings to memory after execution."""

    auto_fix: bool = True
    """Automatically attempt to fix validation failures."""

    model: str | None = None
    """Override model name for this run."""

    lens: Lens | None = None
    """Lens to apply during execution."""

    # =========================================================================
    # RFC-137: Smart-to-Dumb Model Delegation
    # =========================================================================

    enable_delegation: bool = False
    """Enable smart-to-dumb model delegation for cost optimization.

    When enabled, large tasks (based on delegation_threshold_tokens) are
    handled by having a smart model create an EphemeralLens, then a cheap
    model executes using that lens for guidance.

    Requires delegation_model to be set.
    """

    delegation_threshold_tokens: int = 2000
    """Minimum estimated output tokens to trigger delegation.

    Tasks with estimated output below this threshold run on the primary
    model directly. Set higher for more conservative delegation.
    """

    smart_model: ModelProtocol | str | None = None
    """Smart model for lens creation during delegation.

    Can be:
    - A ModelProtocol instance (direct use)
    - A string model name (resolved via ModelRegistry)
    - None (uses primary model for lens creation)

    Example: "claude-3-opus-20240229" or opus_model_instance
    """

    delegation_model: ModelProtocol | str | None = None
    """Cheap model for delegated execution.

    Can be:
    - A ModelProtocol instance (direct use)
    - A string model name (resolved via ModelRegistry)
    - None (delegation disabled even if enable_delegation=True)

    Example: "claude-3-haiku-20240307" or haiku_model_instance
    """
