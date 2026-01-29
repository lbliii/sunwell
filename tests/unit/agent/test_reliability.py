"""Unit tests for agent reliability components.

Tests cover:
- CircuitBreaker: Prevents runaway failures
- BackoffPolicy: Exponential backoff with jitter
- SessionCostTracker: Token and dollar budget tracking
- HealthStatus: Pre-flight health checks
"""

import asyncio
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from sunwell.agent.reliability.backoff import (
    AGGRESSIVE_BACKOFF,
    CONSERVATIVE_BACKOFF,
    DEFAULT_RETRY_BACKOFF,
    BackoffPolicy,
    compute_backoff,
    compute_backoff_sequence,
    sleep_with_backoff,
)
from sunwell.agent.reliability.circuit_breaker import CircuitBreaker, CircuitState
from sunwell.agent.reliability.cost_tracker import (
    ModelCost,
    SessionCostTracker,
    get_model_cost,
)
from sunwell.agent.reliability.health import (
    HealthStatus,
    check_health,
    check_health_sync,
)


# =============================================================================
# CircuitBreaker Tests
# =============================================================================


class TestCircuitBreaker:
    """Tests for CircuitBreaker pattern implementation."""

    def test_starts_closed(self) -> None:
        """Initial state is CLOSED."""
        breaker = CircuitBreaker()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.consecutive_failures == 0
        assert breaker.is_open is False

    def test_stays_closed_on_success(self) -> None:
        """Success keeps circuit closed."""
        breaker = CircuitBreaker()
        breaker.record_success()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.consecutive_failures == 0

    def test_opens_after_threshold_failures(self) -> None:
        """Opens after N consecutive failures."""
        breaker = CircuitBreaker(failure_threshold=3)

        # First two failures don't open
        assert breaker.record_failure() is False
        assert breaker.record_failure() is False
        assert breaker.state == CircuitState.CLOSED

        # Third failure opens the circuit
        assert breaker.record_failure() is True
        assert breaker.state == CircuitState.OPEN
        assert breaker.is_open is True

    def test_blocks_execution_when_open(self) -> None:
        """can_execute() returns False when open."""
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout_seconds=60)

        # Open the circuit
        breaker.record_failure()
        breaker.record_failure()

        assert breaker.is_open is True
        assert breaker.can_execute() is False

    def test_transitions_to_half_open_after_timeout(self) -> None:
        """After recovery_timeout, state is HALF_OPEN."""
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout_seconds=0.1)

        # Open the circuit
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        # Wait for recovery timeout
        time.sleep(0.15)

        # Should transition to HALF_OPEN on next can_execute check
        assert breaker.can_execute() is True
        assert breaker.state == CircuitState.HALF_OPEN

    def test_half_open_allows_limited_calls(self) -> None:
        """Only half_open_max_calls allowed in HALF_OPEN state."""
        breaker = CircuitBreaker(
            failure_threshold=2,
            recovery_timeout_seconds=0.01,
            half_open_max_calls=1,  # Only 1 call allowed after transition
        )

        # Open the circuit
        breaker.record_failure()
        breaker.record_failure()

        # Wait for recovery
        time.sleep(0.02)

        # First call transitions to HALF_OPEN (doesn't count toward limit)
        assert breaker.can_execute() is True
        assert breaker.state == CircuitState.HALF_OPEN

        # Second call allowed (counts as 1st toward limit)
        assert breaker.can_execute() is True

        # Third call blocked (limit reached)
        assert breaker.can_execute() is False

    def test_success_in_half_open_closes_circuit(self) -> None:
        """Success in HALF_OPEN returns to CLOSED."""
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout_seconds=0.01)

        # Open and wait for half-open
        breaker.record_failure()
        breaker.record_failure()
        time.sleep(0.02)
        breaker.can_execute()  # Transitions to HALF_OPEN

        assert breaker.state == CircuitState.HALF_OPEN

        # Success should close the circuit
        breaker.record_success()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.consecutive_failures == 0

    def test_failure_in_half_open_reopens(self) -> None:
        """Failure in HALF_OPEN returns to OPEN."""
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout_seconds=0.01)

        # Open and wait for half-open
        breaker.record_failure()
        breaker.record_failure()
        time.sleep(0.02)
        breaker.can_execute()  # Transitions to HALF_OPEN

        assert breaker.state == CircuitState.HALF_OPEN

        # Failure should reopen
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

    def test_reset_returns_to_initial_state(self) -> None:
        """reset() clears all state."""
        breaker = CircuitBreaker(failure_threshold=2)

        # Build up some state
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        # Reset
        breaker.reset()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.consecutive_failures == 0
        assert breaker.can_execute() is True

    def test_to_dict_exports_statistics(self) -> None:
        """Serialization includes all counters."""
        breaker = CircuitBreaker(failure_threshold=3)

        # Build up some statistics
        breaker.record_success()
        breaker.record_success()
        breaker.record_failure()
        breaker.record_failure()
        breaker.record_failure()  # Opens circuit

        data = breaker.to_dict()
        assert data["state"] == "open"
        assert data["consecutive_failures"] == 3
        assert data["failure_threshold"] == 3
        assert data["total_failures"] == 3
        assert data["total_successes"] == 2
        assert data["times_opened"] == 1


# =============================================================================
# BackoffPolicy Tests
# =============================================================================


class TestBackoffPolicy:
    """Tests for exponential backoff with jitter."""

    def test_policy_validation_rejects_invalid(self) -> None:
        """Validates initial_ms, max_ms, factor, jitter."""
        # initial_ms must be positive
        with pytest.raises(ValueError, match="initial_ms must be positive"):
            BackoffPolicy(initial_ms=0)

        # max_ms must be >= initial_ms
        with pytest.raises(ValueError, match="max_ms must be >= initial_ms"):
            BackoffPolicy(initial_ms=1000, max_ms=500)

        # factor must be >= 1.0
        with pytest.raises(ValueError, match="factor must be >= 1.0"):
            BackoffPolicy(factor=0.5)

        # jitter must be between 0.0 and 1.0
        with pytest.raises(ValueError, match="jitter must be between"):
            BackoffPolicy(jitter=1.5)

    def test_compute_backoff_exponential_growth(self) -> None:
        """delay = initial * factor^(attempt-1)."""
        policy = BackoffPolicy(initial_ms=100, max_ms=10000, factor=2.0, jitter=0.0)

        # With jitter=0, delays are deterministic
        # attempt 1: 100 * 2^0 = 100
        # attempt 2: 100 * 2^1 = 200
        # attempt 3: 100 * 2^2 = 400
        assert compute_backoff(policy, 1) == 100
        assert compute_backoff(policy, 2) == 200
        assert compute_backoff(policy, 3) == 400

    def test_compute_backoff_caps_at_max(self) -> None:
        """Never exceeds max_ms."""
        policy = BackoffPolicy(initial_ms=100, max_ms=500, factor=2.0, jitter=0.0)

        # attempt 4: 100 * 2^3 = 800, but capped at 500
        assert compute_backoff(policy, 4) == 500
        assert compute_backoff(policy, 10) == 500

    def test_compute_backoff_includes_jitter(self) -> None:
        """Adds random jitter component."""
        policy = BackoffPolicy(initial_ms=1000, max_ms=10000, factor=2.0, jitter=0.5)

        # Run multiple times to verify jitter adds variation
        delays = [compute_backoff(policy, 1) for _ in range(20)]

        # All delays should be >= base (1000)
        assert all(d >= 1000 for d in delays)
        # With jitter=0.5, max delay is 1000 + 500 = 1500
        assert all(d <= 1500 for d in delays)
        # Should have some variation (not all the same)
        assert len(set(delays)) > 1

    def test_default_policies_valid(self) -> None:
        """DEFAULT_RETRY_BACKOFF, AGGRESSIVE, CONSERVATIVE are valid."""
        # Should not raise
        assert DEFAULT_RETRY_BACKOFF.initial_ms == 500
        assert AGGRESSIVE_BACKOFF.initial_ms == 100
        assert CONSERVATIVE_BACKOFF.initial_ms == 1000

        # All should be usable
        compute_backoff(DEFAULT_RETRY_BACKOFF, 1)
        compute_backoff(AGGRESSIVE_BACKOFF, 1)
        compute_backoff(CONSERVATIVE_BACKOFF, 1)

    def test_compute_backoff_sequence_deterministic(self) -> None:
        """Sequence preview without jitter."""
        policy = BackoffPolicy(initial_ms=100, max_ms=1000, factor=2.0, jitter=0.25)

        sequence = compute_backoff_sequence(policy, 5)
        # Without jitter: 100, 200, 400, 800, 1000 (capped)
        assert sequence == [100, 200, 400, 800, 1000]

    @pytest.mark.asyncio
    async def test_sleep_with_backoff_completes(self) -> None:
        """Normal sleep completion."""
        policy = BackoffPolicy(initial_ms=10, max_ms=100, factor=2.0, jitter=0.0)

        start = time.time()
        result = await sleep_with_backoff(policy, attempt=1)
        elapsed = time.time() - start

        assert result is True  # Completed normally
        assert elapsed >= 0.01  # At least 10ms

    @pytest.mark.asyncio
    async def test_sleep_with_backoff_aborts_early(self) -> None:
        """Abort event triggers early return."""
        policy = BackoffPolicy(initial_ms=1000, max_ms=10000, factor=2.0, jitter=0.0)

        abort_event = asyncio.Event()

        async def trigger_abort() -> None:
            await asyncio.sleep(0.01)
            abort_event.set()

        # Start abort trigger
        asyncio.create_task(trigger_abort())

        start = time.time()
        result = await sleep_with_backoff(policy, attempt=1, abort_event=abort_event)
        elapsed = time.time() - start

        assert result is False  # Aborted
        assert elapsed < 0.5  # Much less than 1000ms


# =============================================================================
# SessionCostTracker Tests
# =============================================================================


class TestSessionCostTracker:
    """Tests for token and dollar budget tracking."""

    def test_record_calculates_cost_correctly(self) -> None:
        """Cost = (input/1000)*input_rate + (output/1000)*output_rate."""
        tracker = SessionCostTracker(session_id="test")

        # gpt-4o: input=$0.005/1K, output=$0.015/1K
        entry = tracker.record("gpt-4o", input_tokens=1000, output_tokens=500)

        # Expected: (1000/1000)*0.005 + (500/1000)*0.015 = 0.005 + 0.0075 = 0.0125
        assert abs(entry.cost_usd - 0.0125) < 0.0001

    def test_total_cost_sums_all_entries(self) -> None:
        """Aggregate across multiple records."""
        tracker = SessionCostTracker(session_id="test")

        tracker.record("gpt-4o", input_tokens=1000, output_tokens=500)
        tracker.record("gpt-4o", input_tokens=1000, output_tokens=500)

        # Two identical calls = double the cost
        assert abs(tracker.total_cost_usd - 0.025) < 0.0001

    def test_total_tokens_sums_correctly(self) -> None:
        """input + output tokens."""
        tracker = SessionCostTracker(session_id="test")

        tracker.record("gpt-4o", input_tokens=100, output_tokens=50)
        tracker.record("gpt-4o", input_tokens=200, output_tokens=100)

        assert tracker.total_tokens == 450
        assert tracker.total_input_tokens == 300
        assert tracker.total_output_tokens == 150

    def test_budget_remaining_tracks_correctly(self) -> None:
        """budget_usd - total_cost_usd."""
        tracker = SessionCostTracker(session_id="test", budget_usd=1.0)

        # gpt-4o-mini is cheaper
        tracker.record("gpt-4o-mini", input_tokens=10000, output_tokens=5000)

        remaining = tracker.budget_remaining
        assert remaining is not None
        assert remaining < 1.0
        assert remaining > 0

    def test_budget_percentage_used_calculation(self) -> None:
        """(total_cost / budget) * 100."""
        tracker = SessionCostTracker(session_id="test", budget_usd=0.1)

        # Record enough to use ~50% of budget
        # gpt-4o: 1000 input = $0.005, 1000 output = $0.015, total = $0.02
        tracker.record("gpt-4o", input_tokens=1000, output_tokens=1000)

        pct = tracker.budget_percentage_used
        assert pct is not None
        # $0.02 / $0.1 = 20%
        assert abs(pct - 20.0) < 1.0

    def test_is_over_budget_true_when_exceeded(self) -> None:
        """Returns True when cost >= budget."""
        tracker = SessionCostTracker(session_id="test", budget_usd=0.01)

        # This should exceed $0.01 budget
        tracker.record("gpt-4o", input_tokens=1000, output_tokens=1000)

        assert tracker.is_over_budget is True

    def test_local_models_are_free(self) -> None:
        """llama, mistral, etc. have zero cost."""
        tracker = SessionCostTracker(session_id="test")

        tracker.record("llama3", input_tokens=10000, output_tokens=10000)
        tracker.record("mistral", input_tokens=10000, output_tokens=10000)
        tracker.record("codellama", input_tokens=10000, output_tokens=10000)

        assert tracker.total_cost_usd == 0.0

    def test_get_model_cost_partial_match(self) -> None:
        """'gpt-4o-2024-08-06' matches 'gpt-4o'."""
        cost = get_model_cost("gpt-4o-2024-08-06")
        base_cost = get_model_cost("gpt-4o")

        assert cost.input_per_1k == base_cost.input_per_1k
        assert cost.output_per_1k == base_cost.output_per_1k

    def test_unknown_model_defaults_to_free(self) -> None:
        """Unknown models are free."""
        cost = get_model_cost("unknown-model-xyz")
        assert cost.input_per_1k == 0.0
        assert cost.output_per_1k == 0.0

    def test_cost_by_model_breakdown(self) -> None:
        """Per-model cost aggregation."""
        tracker = SessionCostTracker(session_id="test")

        tracker.record("gpt-4o", input_tokens=1000, output_tokens=500)
        tracker.record("gpt-4o-mini", input_tokens=1000, output_tokens=500)
        tracker.record("gpt-4o", input_tokens=1000, output_tokens=500)

        breakdown = tracker.cost_by_model()
        assert "gpt-4o" in breakdown
        assert "gpt-4o-mini" in breakdown
        assert breakdown["gpt-4o"] > breakdown["gpt-4o-mini"]

    def test_summary_includes_all_fields(self) -> None:
        """Complete summary dict."""
        tracker = SessionCostTracker(session_id="test-123", budget_usd=1.0)
        tracker.record("gpt-4o", input_tokens=100, output_tokens=50)

        summary = tracker.summary()
        assert summary["session_id"] == "test-123"
        assert "total_cost_usd" in summary
        assert "total_tokens" in summary
        assert "total_input_tokens" in summary
        assert "total_output_tokens" in summary
        assert "call_count" in summary
        assert "budget_usd" in summary
        assert "budget_remaining" in summary
        assert "budget_percentage_used" in summary
        assert "is_over_budget" in summary

    def test_reset_clears_entries(self) -> None:
        """Reset empties the tracker."""
        tracker = SessionCostTracker(session_id="test")
        tracker.record("gpt-4o", input_tokens=1000, output_tokens=500)

        assert tracker.call_count == 1

        tracker.reset()
        assert tracker.call_count == 0
        assert tracker.total_cost_usd == 0.0
        assert tracker.total_tokens == 0


# =============================================================================
# HealthStatus Tests
# =============================================================================


class TestHealthStatus:
    """Tests for pre-flight health checks."""

    def test_ok_when_all_critical_pass(self, tmp_path: Path) -> None:
        """ok=True when workspace exists, writable, disk OK."""
        status = HealthStatus(
            workspace_exists=True,
            workspace_writable=True,
            git_repo_clean=True,
            disk_space_mb=1000,
            model_available=True,
        )
        assert status.ok is True
        assert len(status.errors) == 0

    def test_not_ok_when_workspace_missing(self) -> None:
        """ok=False, error includes 'does not exist'."""
        status = HealthStatus(
            workspace_exists=False,
            workspace_writable=False,
            git_repo_clean=True,
            disk_space_mb=1000,
            model_available=True,
        )
        assert status.ok is False
        assert any("does not exist" in e for e in status.errors)

    def test_not_ok_when_workspace_not_writable(self) -> None:
        """ok=False, error includes 'not writable'."""
        status = HealthStatus(
            workspace_exists=True,
            workspace_writable=False,
            git_repo_clean=True,
            disk_space_mb=1000,
            model_available=True,
        )
        assert status.ok is False
        assert any("not writable" in e for e in status.errors)

    def test_not_ok_when_disk_space_low(self) -> None:
        """ok=False when below MIN_DISK_SPACE_MB."""
        status = HealthStatus(
            workspace_exists=True,
            workspace_writable=True,
            git_repo_clean=True,
            disk_space_mb=50,  # Below 100MB threshold
            model_available=True,
        )
        assert status.ok is False
        assert any("disk space" in e.lower() for e in status.errors)

    def test_warning_for_uncommitted_git_changes(self) -> None:
        """Warning but still ok."""
        status = HealthStatus(
            workspace_exists=True,
            workspace_writable=True,
            git_repo_clean=False,
            disk_space_mb=1000,
            model_available=True,
        )
        assert status.ok is True  # Still OK
        assert any("uncommitted" in w.lower() for w in status.warnings)

    def test_warning_for_low_disk_space(self) -> None:
        """Warning when below LOW_DISK_SPACE_MB but above MIN."""
        status = HealthStatus(
            workspace_exists=True,
            workspace_writable=True,
            git_repo_clean=True,
            disk_space_mb=200,  # Below 500MB warning, above 100MB min
            model_available=True,
        )
        assert status.ok is True  # Still OK
        assert any("low disk space" in w.lower() for w in status.warnings)

    @pytest.mark.asyncio
    async def test_check_health_async_runs(self, tmp_path: Path) -> None:
        """Async version completes."""
        status = await check_health(tmp_path, check_git=False, check_model=False)
        assert status.workspace_exists is True
        assert status.workspace_writable is True

    def test_check_health_sync_runs(self, tmp_path: Path) -> None:
        """Sync version completes."""
        status = check_health_sync(tmp_path, check_git=False)
        assert status.workspace_exists is True
        assert status.workspace_writable is True
        assert isinstance(status.disk_space_mb, int)
