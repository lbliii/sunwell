"""AwarenessExtractor - Extract behavioral patterns from session data.

Runs at end of session to analyze:
- Confidence calibration: stated vs actual accuracy
- Tool avoidance: tools with high success but low usage
- Error clustering: task types with high failure rates
- Backtrack rate: undo/restore frequency

Uses existing data from SessionTracker, LearningStore, and ToolPatterns.
"""

import logging
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.awareness.patterns import AwarenessPattern, PatternType

if TYPE_CHECKING:
    from sunwell.agent.learning.patterns import ToolPattern
    from sunwell.agent.learning.store import LearningStore
    from sunwell.memory.session.summary import GoalSummary, SessionSummary

logger = logging.getLogger(__name__)

# Minimum samples required before extracting a pattern
MIN_SAMPLES_FOR_PATTERN = 3

# Tools that should be tracked for avoidance analysis
TRACKABLE_TOOLS = frozenset({
    "grep_search",
    "read_file",
    "edit_file",
    "list_directory",
    "run_command",
    "web_search",
    "web_fetch",
})

# File extensions that may have higher backtrack rates
BACKTRACK_CATEGORIES = {
    "test": {"_test.py", "test_", "_spec.ts", ".test.ts", ".spec.js"},
    "config": {".yaml", ".yml", ".toml", ".json", ".ini"},
    "migration": {"migration", "migrate"},
}


class AwarenessExtractor:
    """Extract behavioral self-observations from session data.

    Designed to run at end of session, analyzing accumulated data
    from LearningStore and SessionTracker to identify behavioral patterns.

    Example:
        >>> extractor = AwarenessExtractor()
        >>> patterns = extractor.analyze_session(
        ...     session_summary=tracker.get_summary(),
        ...     learning_store=learning_store,
        ... )
        >>> for p in patterns:
        ...     print(p.observation)
    """

    def analyze_session(
        self,
        session_summary: SessionSummary,
        learning_store: LearningStore,
        *,
        tool_audit_log: list[dict] | None = None,
    ) -> list[AwarenessPattern]:
        """Analyze session data and extract behavioral patterns.

        Args:
            session_summary: Session summary from SessionTracker
            learning_store: Learning store with learnings and tool patterns
            tool_audit_log: Optional list of tool call audit entries

        Returns:
            List of extracted AwarenessPatterns
        """
        patterns: list[AwarenessPattern] = []

        # 1. Confidence calibration
        confidence_patterns = self._extract_confidence_calibration(
            session_summary, learning_store
        )
        patterns.extend(confidence_patterns)

        # 2. Tool avoidance (requires tool audit log)
        if tool_audit_log:
            avoidance_patterns = self._extract_tool_avoidance(tool_audit_log)
            patterns.extend(avoidance_patterns)

        # 3. Error clustering
        error_patterns = self._extract_error_clustering(session_summary)
        patterns.extend(error_patterns)

        # 4. Backtrack rate
        backtrack_patterns = self._extract_backtrack_rate(
            session_summary, tool_audit_log
        )
        patterns.extend(backtrack_patterns)

        logger.info(
            "Extracted %d awareness patterns from session %s",
            len(patterns),
            session_summary.session_id[:8],
        )

        return patterns

    def _extract_confidence_calibration(
        self,
        session_summary: SessionSummary,
        learning_store: LearningStore,
    ) -> list[AwarenessPattern]:
        """Extract confidence calibration patterns.

        Compares stated confidence in learnings with actual task outcomes.
        High confidence + failed task = overconfidence signal.

        Args:
            session_summary: Session summary with goal outcomes
            learning_store: Store with learnings and their confidence

        Returns:
            Patterns indicating confidence miscalibration
        """
        patterns: list[AwarenessPattern] = []

        # Group goals by task type (extracted from goal text)
        from sunwell.agent.learning.patterns import classify_task_type

        task_type_outcomes: dict[str, list[bool]] = defaultdict(list)
        for goal in session_summary.goals:
            task_type = classify_task_type(goal.goal)
            succeeded = goal.status == "completed"
            task_type_outcomes[task_type].append(succeeded)

        # Get average confidence from learnings
        learnings = learning_store.learnings
        if not learnings:
            return patterns

        avg_confidence = sum(lrn.confidence for lrn in learnings) / len(learnings)

        # Check each task type for miscalibration
        for task_type, outcomes in task_type_outcomes.items():
            if len(outcomes) < MIN_SAMPLES_FOR_PATTERN:
                continue

            actual_success_rate = sum(outcomes) / len(outcomes)

            # Miscalibration = stated confidence - actual success rate
            miscalibration = avg_confidence - actual_success_rate

            if abs(miscalibration) >= 0.10:  # 10% threshold
                direction = "overstate" if miscalibration > 0 else "understate"
                pattern = AwarenessPattern(
                    pattern_type=PatternType.CONFIDENCE,
                    observation=f"I tend to {direction} confidence on {task_type} tasks",
                    metric=abs(miscalibration),
                    sample_size=len(outcomes),
                    context=task_type,
                )
                patterns.append(pattern)

        return patterns

    def _extract_tool_avoidance(
        self,
        tool_audit_log: list[dict],
    ) -> list[AwarenessPattern]:
        """Extract tool avoidance patterns.

        Identifies tools with high success rate but low usage frequency,
        suggesting the agent should use them more often.

        Args:
            tool_audit_log: List of tool call audit entries with
                           {"tool": str, "success": bool, ...}

        Returns:
            Patterns indicating underutilized tools
        """
        patterns: list[AwarenessPattern] = []

        # Count usage and success per tool
        tool_stats: dict[str, dict[str, int]] = defaultdict(
            lambda: {"total": 0, "success": 0}
        )

        for entry in tool_audit_log:
            tool = entry.get("tool", "")
            if tool not in TRACKABLE_TOOLS:
                continue

            tool_stats[tool]["total"] += 1
            if entry.get("success", False):
                tool_stats[tool]["success"] += 1

        if not tool_stats:
            return patterns

        # Calculate total calls for usage frequency
        total_calls = sum(stats["total"] for stats in tool_stats.values())
        if total_calls == 0:
            return patterns

        # Find underutilized tools (high success, low frequency)
        for tool, stats in tool_stats.items():
            if stats["total"] < MIN_SAMPLES_FOR_PATTERN:
                continue

            success_rate = stats["success"] / stats["total"]
            usage_rate = stats["total"] / total_calls

            # High success (>80%) but low usage (<10%) = underutilized
            if success_rate >= 0.80 and usage_rate < 0.10:
                pattern = AwarenessPattern(
                    pattern_type=PatternType.TOOL_AVOIDANCE,
                    observation=f"I under-utilize {tool} - prefer it for better results",
                    metric=success_rate,
                    sample_size=stats["total"],
                    context=tool,
                )
                patterns.append(pattern)

        return patterns

    def _extract_error_clustering(
        self,
        session_summary: SessionSummary,
    ) -> list[AwarenessPattern]:
        """Extract error clustering patterns.

        Identifies task types with elevated failure rates,
        suggesting areas where the agent needs to be more careful.

        Args:
            session_summary: Session summary with goal outcomes

        Returns:
            Patterns indicating problematic task types
        """
        patterns: list[AwarenessPattern] = []

        from sunwell.agent.learning.patterns import classify_task_type

        # Group goals by task type
        task_type_outcomes: dict[str, list[bool]] = defaultdict(list)
        for goal in session_summary.goals:
            task_type = classify_task_type(goal.goal)
            succeeded = goal.status == "completed"
            task_type_outcomes[task_type].append(succeeded)

        # Find task types with high failure rates
        for task_type, outcomes in task_type_outcomes.items():
            if len(outcomes) < MIN_SAMPLES_FOR_PATTERN:
                continue

            failure_rate = 1 - (sum(outcomes) / len(outcomes))

            # 25% failure rate threshold
            if failure_rate >= 0.25:
                pattern = AwarenessPattern(
                    pattern_type=PatternType.ERROR_CLUSTER,
                    observation=f"I struggle with {task_type} tasks - be extra careful",
                    metric=failure_rate,
                    sample_size=len(outcomes),
                    context=task_type,
                )
                patterns.append(pattern)

        return patterns

    def _extract_backtrack_rate(
        self,
        session_summary: SessionSummary,
        tool_audit_log: list[dict] | None,
    ) -> list[AwarenessPattern]:
        """Extract backtrack rate patterns.

        Identifies file categories with high undo/restore frequency,
        suggesting areas where more careful planning is needed.

        Args:
            session_summary: Session summary with files touched
            tool_audit_log: Optional tool audit log with undo/restore calls

        Returns:
            Patterns indicating high backtrack rates
        """
        patterns: list[AwarenessPattern] = []

        if not tool_audit_log:
            return patterns

        # Count undo/restore operations per file category
        backtrack_tools = {"undo_file", "restore_file", "revert_file"}

        category_stats: dict[str, dict[str, int]] = defaultdict(
            lambda: {"total_edits": 0, "backtracks": 0}
        )

        for entry in tool_audit_log:
            tool = entry.get("tool", "")
            target = entry.get("arguments", {}).get("path", "")

            # Categorize the file
            category = self._categorize_file(target)

            if tool in {"edit_file", "write_file", "create_file"}:
                category_stats[category]["total_edits"] += 1
            elif tool in backtrack_tools:
                category_stats[category]["backtracks"] += 1

        # Also count from session files if available
        for goal in session_summary.goals:
            for file_path in goal.files_touched:
                category = self._categorize_file(file_path)
                # Increment edit count (rough proxy)
                category_stats[category]["total_edits"] += 1

        # Find categories with high backtrack rates
        for category, stats in category_stats.items():
            if stats["total_edits"] < MIN_SAMPLES_FOR_PATTERN:
                continue

            backtrack_rate = stats["backtracks"] / stats["total_edits"]

            # 20% backtrack rate threshold
            if backtrack_rate >= 0.20:
                pattern = AwarenessPattern(
                    pattern_type=PatternType.BACKTRACK,
                    observation=f"{category.title()} files have high backtrack rate - plan more carefully",
                    metric=backtrack_rate,
                    sample_size=stats["total_edits"],
                    context=category,
                )
                patterns.append(pattern)

        return patterns

    def _categorize_file(self, path: str) -> str:
        """Categorize a file path into a backtrack category.

        Args:
            path: File path to categorize

        Returns:
            Category string: "test", "config", "migration", or "code"
        """
        path_lower = path.lower()
        name = Path(path).name.lower() if path else ""

        for category, patterns in BACKTRACK_CATEGORIES.items():
            for pattern in patterns:
                if pattern in path_lower or pattern in name:
                    return category

        return "code"


def analyze_historical_sessions(
    sessions_dir: Path,
    limit: int = 10,
) -> list[AwarenessPattern]:
    """Analyze multiple historical sessions for patterns.

    Aggregates patterns across sessions for stronger signals.

    Args:
        sessions_dir: Path to .sunwell/sessions/
        limit: Maximum sessions to analyze

    Returns:
        Aggregated patterns from historical analysis
    """
    from sunwell.memory.session.tracker import SessionTracker

    patterns: list[AwarenessPattern] = []
    extractor = AwarenessExtractor()

    # Load recent sessions
    session_files = SessionTracker.list_recent(sessions_dir, limit=limit)

    for session_file in session_files:
        try:
            tracker = SessionTracker.load(session_file)
            summary = tracker.get_summary()

            # Create minimal learning store for analysis
            # (historical sessions don't have full learning store)
            from sunwell.agent.learning.store import LearningStore
            learning_store = LearningStore()

            session_patterns = extractor.analyze_session(
                session_summary=summary,
                learning_store=learning_store,
            )
            patterns.extend(session_patterns)
        except Exception as e:
            logger.warning("Failed to analyze session %s: %s", session_file, e)

    return patterns
