"""Code domain validators (RFC-DOMAINS).

Provides domain-specific validation for code artifacts:
- SyntaxValidator: Python syntax checking
- LintValidator: Ruff linting
- TypeValidator: Type checking (ty/mypy)
- TestValidator: Pytest execution
"""

import asyncio
import logging
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sunwell.domains.protocol import ValidationResult

logger = logging.getLogger(__name__)


async def _run_command(
    cmd: list[str],
    cwd: Path | None = None,
    timeout: int = 60,
) -> subprocess.CompletedProcess[str]:
    """Run a command asynchronously."""
    loop = asyncio.get_running_loop()

    def run() -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout,
        )

    return await asyncio.wait_for(
        loop.run_in_executor(None, run),
        timeout=timeout + 5,
    )


def _normalize_file_paths(
    artifact: Any,
    validator_name: str,
) -> list[Path] | ValidationResult:
    """Normalize artifact to list of paths.

    Returns either a list of Path objects or a ValidationResult error.
    """
    if isinstance(artifact, (str, Path)):
        return [Path(artifact)]
    if isinstance(artifact, list):
        return [Path(f) for f in artifact]
    return ValidationResult(
        passed=False,
        validator_name=validator_name,
        message="Invalid artifact type",
    )


@dataclass(slots=True)
class SyntaxValidator:
    """Python syntax validation using py_compile."""

    name: str = "syntax"
    description: str = "Check Python syntax is valid"

    async def validate(
        self,
        artifact: Any,
        context: dict[str, Any],
    ) -> ValidationResult:
        """Check syntax of Python files."""
        import py_compile

        start = time.monotonic()
        cwd = context.get("cwd", Path.cwd())

        files = _normalize_file_paths(artifact, self.name)
        if isinstance(files, ValidationResult):
            return files

        errors: list[dict[str, Any]] = []
        for f in files:
            file_path = cwd / f if not f.is_absolute() else f
            if file_path.suffix != ".py":
                continue

            try:
                py_compile.compile(str(file_path), doraise=True)
            except py_compile.PyCompileError as e:
                errors.append({"file": str(f), "message": str(e)})

        duration = int((time.monotonic() - start) * 1000)
        passed = len(errors) == 0

        return ValidationResult(
            passed=passed,
            validator_name=self.name,
            message="Syntax OK" if passed else f"{len(errors)} syntax error(s)",
            errors=tuple(errors),
            duration_ms=duration,
        )


@dataclass(slots=True)
class LintValidator:
    """Lint validation using ruff."""

    name: str = "lint"
    description: str = "Check code style with ruff"
    auto_fix: bool = True

    async def validate(
        self,
        artifact: Any,
        context: dict[str, Any],
    ) -> ValidationResult:
        """Run ruff on files."""
        start = time.monotonic()
        cwd = context.get("cwd", Path.cwd())

        paths = _normalize_file_paths(artifact, self.name)
        if isinstance(paths, ValidationResult):
            return paths
        files = [str(f) for f in paths]

        if not files:
            return ValidationResult(
                passed=True,
                validator_name=self.name,
                message="No files to lint",
            )

        # Auto-fix first if enabled
        auto_fixed = False
        if self.auto_fix:
            try:
                await _run_command(["ruff", "check", "--fix", *files], cwd=cwd, timeout=30)
                auto_fixed = True
            except (FileNotFoundError, TimeoutError):
                pass  # Continue with lint check

        # Run lint check
        try:
            result = await _run_command(
                ["ruff", "check", "--output-format=concise", *files],
                cwd=cwd,
                timeout=30,
            )

            duration = int((time.monotonic() - start) * 1000)
            if result.returncode == 0:
                return ValidationResult(
                    passed=True,
                    validator_name=self.name,
                    message="Lint OK",
                    duration_ms=duration,
                    auto_fixed=auto_fixed,
                )

            error_lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            errors = tuple({"message": line} for line in error_lines)

            return ValidationResult(
                passed=False,
                validator_name=self.name,
                message=f"{len(errors)} lint error(s)",
                errors=errors,
                duration_ms=duration,
                auto_fixed=auto_fixed,
            )

        except FileNotFoundError:
            logger.warning("ruff not installed, skipping lint check")
            return ValidationResult(
                passed=True,
                validator_name=self.name,
                message="ruff not installed (skipped)",
                duration_ms=int((time.monotonic() - start) * 1000),
            )
        except TimeoutError:
            return ValidationResult(
                passed=False,
                validator_name=self.name,
                message="Lint check timed out",
                duration_ms=int((time.monotonic() - start) * 1000),
            )


@dataclass(slots=True)
class TypeValidator:
    """Type checking using ty or mypy."""

    name: str = "type"
    description: str = "Check types with ty/mypy"

    async def validate(
        self,
        artifact: Any,
        context: dict[str, Any],
    ) -> ValidationResult:
        """Run type checker on files. Tries ty first, falls back to mypy."""
        start = time.monotonic()
        cwd = context.get("cwd", Path.cwd())

        paths = _normalize_file_paths(artifact, self.name)
        if isinstance(paths, ValidationResult):
            return paths
        files = [str(f) for f in paths]

        if not files:
            return ValidationResult(
                passed=True,
                validator_name=self.name,
                message="No files to type check",
            )

        # Try ty first (faster)
        try:
            result = await _run_command(["ty", "check", *files], cwd=cwd, timeout=60)
            duration = int((time.monotonic() - start) * 1000)

            if result.returncode == 0:
                return ValidationResult(
                    passed=True,
                    validator_name=self.name,
                    message="Types OK",
                    duration_ms=duration,
                )

            error_lines = [
                line.strip()
                for line in result.stdout.splitlines()
                if line.strip() and "error" in line.lower()
            ]
            errors = tuple({"message": line} for line in error_lines)

            return ValidationResult(
                passed=False,
                validator_name=self.name,
                message=f"{len(errors)} type error(s)",
                errors=errors,
                duration_ms=duration,
            )

        except FileNotFoundError:
            pass  # ty not installed, try mypy
        except TimeoutError:
            return ValidationResult(
                passed=False,
                validator_name=self.name,
                message="Type check timed out",
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        # Fall back to mypy
        try:
            result = await _run_command(["mypy", "--no-error-summary", *files], cwd=cwd, timeout=60)
            duration = int((time.monotonic() - start) * 1000)

            if result.returncode == 0:
                return ValidationResult(
                    passed=True,
                    validator_name=self.name,
                    message="Types OK (mypy)",
                    duration_ms=duration,
                )

            error_lines = [
                line.strip()
                for line in result.stdout.splitlines()
                if line.strip() and "error" in line.lower()
            ]
            errors = tuple({"message": line} for line in error_lines)

            return ValidationResult(
                passed=False,
                validator_name=self.name,
                message=f"{len(errors)} type error(s)",
                errors=errors,
                duration_ms=duration,
            )

        except FileNotFoundError:
            logger.warning("Neither ty nor mypy installed, skipping type check")
            return ValidationResult(
                passed=True,
                validator_name=self.name,
                message="No type checker installed (skipped)",
                duration_ms=int((time.monotonic() - start) * 1000),
            )
        except TimeoutError:
            return ValidationResult(
                passed=False,
                validator_name=self.name,
                message="Type check timed out",
                duration_ms=int((time.monotonic() - start) * 1000),
            )


@dataclass(slots=True)
class TestValidator:
    """Test validation using pytest."""

    name: str = "test"
    description: str = "Run tests with pytest"

    async def validate(
        self,
        artifact: Any,
        context: dict[str, Any],
    ) -> ValidationResult:
        """Run pytest on test files."""
        start = time.monotonic()
        cwd = context.get("cwd", Path.cwd())

        files = _normalize_file_paths(artifact, self.name)
        if isinstance(files, ValidationResult):
            return files

        # Filter to test files only
        test_files = [
            f for f in files
            if "test" in f.name.lower() or any(p.name == "tests" for p in f.parents)
        ]

        if not test_files:
            return ValidationResult(
                passed=True,
                validator_name=self.name,
                message="No test files to run",
            )

        try:
            result = await _run_command(
                ["pytest", "-q", "--tb=line", *[str(f) for f in test_files]],
                cwd=cwd,
                timeout=120,
            )
            duration = int((time.monotonic() - start) * 1000)

            if result.returncode == 0:
                return ValidationResult(
                    passed=True,
                    validator_name=self.name,
                    message="Tests passed",
                    duration_ms=duration,
                )

            error_lines = [
                line.strip()
                for line in result.stdout.splitlines()
                if "FAILED" in line or "ERROR" in line
            ]
            errors = tuple({"message": line} for line in error_lines)

            return ValidationResult(
                passed=False,
                validator_name=self.name,
                message=f"{len(errors)} test failure(s)",
                errors=errors,
                duration_ms=duration,
            )

        except FileNotFoundError:
            logger.warning("pytest not installed, skipping test check")
            return ValidationResult(
                passed=True,
                validator_name=self.name,
                message="pytest not installed (skipped)",
                duration_ms=int((time.monotonic() - start) * 1000),
            )
        except TimeoutError:
            return ValidationResult(
                passed=False,
                validator_name=self.name,
                message="Tests timed out",
                duration_ms=int((time.monotonic() - start) * 1000),
            )
