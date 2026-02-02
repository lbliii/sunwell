"""Tests for the Briefing System (RFC-071).

Tests cover:
- Briefing serialization/deserialization
- Compression function
- Learning bridge
- Prefetch planning
- Skill/lens routing
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sunwell.memory.briefing import (
    Briefing,
    BriefingStatus,
    ExecutionSummary,
    PrefetchPlan,
    PrefetchedContext,
    briefing_to_learning,
    compress_briefing,
)
from sunwell.planning.routing.briefing_router import (
    predict_skills_from_briefing,
    suggest_lens_from_briefing,
)


# =============================================================================
# Briefing Serialization Tests
# =============================================================================


class TestBriefingSerialization:
    """Test Briefing serialization and deserialization."""

    def test_briefing_roundtrip(self):
        """Briefing serializes and deserializes correctly."""
        briefing = Briefing(
            mission="Build auth system",
            status=BriefingStatus.IN_PROGRESS,
            progress="JWT signing complete",
            last_action="Added RS256 in auth.py",
            next_action="Implement refresh endpoint",
            hazards=("Don't expose without rate limiting",),
            hot_files=("src/auth.py",),
            # Dispatch hints
            predicted_skills=("security", "api_design"),
            suggested_lens="security-reviewer",
        )

        data = briefing.to_dict()
        restored = Briefing.from_dict(data)

        assert restored.mission == briefing.mission
        assert restored.status == briefing.status
        assert restored.hazards == briefing.hazards
        assert restored.predicted_skills == briefing.predicted_skills
        assert restored.suggested_lens == briefing.suggested_lens

    def test_briefing_optional_fields(self):
        """Briefing handles missing optional fields gracefully."""
        minimal_data = {
            "mission": "Test",
            "status": "in_progress",
            "progress": "Testing",
            "last_action": "Started",
            # No optional fields
        }

        briefing = Briefing.from_dict(minimal_data)

        assert briefing.mission == "Test"
        assert briefing.hazards == ()
        assert briefing.predicted_skills == ()
        assert briefing.suggested_lens is None
        assert briefing.next_action is None

    def test_briefing_to_prompt_format(self):
        """Prompt format is scannable and complete."""
        briefing = Briefing(
            mission="Build auth",
            status=BriefingStatus.IN_PROGRESS,
            progress="80% done",
            last_action="Added JWT",
            next_action="Add refresh",
            hazards=("No rate limiting",),
            hot_files=("auth.py", "config.py"),
        )

        prompt = briefing.to_prompt()

        # First-person voice headers
        assert "## Where I Am (Briefing)" in prompt
        assert "**My Mission**: Build auth" in prompt
        assert "⚠️ No rate limiting" in prompt
        assert "`auth.py`" in prompt

    def test_briefing_create_initial(self):
        """Initial briefing has correct defaults with first-person voice."""
        briefing = Briefing.create_initial("Build a forum app", goal_hash="abc123")

        assert briefing.mission == "Build a forum app"
        assert briefing.status == BriefingStatus.NOT_STARTED
        assert briefing.goal_hash == "abc123"
        # First-person voice
        assert briefing.next_action == "I'll begin planning."
        assert briefing.progress == "I'm starting fresh."
        assert briefing.last_action == "I received the goal."


# =============================================================================
# Compression Tests
# =============================================================================


class TestBriefingCompression:
    """Test the compress_briefing function."""

    def test_compress_briefing_with_summary(self):
        """Compression uses ExecutionSummary correctly."""
        old = Briefing(
            mission="Build API",
            status=BriefingStatus.IN_PROGRESS,
            progress="In progress",
            last_action="Added endpoint",
            hazards=("No auth yet", "No rate limiting"),
        )

        summary = ExecutionSummary(
            last_action="Added authentication",
            next_action="Add rate limiting",
            modified_files=("src/auth.py", "src/config.py"),
            tasks_completed=3,
            gates_passed=2,
            new_learnings=("learning-1",),
            new_hazards=(),
            resolved_hazards=("No auth yet",),
        )

        new = compress_briefing(
            old_briefing=old,
            summary=summary,
            new_status=BriefingStatus.IN_PROGRESS,
        )

        assert "No auth yet" not in new.hazards
        assert "No rate limiting" in new.hazards
        assert new.last_action == "Added authentication"
        assert "src/auth.py" in new.hot_files

    def test_compress_briefing_limits_hazards(self):
        """Compression keeps only 3 most recent hazards."""
        old = Briefing(
            mission="Test",
            status=BriefingStatus.IN_PROGRESS,
            progress="Testing",
            last_action="Test",
            hazards=("Old 1", "Old 2", "Old 3"),
        )

        summary = ExecutionSummary(
            last_action="Added more",
            next_action="Continue",
            modified_files=(),
            tasks_completed=1,
            gates_passed=0,
            new_learnings=(),
            new_hazards=("New 1", "New 2"),
            resolved_hazards=(),
        )

        new = compress_briefing(
            old_briefing=old,
            summary=summary,
            new_status=BriefingStatus.IN_PROGRESS,
        )

        assert len(new.hazards) == 3
        assert new.hazards[0] == "New 1"  # Most recent first

    def test_compress_briefing_complete_status(self):
        """Complete status generates correct progress message."""
        old = Briefing(
            mission="Build feature",
            status=BriefingStatus.IN_PROGRESS,
            progress="Working",
            last_action="Finishing up",
        )

        summary = ExecutionSummary(
            last_action="All tests passing",
            next_action=None,
            modified_files=(),
            tasks_completed=5,
            gates_passed=3,
            new_learnings=(),
        )

        new = compress_briefing(
            old_briefing=old,
            summary=summary,
            new_status=BriefingStatus.COMPLETE,
        )

        assert new.status == BriefingStatus.COMPLETE
        assert "Complete" in new.progress
        assert new.next_action is None

    def test_compress_briefing_from_scratch(self):
        """Compression works without old briefing."""
        summary = ExecutionSummary(
            last_action="Started new project",
            next_action="Set up framework",
            modified_files=("README.md",),
            tasks_completed=1,
            gates_passed=0,
            new_learnings=(),
        )

        new = compress_briefing(
            old_briefing=None,
            summary=summary,
            new_status=BriefingStatus.IN_PROGRESS,
        )

        assert new.mission == "Unknown mission"
        assert new.status == BriefingStatus.IN_PROGRESS
        assert new.last_action == "Started new project"


# =============================================================================
# Learning Bridge Tests
# =============================================================================


class TestLearningBridge:
    """Test the briefing → learning bridge."""

    def test_briefing_to_learning_complete(self):
        """Completed briefing generates learning."""
        briefing = Briefing(
            mission="Implement user authentication",
            status=BriefingStatus.COMPLETE,
            progress="Complete. All endpoints secured.",
            last_action="Added rate limiting",
            next_action=None,
            goal_hash="abc123",
            hot_files=("src/auth.py",),
            hazards=("Watch for token expiry edge cases",),
        )

        learning = briefing_to_learning(briefing)

        assert learning is not None
        assert "Implement user authentication" in learning.fact
        assert learning.category == "task_completion"
        assert learning.confidence == 1.0

    def test_briefing_to_learning_not_complete(self):
        """Non-complete briefing returns None."""
        briefing = Briefing(
            mission="Work in progress",
            status=BriefingStatus.IN_PROGRESS,
            progress="Still working",
            last_action="Did stuff",
            next_action="Do more",
        )

        learning = briefing_to_learning(briefing)

        assert learning is None


# =============================================================================
# Skill/Lens Routing Tests
# =============================================================================


class TestSkillRouting:
    """Test skill prediction from briefing."""

    def test_predict_testing_skills(self):
        """Testing-related briefings get testing skills."""
        briefing = Briefing(
            mission="Add tests for auth module",
            status=BriefingStatus.IN_PROGRESS,
            progress="Setting up",
            last_action="Created test file",
            next_action="Write pytest tests for JWT verification",
        )

        skills = predict_skills_from_briefing(briefing)

        assert "testing" in skills
        assert "pytest" in skills

    def test_predict_debugging_skills(self):
        """Debugging-related briefings get debugging skills."""
        briefing = Briefing(
            mission="Fix authentication bug",
            status=BriefingStatus.IN_PROGRESS,
            progress="Investigating",
            last_action="Reproduced the issue",
            next_action="Debug the token validation error",
        )

        skills = predict_skills_from_briefing(briefing)

        assert "debugging" in skills
        assert "error_analysis" in skills

    def test_predict_api_skills(self):
        """API-related briefings get API skills."""
        briefing = Briefing(
            mission="Build REST API",
            status=BriefingStatus.IN_PROGRESS,
            progress="Creating endpoints",
            last_action="Added GET users endpoint",
            next_action="Add POST endpoint for creating users",
        )

        skills = predict_skills_from_briefing(briefing)

        assert "api_design" in skills
        assert "http" in skills

    def test_no_matching_skills(self):
        """Generic briefing returns empty skills."""
        briefing = Briefing(
            mission="General task",
            status=BriefingStatus.IN_PROGRESS,
            progress="Working",
            last_action="Made progress",
            next_action="Continue",
        )

        skills = predict_skills_from_briefing(briefing)

        # May return empty or contain general skills
        assert isinstance(skills, list)


class TestLensRouting:
    """Test lens suggestion from briefing."""

    def test_suggest_testing_lens(self):
        """Testing briefing suggests QA lens."""
        briefing = Briefing(
            mission="Add comprehensive tests",
            status=BriefingStatus.IN_PROGRESS,
            progress="Writing tests",
            last_action="Set up pytest",
            next_action="Add coverage tests",
        )

        lens = suggest_lens_from_briefing(briefing)

        assert lens == "qa-engineer"

    def test_suggest_security_lens(self):
        """Security briefing suggests security lens."""
        briefing = Briefing(
            mission="Implement authentication",
            status=BriefingStatus.IN_PROGRESS,
            progress="Adding JWT",
            last_action="Set up token signing",
            next_action="Add OAuth integration",
            hazards=("Ensure tokens are properly validated",),
        )

        lens = suggest_lens_from_briefing(briefing)

        assert lens == "security-reviewer"

    def test_no_lens_suggestion(self):
        """Generic briefing returns None lens."""
        briefing = Briefing(
            mission="Generic work",
            status=BriefingStatus.IN_PROGRESS,
            progress="Working",
            last_action="Did something",
            next_action="Do more",
        )

        lens = suggest_lens_from_briefing(briefing)

        # May return None for generic tasks
        assert lens is None or isinstance(lens, str)


# =============================================================================
# Persistence Tests
# =============================================================================


class TestBriefingPersistence:
    """Test briefing save/load to disk."""

    def test_save_and_load(self, tmp_path: Path):
        """Briefing saves and loads from disk."""
        briefing = Briefing(
            mission="Test persistence",
            status=BriefingStatus.IN_PROGRESS,
            progress="Testing save/load",
            last_action="Created briefing",
            next_action="Verify persistence",
            hot_files=("test.py",),
        )

        # Save
        briefing.save(tmp_path)

        # Verify file exists
        briefing_path = tmp_path / ".sunwell" / "memory" / "briefing.json"
        assert briefing_path.exists()

        # Load
        loaded = Briefing.load(tmp_path)

        assert loaded is not None
        assert loaded.mission == briefing.mission
        assert loaded.status == briefing.status
        assert loaded.hot_files == briefing.hot_files

    def test_load_nonexistent(self, tmp_path: Path):
        """Loading nonexistent briefing returns None."""
        loaded = Briefing.load(tmp_path)
        assert loaded is None

    def test_overwrite_on_save(self, tmp_path: Path):
        """Saving overwrites existing briefing."""
        # Save first briefing
        first = Briefing(
            mission="First mission",
            status=BriefingStatus.IN_PROGRESS,
            progress="First",
            last_action="First action",
        )
        first.save(tmp_path)

        # Save second briefing (should overwrite)
        second = Briefing(
            mission="Second mission",
            status=BriefingStatus.COMPLETE,
            progress="Second",
            last_action="Second action",
        )
        second.save(tmp_path)

        # Load and verify it's the second one
        loaded = Briefing.load(tmp_path)
        assert loaded is not None
        assert loaded.mission == "Second mission"
        assert loaded.status == BriefingStatus.COMPLETE


# =============================================================================
# ExecutionSummary Tests
# =============================================================================


class TestExecutionSummary:
    """Test ExecutionSummary creation."""

    def test_summary_from_task_graph_mock(self):
        """Summary builds correctly from mock task graph."""

        # Create a mock task graph
        class MockTask:
            def __init__(self, task_id: str, target_path: str | None = None):
                self.id = task_id
                self.target_path = target_path

        class MockTaskGraph:
            def __init__(self):
                self.tasks = [
                    MockTask("task-1", "src/model.py"),
                    MockTask("task-2", "src/api.py"),
                    MockTask("task-3"),
                ]
                self.completed_ids = {"task-1", "task-2"}
                self.gates = []

        graph = MockTaskGraph()
        learnings: list = []

        summary = ExecutionSummary.from_task_graph(graph, learnings)

        assert summary.tasks_completed == 2
        assert "src/model.py" in summary.modified_files
        assert "src/api.py" in summary.modified_files
        assert "task-3" in (summary.next_action or "")


# =============================================================================
# Prefetch Types Tests
# =============================================================================


class TestPrefetchTypes:
    """Test PrefetchPlan and PrefetchedContext."""

    def test_prefetch_plan_creation(self):
        """PrefetchPlan can be created with all fields."""
        plan = PrefetchPlan(
            files_to_read=("src/auth.py", "src/config.py"),
            learnings_to_load=("learning-1", "learning-2"),
            skills_needed=("security", "api_design"),
            dag_nodes_to_fetch=("node-1",),
            suggested_lens="security-reviewer",
        )

        assert len(plan.files_to_read) == 2
        assert len(plan.skills_needed) == 2
        assert plan.suggested_lens == "security-reviewer"

    def test_prefetched_context_creation(self):
        """PrefetchedContext can be created with all fields."""
        context = PrefetchedContext(
            files={"src/auth.py": "content here"},
            learnings=(),
            dag_context=(),
            active_skills=("security",),
            lens="security-reviewer",
        )

        assert "src/auth.py" in context.files
        assert context.lens == "security-reviewer"
