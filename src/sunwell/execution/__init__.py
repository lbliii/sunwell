"""Execution module for backlog-driven goal execution (RFC-094).

Single entry point for all goal execution.
"""

from sunwell.execution.context import BacklogContext
from sunwell.execution.emitter import StdoutEmitter
from sunwell.execution.manager import ExecutionManager, ExecutionResult

__all__ = [
    "BacklogContext",
    "ExecutionManager",
    "ExecutionResult",
    "StdoutEmitter",
]
