"""Configuration for multi-instance coordination (RFC-051)."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class MultiInstanceConfig:
    """Configuration for multi-instance execution."""

    num_workers: int = 4
    """Number of worker processes."""

    lock_timeout_seconds: float = 30.0
    """Timeout for acquiring file locks."""

    worker_timeout_seconds: float = 3600.0
    """Maximum time for a single worker run (1 hour)."""

    merge_strategy: Literal["rebase", "squash"] = "rebase"
    """How to merge worker branches."""

    auto_merge: bool = True
    """Automatically merge clean branches."""

    cleanup_branches: bool = True
    """Delete worker branches after merge."""

    heartbeat_interval_seconds: float = 5.0
    """How often workers report status."""

    max_retries_per_goal: int = 2
    """How many times to retry a failed goal."""

    stale_lock_threshold_seconds: float = 60.0
    """Lock considered stale after this duration."""

    branch_prefix: str = "sunwell/worker-"
    """Prefix for worker branch names."""
