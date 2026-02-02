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


class CodeValidator:
    """Base class for code validators."""

    @property
    def name(self) -> str:
        raise NotImplementedError

    @property
    def description(self) -> str:
        raise NotImplementedError

    async def validate(
        self,
        artifact: Any,
        context: dict[str, Any],
    ) -> ValidationResult:
        raise NotImplementedError

    async def _run_command(
        self,
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


@dataclass(slots=True)
class SyntaxValidator(CodeValidator):
    """Python syntax validation using py_compile."""

    @property
    def name(self) -> str:
        return "syntax"

    @property
    def description(self) -> str:
        return "Check Python syntax is valid"

    async def validate(
        self,
        artifact: Any,
        context: dict[str, Any],
    ) -> ValidationResult:
        """Check syntax of Python files.

        Args:
            artifact: File path or list of file paths
            context: Must contain 'cwd' for working directory

        Returns:
            ValidationResult with syntax errors if any
        """
        import py_compile

        start = time.monotonic()
        cwd = context.get("cwd", Path.cwd())

        # Normalize artifact to list of paths
        if isinstance(artifact, (str, Path)):
            files = [Path(artifact)]
        elif isinstance(artifact, list):
            files = [Path(f) for f in artifact]
        else:
            return ValidationResult(
                passed=False,
                validator_name=self.name,
                message="Invalid artifact type",
            )

        errors: list[dict[str, Any]] = []
        for f in files:
            file_path = cwd / f if not f.is_absolute() else f
            if file_path.suffix != ".py":
                continue

            try:
                py_compile.compile(str(file_path), doraise=True)
            except py_compile.PyCompileError as e:
                errors.append({
                    "file": str(f),
                    "message": str(e),
                })

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
class LintValidator(CodeValidator):
    """Lint validation using ruff."""

    auto_fix: bool = True
    """Whether to auto-fix fixable issues."""

    @property
    def name(self) -> str:
        return "lint"

    @property
    def description(self) -> str:
        return "Check code style with ruff"

    async def validate(
        self,
        artifact: Any,
        context: dict[str, Any],
    ) -> ValidationResult:
        """Run ruff on files.

        Args:
            artifact: File path or list of file paths
            context: Must contain 'cwd' for working directory

        Returns:
            ValidationResult with lint errors if any
        """
        start = time.monotonic()
        cwd = context.get("cwd", Path.cwd())

        # Normalize artifact to list of paths
        if isinstance(artifact, (str, Path)):
            files = [str(artifact)]
        elif isinstance(artifact, list):
            files = [str(f) for f in artifact]
        else:
            return ValidationResult(
                passed=False,
                validator_name=self.name,
                message="Invalid artifact type",
            )

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
                await self._run_command(
                    ["ruff", "check", "--fix", *files],
                    cwd=cwd,
                    timeout=30,
                )
                auto_fixed = True
            except (FileNotFoundError, TimeoutError):
                pass  # Continue with lint check

        # Run lint check
        try:
            result = await self._run_command(
                ["ruff", "check", "--output-format=concise", *files],
                cwd=cwd,
                timeout=30,
            )

            if result.returncode == 0:
                duration = int((time.monotonic() - start) * 1000)
                return ValidationResult(
                    passed=True,
                    validator_name=self.name,
                    message="Lint OK",
                    duration_ms=duration,
                    auto_fixed=auto_fixed,
                )

            # Parse errors from output
            error_lines = [
                line.strip()
                for line in result.stdout.splitlines()
                if line.strip()
            ]
            errors = tuple({"message": line} for line in error_lines)

            duration = int((time.monotonic() - start) * 1000)
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
class TypeValidator(CodeValidator):
    """Type checking using ty or mypy."""

    @property
    def name(self) -> str:
        return "type"

    @property
    def description(self) -> str:
        return "Check types with ty/mypy"

    async def validate(
        self,
        artifact: Any,
        context: dict[str, Any],
    ) -> ValidationResult:
        """Run type checker on files.

        Tries ty first (faster), falls back to mypy.

        Args:
            artifact: File path or list of file paths
            context: Must contain 'cwd' for working directory

        Returns:
            ValidationResult with type errors if any
        """
        start = time.monotonic()
        cwd = context.get("cwd", Path.cwd())

        # Normalize artifact to list of paths
        if isinstance(artifact, (str, Path)):
            files = [str(artifact)]
        elif isinstance(artifact, list):
            files = [str(f) for f in artifact]
        else:
            return ValidationResult(
                passed=False,
                validator_name=self.name,
                message="Invalid artifact type",
            )

        if not files:
            return ValidationResult(
                passed=True,
                validator_name=self.name,
                message="No files to type check",
            )

        # Try ty first (faster)
        try:
            result = await self._run_command(
                ["ty", "check", *files],
                cwd=cwd,
                timeout=60,
            )

            if result.returncode == 0:
                return ValidationResult(
                    passed=True,
                    validator_name=self.name,
                    message="Types OK",
                    duration_ms=int((time.monotonic() - start) * 1000),
                )

            # Parse errors
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
                duration_ms=int((time.monotonic() - start) * 1000),
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
            result = await self._run_command(
                ["mypy", "--no-error-summary", *files],
                cwd=cwd,
                timeout=60,
            )

            if result.returncode == 0:
                return ValidationResult(
                    passed=True,
                    validator_name=self.name,
                    message="Types OK (mypy)",
                    duration_ms=int((time.monotonic() - start) * 1000),
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
                duration_ms=int((time.monotonic() - start) * 1000),
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
class TestValidator(CodeValidator):
    """Test validation using pytest."""

    @property
    def name(self) -> str:
        return "test"

    @property
    def description(self) -> str:
        return "Run tests with pytest"

    async def validate(
        self,
        artifact: Any,
        context: dict[str, Any],
    ) -> ValidationResult:
        """Run pytest on test files.

        Args:
            artifact: File path or list of file paths
            context: Must contain 'cwd' for working directory

        Returns:
            ValidationResult with test failures if any
        """
        start = time.monotonic()
        cwd = context.get("cwd", Path.cwd())

        # Normalize artifact to list of paths
        if isinstance(artifact, (str, Path)):
            files = [Path(artifact)]
        elif isinstance(artifact, list):
            files = [Path(f) for f in artifact]
        else:
            return ValidationResult(
                passed=False,
                validator_name=self.name,
                message="Invalid artifact type",
            )

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
            result = await self._run_command(
                ["pytest", "-q", "--tb=line", *[str(f) for f in test_files]],
                cwd=cwd,
                timeout=120,
            )

            if result.returncode == 0:
                return ValidationResult(
                    passed=True,
                    validator_name=self.name,
                    message="Tests passed",
                    duration_ms=int((time.monotonic() - start) * 1000),
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
                duration_ms=int((time.monotonic() - start) * 1000),
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
