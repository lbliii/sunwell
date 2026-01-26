"""Tool pattern learning for RFC-134."""

import threading
from dataclasses import dataclass, field


@dataclass(slots=True)
class ToolPattern:
    """A learned tool usage pattern (RFC-134).

    Tracks which tool sequences succeed for which task types.
    Used to suggest optimal tool sequences for new tasks.

    RFC-122: Thread-safe for Python 3.14t free-threading.
    """

    task_type: str
    """Task category: "python_api", "new_file", "refactor", "test", etc."""

    tool_sequence: tuple[str, ...]
    """Ordered sequence of tools used: ("read_file", "edit_file")."""

    success_count: int = 0
    """Number of successful completions with this sequence."""

    failure_count: int = 0
    """Number of failed completions with this sequence."""

    # RFC-122: Thread-safe lock for mutations (3.14t)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    """Lock for thread-safe mutations."""

    @property
    def success_rate(self) -> float:
        """Calculate success rate for this pattern."""
        with self._lock:
            total = self.success_count + self.failure_count
            return self.success_count / total if total > 0 else 0.5

    @property
    def confidence(self) -> float:
        """Confidence in this pattern (more data = higher confidence)."""
        with self._lock:
            total = self.success_count + self.failure_count
            # Base confidence + boost from sample size (up to 0.3 boost at 10+ samples)
            base = self.success_count / total if total > 0 else 0.5
            sample_boost = min(0.3, total * 0.03)
            return min(1.0, base * 0.7 + sample_boost)

    def record(self, success: bool) -> None:
        """Record an outcome for this pattern (thread-safe)."""
        with self._lock:
            if success:
                self.success_count += 1
            else:
                self.failure_count += 1

    @property
    def id(self) -> str:
        """Unique identifier for this pattern."""
        import hashlib
        content = f"{self.task_type}:{','.join(self.tool_sequence)}"
        return hashlib.blake2b(content.encode(), digest_size=6).hexdigest()


def classify_task_type(description: str) -> str:
    """Classify a task description into a task type for tool learning.

    Args:
        description: Task description text

    Returns:
        Task type string
    """
    desc_lower = description.lower()

    # Order matters - check more specific patterns first
    if any(kw in desc_lower for kw in ["test", "spec", "pytest", "unittest"]):
        return "test"
    if any(kw in desc_lower for kw in ["refactor", "rename", "reorganize", "move"]):
        return "refactor"
    if any(kw in desc_lower for kw in ["fix", "bug", "error", "issue"]):
        return "fix"
    if any(kw in desc_lower for kw in ["api", "endpoint", "route", "rest", "graphql"]):
        return "api"
    if any(kw in desc_lower for kw in ["new file", "create", "add", "implement"]):
        return "new_file"
    if any(kw in desc_lower for kw in ["update", "modify", "change", "edit"]):
        return "update"
    if any(kw in desc_lower for kw in ["document", "readme", "comment"]):
        return "documentation"
    if any(kw in desc_lower for kw in ["config", "setup", "install"]):
        return "configuration"

    return "general"
