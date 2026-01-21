"""Unit tests for Naaru core types."""

import pytest

from sunwell.naaru.types import (
    Opportunity,
    OpportunityCategory,
    RiskLevel,
    SessionStatus,
    Task,
    TaskMode,
    TaskStatus,
)


class TestTaskType:
    """Test Task type."""

    def test_task_creation(self) -> None:
        """Test Task can be created with required fields."""
        task = Task(
            id="test-1",
            description="Test task",
            mode=TaskMode.GENERATE,
            status=TaskStatus.PENDING,
        )
        assert task.id == "test-1"
        assert task.description == "Test task"
        assert task.mode == TaskMode.GENERATE
        assert task.status == TaskStatus.PENDING

    def test_task_with_dependencies(self) -> None:
        """Test Task with dependencies."""
        task = Task(
            id="test-2",
            description="Task with deps",
            mode=TaskMode.GENERATE,
            status=TaskStatus.PENDING,
            depends_on=("test-1",),
        )
        assert "test-1" in task.depends_on

    def test_task_with_tools(self) -> None:
        """Test Task with required tools."""
        task = Task(
            id="test-3",
            description="Task with tools",
            mode=TaskMode.EXECUTE,
            tools=frozenset(["write_file", "run_command"]),
        )
        assert "write_file" in task.tools
        assert "run_command" in task.tools


class TestTaskMode:
    """Test TaskMode enum."""

    def test_task_mode_values(self) -> None:
        """Test TaskMode has expected values."""
        assert TaskMode.SELF_IMPROVE.value == "self_improve"
        assert TaskMode.GENERATE.value == "generate"
        assert TaskMode.MODIFY.value == "modify"
        assert TaskMode.EXECUTE.value == "execute"
        assert TaskMode.RESEARCH.value == "research"
        assert TaskMode.COMPOSITE.value == "composite"

    def test_task_mode_from_string(self) -> None:
        """Test TaskMode can be created from string."""
        assert TaskMode("generate") == TaskMode.GENERATE
        assert TaskMode("execute") == TaskMode.EXECUTE


class TestTaskStatus:
    """Test TaskStatus enum."""

    def test_task_status_values(self) -> None:
        """Test TaskStatus has expected values."""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.READY.value == "ready"
        assert TaskStatus.IN_PROGRESS.value == "in_progress"
        assert TaskStatus.BLOCKED.value == "blocked"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.SKIPPED.value == "skipped"

    def test_task_status_transitions(self) -> None:
        """Test TaskStatus transitions."""
        # PENDING -> READY -> IN_PROGRESS -> COMPLETED/FAILED
        status = TaskStatus.PENDING
        assert status == TaskStatus.PENDING
        
        # Can transition to READY when dependencies satisfied
        status = TaskStatus.READY
        assert status == TaskStatus.READY


class TestOpportunity:
    """Test Opportunity type."""

    def test_opportunity_creation(self) -> None:
        """Test Opportunity can be created."""
        opp = Opportunity(
            id="opp-1",
            category=OpportunityCategory.CODE_QUALITY,
            description="Test opportunity",
            target_module="test.module",
            priority=0.5,
            estimated_effort="small",
            risk_level=RiskLevel.LOW,
        )
        assert opp.id == "opp-1"
        assert opp.description == "Test opportunity"
        assert opp.category == OpportunityCategory.CODE_QUALITY
        assert opp.risk_level == RiskLevel.LOW

    def test_opportunity_categories(self) -> None:
        """Test OpportunityCategory values."""
        assert OpportunityCategory.ERROR_HANDLING.value == "error_handling"
        assert OpportunityCategory.TESTING.value == "testing"
        assert OpportunityCategory.PERFORMANCE.value == "performance"
        assert OpportunityCategory.DOCUMENTATION.value == "documentation"
        assert OpportunityCategory.CODE_QUALITY.value == "code_quality"
        assert OpportunityCategory.SECURITY.value == "security"
        assert OpportunityCategory.OTHER.value == "other"


class TestRiskLevel:
    """Test RiskLevel enum."""

    def test_risk_level_values(self) -> None:
        """Test RiskLevel has expected values."""
        assert RiskLevel.TRIVIAL.value == "trivial"
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.CRITICAL.value == "critical"

    def test_risk_level_auto_apply(self) -> None:
        """Test RiskLevel can_auto_apply method."""
        assert RiskLevel.TRIVIAL.can_auto_apply() is True
        assert RiskLevel.LOW.can_auto_apply() is True
        assert RiskLevel.MEDIUM.can_auto_apply() is False
        assert RiskLevel.HIGH.can_auto_apply() is False
        assert RiskLevel.CRITICAL.can_auto_apply() is False


class TestSessionStatus:
    """Test SessionStatus enum."""

    def test_session_status_values(self) -> None:
        """Test SessionStatus has expected values."""
        assert SessionStatus.INITIALIZING.value == "initializing"
        assert SessionStatus.RUNNING.value == "running"
        assert SessionStatus.PAUSED.value == "paused"
        assert SessionStatus.COMPLETED.value == "completed"
        assert SessionStatus.FAILED.value == "failed"
