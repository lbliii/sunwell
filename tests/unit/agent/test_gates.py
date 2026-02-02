"""Tests for validation gates (RFC-042).

Tests gate types, detection, and results.
"""

from unittest.mock import MagicMock

import pytest

from sunwell.agent.validation.gates import (
    GateResult,
    GateStepResult,
    GateType,
    ValidationGate,
    _find_blocked_tasks,
    _matches_task_pattern,
    detect_gates,
    is_runnable_milestone,
)


class TestGateType:
    """Tests for GateType enum."""

    def test_all_gate_types_exist(self) -> None:
        """All expected gate types are defined."""
        expected = {
            "SYNTAX",
            "LINT",
            "TYPE",
            "IMPORT",
            "INSTANTIATE",
            "SCHEMA",
            "SERVE",
            "ENDPOINT",
            "INTEGRATION",
            "TEST",
            "COMMAND",
            "SEMANTIC",
            "CONTRACT",
        }

        actual = {gt.name for gt in GateType}

        assert actual == expected

    def test_gate_type_values(self) -> None:
        """Gate types have lowercase string values."""
        assert GateType.SYNTAX.value == "syntax"
        assert GateType.LINT.value == "lint"
        assert GateType.IMPORT.value == "import"
        assert GateType.SEMANTIC.value == "semantic"


class TestValidationGate:
    """Tests for ValidationGate dataclass."""

    def test_gate_creation(self) -> None:
        """ValidationGate stores all fields."""
        gate = ValidationGate(
            id="gate_models",
            gate_type=GateType.SCHEMA,
            depends_on=("task_user_model", "task_post_model"),
            validation="Base.metadata.create_all(engine)",
            blocks=("task_routes",),
            timeout_s=60,
        )

        assert gate.id == "gate_models"
        assert gate.gate_type == GateType.SCHEMA
        assert gate.depends_on == ("task_user_model", "task_post_model")
        assert gate.validation == "Base.metadata.create_all(engine)"
        assert gate.blocks == ("task_routes",)
        assert gate.timeout_s == 60

    def test_gate_defaults(self) -> None:
        """ValidationGate has sensible defaults."""
        gate = ValidationGate(
            id="gate_test",
            gate_type=GateType.IMPORT,
            depends_on=("task-1",),
            validation="import test",
        )

        assert gate.blocks == ()
        assert gate.is_runnable_milestone is True
        assert gate.timeout_s == 30

    def test_gate_auto_description(self) -> None:
        """ValidationGate auto-generates description."""
        gate = ValidationGate(
            id="gate_protocols",
            gate_type=GateType.IMPORT,
            depends_on=("protocols_task",),
            validation="import protocols",
        )

        assert gate.description != ""
        assert "import" in gate.description.lower() or "Import" in gate.description

    def test_gate_explicit_description(self) -> None:
        """ValidationGate respects explicit description."""
        gate = ValidationGate(
            id="gate_custom",
            gate_type=GateType.TEST,
            depends_on=("task-1",),
            validation="pytest tests/",
            description="Run the custom test suite",
        )

        assert gate.description == "Run the custom test suite"

    def test_gate_is_frozen(self) -> None:
        """ValidationGate is immutable."""
        gate = ValidationGate(
            id="gate_frozen",
            gate_type=GateType.LINT,
            depends_on=("task-1",),
            validation="ruff check",
        )

        with pytest.raises(AttributeError):
            gate.id = "new_id"  # type: ignore


class TestGateStepResult:
    """Tests for GateStepResult dataclass."""

    def test_passed_step(self) -> None:
        """GateStepResult captures passed step."""
        result = GateStepResult(
            step="syntax",
            passed=True,
            message="0 errors",
            duration_ms=50,
        )

        assert result.passed
        assert result.step == "syntax"
        assert result.duration_ms == 50
        assert not result.auto_fixed

    def test_failed_step(self) -> None:
        """GateStepResult captures failed step."""
        result = GateStepResult(
            step="lint",
            passed=False,
            message="3 errors",
            duration_ms=120,
            errors=({"line": 10, "message": "Error 1"},),
        )

        assert not result.passed
        assert len(result.errors) == 1

    def test_auto_fixed_step(self) -> None:
        """GateStepResult tracks auto-fixes."""
        result = GateStepResult(
            step="lint",
            passed=True,
            message="0 errors (2 auto-fixed)",
            duration_ms=200,
            auto_fixed=True,
        )

        assert result.auto_fixed


class TestGateResult:
    """Tests for GateResult dataclass."""

    def test_passed_gate_result(self) -> None:
        """GateResult captures passed gate."""
        gate = ValidationGate(
            id="gate_test",
            gate_type=GateType.IMPORT,
            depends_on=("task-1",),
            validation="import test",
        )
        steps = (
            GateStepResult(step="syntax", passed=True, message="OK"),
            GateStepResult(step="import", passed=True, message="OK"),
        )

        result = GateResult(
            gate=gate,
            passed=True,
            steps=steps,
            duration_ms=150,
        )

        assert result.passed
        assert len(result.steps) == 2
        assert result.duration_ms == 150

    def test_failed_gate_result(self) -> None:
        """GateResult captures failed gate with errors."""
        gate = ValidationGate(
            id="gate_broken",
            gate_type=GateType.LINT,
            depends_on=("task-1",),
            validation="ruff check",
        )

        result = GateResult(
            gate=gate,
            passed=False,
            errors=("Line 10: E501", "Line 20: F401"),
        )

        assert not result.passed
        assert len(result.errors) == 2

    def test_auto_fixed_count(self) -> None:
        """auto_fixed_count tallies auto-fixed steps."""
        gate = ValidationGate(
            id="gate_lint",
            gate_type=GateType.LINT,
            depends_on=("task-1",),
            validation="ruff check",
        )
        steps = (
            GateStepResult(step="lint", passed=True, auto_fixed=True),
            GateStepResult(step="format", passed=True, auto_fixed=True),
            GateStepResult(step="type", passed=True, auto_fixed=False),
        )

        result = GateResult(gate=gate, passed=True, steps=steps)

        assert result.auto_fixed_count == 2


class TestDetectGates:
    """Tests for detect_gates function."""

    def _make_task(
        self,
        task_id: str,
        description: str,
        target_path: str | None = None,
        is_contract: bool = False,
        depends_on: tuple[str, ...] = (),
        verification_command: str | None = None,
    ) -> MagicMock:
        """Create a mock Task."""
        task = MagicMock()
        task.id = task_id
        task.description = description
        task.target_path = target_path
        task.is_contract = is_contract
        task.depends_on = depends_on
        task.verification_command = verification_command
        return task

    def test_detect_protocol_gate(self) -> None:
        """detect_gates finds protocol/interface tasks."""
        tasks = [
            self._make_task("task_protocol", "Define user protocol", "protocols.py", is_contract=True),
            self._make_task("task_impl", "Implement user", "impl.py", depends_on=("task_protocol",)),
        ]

        gates = detect_gates(tasks)

        # Should have an import gate for protocols
        protocol_gates = [g for g in gates if g.id == "gate_protocols"]
        assert len(protocol_gates) == 1
        assert protocol_gates[0].gate_type == GateType.IMPORT

    def test_detect_model_gate(self) -> None:
        """detect_gates finds model/schema tasks."""
        tasks = [
            self._make_task("task_user_model", "Create UserModel", "models.py"),
            self._make_task("task_routes", "Create routes", "routes.py", depends_on=("task_user_model",)),
        ]

        gates = detect_gates(tasks)

        # Should have a schema gate for models
        model_gates = [g for g in gates if g.id == "gate_models"]
        assert len(model_gates) == 1
        assert model_gates[0].gate_type == GateType.SCHEMA

    def test_detect_route_gate(self) -> None:
        """detect_gates finds route/endpoint tasks."""
        tasks = [
            self._make_task("task_routes", "Create API routes", "routes.py"),
        ]

        gates = detect_gates(tasks)

        # Should have an endpoint gate for routes
        route_gates = [g for g in gates if g.id == "gate_routes"]
        assert len(route_gates) == 1
        assert route_gates[0].gate_type == GateType.ENDPOINT

    def test_detect_entry_point_gate(self) -> None:
        """detect_gates finds entry point tasks."""
        tasks = [
            self._make_task("task_app_factory", "Create app factory", "app.py"),
        ]

        gates = detect_gates(tasks)

        # Should have an integration gate
        integration_gates = [g for g in gates if g.id == "gate_integration"]
        assert len(integration_gates) == 1
        assert integration_gates[0].gate_type == GateType.INTEGRATION

    def test_detect_test_gate(self) -> None:
        """detect_gates finds test tasks."""
        tasks = [
            self._make_task("task_test_auth", "Write auth tests", "test_auth.py", verification_command="pytest test_auth.py"),
        ]

        gates = detect_gates(tasks)

        # Should have a test gate
        test_gates = [g for g in gates if "test" in g.id.lower()]
        assert len(test_gates) == 1
        assert test_gates[0].gate_type == GateType.TEST

    def test_detect_no_gates_for_empty(self) -> None:
        """detect_gates returns empty for no tasks."""
        gates = detect_gates([])

        assert gates == []

    def test_gate_blocking_relationships(self) -> None:
        """detect_gates creates gates with correct dependencies."""
        tasks = [
            self._make_task("task_protocol", "Define protocol", "protocol.py", is_contract=True),
            self._make_task("task_impl", "Implement service", "impl.py", depends_on=("task_protocol",)),
        ]

        gates = detect_gates(tasks)

        # Protocol gate should include protocol task in depends_on
        protocol_gate = next((g for g in gates if g.id == "gate_protocols"), None)
        assert protocol_gate is not None
        assert "task_protocol" in protocol_gate.depends_on


class TestMatchesTaskPattern:
    """Tests for _matches_task_pattern helper."""

    def _make_task(self, task_id: str, description: str) -> MagicMock:
        """Create a mock Task."""
        task = MagicMock()
        task.id = task_id
        task.description = description
        return task

    def test_matches_keyword_in_description(self) -> None:
        """_matches_task_pattern finds keyword in description."""
        task = self._make_task("task_1", "Create user model")

        assert _matches_task_pattern(task, ("model",)) is True

    def test_matches_keyword_in_id(self) -> None:
        """_matches_task_pattern finds keyword in task id."""
        task = self._make_task("task_model", "Create something")

        assert _matches_task_pattern(task, ("model",)) is True

    def test_matches_any_of_multiple_keywords(self) -> None:
        """_matches_task_pattern matches any keyword in the tuple."""
        task = self._make_task("task_1", "Create user endpoint")

        assert _matches_task_pattern(task, ("model", "endpoint", "route")) is True

    def test_no_match_returns_false(self) -> None:
        """_matches_task_pattern returns False when no match."""
        task = self._make_task("task_1", "Write documentation")

        assert _matches_task_pattern(task, ("model", "route")) is False

    def test_case_insensitive(self) -> None:
        """_matches_task_pattern is case insensitive."""
        task = self._make_task("TASK_MODEL", "Create USER Model")

        assert _matches_task_pattern(task, ("model",)) is True
        assert _matches_task_pattern(task, ("user",)) is True

    def test_empty_keywords_returns_false(self) -> None:
        """_matches_task_pattern with empty keywords returns False."""
        task = self._make_task("task_1", "anything")

        assert _matches_task_pattern(task, ()) is False


class TestFindBlockedTasks:
    """Tests for _find_blocked_tasks helper."""

    def _make_task(
        self,
        task_id: str,
        depends_on: tuple[str, ...] = (),
    ) -> MagicMock:
        """Create a mock Task."""
        task = MagicMock()
        task.id = task_id
        task.depends_on = depends_on
        return task

    def test_finds_dependent_tasks(self) -> None:
        """_find_blocked_tasks finds tasks that depend on source tasks."""
        source = [self._make_task("task_a")]
        all_tasks = [
            self._make_task("task_a"),
            self._make_task("task_b", depends_on=("task_a",)),
            self._make_task("task_c", depends_on=("task_a",)),
        ]

        blocked = _find_blocked_tasks(source, all_tasks)

        assert "task_b" in blocked
        assert "task_c" in blocked
        assert "task_a" not in blocked  # Source task excluded

    def test_excludes_source_tasks(self) -> None:
        """_find_blocked_tasks excludes source tasks from result."""
        source = [
            self._make_task("task_a"),
            self._make_task("task_b"),
        ]
        all_tasks = [
            self._make_task("task_a"),
            self._make_task("task_b", depends_on=("task_a",)),
        ]

        blocked = _find_blocked_tasks(source, all_tasks)

        assert "task_a" not in blocked
        assert "task_b" not in blocked

    def test_returns_empty_when_no_dependents(self) -> None:
        """_find_blocked_tasks returns empty when no tasks depend on source."""
        source = [self._make_task("task_a")]
        all_tasks = [
            self._make_task("task_a"),
            self._make_task("task_b"),  # No dependency
        ]

        blocked = _find_blocked_tasks(source, all_tasks)

        assert blocked == ()

    def test_handles_multiple_source_tasks(self) -> None:
        """_find_blocked_tasks handles multiple source tasks."""
        source = [
            self._make_task("task_a"),
            self._make_task("task_b"),
        ]
        all_tasks = [
            self._make_task("task_a"),
            self._make_task("task_b"),
            self._make_task("task_c", depends_on=("task_a",)),
            self._make_task("task_d", depends_on=("task_b",)),
            self._make_task("task_e", depends_on=("task_a", "task_b")),
        ]

        blocked = _find_blocked_tasks(source, all_tasks)

        assert "task_c" in blocked
        assert "task_d" in blocked
        assert "task_e" in blocked

    def test_returns_tuple(self) -> None:
        """_find_blocked_tasks returns a tuple."""
        source = [self._make_task("task_a")]
        all_tasks = [self._make_task("task_a")]

        result = _find_blocked_tasks(source, all_tasks)

        assert isinstance(result, tuple)


class TestIsRunnableMilestone:
    """Tests for is_runnable_milestone function."""

    def _make_task(self, task_id: str, target_path: str | None) -> MagicMock:
        """Create a mock Task."""
        task = MagicMock()
        task.id = task_id
        task.target_path = target_path
        return task

    def test_python_files_are_runnable(self) -> None:
        """Tasks producing Python files are runnable milestones."""
        tasks = [
            self._make_task("task_1", "models.py"),
            self._make_task("task_2", "routes.py"),
        ]

        assert is_runnable_milestone(tasks) is True

    def test_non_python_not_runnable(self) -> None:
        """Tasks not producing Python files aren't runnable milestones."""
        tasks = [
            self._make_task("task_1", "config.yaml"),
            self._make_task("task_2", "README.md"),
        ]

        assert is_runnable_milestone(tasks) is False

    def test_mixed_not_runnable(self) -> None:
        """Mixed Python/non-Python isn't runnable milestone."""
        tasks = [
            self._make_task("task_1", "models.py"),
            self._make_task("task_2", "config.yaml"),
        ]

        assert is_runnable_milestone(tasks) is False

    def test_no_target_not_runnable(self) -> None:
        """Tasks without target_path aren't runnable milestones."""
        tasks = [
            self._make_task("task_1", None),
        ]

        assert is_runnable_milestone(tasks) is False

    def test_empty_is_runnable(self) -> None:
        """Empty task list is trivially runnable."""
        # all() returns True for empty iterables
        assert is_runnable_milestone([]) is True
