"""Memory Integration for Surface Composition (RFC-072 prep for RFC-075).

Integrates with Sunwell's memory system to:
- Load historical layout success patterns
- Record successful compositions
- Learn user preferences over time
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any

from sunwell.interface.generative.surface.memory import (
    InteractionMetrics,
    LayoutMemory,
    create_layout_memory,
    layout_memory_to_learning,
    normalize_goal,
)
from sunwell.interface.generative.surface.types import SurfaceLayout

if TYPE_CHECKING:
    pass


class LayoutMemoryStore:
    """Stores and retrieves layout success patterns.

    This integrates with the project's .sunwell directory to persist
    layout patterns that can inform future compositions.
    """

    def __init__(self, project_path: Path) -> None:
        """Initialize memory store.

        Args:
            project_path: Project root path
        """
        self.project_path = project_path
        self.memory_dir = project_path / ".sunwell" / "surface"
        self._patterns: dict[str, list[LayoutMemory]] = {}
        self._primitive_success: dict[str, float] = {}

    def load(self) -> None:
        """Load layout patterns from disk."""
        import json

        patterns_file = self.memory_dir / "patterns.json"
        if not patterns_file.exists():
            return

        try:
            data = json.loads(patterns_file.read_text())
            self._primitive_success = data.get("primitive_success", {})
            # Could also load full pattern history here
        except (json.JSONDecodeError, OSError):
            pass

    def save(self) -> None:
        """Save layout patterns to disk."""
        import json

        self.memory_dir.mkdir(parents=True, exist_ok=True)
        patterns_file = self.memory_dir / "patterns.json"

        data = {
            "primitive_success": self._primitive_success,
        }

        patterns_file.write_text(json.dumps(data, indent=2))

    def record_success(
        self,
        layout: SurfaceLayout,
        goal: str,
        metrics: InteractionMetrics,
    ) -> LayoutMemory | None:
        """Record a successful layout interaction.

        Args:
            layout: The layout that was used
            goal: The goal it was used for
            metrics: Interaction metrics

        Returns:
            Created memory if worth recording, None otherwise
        """
        memory = create_layout_memory(
            layout=layout,
            goal=goal,
            metrics=metrics,
            project_id=str(self.project_path),
        )

        if memory is not None:
            # Update primitive success rates
            self._update_primitive_success(memory)

            # Store pattern
            pattern_key = normalize_goal(goal)
            if pattern_key not in self._patterns:
                self._patterns[pattern_key] = []
            self._patterns[pattern_key].append(memory)

            self.save()

        return memory

    def get_primitive_success_rates(self) -> dict[str, float]:
        """Get success rates for primitives.

        Returns:
            Dict mapping primitive_id to success rate (0.0-1.0)
        """
        return self._primitive_success.copy()

    def get_patterns_for_goal(self, goal: str) -> list[LayoutMemory]:
        """Get historical patterns that match a goal.

        Args:
            goal: Goal to match

        Returns:
            List of matching patterns, sorted by success score
        """
        pattern_key = normalize_goal(goal)

        # Exact match
        if pattern_key in self._patterns:
            return sorted(
                self._patterns[pattern_key],
                key=lambda m: m.success_score,
                reverse=True,
            )

        # Fuzzy match (simple word overlap)
        goal_words = set(pattern_key.split())
        matches: list[tuple[float, LayoutMemory]] = []

        for key, patterns in self._patterns.items():
            key_words = set(key.split())
            overlap = len(goal_words & key_words) / max(len(goal_words), 1)
            if overlap > 0.5:  # 50% word overlap threshold
                for pattern in patterns:
                    matches.append((overlap * pattern.success_score, pattern))

        matches.sort(key=lambda x: x[0], reverse=True)
        return [m[1] for m in matches[:5]]  # Top 5 matches

    def _update_primitive_success(self, memory: LayoutMemory) -> None:
        """Update primitive success rates from a new memory."""
        # Get primitives from layout
        primitives = [memory.layout.primary.id]
        primitives.extend(p.id for p in memory.layout.secondary)
        primitives.extend(p.id for p in memory.layout.contextual)

        # Update running averages
        for prim_id in primitives:
            current = self._primitive_success.get(prim_id, 0.5)
            # Exponential moving average with α=0.3
            new_rate = current * 0.7 + memory.success_score * 0.3
            self._primitive_success[prim_id] = new_rate


def load_memory_patterns(project_path: Path) -> dict[str, float]:
    """Load primitive success patterns for a project.

    Convenience function for use in composition.

    Args:
        project_path: Project root path

    Returns:
        Dict mapping primitive_id to success rate
    """
    store = LayoutMemoryStore(project_path)
    store.load()
    return store.get_primitive_success_rates()


def record_layout_interaction(
    project_path: Path,
    layout: SurfaceLayout,
    goal: str,
    duration_seconds: int,
    completed: bool,
) -> dict[str, Any]:
    """Record a layout interaction.

    Convenience function for recording from CLI or Tauri.

    Args:
        project_path: Project root path
        layout: Layout that was used
        goal: Goal it was used for
        duration_seconds: How long it was used
        completed: Whether goal was completed

    Returns:
        Result dict with success status and learning info
    """
    metrics = InteractionMetrics(
        duration_seconds=duration_seconds,
        goal_completed=completed,
        manual_overrides=0,
        primitive_additions=0,
        primitive_removals=0,
    )

    store = LayoutMemoryStore(project_path)
    store.load()
    memory = store.record_success(layout, goal, metrics)

    if memory is not None:
        learning = layout_memory_to_learning(memory)
        return {
            "success": True,
            "recorded": True,
            "success_score": memory.success_score,
            "learning": learning,
        }

    return {
        "success": True,
        "recorded": False,
        "reason": "Success score below threshold",
    }
