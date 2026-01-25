"""Execution module for backlog-driven goal execution (RFC-094).

Single entry point for all goal execution.
"""

from sunwell.agent.execution.context import BacklogContext
from sunwell.agent.execution.emitter import StdoutEmitter
from sunwell.agent.execution.manager import ExecutionManager, ExecutionResult

__all__ = [
    "BacklogContext",
    "ExecutionManager",
    "ExecutionResult",
    "StdoutEmitter",
]
