"""Convergence Loops — Self-Stabilizing Code Generation (RFC-123).

After file writes, run validation gates (lint, types, tests) in parallel.
If any fail, the agent fixes and loops until stable or limits are reached.

Example:
    >>> from sunwell.agent.convergence import ConvergenceLoop, ConvergenceConfig
    >>> loop = ConvergenceLoop(model=model, cwd=Path.cwd())
    >>> async for event in loop.run(changed_files):
    ...     print(event)
    >>> print(loop.result.status)  # STABLE or ESCALATED
"""

from sunwell.agent.convergence.loop import ConvergenceLoop
from sunwell.agent.convergence.types import (
    ConvergenceConfig,
    ConvergenceIteration,
    ConvergenceResult,
    ConvergenceStatus,
    GateCheckResult,
)

__all__ = [
    "ConvergenceConfig",
    "ConvergenceIteration",
    "ConvergenceLoop",
    "ConvergenceResult",
    "ConvergenceStatus",
    "GateCheckResult",
]
