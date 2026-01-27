"""Coordination — Multi-agent coordination infrastructure.

This module provides infrastructure for coordinating multiple agent instances
working on related tasks (subagents, parallel work, etc.).

Components:
- SubagentRegistry: Track spawned subagents and their lifecycle
- SubagentRecord: Data model for subagent state

Based on patterns from moltbot's subagent-registry.ts but adapted for
sunwell's async/Python patterns.
"""

from sunwell.agent.coordination.registry import (
    SubagentOutcome,
    SubagentRecord,
    SubagentRegistry,
)

__all__ = [
    "SubagentRecord",
    "SubagentRegistry",
    "SubagentOutcome",
]
