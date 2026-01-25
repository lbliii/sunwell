"""Deterministic evaluation checks (Tier 1).

Fast, reproducible checks:
- must_contain / must_not_contain
- Code execution tests
- Lint and type checks
"""


import re
import subprocess
import tempfile
from pathlib import Path

from sunwell.benchmark.types import BenchmarkTask, DeterministicResult


def evaluate_deterministic(
    task: BenchmarkTask,
    output: str,
    run_code_tests: bool = True,
) -> DeterministicResult:
    """Tier 1: Fast, reproducible checks."""
    output_lower = output.lower()

    # Must-contain checks
    must_contain_results: dict[str, bool] = {}
    for term in task.evaluation.must_contain:
        must_contain_results[term] = term.lower() in output_lower

    # Must-not-contain checks
    must_not_contain_results: dict[str, bool] = {}
    for term in task.evaluation.must_not_contain:
        must_not_contain_results[term] = term.lower() not in output_lower

    # Code execution checks (for code_generation tasks)
    tests_pass = None
    lint_clean = None
    type_check = None

    if task.category.value == "code_generation" and run_code_tests:
        tests_pass, lint_clean, type_check = run_code_checks(
            output=output,
            test_suite=task.test_suite,
        )

    return DeterministicResult(
        must_contain_results=must_contain_results,
        must_not_contain_results=must_not_contain_results,
        tests_pass=tests_pass,
        lint_clean=lint_clean,
        type_check=type_check,
    )


def run_code_checks(
    output: str,
    test_suite: str | None,
) -> tuple[bool | None, bool | None, bool | None]:
    """Run code quality checks on generated code.

    Returns:
        Tuple of (tests_pass, lint_clean, type_check)
    """
    # Extract code blocks from output
    code_blocks = re.findall(r'```(?:python)?\n(.*?)```', output, re.DOTALL)

    if not code_blocks:
        return None, None, None

    code = "\n\n".join(code_blocks)

    tests_pass = None
    lint_clean = None
    type_check = None

    with tempfile.NamedTemporaryFile(
        mode='w',
        suffix='.py',
        delete=False,
    ) as f:
        f.write(code)
        temp_path = Path(f.name)

    try:
        # Lint check with ruff
        try:
            result = subprocess.run(
                ["ruff", "check", str(temp_path), "--quiet"],
                capture_output=True,
                timeout=30,
            )
            lint_clean = result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            lint_clean = None

        # Type check with mypy
        try:
            result = subprocess.run(
                ["mypy", str(temp_path), "--ignore-missing-imports"],
                capture_output=True,
                timeout=60,
            )
            type_check = result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            type_check = None

        # Run tests if test suite provided
        if test_suite:
            try:
                result = subprocess.run(
                    ["python", "-m", "pytest", test_suite, "-v"],
                    capture_output=True,
                    timeout=120,
                )
                tests_pass = result.returncode == 0
            except (FileNotFoundError, subprocess.TimeoutExpired):
                tests_pass = None
    finally:
        temp_path.unlink(missing_ok=True)

    return tests_pass, lint_clean, type_check
