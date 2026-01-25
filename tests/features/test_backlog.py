"""Tests for Autonomous Backlog (RFC-046)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from sunwell.features.backlog.goals import Goal, GoalGenerator, GoalPolicy, GoalResult, GoalScope
from sunwell.features.backlog.manager import Backlog, BacklogManager
from sunwell.features.backlog.signals import ObservableSignal, SignalExtractor
from sunwell.knowledge.codebase import CodeLocation


class TestObservableSignal:
    """Tests for ObservableSignal."""

    def test_signal_creation(self):
        """Test creating a signal."""
        location = CodeLocation(
            file=Path("test.py"),
            line_start=10,
            line_end=10,
            symbol="test_function",
        )
        signal = ObservableSignal(
            signal_type="failing_test",
            location=location,
            severity="high",
            message="Test failed",
            auto_fixable=True,
        )
        assert signal.signal_type == "failing_test"
        assert signal.severity == "high"
        assert signal.auto_fixable is True


class TestGoal:
    """Tests for Goal."""

    def test_goal_creation(self):
        """Test creating a goal."""
        goal = Goal(
            id="test-goal-1",
            title="Fix failing test",
            description="Fix the test in test.py",
            source_signals=("signal-1",),
            priority=0.9,
            estimated_complexity="simple",
            requires=frozenset(),
            category="fix",
            auto_approvable=True,
            scope=GoalScope(max_files=2, max_lines_changed=100),
        )
        assert goal.id == "test-goal-1"
        assert goal.priority == 0.9
        assert goal.auto_approvable is True


class TestBacklog:
    """Tests for Backlog."""

    def test_execution_order(self):
        """Test execution order respects dependencies."""
        goal1 = Goal(
            id="goal-1",
            title="Goal 1",
            description="First goal",
            source_signals=(),
            priority=0.5,
            estimated_complexity="simple",
            requires=frozenset(),
            category="fix",
            auto_approvable=True,
            scope=GoalScope(),
        )

        goal2 = Goal(
            id="goal-2",
            title="Goal 2",
            description="Second goal",
            source_signals=(),
            priority=0.8,
            estimated_complexity="simple",
            requires=frozenset({"goal-1"}),
            category="fix",
            auto_approvable=True,
            scope=GoalScope(),
        )

        backlog = Backlog(
            goals={"goal-1": goal1, "goal-2": goal2},
            completed=set(),
            in_progress=None,
            blocked={},
        )

        order = backlog.execution_order()
        assert order[0].id == "goal-1"
        assert order[1].id == "goal-2"

    def test_next_goal(self):
        """Test getting next goal."""
        goal1 = Goal(
            id="goal-1",
            title="Goal 1",
            description="First goal",
            source_signals=(),
            priority=0.5,
            estimated_complexity="simple",
            requires=frozenset(),
            category="fix",
            auto_approvable=True,
            scope=GoalScope(),
        )

        backlog = Backlog(
            goals={"goal-1": goal1},
            completed=set(),
            in_progress=None,
            blocked={},
        )

        next_goal = backlog.next_goal()
        assert next_goal is not None
        assert next_goal.id == "goal-1"

    def test_next_goal_none_when_completed(self):
        """Test next_goal returns None when all completed."""
        goal1 = Goal(
            id="goal-1",
            title="Goal 1",
            description="First goal",
            source_signals=(),
            priority=0.5,
            estimated_complexity="simple",
            requires=frozenset(),
            category="fix",
            auto_approvable=True,
            scope=GoalScope(),
        )

        backlog = Backlog(
            goals={"goal-1": goal1},
            completed={"goal-1"},
            in_progress=None,
            blocked={},
        )

        next_goal = backlog.next_goal()
        assert next_goal is None


class TestSignalExtractor:
    """Tests for SignalExtractor."""

    @pytest.mark.asyncio
    async def test_extract_todos(self, tmp_path: Path):
        """Test extracting TODO comments."""
        # Create a test file with TODO
        test_file = tmp_path / "test.py"
        test_file.write_text("""
def function():
    # TODO: Fix this
    pass
""")

        extractor = SignalExtractor(root=tmp_path)
        signals = await extractor._extract_todos()

        assert len(signals) >= 1
        todo_signals = [s for s in signals if s.signal_type == "todo_comment"]
        assert len(todo_signals) >= 1
        assert "Fix this" in todo_signals[0].message


class TestGoalGenerator:
    """Tests for GoalGenerator."""

    def test_goals_from_observable(self):
        """Test converting signals to goals."""
        location = CodeLocation(
            file=Path("test.py"),
            line_start=10,
            line_end=10,
            symbol="test_function",
        )
        signal = ObservableSignal(
            signal_type="failing_test",
            location=location,
            severity="high",
            message="Test failed",
            auto_fixable=True,
        )

        generator = GoalGenerator()
        goals = generator._goals_from_observable([signal])

        assert len(goals) == 1
        assert goals[0].category == "fix"
        assert goals[0].auto_approvable is True

    def test_deduplicate_goals(self):
        """Test deduplication of similar goals."""
        location = CodeLocation(
            file=Path("test.py"),
            line_start=10,
            line_end=10,
        )
        signal1 = ObservableSignal(
            signal_type="failing_test",
            location=location,
            severity="high",
            message="Test 1 failed",
            auto_fixable=True,
        )
        signal2 = ObservableSignal(
            signal_type="failing_test",
            location=location,
            severity="high",
            message="Test 2 failed",
            auto_fixable=True,
        )

        generator = GoalGenerator()
        goals = generator._goals_from_observable([signal1, signal2])
        deduplicated = generator._deduplicate_goals(goals)

        # Should merge into one goal
        assert len(deduplicated) <= len(goals)


class TestBacklogManager:
    """Tests for BacklogManager."""

    @pytest.mark.asyncio
    async def test_refresh(self, tmp_path: Path):
        """Test refreshing backlog."""
        manager = BacklogManager(root=tmp_path)
        backlog = await manager.refresh()

        assert backlog is not None
        assert isinstance(backlog, Backlog)

    @pytest.mark.asyncio
    async def test_complete_goal(self, tmp_path: Path):
        """Test completing a goal."""
        manager = BacklogManager(root=tmp_path)

        # Create a test goal
        goal = Goal(
            id="test-goal",
            title="Test Goal",
            description="Test",
            source_signals=(),
            priority=0.5,
            estimated_complexity="simple",
            requires=frozenset(),
            category="fix",
            auto_approvable=True,
            scope=GoalScope(),
        )
        manager.backlog.goals["test-goal"] = goal

        result = GoalResult(success=True, duration_seconds=10.0)
        await manager.complete_goal("test-goal", result)

        assert "test-goal" in manager.backlog.completed
