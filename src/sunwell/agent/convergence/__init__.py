"""Convergence mode for self-driving agent execution.

Implements the accept-and-fix pattern from Cursor's self-driving
codebases research: workers commit freely to work branches, and a
separate reconciliation pass validates and merges to main.

This trades strict per-commit correctness for dramatically higher
throughput, accepting a small stable error rate that gets fixed
by the reconciler.

Key insight: "When we required 100% correctness before every single
commit, it caused major serialization and slowdowns of effective
throughput."
"""

from sunwell.agent.convergence.reconciler import (
    ErrorBudget,
    ReconciliationResult,
    Reconciler,
)

__all__ = [
    "ErrorBudget",
    "ReconciliationResult",
    "Reconciler",
]
