"""Tests for PlanningEvaluator (benchmark/planning).

Tests coverage:
- Task loading from YAML
- Coverage scoring (artifact matching)
- Coherence scoring (dependency validation)
- Tech alignment scoring
- Granularity scoring (smooth transitions)
- Speed scoring
- Edge cases and error handling
"""

import json
import tempfile
from pathlib import Path

import pytest
import yaml

from sunwell.benchmark.planning import (
    PlanningEvaluationResult,
    PlanningEvaluator,
    evaluate_plan,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_task_yaml() -> dict:
    """Minimal valid task specification."""
    return {
        "id": "test-task-001",
        "name": "Test Task",
        "category": "planning",
        "goal": "Build a Tauri desktop app with Svelte frontend",
        "expected_artifacts": {
            "required": [
                {
                    "id": "tauri_project",
                    "description": "Tauri project initialization",
                    "files": ["src-tauri/Cargo.toml"],
                },
                {
                    "id": "svelte_project",
                    "description": "Svelte project setup",
                    "files": ["package.json"],
                },
            ],
        },
        "grading": {
            "coverage": {"weight": 40},
            "coherence": {"weight": 25},
            "tech_alignment": {"weight": 20},
            "granularity": {"weight": 10},
            "speed": {"weight": 5},
        },
    }


@pytest.fixture
def sample_plan() -> dict:
    """Minimal valid plan that matches the task."""
    return {
        "artifacts": [
            {
                "id": "tauri_setup",
                "description": "Initialize Tauri project",
                "produces_file": "src-tauri/Cargo.toml",
                "wave": 1,
                "requires": [],
            },
            {
                "id": "svelte_setup",
                "description": "Setup Svelte project",
                "produces_file": "package.json",
                "wave": 1,
                "requires": [],
            },
            {
                "id": "frontend_app",
                "description": "Main Svelte application",
                "produces_file": "src/App.svelte",
                "wave": 2,
                "requires": ["svelte_setup"],
            },
        ],
        "waves": [
            {"id": 1, "artifacts": ["tauri_setup", "svelte_setup"]},
            {"id": 2, "artifacts": ["frontend_app"]},
        ],
    }


@pytest.fixture
def task_file(sample_task_yaml: dict, tmp_path: Path) -> Path:
    """Write task YAML to temp file."""
    path = tmp_path / "task.yaml"
    path.write_text(yaml.safe_dump(sample_task_yaml))
    return path


@pytest.fixture
def plan_file(sample_plan: dict, tmp_path: Path) -> Path:
    """Write plan JSON to temp file."""
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(sample_plan))
    return path


# =============================================================================
# Task Loading Tests
# =============================================================================


class TestTaskLoading:
    """Tests for loading task specifications."""

    def test_from_task_loads_yaml(self, task_file: Path):
        """from_task() loads and parses YAML file."""
        evaluator = PlanningEvaluator.from_task(task_file)

        assert evaluator.task["id"] == "test-task-001"
        assert "expected_artifacts" in evaluator.task

    def test_from_task_extracts_weights(self, task_file: Path):
        """from_task() extracts grading weights."""
        evaluator = PlanningEvaluator.from_task(task_file)

        assert evaluator.weights["coverage"] == 0.4
        assert evaluator.weights["coherence"] == 0.25
        assert evaluator.weights["tech_alignment"] == 0.2
        assert evaluator.weights["granularity"] == 0.1
        assert evaluator.weights["speed"] == 0.05

    def test_from_task_uses_defaults(self, tmp_path: Path):
        """from_task() uses default weights when not specified."""
        task = {"id": "minimal", "goal": "Do something"}
        path = tmp_path / "minimal.yaml"
        path.write_text(yaml.safe_dump(task))

        evaluator = PlanningEvaluator.from_task(path)

        # Default weights
        assert evaluator.weights["coverage"] == 0.4
        assert evaluator.weights["coherence"] == 0.25

    def test_from_task_missing_file_raises(self, tmp_path: Path):
        """from_task() raises FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            PlanningEvaluator.from_task(tmp_path / "nonexistent.yaml")


# =============================================================================
# Evaluation Tests
# =============================================================================


class TestEvaluation:
    """Tests for plan evaluation."""

    def test_evaluate_returns_result(self, task_file: Path, plan_file: Path):
        """evaluate() returns PlanningEvaluationResult."""
        evaluator = PlanningEvaluator.from_task(task_file)
        result = evaluator.evaluate(plan_file)

        assert isinstance(result, PlanningEvaluationResult)
        assert result.task_id == "test-task-001"
        assert result.plan_file == str(plan_file)

    def test_evaluate_computes_total_score(self, task_file: Path, plan_file: Path):
        """evaluate() computes weighted total score."""
        evaluator = PlanningEvaluator.from_task(task_file)
        result = evaluator.evaluate(plan_file)

        # Total should be weighted sum
        expected_total = (
            result.coverage_score * 0.4
            + result.coherence_score * 0.25
            + result.tech_alignment_score * 0.2
            + result.granularity_score * 0.1
            + result.speed_score * 0.05
        )
        assert abs(result.total_score - expected_total) < 0.01

    def test_evaluate_missing_task_id_raises(self, tmp_path: Path, plan_file: Path):
        """evaluate() raises ValueError if task has no 'id' field."""
        task = {"goal": "No ID field"}
        task_path = tmp_path / "no_id.yaml"
        task_path.write_text(yaml.safe_dump(task))

        evaluator = PlanningEvaluator.from_task(task_path)
        with pytest.raises(ValueError, match="must contain 'id' field"):
            evaluator.evaluate(plan_file)


# =============================================================================
# Coverage Scoring Tests
# =============================================================================


class TestCoverageScoring:
    """Tests for artifact coverage scoring."""

    def test_coverage_full_match(self, task_file: Path, plan_file: Path):
        """Full coverage when all required artifacts matched."""
        evaluator = PlanningEvaluator.from_task(task_file)
        result = evaluator.evaluate(plan_file)

        # Should have high coverage (both required artifacts matched)
        assert result.coverage_score >= 80.0

    def test_coverage_partial_match(self, tmp_path: Path):
        """Partial coverage when some artifacts missing."""
        # Task with distinct artifact names that won't cross-match
        task = {
            "id": "test-task",
            "goal": "Build an app",
            "expected_artifacts": {
                "required": [
                    {
                        "id": "database",
                        "description": "Database initialization",
                        "files": ["db/schema.sql"],
                    },
                    {
                        "id": "api",
                        "description": "REST API endpoints",
                        "files": ["api/routes.py"],
                    },
                ],
            },
        }
        task_path = tmp_path / "task.yaml"
        task_path.write_text(yaml.safe_dump(task))

        # Plan only has database (matches via file path), missing API
        plan = {
            "artifacts": [
                {
                    "id": "database",
                    "description": "Database schema",
                    "produces_file": "db/schema.sql",
                    "wave": 1,
                },
            ],
            "waves": [{"id": 1}],
        }
        plan_path = tmp_path / "partial.json"
        plan_path.write_text(json.dumps(plan))

        evaluator = PlanningEvaluator.from_task(task_path)
        result = evaluator.evaluate(plan_path)

        # Only 1 of 2 required artifacts matched
        assert result.coverage_score == 50.0
        assert len(result.coverage_details.get("missing", [])) == 1

    def test_coverage_no_required_artifacts(self, tmp_path: Path):
        """100% coverage when no artifacts required."""
        task = {"id": "empty", "expected_artifacts": {"required": []}}
        task_path = tmp_path / "empty.yaml"
        task_path.write_text(yaml.safe_dump(task))

        plan = {"artifacts": [], "waves": []}
        plan_path = tmp_path / "plan.json"
        plan_path.write_text(json.dumps(plan))

        evaluator = PlanningEvaluator.from_task(task_path)
        result = evaluator.evaluate(plan_path)

        assert result.coverage_score == 100.0

    def test_coverage_handles_missing_artifact_id(self, tmp_path: Path):
        """Coverage handles artifacts without 'id' field."""
        task = {
            "id": "test",
            "expected_artifacts": {"required": [{"id": "required_one"}]},
        }
        task_path = tmp_path / "task.yaml"
        task_path.write_text(yaml.safe_dump(task))

        # Plan artifact missing 'id' key
        plan = {
            "artifacts": [{"description": "No ID field", "wave": 1}],
            "waves": [{"id": 1}],
        }
        plan_path = tmp_path / "plan.json"
        plan_path.write_text(json.dumps(plan))

        evaluator = PlanningEvaluator.from_task(task_path)
        result = evaluator.evaluate(plan_path)

        # Should not crash, coverage = 0%
        assert result.coverage_score == 0.0


# =============================================================================
# Coherence Scoring Tests
# =============================================================================


class TestCoherenceScoring:
    """Tests for dependency coherence scoring."""

    def test_coherence_valid_dependencies(self, task_file: Path, plan_file: Path):
        """100% coherence with valid dependency order."""
        evaluator = PlanningEvaluator.from_task(task_file)
        result = evaluator.evaluate(plan_file)

        assert result.coherence_score == 100.0

    def test_coherence_wave_violation(self, task_file: Path, tmp_path: Path):
        """Reduced coherence when depending on later wave."""
        plan = {
            "artifacts": [
                {"id": "A", "wave": 1, "requires": ["B"]},  # Violation: A depends on B
                {"id": "B", "wave": 2, "requires": []},     # B is in later wave
            ],
            "waves": [{"id": 1}, {"id": 2}],
        }
        plan_path = tmp_path / "violation.json"
        plan_path.write_text(json.dumps(plan))

        evaluator = PlanningEvaluator.from_task(task_file)
        result = evaluator.evaluate(plan_path)

        # Should be penalized
        assert result.coherence_score < 100.0
        assert "violations" in result.coherence_details

    def test_coherence_orphan_dependency(self, task_file: Path, tmp_path: Path):
        """Reduced coherence when requiring non-existent artifact."""
        plan = {
            "artifacts": [
                {"id": "A", "wave": 1, "requires": ["nonexistent"]},
            ],
            "waves": [{"id": 1}],
        }
        plan_path = tmp_path / "orphan.json"
        plan_path.write_text(json.dumps(plan))

        evaluator = PlanningEvaluator.from_task(task_file)
        result = evaluator.evaluate(plan_path)

        assert result.coherence_score < 100.0
        assert "orphan_dependencies" in result.coherence_details

    def test_coherence_no_artifacts(self, task_file: Path, tmp_path: Path):
        """50% coherence when no artifacts or waves."""
        plan = {"artifacts": [], "waves": []}
        plan_path = tmp_path / "empty.json"
        plan_path.write_text(json.dumps(plan))

        evaluator = PlanningEvaluator.from_task(task_file)
        result = evaluator.evaluate(plan_path)

        assert result.coherence_score == 50.0


# =============================================================================
# Tech Alignment Scoring Tests
# =============================================================================


class TestTechAlignmentScoring:
    """Tests for tech stack alignment scoring."""

    def test_tech_alignment_correct_stack(self, task_file: Path, plan_file: Path):
        """High score when using correct tech stack."""
        evaluator = PlanningEvaluator.from_task(task_file)
        result = evaluator.evaluate(plan_file)

        # Goal mentions Tauri and Svelte, plan uses them
        assert result.tech_alignment_score > 0

    def test_tech_alignment_wrong_stack(self, tmp_path: Path):
        """Penalized when using conflicting tech."""
        task = {
            "id": "test",
            "goal": "Build a Svelte frontend app",  # Expects Svelte
        }
        task_path = tmp_path / "task.yaml"
        task_path.write_text(yaml.safe_dump(task))

        # Plan uses React instead of Svelte
        plan = {
            "artifacts": [
                {"id": "app", "description": "React app component", "wave": 1},
            ],
            "waves": [{"id": 1}],
        }
        plan_path = tmp_path / "wrong_tech.json"
        plan_path.write_text(json.dumps(plan))

        evaluator = PlanningEvaluator.from_task(task_path)
        result = evaluator.evaluate(plan_path)

        # Should be penalized for using React when Svelte expected
        assert "wrong_tech" in result.tech_details
        assert result.tech_alignment_score < 100.0

    def test_tech_alignment_no_specific_tech(self, tmp_path: Path):
        """100% when no specific tech required."""
        task = {"id": "test", "goal": "Write documentation"}
        task_path = tmp_path / "task.yaml"
        task_path.write_text(yaml.safe_dump(task))

        plan = {"artifacts": [], "waves": []}
        plan_path = tmp_path / "plan.json"
        plan_path.write_text(json.dumps(plan))

        evaluator = PlanningEvaluator.from_task(task_path)
        result = evaluator.evaluate(plan_path)

        assert result.tech_alignment_score == 100.0


# =============================================================================
# Granularity Scoring Tests
# =============================================================================


class TestGranularityScoring:
    """Tests for task decomposition granularity scoring."""

    def test_granularity_sweet_spot(self, tmp_path: Path):
        """100% for 5-15 artifacts (sweet spot)."""
        task = {"id": "test"}
        task_path = tmp_path / "task.yaml"
        task_path.write_text(yaml.safe_dump(task))

        for n in [5, 10, 15]:
            plan = {
                "artifacts": [{"id": f"a{i}", "wave": 1} for i in range(n)],
                "waves": [{"id": 1}],
            }
            plan_path = tmp_path / f"plan_{n}.json"
            plan_path.write_text(json.dumps(plan))

            evaluator = PlanningEvaluator.from_task(task_path)
            result = evaluator.evaluate(plan_path)

            assert result.granularity_score >= 100.0, f"Failed for n={n}"

    def test_granularity_too_coarse(self, tmp_path: Path):
        """Low score for < 3 artifacts."""
        task = {"id": "test"}
        task_path = tmp_path / "task.yaml"
        task_path.write_text(yaml.safe_dump(task))

        plan = {
            "artifacts": [{"id": "single", "wave": 1}],
            "waves": [{"id": 1}],
        }
        plan_path = tmp_path / "coarse.json"
        plan_path.write_text(json.dumps(plan))

        evaluator = PlanningEvaluator.from_task(task_path)
        result = evaluator.evaluate(plan_path)

        assert result.granularity_score == 40.0

    def test_granularity_smooth_transition(self, tmp_path: Path):
        """No cliff between 20 and 21 artifacts."""
        task = {"id": "test"}
        task_path = tmp_path / "task.yaml"
        task_path.write_text(yaml.safe_dump(task))

        scores = {}
        for n in [19, 20, 21, 22]:
            plan = {
                "artifacts": [{"id": f"a{i}", "wave": 1} for i in range(n)],
                "waves": [{"id": 1}],
            }
            plan_path = tmp_path / f"plan_{n}.json"
            plan_path.write_text(json.dumps(plan))

            evaluator = PlanningEvaluator.from_task(task_path)
            result = evaluator.evaluate(plan_path)
            scores[n] = result.granularity_score

        # No more than 10 points difference between adjacent counts
        assert abs(scores[20] - scores[21]) <= 10.0
        assert abs(scores[19] - scores[20]) <= 10.0

    def test_granularity_empty_plan(self, task_file: Path, tmp_path: Path):
        """0% for empty plan."""
        plan = {"artifacts": [], "waves": []}
        plan_path = tmp_path / "empty.json"
        plan_path.write_text(json.dumps(plan))

        evaluator = PlanningEvaluator.from_task(task_file)
        result = evaluator.evaluate(plan_path)

        assert result.granularity_score == 0.0


# =============================================================================
# Result Methods Tests
# =============================================================================


class TestResultMethods:
    """Tests for PlanningEvaluationResult methods."""

    def test_report_generates_markdown(self, task_file: Path, plan_file: Path):
        """report() generates human-readable markdown."""
        evaluator = PlanningEvaluator.from_task(task_file)
        result = evaluator.evaluate(plan_file)

        report = result.report()

        assert "# Planning Evaluation" in report
        assert "Coverage" in report
        assert "TOTAL" in report

    def test_to_dict_serializable(self, task_file: Path, plan_file: Path):
        """to_dict() produces JSON-serializable dict."""
        evaluator = PlanningEvaluator.from_task(task_file)
        result = evaluator.evaluate(plan_file)

        d = result.to_dict()

        # Should be JSON serializable
        json_str = json.dumps(d)
        assert "task_id" in json_str
        assert "scores" in json_str

    def test_to_dict_contains_all_scores(self, task_file: Path, plan_file: Path):
        """to_dict() includes all score components."""
        evaluator = PlanningEvaluator.from_task(task_file)
        result = evaluator.evaluate(plan_file)

        d = result.to_dict()

        assert "coverage" in d["scores"]
        assert "coherence" in d["scores"]
        assert "tech_alignment" in d["scores"]
        assert "granularity" in d["scores"]
        assert "speed" in d["scores"]
        assert "total" in d["scores"]


# =============================================================================
# Convenience Function Tests
# =============================================================================


class TestEvaluatePlanFunction:
    """Tests for evaluate_plan() convenience function."""

    def test_evaluate_plan_works(self, task_file: Path, plan_file: Path):
        """evaluate_plan() works as convenience wrapper."""
        result = evaluate_plan(str(task_file), str(plan_file))

        assert isinstance(result, PlanningEvaluationResult)
        assert result.task_id == "test-task-001"
