"""Unified memory facade (RFC-MEMORY)."""

from sunwell.memory.facade.persistent import GoalMemory, PersistentMemory

__all__ = [
    "PersistentMemory",
    "GoalMemory",
]
