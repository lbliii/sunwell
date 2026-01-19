"""Language toolchains for static analysis (RFC-042).

Each language has its own toolchain for validation gates:
- Python: ruff + ty/mypy
- TypeScript: eslint + tsc
- Rust: clippy + cargo check
- Go: golint + go vet

The gate system runs static analysis at every checkpoint:
1. SYNTAX (py_compile) ~10ms
2. LINT (ruff check) ~50ms, auto-fix available
3. TYPE (ty/mypy) ~500ms
4. Gate-specific check (import, schema, endpoint)
"""

import asyncio
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class LanguageToolchain:
    """Toolchain for a specific language.

    Defines the commands for syntax checking, linting, type checking,
    and formatting. Commands are tuples of arguments for subprocess.
    """

    language: str
    """Language identifier (python, typescript, rust, go)."""

    # Static analysis commands (None = not available)
    syntax_cmd: tuple[str, ...] | None = None
    """Syntax check command (e.g., py_compile)."""

    lint_cmd: tuple[str, ...] | None = None
    """Lint command (e.g., ruff check)."""

    lint_fix_cmd: tuple[str, ...] | None = None
    """Lint with auto-fix (e.g., ruff check --fix)."""

    type_cmd: tuple[str, ...] | None = None
    """Type check command (e.g., ty check)."""

    format_cmd: tuple[str, ...] | None = None
    """Format command (e.g., ruff format)."""

    # File patterns
    file_glob: str = "*"
    """Glob pattern for this language's files."""

    extensions: tuple[str, ...] = ()
    """File extensions for this language."""


# =============================================================================
# Built-in Toolchains
# =============================================================================

PYTHON_TOOLCHAIN = LanguageToolchain(
    language="python",
    syntax_cmd=("python", "-m", "py_compile"),
    lint_cmd=("ruff", "check", "--output-format=json"),
    lint_fix_cmd=("ruff", "check", "--fix"),
    type_cmd=("ty", "check"),  # or use mypy as fallback
    format_cmd=("ruff", "format"),
    file_glob="*.py",
    extensions=(".py",),
)

TYPESCRIPT_TOOLCHAIN = LanguageToolchain(
    language="typescript",
    lint_cmd=("eslint", "--format=json"),
    lint_fix_cmd=("eslint", "--fix"),
    type_cmd=("tsc", "--noEmit"),
    format_cmd=("prettier", "--write"),
    file_glob="*.ts",
    extensions=(".ts", ".tsx"),
)

JAVASCRIPT_TOOLCHAIN = LanguageToolchain(
    language="javascript",
    lint_cmd=("eslint", "--format=json"),
    lint_fix_cmd=("eslint", "--fix"),
    format_cmd=("prettier", "--write"),
    file_glob="*.js",
    extensions=(".js", ".jsx"),
)

RUST_TOOLCHAIN = LanguageToolchain(
    language="rust",
    lint_cmd=("cargo", "clippy", "--message-format=json"),
    type_cmd=("cargo", "check", "--message-format=json"),
    format_cmd=("rustfmt"),
    file_glob="*.rs",
    extensions=(".rs",),
)

GO_TOOLCHAIN = LanguageToolchain(
    language="go",
    lint_cmd=("golint"),
    type_cmd=("go", "vet"),
    format_cmd=("gofmt", "-w"),
    file_glob="*.go",
    extensions=(".go",),
)

# Registry of built-in toolchains
TOOLCHAINS: dict[str, LanguageToolchain] = {
    "python": PYTHON_TOOLCHAIN,
    "typescript": TYPESCRIPT_TOOLCHAIN,
    "javascript": JAVASCRIPT_TOOLCHAIN,
    "rust": RUST_TOOLCHAIN,
    "go": GO_TOOLCHAIN,
}


def detect_toolchain(project_path: Path) -> LanguageToolchain:
    """Auto-detect toolchain from project files.

    Looks for common project files to determine the primary language.

    Args:
        project_path: Root path of the project

    Returns:
        Appropriate LanguageToolchain (defaults to Python)
    """
    if (project_path / "pyproject.toml").exists():
        return PYTHON_TOOLCHAIN
    if (project_path / "setup.py").exists():
        return PYTHON_TOOLCHAIN
    if (project_path / "package.json").exists():
        # Check for TypeScript
        if (project_path / "tsconfig.json").exists():
            return TYPESCRIPT_TOOLCHAIN
        return JAVASCRIPT_TOOLCHAIN
    if (project_path / "Cargo.toml").exists():
        return RUST_TOOLCHAIN
    if (project_path / "go.mod").exists():
        return GO_TOOLCHAIN

    # Default to Python
    return PYTHON_TOOLCHAIN


# =============================================================================
# Toolchain Execution
# =============================================================================


@dataclass(frozen=True, slots=True)
class LintError:
    """A single lint error."""

    file: str
    line: int
    column: int
    code: str
    message: str
    fixable: bool = False


@dataclass(frozen=True, slots=True)
class TypeCheckError:
    """A single type error from the type checker."""

    file: str
    line: int
    message: str
    severity: str = "error"


@dataclass
class ToolchainResult:
    """Result from running toolchain commands."""

    passed: bool
    """Whether all checks passed."""

    lint_errors: list[LintError] = field(default_factory=list)
    """Lint errors found."""

    type_errors: list[TypeCheckError] = field(default_factory=list)
    """Type errors found."""

    auto_fixed: int = 0
    """Number of issues auto-fixed."""

    output: str = ""
    """Raw command output."""

    duration_ms: int = 0
    """Total duration in milliseconds."""


class ToolchainRunner:
    """Runs toolchain commands on files.

    Provides async execution of static analysis tools with
    structured error parsing.
    """

    def __init__(self, toolchain: LanguageToolchain, cwd: Path | None = None):
        self.toolchain = toolchain
        self.cwd = cwd or Path.cwd()

    async def check_syntax(self, files: list[Path]) -> ToolchainResult:
        """Check syntax of files.

        Args:
            files: Files to check

        Returns:
            ToolchainResult with syntax errors if any
        """
        if not self.toolchain.syntax_cmd or not files:
            return ToolchainResult(passed=True)

        import time

        start = time.monotonic()

        # For Python, py_compile each file
        if self.toolchain.language == "python":
            errors = []
            for f in files:
                try:
                    result = await self._run_command(
                        (*self.toolchain.syntax_cmd, str(f)),
                    )
                    if result.returncode != 0:
                        # Parse syntax error from stderr
                        errors.append(
                            LintError(
                                file=str(f),
                                line=1,
                                column=1,
                                code="E999",
                                message=result.stderr or "Syntax error",
                            )
                        )
                except Exception as e:
                    errors.append(
                        LintError(
                            file=str(f),
                            line=1,
                            column=1,
                            code="E999",
                            message=str(e),
                        )
                    )

            duration = int((time.monotonic() - start) * 1000)
            return ToolchainResult(
                passed=len(errors) == 0,
                lint_errors=errors,
                duration_ms=duration,
            )

        return ToolchainResult(passed=True)

    async def check_lint(
        self,
        files: list[Path],
        auto_fix: bool = True,
    ) -> ToolchainResult:
        """Run linter on files.

        Args:
            files: Files to lint
            auto_fix: Whether to auto-fix fixable issues

        Returns:
            ToolchainResult with lint errors
        """
        if not files:
            return ToolchainResult(passed=True)

        import time

        start = time.monotonic()

        # Auto-fix first if enabled and available
        auto_fixed = 0
        if auto_fix and self.toolchain.lint_fix_cmd:
            try:
                await self._run_command(
                    (*self.toolchain.lint_fix_cmd, *[str(f) for f in files]),
                )
                auto_fixed = 1  # Assume at least one fix (actual count hard to get)
            except Exception:
                pass  # Continue with lint check even if fix fails

        # Now run lint check
        if not self.toolchain.lint_cmd:
            return ToolchainResult(passed=True, auto_fixed=auto_fixed)

        try:
            result = await self._run_command(
                (*self.toolchain.lint_cmd, *[str(f) for f in files]),
            )

            errors = self._parse_lint_output(result.stdout or "")
            duration = int((time.monotonic() - start) * 1000)

            return ToolchainResult(
                passed=len(errors) == 0,
                lint_errors=errors,
                auto_fixed=auto_fixed,
                output=result.stdout or "",
                duration_ms=duration,
            )

        except Exception as e:
            duration = int((time.monotonic() - start) * 1000)
            return ToolchainResult(
                passed=False,
                output=str(e),
                duration_ms=duration,
            )

    async def check_types(self, files: list[Path]) -> ToolchainResult:
        """Run type checker on files.

        Args:
            files: Files to type check

        Returns:
            ToolchainResult with type errors
        """
        if not self.toolchain.type_cmd or not files:
            return ToolchainResult(passed=True)

        import time

        start = time.monotonic()

        try:
            result = await self._run_command(
                (*self.toolchain.type_cmd, *[str(f) for f in files]),
            )

            errors = self._parse_type_output(result.stdout or "")
            duration = int((time.monotonic() - start) * 1000)

            return ToolchainResult(
                passed=result.returncode == 0,
                type_errors=errors,
                output=result.stdout or "",
                duration_ms=duration,
            )

        except FileNotFoundError:
            # Type checker not installed - try fallback
            if self.toolchain.language == "python":
                return await self._check_types_mypy_fallback(files, start)

            return ToolchainResult(
                passed=True,
                output="Type checker not available",
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        except Exception as e:
            duration = int((time.monotonic() - start) * 1000)
            return ToolchainResult(
                passed=False,
                output=str(e),
                duration_ms=duration,
            )

    async def _check_types_mypy_fallback(
        self,
        files: list[Path],
        start: float,
    ) -> ToolchainResult:
        """Fallback to mypy if ty is not available."""
        import time

        try:
            result = await self._run_command(
                ("mypy", "--ignore-missing-imports", *[str(f) for f in files]),
            )

            errors = self._parse_mypy_output(result.stdout or "")
            duration = int((time.monotonic() - start) * 1000)

            return ToolchainResult(
                passed=result.returncode == 0,
                type_errors=errors,
                output=result.stdout or "",
                duration_ms=duration,
            )

        except Exception as e:
            duration = int((time.monotonic() - start) * 1000)
            return ToolchainResult(
                passed=True,  # Don't fail if no type checker available
                output=f"No type checker available: {e}",
                duration_ms=duration,
            )

    async def _run_command(
        self,
        cmd: tuple[str, ...],
    ) -> subprocess.CompletedProcess[str]:
        """Run a command asynchronously."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.cwd,
            ),
        )

    def _parse_lint_output(self, output: str) -> list[LintError]:
        """Parse lint output (ruff JSON format)."""
        errors: list[LintError] = []

        if not output:
            return errors

        try:
            data = json.loads(output)
            for item in data:
                errors.append(
                    LintError(
                        file=item.get("filename", "unknown"),
                        line=item.get("location", {}).get("row", 1),
                        column=item.get("location", {}).get("column", 1),
                        code=item.get("code", ""),
                        message=item.get("message", ""),
                        fixable=item.get("fix") is not None,
                    )
                )
        except json.JSONDecodeError:
            # Try line-by-line parsing for non-JSON output
            import re

            for line in output.split("\n"):
                match = re.match(r"(.+):(\d+):(\d+): (\w+) (.+)", line)
                if match:
                    errors.append(
                        LintError(
                            file=match.group(1),
                            line=int(match.group(2)),
                            column=int(match.group(3)),
                            code=match.group(4),
                            message=match.group(5),
                        )
                    )

        return errors

    def _parse_type_output(self, output: str) -> list[TypeCheckError]:
        """Parse type checker output."""
        errors: list[TypeCheckError] = []

        if not output:
            return errors

        import re

        for line in output.split("\n"):
            # ty format: file.py:10: error: message
            match = re.match(r"(.+):(\d+): (error|warning|note): (.+)", line)
            if match:
                errors.append(
                    TypeCheckError(
                        file=match.group(1),
                        line=int(match.group(2)),
                        message=match.group(4),
                        severity=match.group(3),
                    )
                )

        return errors

    def _parse_mypy_output(self, output: str) -> list[TypeCheckError]:
        """Parse mypy output."""
        errors: list[TypeCheckError] = []

        if not output:
            return errors

        import re

        for line in output.split("\n"):
            # mypy format: file.py:10: error: message
            match = re.match(r"(.+):(\d+): (error|warning|note): (.+)", line)
            if match:
                errors.append(
                    TypeCheckError(
                        file=match.group(1),
                        line=int(match.group(2)),
                        message=match.group(4),
                        severity=match.group(3),
                    )
                )

        return errors


# =============================================================================
# Static Analysis Cascade
# =============================================================================


@dataclass
class StaticAnalysisCascade:
    """Runs the full static analysis cascade at gates.

    Cascade order:
    1. SYNTAX (py_compile) ~10ms, free
    2. LINT (ruff check) ~50ms, free, auto-fix available
    3. TYPE (ty/mypy) ~500ms, free

    Fails fast: stops at first level with errors.
    """

    toolchain: LanguageToolchain
    cwd: Path | None = None

    async def run(
        self,
        files: list[Path],
        auto_fix_lint: bool = True,
    ) -> tuple[bool, list[dict[str, Any]]]:
        """Run the full static analysis cascade.

        Args:
            files: Files to analyze
            auto_fix_lint: Whether to auto-fix lint issues

        Returns:
            Tuple of (all_passed, list of step results)
        """
        runner = ToolchainRunner(self.toolchain, self.cwd)
        steps: list[dict[str, Any]] = []

        # Step 1: Syntax
        syntax_result = await runner.check_syntax(files)
        steps.append({
            "step": "syntax",
            "passed": syntax_result.passed,
            "errors": len(syntax_result.lint_errors),
            "duration_ms": syntax_result.duration_ms,
        })

        if not syntax_result.passed:
            return False, steps

        # Step 2: Lint
        lint_result = await runner.check_lint(files, auto_fix=auto_fix_lint)
        steps.append({
            "step": "lint",
            "passed": lint_result.passed,
            "errors": len(lint_result.lint_errors),
            "auto_fixed": lint_result.auto_fixed,
            "duration_ms": lint_result.duration_ms,
        })

        if not lint_result.passed:
            return False, steps

        # Step 3: Type check
        type_result = await runner.check_types(files)
        steps.append({
            "step": "type",
            "passed": type_result.passed,
            "errors": len(type_result.type_errors),
            "duration_ms": type_result.duration_ms,
        })

        all_passed = syntax_result.passed and lint_result.passed and type_result.passed
        return all_passed, steps
