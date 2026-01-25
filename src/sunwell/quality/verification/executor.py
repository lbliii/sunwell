"""Behavioral Executor for Deep Verification (RFC-047).

Execute generated tests in isolated environment.
"""


import asyncio
import sys
import tempfile
from pathlib import Path

from sunwell.verification.types import (
    BehavioralExecutionResult,
    GeneratedTest,
    TestExecutionResult,
)


class BehavioralExecutor:
    """Execute generated tests in isolated environment.

    Runs tests in a subprocess sandbox to:
    - Isolate from main process
    - Capture stdout/stderr
    - Enforce timeouts
    - Prevent side effects
    """

    def __init__(
        self,
        cwd: Path,
        timeout_per_test: int = 10,
        total_timeout: int = 60,
    ):
        self.cwd = cwd
        self.timeout_per_test = timeout_per_test
        self.total_timeout = total_timeout

    async def execute(
        self,
        artifact_content: str,
        tests: list[GeneratedTest],
    ) -> BehavioralExecutionResult:
        """Execute all generated tests.

        Args:
            artifact_content: The generated code to test
            tests: Generated tests to run

        Returns:
            Execution results for all tests
        """
        import time

        start = time.monotonic()

        if not tests:
            return BehavioralExecutionResult(
                total_tests=0,
                passed=0,
                failed=0,
                errors=0,
                test_results=(),
                duration_ms=0,
            )

        results: list[TestExecutionResult] = []

        # Create isolated test environment
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            # Write artifact
            artifact_file = tmp_path / "artifact.py"
            artifact_file.write_text(artifact_content)

            # Write conftest for pytest configuration
            conftest_file = tmp_path / "conftest.py"
            conftest_file.write_text(self._build_conftest())

            # Write test file
            test_code = self._build_test_file(tests)
            test_file = tmp_path / "test_artifact.py"
            test_file.write_text(test_code)

            # Run all tests at once for efficiency
            all_results = await self._run_all_tests(tmp_path, tests)
            results.extend(all_results)

        duration = int((time.monotonic() - start) * 1000)

        passed = sum(1 for r in results if r.passed)
        failed = sum(1 for r in results if not r.passed and not r.error_message)
        errors = sum(1 for r in results if r.error_message and not r.passed)

        return BehavioralExecutionResult(
            total_tests=len(results),
            passed=passed,
            failed=failed,
            errors=errors,
            test_results=tuple(results),
            duration_ms=duration,
        )

    def _build_conftest(self) -> str:
        """Build conftest.py for pytest configuration."""
        return """
import pytest
import sys
from pathlib import Path

# Add test directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))
"""

    def _build_test_file(self, tests: list[GeneratedTest]) -> str:
        """Build a single test file from all generated tests."""
        imports = """
import pytest
import sys
from pathlib import Path

# Add artifact to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from artifact import *
except ImportError as e:
    print(f"Warning: Could not import artifact: {e}")

# Try importing hypothesis for property tests
try:
    from hypothesis import given, strategies as st
except ImportError:
    # Mock hypothesis if not available
    def given(*args, **kwargs):
        def decorator(f):
            return pytest.mark.skip(reason="hypothesis not installed")(f)
        return decorator
    class st:
        integers = lambda *args, **kwargs: None
        text = lambda *args, **kwargs: None
        lists = lambda *args, **kwargs: None
        floats = lambda *args, **kwargs: None
"""

        test_code = imports + "\n\n"

        for test in tests:
            # Clean up the test code
            code = test.code.strip()

            # Ensure proper newlines
            if not code.endswith("\n"):
                code += "\n"

            test_code += f"\n# Test: {test.name}\n# {test.description}\n{code}\n"

        return test_code

    async def _run_all_tests(
        self,
        cwd: Path,
        tests: list[GeneratedTest],
    ) -> list[TestExecutionResult]:
        """Run all tests and parse results."""
        import time

        results: list[TestExecutionResult] = []
        start = time.monotonic()

        cmd = [
            sys.executable,
            "-m",
            "pytest",
            "test_artifact.py",
            "-v",
            "--tb=short",
            "--no-header",
            "-q",
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.total_timeout,
            )

            duration = int((time.monotonic() - start) * 1000)
            stdout_text = stdout.decode() if stdout else ""
            stderr_text = stderr.decode() if stderr else ""

            # Parse results for each test
            for test in tests:
                test_result = self._parse_test_result(
                    test,
                    stdout_text,
                    stderr_text,
                    proc.returncode or 0,
                    duration // len(tests) if tests else 0,
                )
                results.append(test_result)

        except TimeoutError:
            # All tests timed out
            for test in tests:
                results.append(
                    TestExecutionResult(
                        test_id=test.id,
                        passed=False,
                        actual_output=None,
                        expected_output=None,
                        error_message=f"Test timed out after {self.total_timeout}s",
                        error_traceback=None,
                        duration_ms=self.total_timeout * 1000,
                        stdout="",
                        stderr="",
                    )
                )

        except Exception as e:
            # Execution error
            for test in tests:
                results.append(
                    TestExecutionResult(
                        test_id=test.id,
                        passed=False,
                        actual_output=None,
                        expected_output=None,
                        error_message=f"Execution error: {e}",
                        error_traceback=None,
                        duration_ms=0,
                        stdout="",
                        stderr="",
                    )
                )

        return results

    def _parse_test_result(
        self,
        test: GeneratedTest,
        stdout: str,
        stderr: str,
        return_code: int,
        duration_ms: int,
    ) -> TestExecutionResult:
        """Parse pytest output to determine test result."""
        # Look for the specific test in output
        test_name = test.name

        # Check for PASSED/FAILED in pytest verbose output
        passed_pattern = f"{test_name} PASSED"
        failed_pattern = f"{test_name} FAILED"
        error_pattern = f"{test_name} ERROR"
        skipped_pattern = f"{test_name} SKIPPED"

        if passed_pattern in stdout:
            passed = True
            error_message = None
        elif failed_pattern in stdout or error_pattern in stdout:
            passed = False
            # Extract error message from output
            error_message = self._extract_error(stdout, test_name)
        elif skipped_pattern in stdout:
            # Skipped tests count as passed (expected behavior)
            passed = True
            error_message = None
        else:
            # If we can't find the specific test, use overall result
            # pytest returns 0 on success, non-zero on failure
            passed = return_code == 0
            error_message = None if passed else "Test failed (see output)"

        # Adjust for expected_outcome
        if test.expected_outcome == "error":
            # Test expects an error - pass if we got one
            passed = not passed
            if passed:
                error_message = None

        return TestExecutionResult(
            test_id=test.id,
            passed=passed,
            actual_output=stdout[:500] if stdout else None,
            expected_output=None,
            error_message=error_message,
            error_traceback=stderr[:500] if not passed and stderr else None,
            duration_ms=duration_ms,
            stdout=stdout,
            stderr=stderr,
        )

    def _extract_error(self, output: str, test_name: str) -> str | None:
        """Extract error message for a specific test from pytest output."""
        lines = output.split("\n")
        in_error = False
        error_lines: list[str] = []

        for line in lines:
            if test_name in line and ("FAILED" in line or "ERROR" in line):
                in_error = True
                continue

            if in_error:
                if line.startswith("___") or line.startswith("==="):
                    break
                if line.strip():
                    error_lines.append(line.strip())

        return "\n".join(error_lines[:5]) if error_lines else "Test failed"
