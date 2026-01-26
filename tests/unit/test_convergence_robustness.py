"""Robustness tests for convergence and incremental packages.

Tests derived from bug bash findings to prevent regressions:
- Import correctness
- Timeout exception handling
- Thread safety
- Encoding handling
- Tool availability warnings
- Test file detection
- Error attribution
- Async deduplication
- Deprecation checks
"""

import asyncio
import subprocess
import warnings
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sunwell.agent.convergence import (
    ConvergenceConfig,
    ConvergenceIteration,
    ConvergenceLoop,
    ConvergenceResult,
    ConvergenceStatus,
    GateCheckResult,
)
from sunwell.agent.incremental import AsyncWorkDeduper, WorkDeduper
from sunwell.agent.validation.gates import GateType


# =============================================================================
# Import Correctness Tests
# =============================================================================


class TestImportCorrectness:
    """Verify imports come from correct modules."""

    def test_convergence_loop_module_path(self):
        """ConvergenceLoop should come from agent.convergence, not planning.naaru."""
        assert ConvergenceLoop.__module__ == "sunwell.agent.convergence.loop"

    def test_convergence_types_module_path(self):
        """Convergence types should come from agent.convergence.types."""
        assert ConvergenceConfig.__module__ == "sunwell.agent.convergence.types"
        assert ConvergenceResult.__module__ == "sunwell.agent.convergence.types"
        assert ConvergenceStatus.__module__ == "sunwell.agent.convergence.types"
        assert GateCheckResult.__module__ == "sunwell.agent.convergence.types"

    def test_planning_convergence_is_different_module(self):
        """planning.naaru.convergence should be a different module (working memory)."""
        from sunwell.planning.naaru.convergence import Convergence, Slot

        # These are working memory types, not validation loop types
        assert Convergence.__module__ == "sunwell.planning.naaru.convergence"
        assert Slot.__module__ == "sunwell.planning.naaru.convergence"

        # Verify they're different classes
        assert not hasattr(Convergence, "run")  # No run method (it's working memory)


# =============================================================================
# Timeout Exception Handling Tests
# =============================================================================


class TestTimeoutHandling:
    """Verify timeout exceptions are properly caught."""

    @pytest.fixture
    def mock_model(self):
        """Create a mock model for ConvergenceLoop."""
        model = MagicMock()
        model.generate = AsyncMock(return_value=MagicMock(text="fixed code"))
        return model

    @pytest.mark.asyncio
    async def test_subprocess_timeout_expired_caught_in_lint(self, mock_model, tmp_path):
        """subprocess.TimeoutExpired should be caught in _check_lint."""
        loop = ConvergenceLoop(model=mock_model, cwd=tmp_path)

        # Patch at module level since ConvergenceLoop uses slots=True
        with patch(
            "sunwell.agent.convergence.loop.ConvergenceLoop._run_subprocess",
            new_callable=AsyncMock,
            side_effect=subprocess.TimeoutExpired(cmd=["ruff"], timeout=30),
        ):
            passed, errors = await loop._check_lint([tmp_path / "test.py"])

            assert not passed
            assert any("timed out" in e.lower() for e in errors)

    @pytest.mark.asyncio
    async def test_asyncio_timeout_error_caught_in_lint(self, mock_model, tmp_path):
        """asyncio.TimeoutError should be caught in _check_lint."""
        loop = ConvergenceLoop(model=mock_model, cwd=tmp_path)

        with patch(
            "sunwell.agent.convergence.loop.ConvergenceLoop._run_subprocess",
            new_callable=AsyncMock,
            side_effect=asyncio.TimeoutError(),
        ):
            passed, errors = await loop._check_lint([tmp_path / "test.py"])

            assert not passed
            assert any("timed out" in e.lower() for e in errors)

    @pytest.mark.asyncio
    async def test_subprocess_timeout_expired_caught_in_types(self, mock_model, tmp_path):
        """subprocess.TimeoutExpired should be caught in _check_types."""
        loop = ConvergenceLoop(model=mock_model, cwd=tmp_path)

        with patch(
            "sunwell.agent.convergence.loop.ConvergenceLoop._run_subprocess",
            new_callable=AsyncMock,
            side_effect=subprocess.TimeoutExpired(cmd=["ty"], timeout=60),
        ):
            passed, errors = await loop._check_types([tmp_path / "test.py"])

            assert not passed
            assert any("timed out" in e.lower() for e in errors)

    @pytest.mark.asyncio
    async def test_subprocess_timeout_expired_caught_in_tests(self, mock_model, tmp_path):
        """subprocess.TimeoutExpired should be caught in _check_tests."""
        loop = ConvergenceLoop(model=mock_model, cwd=tmp_path)
        test_file = tmp_path / "test_example.py"
        test_file.touch()

        with patch(
            "sunwell.agent.convergence.loop.ConvergenceLoop._run_subprocess",
            new_callable=AsyncMock,
            side_effect=subprocess.TimeoutExpired(cmd=["pytest"], timeout=120),
        ):
            passed, errors = await loop._check_tests([test_file])

            assert not passed
            assert any("timed out" in e.lower() for e in errors)


# =============================================================================
# Thread Safety Tests
# =============================================================================


class TestThreadSafety:
    """Verify thread-safe access to shared state."""

    @pytest.fixture
    def mock_model(self):
        """Create a mock model for ConvergenceLoop."""
        model = MagicMock()
        model.generate = AsyncMock(return_value=MagicMock(text="fixed code"))
        return model

    def test_error_history_lock_exists(self, mock_model, tmp_path):
        """ConvergenceLoop should have _error_history_lock for thread safety."""
        loop = ConvergenceLoop(model=mock_model, cwd=tmp_path)
        assert hasattr(loop, "_error_history_lock")
        assert loop._error_history_lock is not None

    @pytest.mark.asyncio
    async def test_concurrent_gate_execution_no_race(self, mock_model, tmp_path):
        """Concurrent gate executions should not cause race conditions."""
        loop = ConvergenceLoop(model=mock_model, cwd=tmp_path)

        # Create test files
        files = [tmp_path / f"file{i}.py" for i in range(10)]
        for f in files:
            f.write_text("# test")

        # Mock subprocess to return errors
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = "error: test error\n" * 5

        with patch(
            "sunwell.agent.convergence.loop.ConvergenceLoop._run_subprocess",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            # Run multiple gates concurrently
            results = await asyncio.gather(*[
                loop._run_single_gate(GateType.LINT, files)
                for _ in range(10)
            ], return_exceptions=True)

            # Should not raise any exceptions
            exceptions = [r for r in results if isinstance(r, Exception)]
            assert len(exceptions) == 0

    def test_check_stuck_errors_uses_lock(self, mock_model, tmp_path):
        """_check_stuck_errors should safely access _error_history."""
        loop = ConvergenceLoop(model=mock_model, cwd=tmp_path)

        # Manually add some error history
        with loop._error_history_lock:
            loop._error_history["lint:test error"] = 5

        results = [
            GateCheckResult(
                gate=GateType.LINT,
                passed=False,
                errors=("test error",),
                duration_ms=100,
            )
        ]

        # Should not raise
        is_stuck = loop._check_stuck_errors(results)
        assert is_stuck is True


# =============================================================================
# Encoding Handling Tests
# =============================================================================


class TestEncodingHandling:
    """Verify non-UTF-8 files are handled gracefully."""

    @pytest.fixture
    def mock_model(self):
        """Create a mock model for ConvergenceLoop."""
        model = MagicMock()
        model.generate = AsyncMock(return_value=MagicMock(text="fixed code"))
        return model

    @pytest.mark.asyncio
    async def test_non_utf8_file_does_not_crash(self, mock_model, tmp_path):
        """Files with non-UTF-8 content should not crash artifact building."""
        bad_file = tmp_path / "bad.py"
        # Write invalid UTF-8 bytes
        bad_file.write_bytes(b"# -*- coding: utf-8 -*-\n# \xff\xfe invalid\nprint('test')")

        loop = ConvergenceLoop(model=mock_model, cwd=tmp_path)

        # Mock the fixer to avoid actual model calls
        with patch.object(loop, "_fixer"):
            # This should not raise UnicodeDecodeError
            events = []
            async for event in loop.run([bad_file]):
                events.append(event)

            # Should have started (even if it fails later)
            assert len(events) > 0


# =============================================================================
# Missing Tool Warning Tests
# =============================================================================


class TestMissingToolWarnings:
    """Verify warnings are logged when tools are not installed."""

    @pytest.fixture
    def mock_model(self):
        """Create a mock model for ConvergenceLoop."""
        model = MagicMock()
        model.generate = AsyncMock(return_value=MagicMock(text="fixed code"))
        return model

    @pytest.mark.asyncio
    async def test_missing_ruff_logs_warning(self, mock_model, tmp_path, caplog):
        """When ruff is not installed, a warning should be logged."""
        import logging

        loop = ConvergenceLoop(model=mock_model, cwd=tmp_path)

        with patch(
            "sunwell.agent.convergence.loop.ConvergenceLoop._run_subprocess",
            new_callable=AsyncMock,
            side_effect=FileNotFoundError("ruff"),
        ):
            with caplog.at_level(logging.WARNING):
                passed, errors = await loop._check_lint([tmp_path / "test.py"])

            assert passed is True  # Skipped, so passes
            assert "ruff not installed" in caplog.text

    @pytest.mark.asyncio
    async def test_missing_type_checker_logs_warning(self, mock_model, tmp_path, caplog):
        """When neither ty nor mypy is installed, a warning should be logged."""
        import logging

        loop = ConvergenceLoop(model=mock_model, cwd=tmp_path)

        with patch(
            "sunwell.agent.convergence.loop.ConvergenceLoop._run_subprocess",
            new_callable=AsyncMock,
            side_effect=FileNotFoundError("ty"),
        ):
            with caplog.at_level(logging.WARNING):
                passed, errors = await loop._check_types([tmp_path / "test.py"])

            assert passed is True  # Skipped, so passes
            assert "ty" in caplog.text.lower() or "mypy" in caplog.text.lower()

    @pytest.mark.asyncio
    async def test_missing_pytest_logs_warning(self, mock_model, tmp_path, caplog):
        """When pytest is not installed, a warning should be logged."""
        import logging

        loop = ConvergenceLoop(model=mock_model, cwd=tmp_path)
        test_file = tmp_path / "test_example.py"
        test_file.touch()

        with patch(
            "sunwell.agent.convergence.loop.ConvergenceLoop._run_subprocess",
            new_callable=AsyncMock,
            side_effect=FileNotFoundError("pytest"),
        ):
            with caplog.at_level(logging.WARNING):
                passed, errors = await loop._check_tests([test_file])

            assert passed is True  # Skipped, so passes
            assert "pytest not installed" in caplog.text


# =============================================================================
# Test File Detection Tests
# =============================================================================


class TestTestFileDetection:
    """Verify test files are correctly detected in nested directories."""

    @pytest.fixture
    def mock_model(self):
        """Create a mock model for ConvergenceLoop."""
        model = MagicMock()
        model.generate = AsyncMock(return_value=MagicMock(text="fixed code"))
        return model

    def test_detects_nested_test_files(self):
        """Files in tests/unit/subdir/ should be detected as test files."""
        files = [
            Path("tests/unit/subdir/test_foo.py"),
            Path("tests/integration/deep/nested/test_bar.py"),
            Path("src/main.py"),
            Path("lib/utils.py"),
        ]

        # Apply the same logic as _check_tests
        test_files = [
            f for f in files
            if "test" in f.name.lower() or any(p.name == "tests" for p in f.parents)
        ]

        assert len(test_files) == 2
        assert Path("tests/unit/subdir/test_foo.py") in test_files
        assert Path("tests/integration/deep/nested/test_bar.py") in test_files

    def test_detects_test_by_filename(self):
        """Files with 'test' in name should be detected."""
        files = [
            Path("src/test_utils.py"),
            Path("lib/testing_helpers.py"),
            Path("app/main.py"),
        ]

        test_files = [
            f for f in files
            if "test" in f.name.lower() or any(p.name == "tests" for p in f.parents)
        ]

        assert len(test_files) == 2
        assert Path("src/test_utils.py") in test_files
        assert Path("lib/testing_helpers.py") in test_files


# =============================================================================
# Async Work Deduplication Tests
# =============================================================================


class TestAsyncWorkDeduper:
    """Verify AsyncWorkDeduper correctly deduplicates concurrent work."""

    @pytest.mark.asyncio
    async def test_concurrent_same_key_executes_once(self):
        """Multiple concurrent calls with same key should execute work only once."""
        call_count = 0

        async def expensive_work():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.05)
            return "result"

        deduper = AsyncWorkDeduper[str]()

        # Fire 10 concurrent requests with same key
        results = await asyncio.gather(*[
            deduper.do("key1", expensive_work) for _ in range(10)
        ])

        assert call_count == 1  # Only one execution
        assert all(r == "result" for r in results)

    @pytest.mark.asyncio
    async def test_different_keys_execute_separately(self):
        """Different keys should execute their work independently."""
        call_counts: dict[str, int] = {}

        async def work_for_key(key: str):
            call_counts[key] = call_counts.get(key, 0) + 1
            await asyncio.sleep(0.01)
            return f"result_{key}"

        deduper = AsyncWorkDeduper[str]()

        # Fire requests for different keys
        results = await asyncio.gather(*[
            deduper.do(f"key{i}", lambda k=f"key{i}": work_for_key(k))
            for i in range(5)
        ])

        assert len(call_counts) == 5
        assert all(count == 1 for count in call_counts.values())

    @pytest.mark.asyncio
    async def test_error_propagates_to_all_waiters(self):
        """If work raises, all waiters should receive the same exception."""
        call_count = 0

        async def failing_work():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.05)
            raise ValueError("test error")

        deduper = AsyncWorkDeduper[str]()

        # Fire 5 concurrent requests
        results = await asyncio.gather(*[
            deduper.do("key1", failing_work) for _ in range(5)
        ], return_exceptions=True)

        assert call_count == 1  # Only one execution
        assert all(isinstance(r, ValueError) for r in results)

    @pytest.mark.asyncio
    async def test_async_safe_cache_size_method(self):
        """get_cache_size() should be async-safe."""
        deduper = AsyncWorkDeduper[str]()

        async def work():
            return "result"

        await deduper.do("key1", work)
        await deduper.do("key2", work)

        size = await deduper.get_cache_size()
        assert size == 2

    @pytest.mark.asyncio
    async def test_async_safe_pending_count_method(self):
        """get_pending_count() should be async-safe."""
        deduper = AsyncWorkDeduper[str]()

        # Initially no pending
        count = await deduper.get_pending_count()
        assert count == 0


class TestSyncWorkDeduper:
    """Verify synchronous WorkDeduper correctly deduplicates work."""

    def test_cached_result_returned(self):
        """Second call with same key should return cached result."""
        call_count = 0

        def work():
            nonlocal call_count
            call_count += 1
            return "result"

        deduper = WorkDeduper[str]()

        result1 = deduper.do("key1", work)
        result2 = deduper.do("key1", work)

        assert call_count == 1
        assert result1 == result2 == "result"

    def test_clear_removes_cache(self):
        """clear() should remove cached results."""
        deduper = WorkDeduper[str]()
        deduper.do("key1", lambda: "result1")
        deduper.do("key2", lambda: "result2")

        assert deduper.cache_size == 2

        deduper.clear("key1")
        assert deduper.cache_size == 1

        deduper.clear()
        assert deduper.cache_size == 0


# =============================================================================
# Deprecation Warning Tests
# =============================================================================


class TestNoDeprecationWarnings:
    """Verify modules don't use deprecated APIs."""

    def test_no_get_event_loop_deprecation(self):
        """Modules should not trigger get_event_loop deprecation warnings."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always", DeprecationWarning)

            # Re-import to trigger any module-level deprecation warnings
            import importlib
            import sunwell.agent.convergence.loop
            import sunwell.planning.naaru.convergence

            importlib.reload(sunwell.agent.convergence.loop)
            importlib.reload(sunwell.planning.naaru.convergence)

            # Filter for get_event_loop warnings
            loop_warnings = [
                x for x in w
                if "get_event_loop" in str(x.message)
            ]

            assert len(loop_warnings) == 0, f"Found deprecation warnings: {loop_warnings}"


# =============================================================================
# GateCheckResult Tests
# =============================================================================


class TestGateCheckResult:
    """Verify GateCheckResult behaves correctly."""

    def test_error_count_property(self):
        """error_count should return number of errors."""
        result = GateCheckResult(
            gate=GateType.LINT,
            passed=False,
            errors=("error1", "error2", "error3"),
            duration_ms=100,
        )
        assert result.error_count == 3

    def test_empty_errors_count(self):
        """error_count should be 0 for passed result."""
        result = GateCheckResult(
            gate=GateType.LINT,
            passed=True,
            errors=(),
            duration_ms=50,
        )
        assert result.error_count == 0

    def test_frozen_dataclass(self):
        """GateCheckResult should be immutable."""
        result = GateCheckResult(
            gate=GateType.LINT,
            passed=True,
            errors=(),
            duration_ms=50,
        )
        with pytest.raises(AttributeError):
            result.passed = False  # type: ignore


# =============================================================================
# ConvergenceIteration Tests
# =============================================================================


class TestConvergenceIteration:
    """Verify ConvergenceIteration behaves correctly."""

    def test_all_passed_true_when_all_gates_pass(self):
        """all_passed should be True when all gates pass."""
        iteration = ConvergenceIteration(
            iteration=1,
            gate_results=(
                GateCheckResult(GateType.LINT, passed=True, errors=(), duration_ms=50),
                GateCheckResult(GateType.TYPE, passed=True, errors=(), duration_ms=100),
            ),
            files_changed=(Path("test.py"),),
            duration_ms=150,
        )
        assert iteration.all_passed is True

    def test_all_passed_false_when_any_gate_fails(self):
        """all_passed should be False when any gate fails."""
        iteration = ConvergenceIteration(
            iteration=1,
            gate_results=(
                GateCheckResult(GateType.LINT, passed=True, errors=(), duration_ms=50),
                GateCheckResult(GateType.TYPE, passed=False, errors=("error",), duration_ms=100),
            ),
            files_changed=(Path("test.py"),),
            duration_ms=150,
        )
        assert iteration.all_passed is False

    def test_total_errors_sums_all_gates(self):
        """total_errors should sum errors across all gates."""
        iteration = ConvergenceIteration(
            iteration=1,
            gate_results=(
                GateCheckResult(GateType.LINT, passed=False, errors=("e1", "e2"), duration_ms=50),
                GateCheckResult(GateType.TYPE, passed=False, errors=("e3",), duration_ms=100),
            ),
            files_changed=(Path("test.py"),),
            duration_ms=150,
        )
        assert iteration.total_errors == 3
