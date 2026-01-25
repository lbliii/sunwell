"""Signal Extraction for Autonomous Backlog (RFC-046 Phase 1).

Extract observable signals from codebase without LLM:
- Failing tests
- TODO/FIXME comments
- Type errors
- Lint warnings
- Missing test coverage
- Stale dependencies
"""


import asyncio
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from sunwell.knowledge.codebase.codebase import CodeLocation

# Pre-compiled regex patterns for performance
_PYTEST_FAILURE_PATTERN = re.compile(r"FAILED\s+([^:]+)::([^\s]+)")
_TODO_PATTERN = re.compile(r"(TODO|FIXME|XXX|HACK|NOTE):\s*(.+)", re.IGNORECASE)
_MYPY_ERROR_PATTERN = re.compile(r"([^:]+):(\d+):\s+error:\s+(.+)")
_RUFF_WARNING_PATTERN = re.compile(r"([^:]+):(\d+):(\d+):\s+([A-Z]\d+)\s+(.+)")
_COVERAGE_PATTERN = re.compile(r"([^\s]+)\s+\d+\s+(\d+)")


@dataclass(frozen=True, slots=True)
class ObservableSignal:
    """A signal extracted from code without LLM."""

    signal_type: Literal[
        "failing_test",
        "todo_comment",
        "fixme_comment",
        "type_error",
        "lint_warning",
        "missing_test",
        "stale_dependency",
        "large_file",
        "high_complexity",
        "missing_docstring",
        "dead_code",
    ]
    location: CodeLocation
    severity: Literal["critical", "high", "medium", "low"]
    message: str
    auto_fixable: bool
    """Can this be fixed without human decision-making?"""


class SignalExtractor:
    """Extract observable signals from codebase."""

    def __init__(self, root: Path | None = None):
        """Initialize signal extractor.

        Args:
            root: Project root directory (defaults to cwd)
        """
        self.root = Path(root) if root else Path.cwd()

    async def extract_all(self) -> list[ObservableSignal]:
        """Run all extractors and deduplicate.

        Returns:
            List of unique signals
        """
        signals: list[ObservableSignal] = []
        signals.extend(await self._extract_test_failures())
        signals.extend(await self._extract_todos())
        signals.extend(await self._extract_type_errors())
        signals.extend(await self._extract_lint_warnings())
        signals.extend(await self._extract_coverage_gaps())
        signals.extend(await self._extract_stale_deps())
        return self._deduplicate(signals)

    async def _extract_test_failures(self) -> list[ObservableSignal]:
        """Run pytest --collect-only, then pytest on collected."""
        signals: list[ObservableSignal] = []

        try:
            # First collect tests
            result = await self._run_subprocess(
                ["pytest", "--collect-only", "-q"],
                timeout=30,
            )

            if result.returncode != 0:
                # Collection failed - might be syntax errors
                return []

            # Run tests
            test_result = await self._run_subprocess(
                ["pytest", "-v", "--tb=no"],
                timeout=60,
            )

            if test_result.returncode == 0:
                return []

            # Parse pytest output for failures
            output = test_result.stdout + test_result.stderr
            for line in output.splitlines():
                # Match pytest failure format: "FAILED test_file.py::test_func"
                match = _PYTEST_FAILURE_PATTERN.search(line)
                if match:
                    file_path = match.group(1)
                    test_name = match.group(2)
                    full_path = self.root / file_path

                    if full_path.exists():
                        signals.append(
                            ObservableSignal(
                                signal_type="failing_test",
                                location=CodeLocation(
                                    file=full_path,
                                    line_start=1,
                                    line_end=1,
                                    symbol=test_name,
                                ),
                                severity="high",
                                message=f"Failing test: {test_name}",
                                auto_fixable=True,
                            )
                        )

        except (subprocess.TimeoutExpired, FileNotFoundError):
            # pytest not available or timeout
            pass

        return signals

    async def _extract_todos(self) -> list[ObservableSignal]:
        """Grep for TODO, FIXME, XXX, HACK comments."""
        signals: list[ObservableSignal] = []

        # Find all Python files
        python_files = list(self.root.rglob("*.py"))
        # Exclude common ignore patterns
        ignore_dirs = {".git", "__pycache__", ".venv", "venv", "node_modules", ".sunwell"}
        python_files = [
            f for f in python_files
            if not any(part in ignore_dirs for part in f.parts)
        ]

        for file_path in python_files:
            try:
                content = file_path.read_text(encoding="utf-8")
                for line_num, line in enumerate(content.splitlines(), start=1):
                    match = _TODO_PATTERN.search(line)
                    if match:
                        todo_type = match.group(1).upper()
                        message = match.group(2).strip()

                        signal_type: Literal["todo_comment", "fixme_comment"]
                        if todo_type == "FIXME":
                            signal_type = "fixme_comment"
                        else:
                            signal_type = "todo_comment"

                        severity: Literal["critical", "high", "medium", "low"]
                        if todo_type == "FIXME":
                            severity = "high"
                        elif todo_type == "HACK":
                            severity = "medium"
                        else:
                            severity = "low"

                        signals.append(
                            ObservableSignal(
                                signal_type=signal_type,
                                location=CodeLocation(
                                    file=file_path.relative_to(self.root),
                                    line_start=line_num,
                                    line_end=line_num,
                                ),
                                severity=severity,
                                message=message,
                                auto_fixable=False,  # TODOs need human judgment
                            )
                        )
            except (UnicodeDecodeError, PermissionError):
                continue

        return signals

    async def _extract_type_errors(self) -> list[ObservableSignal]:
        """Run mypy/pyright and parse output."""
        signals: list[ObservableSignal] = []

        # Try mypy first
        try:
            result = await self._run_subprocess(
                ["mypy", ".", "--no-error-summary"],
                timeout=60,
            )

            if result.returncode == 0:
                return []

            # Parse mypy output
            for line in result.stdout.splitlines():
                # Format: "file.py:line: error: message"
                match = _MYPY_ERROR_PATTERN.search(line)
                if match:
                    file_path = Path(match.group(1))
                    line_num = int(match.group(2))
                    message = match.group(3).strip()

                    if file_path.is_absolute():
                        file_path = file_path.relative_to(self.root)

                    signals.append(
                        ObservableSignal(
                            signal_type="type_error",
                            location=CodeLocation(
                                file=file_path,
                                line_start=line_num,
                                line_end=line_num,
                            ),
                            severity="high",
                            message=message,
                            auto_fixable=False,  # Type errors need careful fixing
                        )
                    )

        except (subprocess.TimeoutExpired, FileNotFoundError):
            # mypy not available
            pass

        return signals

    async def _extract_lint_warnings(self) -> list[ObservableSignal]:
        """Run ruff check and parse output."""
        signals: list[ObservableSignal] = []

        try:
            result = await self._run_subprocess(
                ["ruff", "check", "--output-format=text"],
                timeout=60,
            )

            if result.returncode == 0:
                return []

            # Parse ruff output
            for line in result.stdout.splitlines():
                # Format: "file.py:line:col: code message"
                match = _RUFF_WARNING_PATTERN.search(line)
                if match:
                    file_path = Path(match.group(1))
                    line_num = int(match.group(2))
                    code = match.group(4)
                    message = match.group(5).strip()

                    if file_path.is_absolute():
                        file_path = file_path.relative_to(self.root)

                    # Auto-fixable if ruff can fix it
                    auto_fixable = code in {
                        "E",  # pycodestyle errors
                        "W",  # pycodestyle warnings
                        "F",  # pyflakes
                        "I",  # isort
                    }

                    signals.append(
                        ObservableSignal(
                            signal_type="lint_warning",
                            location=CodeLocation(
                                file=file_path,
                                line_start=line_num,
                                line_end=line_num,
                            ),
                            severity="medium",
                            message=f"{code}: {message}",
                            auto_fixable=auto_fixable,
                        )
                    )

        except (subprocess.TimeoutExpired, FileNotFoundError):
            # ruff not available
            pass

        return signals

    async def _extract_coverage_gaps(self) -> list[ObservableSignal]:
        """Run coverage and find uncovered critical paths."""
        signals: list[ObservableSignal] = []

        try:
            # Run coverage
            result = await self._run_subprocess(
                ["coverage", "run", "-m", "pytest"],
                timeout=120,
            )

            if result.returncode != 0:
                return []

            # Generate report
            report_result = await self._run_subprocess(
                ["coverage", "report", "--format=text"],
                timeout=30,
            )

            if report_result.returncode != 0:
                return []

            # Parse coverage report
            # Format: "file.py     line  missing"
            for line in report_result.stdout.splitlines():
                match = _COVERAGE_PATTERN.search(line)
                if match:
                    file_path = Path(match.group(1))
                    missing_lines = int(match.group(2))

                    if missing_lines > 0 and file_path.suffix == ".py":
                        if file_path.is_absolute():
                            file_path = file_path.relative_to(self.root)

                        signals.append(
                            ObservableSignal(
                                signal_type="missing_test",
                                location=CodeLocation(
                                    file=file_path,
                                    line_start=1,
                                    line_end=1,
                                ),
                                severity="medium",
                                message=f"{missing_lines} lines uncovered",
                                auto_fixable=False,
                            )
                        )

        except (subprocess.TimeoutExpired, FileNotFoundError):
            # coverage not available
            pass

        return signals

    async def _extract_stale_deps(self) -> list[ObservableSignal]:
        """Check for stale dependencies.

        Currently checks for dependency files. Future enhancement:
        could run 'pip list --outdated' or similar to detect outdated packages.
        """
        signals: list[ObservableSignal] = []

        pyproject = self.root / "pyproject.toml"
        requirements = self.root / "requirements.txt"

        if not pyproject.exists() and not requirements.exists():
            return []

        # Dependency checking requires package manager integration
        # Deferred to future enhancement (RFC-049: External Integration)
        return signals

    def _deduplicate(self, signals: list[ObservableSignal]) -> list[ObservableSignal]:
        """Remove duplicate signals (same location and type)."""
        seen: set[tuple[Path, int, str]] = set()
        unique: list[ObservableSignal] = []

        for signal in signals:
            key = (
                signal.location.file,
                signal.location.line_start,
                signal.signal_type,
            )
            if key not in seen:
                seen.add(key)
                unique.append(signal)

        return unique

    async def _run_subprocess(
        self,
        cmd: list[str],
        timeout: int = 30,
    ) -> subprocess.CompletedProcess[str]:
        """Run a command in subprocess with timeout."""
        loop = asyncio.get_event_loop()

        def run():
            return subprocess.run(
                cmd,
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

        return await asyncio.wait_for(
            loop.run_in_executor(None, run),
            timeout=timeout + 5,
        )
