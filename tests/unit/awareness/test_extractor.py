"""Tests for AwarenessExtractor."""

from datetime import UTC, datetime, timedelta

import pytest

from sunwell.awareness.extractor import AwarenessExtractor
from sunwell.awareness.patterns import PatternType
from sunwell.agent.learning.store import LearningStore
from sunwell.agent.learning.learning import Learning
from sunwell.memory.session.summary import GoalSummary, SessionSummary


def _make_goal(
    goal: str,
    status: str = "completed",
    tasks_completed: int = 1,
    tasks_failed: int = 0,
) -> GoalSummary:
    """Create a GoalSummary for testing."""
    return GoalSummary(
        goal_id=f"g-{hash(goal) % 1000}",
        goal=goal,
        status=status,
        source="cli",
        started_at=datetime.now(UTC) - timedelta(minutes=5),
        duration_seconds=60.0,
        tasks_completed=tasks_completed,
        tasks_failed=tasks_failed,
        files_touched=(),
    )


def _make_session(goals: list[GoalSummary]) -> SessionSummary:
    """Create a SessionSummary for testing."""
    return SessionSummary(
        session_id="test-session",
        started_at=datetime.now(UTC) - timedelta(hours=1),
        source="cli",
        goals_started=len(goals),
        goals_completed=len([g for g in goals if g.status == "completed"]),
        goals_failed=len([g for g in goals if g.status == "failed"]),
        goals=goals,
    )


class TestConfidenceCalibration:
    """Tests for confidence calibration extraction."""

    def test_no_patterns_when_no_goals(self) -> None:
        """Should return no patterns when no goals."""
        extractor = AwarenessExtractor()
        session = _make_session([])
        learning_store = LearningStore()

        patterns = extractor.analyze_session(session, learning_store)

        assert len(patterns) == 0

    def test_no_patterns_when_insufficient_samples(self) -> None:
        """Should not extract pattern with < 3 samples of same task type."""
        extractor = AwarenessExtractor()

        goals = [
            _make_goal("refactor the auth module", status="failed"),
            _make_goal("refactor the user model", status="failed"),
        ]
        session = _make_session(goals)

        learning_store = LearningStore()
        learning_store.add_learning(Learning(fact="test", category="pattern", confidence=0.9))

        patterns = extractor.analyze_session(session, learning_store)

        # Should not extract pattern - only 2 refactoring tasks
        confidence_patterns = [p for p in patterns if p.pattern_type == PatternType.CONFIDENCE]
        assert len(confidence_patterns) == 0

    def test_extracts_overconfidence_pattern(self) -> None:
        """Should extract overconfidence pattern when avg confidence > success rate."""
        extractor = AwarenessExtractor()

        # 5 refactoring tasks, 2 successful = 40% success rate
        goals = [
            _make_goal("refactor auth", status="completed"),
            _make_goal("refactor user", status="completed"),
            _make_goal("refactor settings", status="failed"),
            _make_goal("refactor config", status="failed"),
            _make_goal("refactor db", status="failed"),
        ]
        session = _make_session(goals)

        # High confidence learnings = 90% average
        learning_store = LearningStore()
        for i in range(5):
            learning_store.add_learning(
                Learning(fact=f"fact {i}", category="pattern", confidence=0.9)
            )

        patterns = extractor.analyze_session(session, learning_store)

        # Should detect overconfidence: 90% confidence vs 40% success
        confidence_patterns = [p for p in patterns if p.pattern_type == PatternType.CONFIDENCE]
        assert len(confidence_patterns) >= 1

        pattern = confidence_patterns[0]
        assert "overstate" in pattern.observation.lower()
        assert pattern.metric > 0.10  # At least 10% miscalibration


class TestErrorClustering:
    """Tests for error clustering extraction."""

    def test_extracts_error_cluster_for_high_failure_rate(self) -> None:
        """Should extract error cluster when task type has high failure rate."""
        extractor = AwarenessExtractor()

        # 5 test tasks, 4 failed = 80% failure rate
        goals = [
            _make_goal("add tests for auth", status="failed"),
            _make_goal("write tests for user", status="failed"),
            _make_goal("create tests for settings", status="failed"),
            _make_goal("implement tests for config", status="failed"),
            _make_goal("fix tests for db", status="completed"),
        ]
        session = _make_session(goals)

        patterns = extractor.analyze_session(session, LearningStore())

        error_patterns = [p for p in patterns if p.pattern_type == PatternType.ERROR_CLUSTER]
        assert len(error_patterns) >= 1

        pattern = error_patterns[0]
        assert "test" in pattern.context.lower()
        assert pattern.metric >= 0.25  # At least 25% failure rate

    def test_no_error_cluster_for_low_failure_rate(self) -> None:
        """Should not extract error cluster when failure rate is low."""
        extractor = AwarenessExtractor()

        # 5 test tasks, 1 failed = 20% failure rate
        goals = [
            _make_goal("add tests for auth", status="completed"),
            _make_goal("write tests for user", status="completed"),
            _make_goal("create tests for settings", status="completed"),
            _make_goal("implement tests for config", status="completed"),
            _make_goal("fix tests for db", status="failed"),
        ]
        session = _make_session(goals)

        patterns = extractor.analyze_session(session, LearningStore())

        # 20% failure is below 25% threshold
        error_patterns = [p for p in patterns if p.pattern_type == PatternType.ERROR_CLUSTER]
        assert len(error_patterns) == 0


class TestToolAvoidance:
    """Tests for tool avoidance extraction."""

    def test_extracts_underutilized_tool(self) -> None:
        """Should extract pattern for high-success but low-usage tools."""
        extractor = AwarenessExtractor()

        # grep_search: 5 uses, 4 successes = 80% success, 5% usage
        # read_file: 95 uses, 50 successes = 53% success, 95% usage
        tool_audit_log = [
            {"tool": "read_file", "success": i % 2 == 0}
            for i in range(95)
        ] + [
            {"tool": "grep_search", "success": i < 4}
            for i in range(5)
        ]

        session = _make_session([_make_goal("test")])

        patterns = extractor.analyze_session(
            session,
            LearningStore(),
            tool_audit_log=tool_audit_log,
        )

        avoidance_patterns = [p for p in patterns if p.pattern_type == PatternType.TOOL_AVOIDANCE]
        assert len(avoidance_patterns) >= 1

        pattern = avoidance_patterns[0]
        assert "grep_search" in pattern.context
        assert "under-utilize" in pattern.observation.lower()

    def test_no_avoidance_without_audit_log(self) -> None:
        """Should not extract tool avoidance without audit log."""
        extractor = AwarenessExtractor()
        session = _make_session([_make_goal("test")])

        patterns = extractor.analyze_session(session, LearningStore())

        avoidance_patterns = [p for p in patterns if p.pattern_type == PatternType.TOOL_AVOIDANCE]
        assert len(avoidance_patterns) == 0


class TestBacktrackRate:
    """Tests for backtrack rate extraction."""

    def test_extracts_high_backtrack_rate(self) -> None:
        """Should extract pattern when undo/restore rate is high."""
        extractor = AwarenessExtractor()

        # 10 test file edits, 3 undos = 30% backtrack rate
        tool_audit_log = [
            {"tool": "edit_file", "success": True, "arguments": {"path": f"test_{i}.py"}}
            for i in range(10)
        ] + [
            {"tool": "undo_file", "success": True, "arguments": {"path": f"test_{i}.py"}}
            for i in range(3)
        ]

        session = _make_session([_make_goal("test")])

        patterns = extractor.analyze_session(
            session,
            LearningStore(),
            tool_audit_log=tool_audit_log,
        )

        backtrack_patterns = [p for p in patterns if p.pattern_type == PatternType.BACKTRACK]
        assert len(backtrack_patterns) >= 1

        pattern = backtrack_patterns[0]
        assert "test" in pattern.context.lower()
        assert pattern.metric >= 0.20  # At least 20% backtrack rate
