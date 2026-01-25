"""Convergence Loop — Self-stabilizing code generation (RFC-123).

After file writes, runs validation gates in parallel. If any fail,
the agent fixes errors and loops until stable or limits are reached.

Example:
    >>> loop = ConvergenceLoop(model=model, cwd=Path.cwd())
    >>> async for event in loop.run([Path("api.py")]):
    ...     print(event)
    >>> print(loop.result.status)  # STABLE or ESCALATED
"""

import asyncio
import subprocess
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sunwell.agent.events import (
    AgentEvent,
    EventType,
    convergence_budget_exceeded_event,
    convergence_fixing_event,
    convergence_iteration_complete_event,
    convergence_iteration_start_event,
    convergence_max_iterations_event,
    convergence_stable_event,
    convergence_start_event,
    convergence_stuck_event,
    convergence_timeout_event,
)
from sunwell.agent.validation.gates import GateType
from sunwell.agent.validation import Artifact, ValidationError
from sunwell.agent.convergence.types import (
    ConvergenceConfig,
    ConvergenceIteration,
    ConvergenceResult,
    ConvergenceStatus,
    GateCheckResult,
)

if TYPE_CHECKING:
    from sunwell.agent.execution.fixer import FixStage
    from sunwell.models.protocol import ModelProtocol


@dataclass(slots=True)
class ConvergenceLoop:
    """Self-stabilizing code generation loop.

    After file writes, runs validation gates in parallel.
    If any fail, agent fixes and loop continues until stable.

    RFC-125: On escalation, saves recovery state so user can review
    and resume with hints or manual fixes.

    Example:
        >>> loop = ConvergenceLoop(model=model, cwd=Path.cwd())
        >>> async for event in loop.run(changed_files, artifacts):
        ...     print(event)  # Progress events
        >>> print(loop.result.status)  # STABLE or ESCALATED
    """

    model: ModelProtocol
    """Model for generating fixes."""

    cwd: Path
    """Working directory for file operations."""

    config: ConvergenceConfig = field(default_factory=ConvergenceConfig)
    """Convergence configuration."""

    # RFC-125: Recovery context (optional)
    goal: str = ""
    """Original goal for recovery context."""

    run_id: str = ""
    """Run identifier for recovery."""

    result: ConvergenceResult | None = field(default=None, init=False)
    """Final result (set after run completes)."""

    recovery_state: Any = field(default=None, init=False)
    """Recovery state if escalated (RFC-125)."""

    # Internal state
    _fixer: FixStage | None = field(default=None, init=False)
    _start_time: float = field(default=0.0, init=False)
    _tokens_used: int = field(default=0, init=False)
    _error_history: dict[str, int] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        """Initialize fix stage."""
        from sunwell.agent.execution.fixer import FixStage

        self._fixer = FixStage(
            self.model,
            self.cwd,
            max_attempts=self.config.max_iterations,
        )

    async def run(
        self,
        initial_files: list[Path],
        artifacts: dict[str, Artifact] | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """Run convergence loop until stable or limits hit.

        Args:
            initial_files: Files to validate initially
            artifacts: Optional mapping of file paths to Artifact objects

        Yields:
            AgentEvent for progress tracking
        """
        self._start_time = time.monotonic()
        self._tokens_used = 0
        self._error_history.clear()
        iterations: list[ConvergenceIteration] = []
        changed_files = set(initial_files)

        # Build artifacts dict if not provided
        if artifacts is None:
            artifacts = {}
            for f in initial_files:
                if f.exists():
                    artifacts[str(f)] = Artifact(
                        path=f,
                        content=f.read_text(),
                        task_id="convergence",
                    )

        yield convergence_start_event(
            files=[str(f) for f in initial_files],
            gates=[g.value for g in self.config.enabled_gates],
            max_iterations=self.config.max_iterations,
        )

        for iteration_num in range(1, self.config.max_iterations + 1):
            # Check timeout
            if self._check_timeout():
                self.result = ConvergenceResult(
                    status=ConvergenceStatus.TIMEOUT,
                    iterations=iterations,
                    total_duration_ms=self._elapsed_ms(),
                    tokens_used=self._tokens_used,
                )
                # RFC-125: Save recovery state for later review
                self._save_recovery_state(artifacts, iterations, "timeout")
                yield convergence_timeout_event(iterations=iteration_num - 1)
                return

            # Check token budget
            if self._tokens_used >= self.config.max_tokens:
                self.result = ConvergenceResult(
                    status=ConvergenceStatus.ESCALATED,
                    iterations=iterations,
                    total_duration_ms=self._elapsed_ms(),
                    tokens_used=self._tokens_used,
                )
                # RFC-125: Save recovery state for later review
                self._save_recovery_state(artifacts, iterations, "budget_exceeded")
                yield convergence_budget_exceeded_event(
                    tokens_used=self._tokens_used,
                    max_tokens=self.config.max_tokens,
                )
                return

            yield convergence_iteration_start_event(
                iteration=iteration_num,
                files=[str(f) for f in changed_files],
            )

            # Run gates in parallel
            iter_start = time.monotonic()
            gate_results = await self._run_gates_parallel(list(changed_files))

            iteration = ConvergenceIteration(
                iteration=iteration_num,
                gate_results=tuple(gate_results),
                files_changed=tuple(changed_files),
                duration_ms=int((time.monotonic() - iter_start) * 1000),
            )
            iterations.append(iteration)

            yield convergence_iteration_complete_event(
                iteration=iteration_num,
                all_passed=iteration.all_passed,
                total_errors=iteration.total_errors,
                gate_results=[
                    {"gate": r.gate.value, "passed": r.passed, "errors": r.error_count}
                    for r in gate_results
                ],
            )

            # Check if stable
            if iteration.all_passed:
                self.result = ConvergenceResult(
                    status=ConvergenceStatus.STABLE,
                    iterations=iterations,
                    total_duration_ms=self._elapsed_ms(),
                    tokens_used=self._tokens_used,
                )
                yield convergence_stable_event(
                    iterations=iteration_num,
                    duration_ms=self._elapsed_ms(),
                )
                return

            # Check for stuck errors (same error repeated)
            if self._check_stuck_errors(gate_results):
                self.result = ConvergenceResult(
                    status=ConvergenceStatus.ESCALATED,
                    iterations=iterations,
                    total_duration_ms=self._elapsed_ms(),
                    tokens_used=self._tokens_used,
                )
                # RFC-125: Save recovery state for later review
                self._save_recovery_state(artifacts, iterations, "stuck_errors")
                yield convergence_stuck_event(
                    iterations=iteration_num,
                    repeated_errors=list(self._get_stuck_errors()),
                )
                return

            # Convert gate errors to ValidationError format
            validation_errors: list[ValidationError] = [
                ValidationError(
                    error_type=r.gate.value,
                    message=err,
                )
                for r in gate_results
                if not r.passed
                for err in r.errors
            ]

            yield convergence_fixing_event(
                iteration=iteration_num,
                error_count=len(validation_errors),
            )

            # Use FixStage to fix errors
            changed_files.clear()
            async for fix_event in self._fixer.fix_errors(validation_errors, artifacts):
                yield fix_event

                # Track files changed by fix
                if fix_event.type == EventType.FIX_COMPLETE:
                    fixed_file = fix_event.data.get("file")
                    if fixed_file:
                        path = Path(fixed_file)
                        changed_files.add(path)
                        # Update artifacts dict with new content
                        if path.exists():
                            artifacts[str(path)] = Artifact(
                                path=path,
                                content=path.read_text(),
                                task_id="convergence",
                            )

                # Track tokens
                if "tokens" in fix_event.data:
                    self._tokens_used += fix_event.data["tokens"]

            # If no files changed during fix, re-check all
            if not changed_files:
                changed_files = set(initial_files)

            # Debounce before next iteration
            await asyncio.sleep(self.config.debounce_ms / 1000)

        # Max iterations reached
        self.result = ConvergenceResult(
            status=ConvergenceStatus.ESCALATED,
            iterations=iterations,
            total_duration_ms=self._elapsed_ms(),
            tokens_used=self._tokens_used,
        )

        # RFC-125: Save recovery state for later review
        self._save_recovery_state(artifacts, iterations, "max_iterations")

        yield convergence_max_iterations_event(
            iterations=self.config.max_iterations,
        )

    async def _run_gates_parallel(
        self,
        files: list[Path],
    ) -> list[GateCheckResult]:
        """Run all enabled gates in parallel."""
        tasks = [self._run_single_gate(gate, files) for gate in self.config.enabled_gates]
        return list(await asyncio.gather(*tasks))

    async def _run_single_gate(
        self,
        gate: GateType,
        files: list[Path],
    ) -> GateCheckResult:
        """Run a single gate check."""
        start = time.monotonic()

        match gate:
            case GateType.LINT:
                passed, errors = await self._check_lint(files)
            case GateType.TYPE:
                passed, errors = await self._check_types(files)
            case GateType.TEST:
                passed, errors = await self._check_tests(files)
            case GateType.SYNTAX:
                passed, errors = await self._check_syntax(files)
            case _:
                passed, errors = True, []

        duration = int((time.monotonic() - start) * 1000)

        # Track error frequency for stuck detection
        for err in errors:
            err_key = f"{gate.value}:{err[:100]}"
            self._error_history[err_key] = self._error_history.get(err_key, 0) + 1

        return GateCheckResult(
            gate=gate,
            passed=passed,
            errors=tuple(errors),
            duration_ms=duration,
        )

    async def _check_lint(self, files: list[Path]) -> tuple[bool, list[str]]:
        """Run ruff on files."""
        if not files:
            return True, []

        try:
            result = await self._run_subprocess(
                ["ruff", "check", "--output-format=concise", *[str(f) for f in files]],
                timeout=30,
            )
            if result.returncode == 0:
                return True, []

            errors = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            return False, errors
        except FileNotFoundError:
            return True, []  # ruff not installed, skip
        except TimeoutError:
            return False, ["Lint check timed out"]
        except Exception as e:
            return False, [str(e)]

    async def _check_types(self, files: list[Path]) -> tuple[bool, list[str]]:
        """Run ty (or mypy) on files."""
        if not files:
            return True, []

        # Try ty first (faster)
        try:
            result = await self._run_subprocess(
                ["ty", "check", *[str(f) for f in files]],
                timeout=60,
            )
            if result.returncode == 0:
                return True, []

            errors = [
                line.strip()
                for line in result.stdout.splitlines()
                if line.strip() and "error" in line.lower()
            ]
            return False, errors
        except FileNotFoundError:
            pass  # ty not installed, try mypy
        except TimeoutError:
            return False, ["Type check timed out"]
        except Exception as e:
            return False, [str(e)]

        # Fall back to mypy
        try:
            result = await self._run_subprocess(
                ["mypy", "--no-error-summary", *[str(f) for f in files]],
                timeout=60,
            )
            if result.returncode == 0:
                return True, []

            errors = [
                line.strip()
                for line in result.stdout.splitlines()
                if line.strip() and "error" in line.lower()
            ]
            return False, errors
        except FileNotFoundError:
            return True, []  # Neither ty nor mypy installed, skip
        except TimeoutError:
            return False, ["Type check timed out"]
        except Exception as e:
            return False, [str(e)]

    async def _check_tests(self, files: list[Path]) -> tuple[bool, list[str]]:
        """Run pytest on related test files."""
        # Find related test files
        test_files = [f for f in files if "test" in f.name.lower() or f.parent.name == "tests"]

        if not test_files:
            return True, []

        try:
            result = await self._run_subprocess(
                ["pytest", "-q", "--tb=line", *[str(f) for f in test_files]],
                timeout=120,
            )
            if result.returncode == 0:
                return True, []

            errors = [
                line.strip()
                for line in result.stdout.splitlines()
                if "FAILED" in line or "ERROR" in line
            ]
            return False, errors
        except FileNotFoundError:
            return True, []  # pytest not installed, skip
        except TimeoutError:
            return False, ["Tests timed out"]
        except Exception as e:
            return False, [str(e)]

    async def _check_syntax(self, files: list[Path]) -> tuple[bool, list[str]]:
        """Check Python syntax."""
        import py_compile

        errors = []
        for f in files:
            if f.suffix == ".py":
                try:
                    py_compile.compile(str(f), doraise=True)
                except py_compile.PyCompileError as e:
                    errors.append(str(e))

        return len(errors) == 0, errors

    async def _run_subprocess(
        self,
        cmd: list[str],
        timeout: int = 30,
    ) -> subprocess.CompletedProcess[str]:
        """Run a command in subprocess with timeout."""
        loop = asyncio.get_event_loop()

        def run() -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.cwd,
                timeout=timeout,
            )

        return await asyncio.wait_for(
            loop.run_in_executor(None, run),
            timeout=timeout + 5,
        )

    def _check_timeout(self) -> bool:
        """Check if timeout exceeded."""
        return self._elapsed_ms() > self.config.timeout_seconds * 1000

    def _elapsed_ms(self) -> int:
        """Elapsed time in milliseconds."""
        return int((time.monotonic() - self._start_time) * 1000)

    def _check_stuck_errors(self, results: list[GateCheckResult]) -> bool:
        """Check if any error has repeated too many times."""
        for r in results:
            for err in r.errors:
                err_key = f"{r.gate.value}:{err[:100]}"
                if self._error_history.get(err_key, 0) >= self.config.escalate_after_same_error:
                    return True
        return False

    def _get_stuck_errors(self) -> list[str]:
        """Get errors that have repeated too many times."""
        return [
            key
            for key, count in self._error_history.items()
            if count >= self.config.escalate_after_same_error
        ]

    def _save_recovery_state(
        self,
        artifacts: dict[str, Artifact],
        iterations: list[ConvergenceIteration],
        failure_reason: str,
    ) -> None:
        """Save recovery state for later review (RFC-125).

        Creates a RecoveryState from the current execution state and
        saves it to disk for user review.

        Args:
            artifacts: All artifacts with their content
            iterations: Convergence iteration history
            failure_reason: Why convergence failed
        """
        import hashlib

        from sunwell.recovery import ArtifactStatus, RecoveryManager, RecoveryState
        from sunwell.agent.recovery.types import RecoveryArtifact

        if not self.goal:
            return  # No goal, can't create recovery

        # Create goal hash
        goal_hash = hashlib.sha256(self.goal.encode()).hexdigest()[:12]
        run_id = self.run_id or f"conv-{goal_hash[:8]}"

        # Build gate results from last iteration
        gate_results: dict[str, tuple[bool, list[str]]] = {}
        if iterations:
            last_iter = iterations[-1]
            for gate_result in last_iter.gate_results:
                for file in last_iter.files_changed:
                    path = str(file)
                    existing_passed, existing_errors = gate_results.get(path, (True, []))
                    if not gate_result.passed:
                        gate_results[path] = (False, existing_errors + list(gate_result.errors))
                    elif path not in gate_results:
                        gate_results[path] = (True, [])

        # Build recovery artifacts
        recovery_artifacts: dict[str, RecoveryArtifact] = {}
        for path, artifact in artifacts.items():
            passed, errors = gate_results.get(path, (True, []))
            status = ArtifactStatus.PASSED if passed else ArtifactStatus.FAILED

            recovery_artifacts[path] = RecoveryArtifact(
                path=Path(path),
                content=artifact.content,
                status=status,
                errors=tuple(errors),
                depends_on=(),
            )

        # Create state
        iteration_history = [
            {
                "iteration": it.iteration,
                "all_passed": it.all_passed,
                "total_errors": it.total_errors,
            }
            for it in iterations
        ]

        state = RecoveryState(
            goal=self.goal,
            goal_hash=goal_hash,
            run_id=run_id,
            artifacts=recovery_artifacts,
            failure_reason=failure_reason,
            error_details=[
                err for path, (passed, errs) in gate_results.items()
                if not passed for err in errs
            ],
            iteration_history=iteration_history,
        )

        # Save to disk
        recovery_dir = self.cwd / ".sunwell" / "recovery"
        manager = RecoveryManager(recovery_dir)
        manager.save(state)

        self.recovery_state = state
