"""Hierarchical render context for CLI event display.

Tracks rendering state to enable proper visual hierarchy:
- Phase tracking (understanding → crafting → verifying → complete)
- Task grouping (task + its gates as a visual unit)
- Tool calls nested under tasks
- Indentation depth
- Deferred learnings (batched at boundaries)
- Budget/cost tracking
- Timing since session start
- Timeline for execution history
- Accessibility (reduced motion, plain mode)

RFC-131 Holy Light aesthetic with proper topology.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from time import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rich.console import Console


# =============================================================================
# ACCESSIBILITY
# =============================================================================

def should_reduce_motion() -> bool:
    """Check if animations should be disabled."""
    return bool(
        os.environ.get("SUNWELL_REDUCED_MOTION") or os.environ.get("NO_COLOR")
    )


def is_plain_mode() -> bool:
    """Check if plain output mode is enabled (no colors/styling)."""
    return bool(os.environ.get("SUNWELL_PLAIN") or os.environ.get("NO_COLOR"))


class RenderPhase(Enum):
    """Current rendering phase."""

    IDLE = "idle"
    UNDERSTANDING = "understanding"
    PLANNING = "planning"
    CRAFTING = "crafting"
    VERIFYING = "verifying"
    FIXING = "fixing"
    COMPLETE = "complete"


# Tree drawing characters
TREE = {
    "branch": "├─",      # Non-last child
    "last": "└─",        # Last child
    "pipe": "│ ",        # Continuation
    "space": "  ",       # No continuation
    "top": "┌─",         # First/top of group
}


@dataclass
class ToolCall:
    """A tool call within a task."""

    name: str
    started_at: float = field(default_factory=time)
    completed: bool = False
    success: bool = True
    duration_ms: int = 0
    error: str | None = None


@dataclass
class TimelineEvent:
    """An event in the execution timeline."""

    timestamp: float
    description: str
    phase: str
    completed: bool = False
    duration_ms: int = 0

    @property
    def formatted_time(self) -> str:
        """Format timestamp as relative time from session start."""
        # Will be calculated relative to session start when rendered
        return ""


@dataclass
class TaskGroup:
    """A task and its associated validations as a visual unit."""

    task_id: str
    description: str
    task_number: int
    total_tasks: int
    started: bool = False
    completed: bool = False
    duration_ms: int = 0
    gates: list[tuple[str, bool, str]] = field(default_factory=list)  # (name, passed, details)
    tools: list[ToolCall] = field(default_factory=list)
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)


@dataclass
class RenderContext:
    """Stateful context for hierarchical rendering.

    Tracks current phase, active task, and deferred items to enable
    proper visual grouping and indentation.
    """

    # Current state
    phase: RenderPhase = RenderPhase.IDLE
    current_task: TaskGroup | None = None
    current_tool: ToolCall | None = None
    task_count: int = 0
    total_tasks: int = 0

    # Deferred items (batched at boundaries)
    learnings: list[str] = field(default_factory=list)
    learning_counts: dict[str, int] = field(default_factory=dict)

    # Session metrics
    session_start: float = field(default_factory=time)
    total_tokens: int = 0
    total_cost: float = 0.0
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)

    # Convergence tracking
    convergence_iteration: int = 0
    convergence_max: int = 0
    is_fixing: bool = False

    # Timeline for execution history
    timeline: list[TimelineEvent] = field(default_factory=list)

    # Accessibility
    reduced_motion: bool = field(default_factory=should_reduce_motion)
    plain_mode: bool = field(default_factory=is_plain_mode)

    # Streaming state
    streaming_text: str = ""
    is_streaming: bool = False

    # Phase tracking (avoid redundant headers)
    _last_phase_rendered: RenderPhase | None = None
    _in_task_group: bool = False

    # Indentation
    base_indent: str = "  "

    def indent(self, depth: int = 0) -> str:
        """Get indentation string for given depth."""
        return self.base_indent * (depth + 1)

    def tree_line(self, depth: int, is_last: bool = False, is_first: bool = False) -> str:
        """Get tree connector for given position."""
        prefix = self.indent(depth)
        if is_first:
            return f"{prefix}{TREE['top']} "
        elif is_last:
            return f"{prefix}{TREE['last']} "
        else:
            return f"{prefix}{TREE['branch']} "

    def continuation_line(self, depth: int, has_more: bool = True) -> str:
        """Get continuation line (vertical pipe or space)."""
        prefix = self.indent(depth)
        return f"{prefix}{TREE['pipe'] if has_more else TREE['space']}"

    def transition_phase(self, new_phase: RenderPhase) -> bool:
        """Transition to new phase, returns True if header should be rendered."""
        if new_phase == self.phase:
            return False

        # Close current task group if open
        if self.current_task and self.current_task.started:
            self._in_task_group = False
            self.current_task = None

        old_phase = self.phase
        self.phase = new_phase

        # Only render header for major transitions
        # Don't render VERIFYING header for each gate (inline with task)
        if new_phase == RenderPhase.VERIFYING and old_phase == RenderPhase.CRAFTING:
            return False  # Gates are shown inline with tasks

        if new_phase == self._last_phase_rendered:
            return False

        self._last_phase_rendered = new_phase
        return True

    def start_task(
        self,
        task_id: str,
        description: str,
        task_number: int,
        total_tasks: int,
    ) -> TaskGroup:
        """Start a new task group."""
        # Finalize previous task if exists
        if self.current_task:
            self._in_task_group = False

        self.current_task = TaskGroup(
            task_id=task_id,
            description=description,
            task_number=task_number,
            total_tasks=total_tasks,
            started=True,
        )
        self.task_count = task_number
        self.total_tasks = total_tasks
        self._in_task_group = True

        return self.current_task

    def complete_task(self, duration_ms: int = 0) -> None:
        """Mark current task as complete."""
        if self.current_task:
            self.current_task.completed = True
            self.current_task.duration_ms = duration_ms

    def add_gate(self, gate_name: str, passed: bool, details: str = "") -> None:
        """Add a gate result to current task."""
        if self.current_task:
            self.current_task.gates.append((gate_name, passed, details))

    # ═══════════════════════════════════════════════════════════════
    # Tool tracking
    # ═══════════════════════════════════════════════════════════════

    def start_tool(self, tool_name: str) -> ToolCall:
        """Start tracking a tool call."""
        tool = ToolCall(name=tool_name)
        self.current_tool = tool
        if self.current_task:
            self.current_task.tools.append(tool)
        return tool

    def complete_tool(self, success: bool = True, error: str | None = None) -> None:
        """Mark current tool as complete."""
        if self.current_tool:
            self.current_tool.completed = True
            self.current_tool.success = success
            self.current_tool.error = error
            self.current_tool.duration_ms = int((time() - self.current_tool.started_at) * 1000)
            self.current_tool = None

    def has_active_tool(self) -> bool:
        """Check if there's an active tool call."""
        return self.current_tool is not None

    # ═══════════════════════════════════════════════════════════════
    # File tracking
    # ═══════════════════════════════════════════════════════════════

    def add_file_created(self, path: str) -> None:
        """Track a created file."""
        if path not in self.files_created:
            self.files_created.append(path)
        if self.current_task and path not in self.current_task.files_created:
            self.current_task.files_created.append(path)

    def add_file_modified(self, path: str) -> None:
        """Track a modified file."""
        if path not in self.files_modified:
            self.files_modified.append(path)
        if self.current_task and path not in self.current_task.files_modified:
            self.current_task.files_modified.append(path)

    # ═══════════════════════════════════════════════════════════════
    # Metrics tracking
    # ═══════════════════════════════════════════════════════════════

    def add_tokens(self, tokens: int, cost: float = 0.0) -> None:
        """Add token usage to session total."""
        self.total_tokens += tokens
        self.total_cost += cost

    def get_elapsed_seconds(self) -> float:
        """Get elapsed time since session start."""
        return time() - self.session_start

    def get_session_summary(self) -> dict[str, any]:
        """Get summary metrics for the session."""
        return {
            "elapsed_s": self.get_elapsed_seconds(),
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost,
            "tasks_completed": self.task_count,
            "files_created": len(self.files_created),
            "files_modified": len(self.files_modified),
            "learnings": len(set(self.learnings)),
        }

    # ═══════════════════════════════════════════════════════════════
    # Convergence tracking
    # ═══════════════════════════════════════════════════════════════

    def start_convergence(self, max_iterations: int) -> None:
        """Start tracking a convergence loop."""
        self.convergence_iteration = 0
        self.convergence_max = max_iterations
        self.is_fixing = False

    def next_convergence_iteration(self) -> int:
        """Move to next convergence iteration."""
        self.convergence_iteration += 1
        return self.convergence_iteration

    def start_fixing(self) -> None:
        """Mark that we're in a fix attempt."""
        self.is_fixing = True
        self.transition_phase(RenderPhase.FIXING)

    def end_fixing(self) -> None:
        """Mark that fix attempt is complete."""
        self.is_fixing = False

    def in_convergence(self) -> bool:
        """Check if we're in a convergence loop."""
        return self.convergence_max > 0

    # ═══════════════════════════════════════════════════════════════
    # Streaming state
    # ═══════════════════════════════════════════════════════════════

    def start_streaming(self) -> None:
        """Start streaming output mode."""
        self.is_streaming = True
        self.streaming_text = ""

    def append_streaming(self, text: str) -> str:
        """Append text to streaming buffer and return full text."""
        self.streaming_text += text
        return self.streaming_text

    def end_streaming(self) -> str:
        """End streaming and return final text."""
        final_text = self.streaming_text
        self.is_streaming = False
        self.streaming_text = ""
        return final_text

    # ═══════════════════════════════════════════════════════════════
    # Timeline tracking
    # ═══════════════════════════════════════════════════════════════

    def add_timeline_event(
        self,
        description: str,
        phase: str | None = None,
        completed: bool = False,
    ) -> TimelineEvent:
        """Add an event to the execution timeline."""
        event = TimelineEvent(
            timestamp=time(),
            description=description,
            phase=phase or self.phase.value,
            completed=completed,
        )
        self.timeline.append(event)
        return event

    def complete_timeline_event(self, event: TimelineEvent, duration_ms: int = 0) -> None:
        """Mark a timeline event as complete."""
        event.completed = True
        event.duration_ms = duration_ms

    def get_timeline_for_render(self) -> list[tuple[str, str, bool]]:
        """Get timeline in format expected by render_timeline.

        Returns:
            List of (timestamp_str, description, is_complete) tuples
        """
        result = []
        for event in self.timeline:
            # Format timestamp relative to session start
            elapsed = event.timestamp - self.session_start
            if elapsed < 60:
                time_str = f"+{elapsed:.1f}s"
            else:
                minutes = int(elapsed // 60)
                seconds = int(elapsed % 60)
                time_str = f"+{minutes}m{seconds}s"

            result.append((time_str, event.description, event.completed))
        return result

    # ═══════════════════════════════════════════════════════════════
    # Learning tracking
    # ═══════════════════════════════════════════════════════════════

    def add_learning(self, fact: str) -> None:
        """Add a learning (deferred for batching)."""
        self.learnings.append(fact)
        self.learning_counts[fact] = self.learning_counts.get(fact, 0) + 1

    def get_batched_learnings(self) -> list[tuple[str, int]]:
        """Get deduplicated learnings with counts."""
        # Return unique learnings with their counts
        seen: set[str] = set()
        result: list[tuple[str, int]] = []
        for fact in self.learnings:
            if fact not in seen:
                seen.add(fact)
                result.append((fact, self.learning_counts[fact]))
        return result

    def clear_learnings(self) -> None:
        """Clear accumulated learnings after rendering."""
        self.learnings.clear()
        self.learning_counts.clear()

    def is_last_task(self) -> bool:
        """Check if current task is the last one."""
        if self.current_task:
            return self.current_task.task_number >= self.total_tasks
        return False

    def reset(self) -> None:
        """Reset context for new session."""
        self.phase = RenderPhase.IDLE
        self.current_task = None
        self.current_tool = None
        self.task_count = 0
        self.total_tasks = 0
        self.learnings.clear()
        self.learning_counts.clear()
        self._last_phase_rendered = None
        self._in_task_group = False
        # Reset metrics
        self.session_start = time()
        self.total_tokens = 0
        self.total_cost = 0.0
        self.files_created.clear()
        self.files_modified.clear()
        # Reset convergence
        self.convergence_iteration = 0
        self.convergence_max = 0
        self.is_fixing = False
        # Reset timeline
        self.timeline.clear()
        # Reset streaming
        self.streaming_text = ""
        self.is_streaming = False
        # Re-check accessibility settings
        self.reduced_motion = should_reduce_motion()
        self.plain_mode = is_plain_mode()


# Module-level singleton for shared state across event renders
_context: RenderContext | None = None


def get_render_context() -> RenderContext:
    """Get the shared render context."""
    global _context
    if _context is None:
        _context = RenderContext()
    return _context


def reset_render_context() -> None:
    """Reset the render context (for new sessions)."""
    global _context
    if _context:
        _context.reset()
    else:
        _context = RenderContext()
