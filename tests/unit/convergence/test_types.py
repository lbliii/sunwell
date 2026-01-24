"""Unit tests for convergence types (RFC-123)."""

import pytest

from sunwell.agent.gates import GateType
from sunwell.convergence.types import (
    ConvergenceConfig,
    ConvergenceIteration,
    ConvergenceResult,
    ConvergenceStatus,
    GateCheckResult,
)


class TestGateCheckResult:
    """Tests for GateCheckResult data structure."""

    def test_creation(self):
        """Should create a gate check result."""
        result = GateCheckResult(
            gate=GateType.LINT,
            passed=True,
            errors=(),
            duration_ms=100,
        )
        assert result.gate == GateType.LINT
        assert result.passed is True
        assert result.errors == ()
        assert result.duration_ms == 100

    def test_error_count(self):
        """Should calculate error count correctly."""
        result = GateCheckResult(
            gate=GateType.LINT,
            passed=False,
            errors=("E501 line too long", "E302 expected 2 blank lines"),
        )
        assert result.error_count == 2

    def test_is_frozen(self):
        """GateCheckResult should be immutable."""
        result = GateCheckResult(
            gate=GateType.LINT,
            passed=True,
            errors=(),
        )
        with pytest.raises(Exception):
            result.passed = False


class TestConvergenceIteration:
    """Tests for ConvergenceIteration data structure."""

    def test_all_passed_true(self):
        """Should return True when all gates pass."""
        iter_result = ConvergenceIteration(
            iteration=1,
            gate_results=(
                GateCheckResult(gate=GateType.LINT, passed=True, errors=()),
                GateCheckResult(gate=GateType.TYPE, passed=True, errors=()),
            ),
            files_changed=(),
            duration_ms=500,
        )
        assert iter_result.all_passed is True

    def test_all_passed_false(self):
        """Should return False when any gate fails."""
        iter_result = ConvergenceIteration(
            iteration=1,
            gate_results=(
                GateCheckResult(gate=GateType.LINT, passed=True, errors=()),
                GateCheckResult(gate=GateType.TYPE, passed=False, errors=("type error",)),
            ),
            files_changed=(),
            duration_ms=500,
        )
        assert iter_result.all_passed is False

    def test_total_errors(self):
        """Should sum errors across all gates."""
        iter_result = ConvergenceIteration(
            iteration=1,
            gate_results=(
                GateCheckResult(gate=GateType.LINT, passed=False, errors=("E1", "E2")),
                GateCheckResult(gate=GateType.TYPE, passed=False, errors=("T1",)),
            ),
            files_changed=(),
            duration_ms=500,
        )
        assert iter_result.total_errors == 3


class TestConvergenceResult:
    """Tests for ConvergenceResult data structure."""

    def test_stable_property(self):
        """stable property should return True only for STABLE status."""
        stable = ConvergenceResult(status=ConvergenceStatus.STABLE)
        assert stable.stable is True

        escalated = ConvergenceResult(status=ConvergenceStatus.ESCALATED)
        assert escalated.stable is False

        timeout = ConvergenceResult(status=ConvergenceStatus.TIMEOUT)
        assert timeout.stable is False

    def test_iteration_count(self):
        """Should count iterations correctly."""
        result = ConvergenceResult(
            status=ConvergenceStatus.STABLE,
            iterations=[
                ConvergenceIteration(
                    iteration=1,
                    gate_results=(),
                    files_changed=(),
                    duration_ms=100,
                ),
                ConvergenceIteration(
                    iteration=2,
                    gate_results=(),
                    files_changed=(),
                    duration_ms=100,
                ),
            ],
        )
        assert result.iteration_count == 2


class TestConvergenceConfig:
    """Tests for ConvergenceConfig data structure."""

    def test_default_values(self):
        """Should have sensible defaults."""
        config = ConvergenceConfig()
        assert config.max_iterations == 5
        assert config.max_tokens == 50_000
        assert config.timeout_seconds == 300
        assert GateType.LINT in config.enabled_gates
        assert GateType.TYPE in config.enabled_gates
        assert config.debounce_ms == 200
        assert config.escalate_after_same_error == 2

    def test_custom_gates(self):
        """Should accept custom gate configuration."""
        config = ConvergenceConfig(
            enabled_gates=frozenset({GateType.LINT}),
            advisory_gates=frozenset({GateType.TEST}),
        )
        assert GateType.LINT in config.enabled_gates
        assert GateType.TYPE not in config.enabled_gates
        assert GateType.TEST in config.advisory_gates


class TestConvergenceStatus:
    """Tests for ConvergenceStatus enum."""

    def test_status_values(self):
        """All expected statuses should exist."""
        assert ConvergenceStatus.RUNNING.value == "running"
        assert ConvergenceStatus.STABLE.value == "stable"
        assert ConvergenceStatus.ESCALATED.value == "escalated"
        assert ConvergenceStatus.TIMEOUT.value == "timeout"
        assert ConvergenceStatus.CANCELLED.value == "cancelled"
