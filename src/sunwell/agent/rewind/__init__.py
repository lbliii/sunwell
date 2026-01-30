"""Code state rewind system for error recovery.

Enables users to rewind file system changes to previous states,
supporting both conversation-only and code-only rewind modes.

Usage:
    from sunwell.agent.rewind import SnapshotManager, RewindMode
    
    manager = SnapshotManager(workspace)
    snapshot = manager.take_snapshot()
    
    # Later, if needed
    result = manager.rewind_to(snapshot.id, mode=RewindMode.CODE_ONLY)
"""

from sunwell.agent.rewind.snapshot import (
    CodeSnapshot,
    RewindMode,
    RewindResult,
    SnapshotManager,
)

__all__ = [
    "CodeSnapshot",
    "RewindMode",
    "RewindResult",
    "SnapshotManager",
]
