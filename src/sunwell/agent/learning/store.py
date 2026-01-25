"""Learning store for in-memory session learnings."""

import json
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sunwell.agent.learning.dead_end import DeadEnd
from sunwell.agent.learning.learning import Learning
from sunwell.agent.learning.patterns import ToolPattern

if TYPE_CHECKING:
    pass

# Regex pattern for loading from disk
_RE_CLASS_OR_DEF = re.compile(r"(?:class|def)\s+(\w+)")


@dataclass(slots=True)
class LearningStore:
    """In-memory store for learnings during a session.

    Integrates with Simulacrum for persistence.

    RFC-122: Extended with thread-safe operations for Python 3.14t
    free-threading support.

    RFC-134: Extended with tool pattern tracking for tool usage learning.
    """

    learnings: list[Learning] = field(default_factory=list)
    """All learnings in this session."""

    dead_ends: list[DeadEnd] = field(default_factory=list)
    """Dead ends encountered."""

    # O(1) deduplication index
    _learning_ids: set[str] = field(default_factory=set, init=False)
    """Set of learning IDs for O(1) deduplication."""

    # RFC-122: Thread-safe lock for mutable operations (3.14t)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    """Lock for thread-safe mutations."""

    # RFC-134: Tool pattern tracking
    _tool_patterns: dict[str, ToolPattern] = field(default_factory=dict, init=False)
    """Patterns indexed by id for O(1) lookup."""

    def add_learning(self, learning: Learning) -> None:
        """Add a learning, deduplicating by ID (thread-safe, O(1))."""
        with self._lock:
            if learning.id not in self._learning_ids:
                self._learning_ids.add(learning.id)
                self.learnings.append(learning)

    def add_dead_end(self, dead_end: DeadEnd) -> None:
        """Add a dead end (thread-safe)."""
        with self._lock:
            self.dead_ends.append(dead_end)

    # =========================================================================
    # RFC-134: Tool Pattern Learning
    # =========================================================================

    def record_tool_sequence(
        self,
        task_type: str,
        tools: list[str],
        success: bool,
    ) -> None:
        """Record outcome of a tool sequence for learning (RFC-134, thread-safe).

        Args:
            task_type: Task category (from classify_task_type)
            tools: Ordered list of tools used
            success: Whether the task succeeded
        """
        if not tools:
            return

        tool_tuple = tuple(tools)
        pattern_id = f"{task_type}:{','.join(tool_tuple)}"

        with self._lock:
            if pattern_id not in self._tool_patterns:
                self._tool_patterns[pattern_id] = ToolPattern(
                    task_type=task_type,
                    tool_sequence=tool_tuple,
                )
            self._tool_patterns[pattern_id].record(success)

    def suggest_tools(self, task_type: str, limit: int = 3) -> list[str]:
        """Suggest best tool sequence for a task type (RFC-134).

        Returns the tools from the highest-confidence successful pattern.

        Args:
            task_type: Task category to look up
            limit: Maximum number of tools to suggest

        Returns:
            Ordered list of suggested tools
        """
        with self._lock:
            # Find all patterns for this task type
            matching = [
                p for p in self._tool_patterns.values()
                if p.task_type == task_type and p.success_count > 0
            ]

            if not matching:
                return []

            # Sort by confidence (success rate + sample size boost)
            matching.sort(key=lambda p: p.confidence, reverse=True)

            # Return tools from best pattern
            best = matching[0]
            return list(best.tool_sequence[:limit])

    def get_tool_patterns(self, min_samples: int = 2) -> list[ToolPattern]:
        """Get all tool patterns with sufficient samples (RFC-134).

        Args:
            min_samples: Minimum total samples required

        Returns:
            List of ToolPattern objects
        """
        with self._lock:
            return [
                p for p in self._tool_patterns.values()
                if (p.success_count + p.failure_count) >= min_samples
            ]

    def format_tool_suggestions(self, task_type: str) -> str | None:
        """Format tool suggestions for prompt injection (RFC-134).

        Args:
            task_type: Task category

        Returns:
            Formatted string or None if no suggestions
        """
        suggested = self.suggest_tools(task_type)
        if not suggested:
            return None

        # Get the pattern for stats
        with self._lock:
            pattern_id = f"{task_type}:{','.join(suggested)}"
            pattern = self._tool_patterns.get(pattern_id)

        if pattern:
            return (
                f"Recommended tool sequence for {task_type} tasks: "
                f"{' → '.join(suggested)} "
                f"(success rate: {pattern.success_rate:.0%})"
            )
        return f"Recommended tool sequence: {' → '.join(suggested)}"

    # =========================================================================
    # RFC-122: Usage Tracking and Template Access
    # =========================================================================

    def record_usage(self, learning_id: str, success: bool) -> None:
        """Record that a learning was used (RFC-122, thread-safe).

        Updates the learning's use_count and adjusts confidence based on outcome.

        Args:
            learning_id: ID of learning used
            success: Whether the task succeeded
        """
        with self._lock:
            for i, learning in enumerate(self.learnings):
                if learning.id == learning_id:
                    # Adjust confidence based on outcome
                    new_confidence = learning.confidence
                    if success:
                        new_confidence = min(1.0, new_confidence + 0.05)
                    else:
                        new_confidence = max(0.1, new_confidence - 0.1)

                    # Create updated learning (Learning is frozen)
                    self.learnings[i] = Learning(
                        fact=learning.fact,
                        category=learning.category,
                        confidence=new_confidence,
                        source_file=learning.source_file,
                        source_line=learning.source_line,
                    )
                    break

    def get_templates(self) -> list[Learning]:
        """Get all template learnings (RFC-122).

        Returns:
            List of learnings with category="template"
        """
        with self._lock:
            return [lrn for lrn in self.learnings if lrn.category == "template"]

    def get_heuristics(self) -> list[Learning]:
        """Get all heuristic learnings (RFC-122).

        Returns:
            List of learnings with category="heuristic"
        """
        with self._lock:
            return [lrn for lrn in self.learnings if lrn.category == "heuristic"]

    def get_relevant(self, query: str, limit: int = 10) -> list[Learning]:
        """Get learnings relevant to a query.

        Simple keyword matching for now.
        Could use embeddings for better retrieval.

        Args:
            query: Search query
            limit: Max results

        Returns:
            Relevant learnings
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())

        scored: list[tuple[float, Learning]] = []
        for learning in self.learnings:
            fact_lower = learning.fact.lower()
            fact_words = set(fact_lower.split())

            # Score by word overlap
            overlap = len(query_words & fact_words)
            if overlap > 0:
                score = overlap / len(query_words)
                scored.append((score, learning))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)
        return [lrn for _, lrn in scored[:limit]]

    def get_dead_ends_for(self, query: str) -> list[DeadEnd]:
        """Get dead ends relevant to a query."""
        query_lower = query.lower()
        return [
            de
            for de in self.dead_ends
            if any(word in de.approach.lower() for word in query_lower.split())
        ]

    def format_for_prompt(self, limit: int = 10) -> str:
        """Format learnings for injection into prompts.

        Args:
            limit: Max learnings to include

        Returns:
            Formatted string for prompt injection
        """
        if not self.learnings:
            return ""

        recent = self.learnings[-limit:]
        lines = ["Known facts from this session:"]
        for lrn in recent:
            lines.append(f"- {lrn.fact}")

        if self.dead_ends:
            lines.append("\nApproaches that didn't work:")
            for de in self.dead_ends[-5:]:
                lines.append(f"- {de.approach}: {de.reason}")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for serialization."""
        return {
            "learnings": [
                {"fact": lrn.fact, "category": lrn.category, "confidence": lrn.confidence}
                for lrn in self.learnings
            ],
            "dead_ends": [
                {"approach": d.approach, "reason": d.reason, "context": d.context}
                for d in self.dead_ends
            ],
        }

    def sync_to_simulacrum(self, store: Any) -> int:
        """Sync learnings to Simulacrum store for persistence.

        Args:
            store: SimulacrumStore instance

        Returns:
            Number of learnings synced
        """
        try:
            from sunwell.memory.simulacrum.core import Learning as SimLearning

            synced = 0
            for lrn in self.learnings:
                sim_learning = SimLearning(
                    fact=lrn.fact,
                    category=lrn.category,
                    confidence=lrn.confidence,
                    source_file=lrn.source_file,
                    source_line=lrn.source_line,
                )
                store.add_learning(sim_learning)
                synced += 1

            return synced
        except (ImportError, AttributeError):
            return 0

    def load_from_simulacrum(self, store: Any) -> int:
        """Load learnings from Simulacrum store.

        Args:
            store: SimulacrumStore instance

        Returns:
            Number of learnings loaded
        """
        try:
            loaded = 0
            for sim_learning in store.get_learnings():
                lrn = Learning(
                    fact=sim_learning.fact,
                    category=getattr(sim_learning, "category", "pattern"),
                    confidence=getattr(sim_learning, "confidence", 0.7),
                    source_file=getattr(sim_learning, "source_file", None),
                    source_line=getattr(sim_learning, "source_line", None),
                )
                self.add_learning(lrn)
                loaded += 1

            return loaded
        except (ImportError, AttributeError):
            return 0

    def save_to_disk(self, base_path: Path | None = None) -> int:
        """Persist learnings to .sunwell/intelligence/learnings.jsonl.

        This enables cross-session learning without requiring a full Simulacrum setup.
        Learnings are appended to the file, deduplicating by learning ID.

        Args:
            base_path: Project root (defaults to cwd)

        Returns:
            Number of learnings saved
        """
        if not self.learnings and not self.dead_ends:
            return 0

        base = base_path or Path.cwd()
        intel_dir = base / ".sunwell" / "intelligence"
        intel_dir.mkdir(parents=True, exist_ok=True)

        learnings_path = intel_dir / "learnings.jsonl"
        dead_ends_path = intel_dir / "dead_ends.jsonl"

        # Load existing IDs to avoid duplicates
        existing_ids: set[str] = set()
        if learnings_path.exists():
            with open(learnings_path) as f:
                for line in f:
                    if line.strip():
                        try:
                            data = json.loads(line)
                            existing_ids.add(data.get("id", ""))
                        except json.JSONDecodeError:
                            pass

        # Append new learnings
        saved = 0
        timestamp = datetime.now().isoformat()

        with open(learnings_path, "a") as f:
            for lrn in self.learnings:
                if lrn.id not in existing_ids:
                    record = {
                        "id": lrn.id,
                        "fact": lrn.fact,
                        "category": lrn.category,
                        "confidence": lrn.confidence,
                        "source_file": lrn.source_file,
                        "source_line": lrn.source_line,
                        "created_at": timestamp,
                    }
                    f.write(json.dumps(record) + "\n")
                    saved += 1

        # Also save dead ends
        existing_approaches: set[str] = set()
        if dead_ends_path.exists():
            with open(dead_ends_path) as f:
                for line in f:
                    if line.strip():
                        try:
                            data = json.loads(line)
                            existing_approaches.add(data.get("approach", ""))
                        except json.JSONDecodeError:
                            pass

        with open(dead_ends_path, "a") as f:
            for de in self.dead_ends:
                if de.approach not in existing_approaches:
                    record = {
                        "approach": de.approach,
                        "reason": de.reason,
                        "context": de.context,
                        "created_at": timestamp,
                    }
                    f.write(json.dumps(record) + "\n")

        return saved

    def load_from_disk(self, base_path: Path | None = None) -> int:
        """Load learnings from .sunwell/ directories.

        Reads from multiple sources:
        1. .sunwell/intelligence/learnings.jsonl (JSONL format)
        2. .sunwell/learnings/*.json (Naaru execution format - JSON arrays)
        3. .sunwell/intelligence/dead_ends.jsonl

        Args:
            base_path: Project root (defaults to cwd)

        Returns:
            Number of learnings loaded
        """
        base = base_path or Path.cwd()
        learnings_path = base / ".sunwell" / "intelligence" / "learnings.jsonl"
        dead_ends_path = base / ".sunwell" / "intelligence" / "dead_ends.jsonl"
        naaru_learnings_dir = base / ".sunwell" / "learnings"

        loaded = 0

        # Source 1: .sunwell/intelligence/learnings.jsonl (JSONL format)
        if learnings_path.exists():
            with open(learnings_path) as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        lrn = Learning(
                            fact=data["fact"],
                            category=data.get("category", "pattern"),
                            confidence=data.get("confidence", 0.7),
                            source_file=data.get("source_file"),
                            source_line=data.get("source_line"),
                        )
                        self.add_learning(lrn)
                        loaded += 1
                    except (json.JSONDecodeError, KeyError):
                        pass

        # Source 2: .sunwell/learnings/*.json (Naaru execution format)
        # Format: [{"type": "task_completion", "task_id": ..., "task_description": ..., ...}]
        if naaru_learnings_dir.exists():
            for json_file in naaru_learnings_dir.glob("*.json"):
                try:
                    with open(json_file) as f:
                        data = json.load(f)
                    if isinstance(data, list):
                        for entry in data:
                            task_id = entry.get("task_id", "")
                            description = entry.get("task_description", "")
                            output = entry.get("output", "")

                            # Create learning from task completion
                            if task_id and description:
                                lrn = Learning(
                                    fact=f"Completed: {description}",
                                    category="task_completion",
                                    confidence=1.0,
                                    source_file=task_id,
                                )
                                self.add_learning(lrn)
                                loaded += 1

                            # Extract useful patterns from output if available
                            if output and len(output) > 20:
                                # Extract class/function definitions
                                for match in _RE_CLASS_OR_DEF.finditer(output):
                                    lrn = Learning(
                                        fact=f"Defined {match.group(1)} in {task_id}",
                                        category="pattern",
                                        confidence=0.9,
                                        source_file=task_id,
                                    )
                                    self.add_learning(lrn)
                                    loaded += 1
                except (json.JSONDecodeError, OSError):
                    pass

        # Source 3: Dead ends
        if dead_ends_path.exists():
            with open(dead_ends_path) as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        de = DeadEnd(
                            approach=data["approach"],
                            reason=data.get("reason", ""),
                            context=data.get("context"),
                        )
                        self.add_dead_end(de)
                    except (json.JSONDecodeError, KeyError):
                        pass

        return loaded
