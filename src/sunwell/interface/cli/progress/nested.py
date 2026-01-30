"""Nested task progress for hierarchical operations.

Tracks progress through nested task hierarchies with
visual indentation and status indicators.
"""

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Generator

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TaskID,
)

from sunwell.interface.cli.core.theme import SUNWELL_THEME


@dataclass
class ProgressTask:
    """A single task in the progress hierarchy.
    
    Supports nested subtasks with visual indentation.
    """
    
    id: TaskID
    name: str
    progress: Progress
    depth: int = 0
    parent: "ProgressTask | None" = None
    children: list["ProgressTask"] = field(default_factory=list)
    
    def update(self, completed: float | None = None, total: float | None = None) -> None:
        """Update task progress.
        
        Args:
            completed: Completed amount (0-100 for percentage)
            total: Total amount
        """
        kwargs = {}
        if completed is not None:
            kwargs["completed"] = completed
        if total is not None:
            kwargs["total"] = total
        self.progress.update(self.id, **kwargs)
    
    def complete(self) -> None:
        """Mark task as complete."""
        self.progress.update(self.id, completed=100)
    
    @contextmanager
    def subtask(
        self,
        description: str,
        total: float = 100,
    ) -> Generator["ProgressTask", None, None]:
        """Create a subtask.
        
        Args:
            description: Subtask description
            total: Total progress value
            
        Yields:
            ProgressTask for the subtask
        """
        # Create indented description
        indent = "  " * (self.depth + 1)
        prefix = "└─ " if self.depth < 2 else "·"
        indented_desc = f"{indent}{prefix} {description}"
        
        task_id = self.progress.add_task(indented_desc, total=total)
        subtask = ProgressTask(
            id=task_id,
            name=description,
            progress=self.progress,
            depth=self.depth + 1,
            parent=self,
        )
        self.children.append(subtask)
        
        try:
            yield subtask
        finally:
            # Auto-complete if not already complete
            task_info = self.progress.tasks[task_id]
            if task_info.completed < task_info.total:
                self.progress.update(task_id, completed=task_info.total)


@dataclass
class NestedProgress:
    """Manager for nested task progress visualization.
    
    Provides a context manager for creating hierarchical
    progress displays with proper indentation.
    
    Example:
        >>> with NestedProgress(console) as np:
        ...     with np.task("Building authentication") as auth:
        ...         auth.update(25)
        ...         with auth.subtask("Writing tests") as tests:
        ...             tests.update(50)
        ...         auth.complete()
    """
    
    console: Console | None = None
    _progress: Progress | None = field(default=None, init=False)
    _tasks: list[ProgressTask] = field(default_factory=list, init=False)
    _active: bool = field(default=False, init=False)
    
    def __post_init__(self) -> None:
        if self.console is None:
            self.console = Console(theme=SUNWELL_THEME)
    
    def __enter__(self) -> "NestedProgress":
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()
    
    def start(self) -> None:
        """Start the progress display."""
        if self._active:
            return
        
        self._progress = Progress(
            SpinnerColumn(spinner_name="dots", style="holy.gold"),
            TextColumn("[sunwell.phase]{task.description}"),
            BarColumn(
                complete_style="sunwell.progress.complete",
                finished_style="holy.radiant",
                pulse_style="holy.gold",
            ),
            TaskProgressColumn(),
            console=self.console,
        )
        self._progress.start()
        self._active = True
    
    def stop(self) -> None:
        """Stop the progress display."""
        if self._progress and self._active:
            self._progress.stop()
            self._active = False
    
    @contextmanager
    def task(
        self,
        description: str,
        total: float = 100,
    ) -> Generator[ProgressTask, None, None]:
        """Create a top-level task.
        
        Args:
            description: Task description
            total: Total progress value (default 100 for percentage)
            
        Yields:
            ProgressTask for tracking progress
        """
        if not self._progress:
            raise RuntimeError("NestedProgress not started. Use as context manager.")
        
        # Top-level tasks get icon prefix
        styled_desc = f"[holy.radiant]✦[/] {description}"
        task_id = self._progress.add_task(styled_desc, total=total)
        
        task = ProgressTask(
            id=task_id,
            name=description,
            progress=self._progress,
            depth=0,
        )
        self._tasks.append(task)
        
        try:
            yield task
        finally:
            # Auto-complete if not already complete
            task_info = self._progress.tasks[task_id]
            if task_info.completed < task_info.total:
                self._progress.update(task_id, completed=task_info.total)
    
    def add_task(self, description: str, total: float = 100) -> ProgressTask:
        """Add a standalone task (non-context manager).
        
        Args:
            description: Task description
            total: Total progress value
            
        Returns:
            ProgressTask for tracking
        """
        if not self._progress:
            raise RuntimeError("NestedProgress not started.")
        
        styled_desc = f"[holy.radiant]✦[/] {description}"
        task_id = self._progress.add_task(styled_desc, total=total)
        
        task = ProgressTask(
            id=task_id,
            name=description,
            progress=self._progress,
            depth=0,
        )
        self._tasks.append(task)
        return task
    
    def get_progress(self) -> Progress | None:
        """Get the underlying Rich Progress object.
        
        Returns:
            Progress instance or None if not started
        """
        return self._progress


def create_nested_progress(console: Console | None = None) -> NestedProgress:
    """Factory function to create NestedProgress.
    
    Args:
        console: Rich console (creates one if not provided)
        
    Returns:
        NestedProgress instance
    """
    return NestedProgress(console=console)
