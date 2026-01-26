"""Tests for the evaluation module (RFC-098)."""

from pathlib import Path

import pytest

from sunwell.benchmark.eval.evaluator import FullStackEvaluator
from sunwell.benchmark.eval.tasks import FULL_STACK_TASKS, get_eval_task, list_eval_tasks
from sunwell.benchmark.eval.types import (
    FullStackTask,
    SingleShotResult,
    SunwellResult,
)


class TestTasks:
    """Tests for evaluation task loading."""

    def test_list_tasks_returns_all_builtin(self):
        """Should return all built-in task IDs."""
        tasks = list_eval_tasks()
        task_names = [t[0] for t in tasks]
        assert "forum_app" in task_names
        assert "cli_tool" in task_names
        assert "rest_api" in task_names

    def test_get_builtin_task(self):
        """Should return a FullStackTask for built-in IDs."""
        task = get_eval_task("forum_app")
        assert isinstance(task, FullStackTask)
        assert task.name == "forum_app"
        assert "forum" in task.prompt.lower() or "flask" in task.prompt.lower()

    def test_get_custom_task(self):
        """Should create a custom task from a prompt string."""
        task = get_eval_task("Build a todo app with React that works well")
        assert task.name == "custom"
        assert task.prompt == "Build a todo app with React that works well"
        assert "create_file" in task.available_tools

    def test_builtin_tasks_have_tools(self):
        """All built-in tasks should have available tools."""
        for task_id, task in FULL_STACK_TASKS.items():
            assert len(task.available_tools) > 0, f"{task_id} has no tools"
            assert "create_file" in task.available_tools

    def test_task_has_required_attributes(self):
        """Tasks should have all required attributes."""
        task = get_eval_task("forum_app")
        assert hasattr(task, "name")
        assert hasattr(task, "prompt")
        assert hasattr(task, "description")
        assert hasattr(task, "available_tools")
        assert hasattr(task, "expected_structure")
        assert hasattr(task, "expected_features")
        assert hasattr(task, "estimated_minutes")


class TestEvaluator:
    """Tests for the evaluator scoring logic."""

    @pytest.fixture
    def evaluator(self):
        """Create an evaluator instance."""
        return FullStackEvaluator()

    @pytest.fixture
    def task(self):
        """Get a task for evaluation."""
        return get_eval_task("forum_app")

    def test_evaluate_returns_score(self, evaluator, task, tmp_path):
        """Evaluator should return a FullStackScore."""
        score = evaluator.evaluate(tmp_path, task)
        # Verify the score has expected attributes
        assert hasattr(score, "final_score")
        assert hasattr(score, "subscores")
        assert hasattr(score, "runnable")
        assert hasattr(score, "files_count")
        assert isinstance(score.final_score, float)

    def test_score_empty_project(self, evaluator, task, tmp_path):
        """Empty project should score low."""
        score = evaluator.evaluate(tmp_path, task)
        assert score.files_count == 0
        assert not score.runnable

    def test_score_with_files(self, evaluator, task, tmp_path):
        """Project with files should have files_count > 0."""
        (tmp_path / "app.py").write_text("print('hello')")
        score = evaluator.evaluate(tmp_path, task)
        assert score.files_count > 0

    def test_score_has_subscores(self, evaluator, task, tmp_path):
        """Score should have a subscores dict."""
        (tmp_path / "app.py").write_text("def main(): pass")
        score = evaluator.evaluate(tmp_path, task)
        assert isinstance(score.subscores, dict)


class TestResults:
    """Tests for result data classes."""

    def test_single_shot_result_creation(self):
        """SingleShotResult should be creatable with required fields."""
        result = SingleShotResult(
            files=("app.py", "models.py"),
            output_dir=Path("/tmp/test"),
            time_seconds=5.5,
            turns=1,
            input_tokens=100,
            output_tokens=500,
        )
        assert len(result.files) == 2
        assert result.turns == 1
        assert result.time_seconds == 5.5
        assert result.total_tokens == 600

    def test_sunwell_result_creation(self):
        """SunwellResult should include cognitive architecture tracking."""
        result = SunwellResult(
            files=("app.py", "models.py"),
            output_dir=Path("/tmp/test"),
            time_seconds=10.5,
            turns=2,
            input_tokens=200,
            output_tokens=800,
            lens_used="coder.lens",
            judge_scores=(6.5, 8.5),
            resonance_iterations=1,
        )
        assert result.lens_used == "coder.lens"
        assert len(result.judge_scores) == 2
        assert result.resonance_iterations == 1
        assert result.final_judge_score == 8.5
        assert result.total_tokens == 1000

    def test_sunwell_result_no_judge_scores(self):
        """SunwellResult without judge scores should have None final score."""
        result = SunwellResult(
            files=("app.py",),
            output_dir=Path("/tmp/test"),
            time_seconds=5.0,
            turns=1,
        )
        assert result.final_judge_score is None


class TestStore:
    """Tests for EvaluationStore persistence."""

    def test_store_creation(self, tmp_path):
        """Store should be creatable with a path."""
        from sunwell.benchmark.eval.store import EvaluationStore

        db_path = tmp_path / "eval.db"
        store = EvaluationStore(db_path)
        assert store is not None
        # Check that database file was created
        assert db_path.exists()

    def test_store_aggregate_stats_empty(self, tmp_path):
        """Empty store should return zero stats."""
        from sunwell.benchmark.eval.store import EvaluationStore

        db_path = tmp_path / "empty.db"
        store = EvaluationStore(db_path)
        stats = store.aggregate_stats()
        assert stats.total_runs == 0

    def test_store_load_recent_empty(self, tmp_path):
        """Empty store should return empty list."""
        from sunwell.benchmark.eval.store import EvaluationStore

        db_path = tmp_path / "empty2.db"
        store = EvaluationStore(db_path)
        runs = store.load_recent(limit=10)
        assert runs == []
