"""Enhanced Progress Visualization with DAG Path Display.

Provides:
- DAGPathDisplay: Show current intent classification path
- NestedProgress: Track hierarchical task progress
- StatusBar: Persistent status bar with session metrics

Usage:
    from sunwell.interface.cli.progress import (
        DAGPathDisplay,
        NestedProgress,
        StatusBar,
    )
    
    # Show DAG path
    path_display = DAGPathDisplay(console)
    path_display.update(["conversation", "act", "write"])
    
    # Track nested progress
    progress = NestedProgress(console)
    with progress.task("Building auth") as task:
        with task.subtask("Writing tests") as sub:
            sub.update(50)
"""

from sunwell.interface.cli.progress.dag_path import DAGPathDisplay
from sunwell.interface.cli.progress.nested import NestedProgress, ProgressTask
from sunwell.interface.cli.progress.status_bar import StatusBar, StatusMetrics

__all__ = [
    "DAGPathDisplay",
    "NestedProgress",
    "ProgressTask",
    "StatusBar",
    "StatusMetrics",
]
