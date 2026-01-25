"""Fix stage for Adaptive Agent (RFC-042).

When validation fails, the fix stage attempts automatic repair:
1. Compound Eye scans for hotspots (where error likely is)
2. Signal-based routing selects fix strategy
3. Targeted fix applied (region, not whole file)
4. Re-validation to confirm fix

Fix strategies:
- DIRECT: Syntax/lint errors → deterministic fix
- COMPOUND_EYE: Find hotspot first, then fix
- VORTEX: Generate multiple fix candidates, select best
- ESCALATE: Too complex, ask user
"""


from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import re

from sunwell.agent.events import (
    AgentEvent,
    EventType,
    fix_progress_event,
)
from sunwell.agent.signals import ErrorSignals, classify_error
from sunwell.agent.validation import Artifact, ValidationError

if TYPE_CHECKING:
    from sunwell.models.protocol import ModelProtocol

# Pre-compiled regex for code block extraction (avoid recompiling per call)
_RE_CODE_BLOCK = re.compile(r"```(?:python)?\s*\n(.*?)\n```", re.DOTALL)


@dataclass(frozen=True, slots=True)
class FixAttempt:
    """A single fix attempt."""

    strategy: str
    """Strategy used (direct, compound_eye, vortex)."""

    target_file: str
    """File that was modified."""

    target_lines: tuple[int, int] | None
    """Line range that was modified (if targeted)."""

    original_code: str
    """Code before fix."""

    fixed_code: str
    """Code after fix."""

    success: bool
    """Whether fix passed validation."""

    error_message: str = ""
    """Error message if fix failed."""


@dataclass(frozen=True, slots=True)
class FixResult:
    """Result of fix stage."""

    success: bool
    """Whether all errors were fixed."""

    attempts: tuple[FixAttempt, ...] = ()
    """Fix attempts made."""

    remaining_errors: tuple[ValidationError, ...] = ()
    """Errors that couldn't be fixed."""


# =============================================================================
# Fix Prompts
# =============================================================================

TARGETED_FIX_PROMPT = """Fix the following error in this code region.

ERROR TYPE: {error_type}
ERROR MESSAGE: {error_message}
FILE: {file_path}
LINE: {line}

CODE REGION:
```python
{code_region}
```

CONTEXT: {context}

Output ONLY the fixed code region (no explanation, no markdown fences):"""


SYNTAX_FIX_PROMPT = """Fix the syntax error in this Python code.

ERROR: {error_message}
LINE: {line}

CODE:
```python
{code}
```

Output ONLY the corrected code (no explanation, no markdown fences):"""


TYPE_FIX_PROMPT = """Fix this type error.

ERROR: {error_message}
FILE: {file_path}
LINE: {line}

CODE REGION:
```python
{code_region}
```

Rules:
- Use Python 3.14 syntax (list[str] not List[str])
- Use X | None not Optional[X]
- All public functions need type annotations
- Fix the specific type issue mentioned

Output ONLY the fixed code (no explanation):"""


# =============================================================================
# Fix Stage
# =============================================================================


class FixStage:
    """Automatic fix stage for the adaptive agent.

    Uses signal-based routing to select fix strategy:
    - syntax/lint → Direct fix
    - type/import → Compound Eye + targeted fix
    - runtime → Vortex for multiple candidates

    Limits fix attempts to prevent infinite loops.
    """

    def __init__(
        self,
        model: ModelProtocol,
        cwd: Path | None = None,
        max_attempts: int = 3,
    ):
        self.model = model
        self.cwd = cwd or Path.cwd()
        self.max_attempts = max_attempts

    async def fix_errors(
        self,
        errors: list[ValidationError],
        artifacts: dict[str, Artifact],
    ) -> AsyncIterator[AgentEvent]:
        """Attempt to fix validation errors.

        Args:
            errors: Errors to fix
            artifacts: Current artifacts (path → Artifact)

        Yields:
            AgentEvent for fix progress
        """
        yield AgentEvent(EventType.FIX_START, {"errors": len(errors)})

        fixed_count = 0
        remaining_errors: list[ValidationError] = []

        for i, error in enumerate(errors):
            # Classify error to determine strategy
            signals = classify_error(error.message, error.file)

            yield fix_progress_event(
                stage="classify",
                progress=(i / len(errors)),
                detail=f"Error type: {signals.error_type}, route: {signals.fix_route}",
            )

            # Get artifact for this file
            artifact = artifacts.get(error.file or "") if error.file else None
            if not artifact:
                remaining_errors.append(error)
                continue

            # Attempt fix based on strategy
            for attempt_num in range(self.max_attempts):
                yield fix_progress_event(
                    stage=signals.fix_route.lower(),
                    progress=((i + attempt_num / self.max_attempts) / len(errors)),
                    detail=f"Attempt {attempt_num + 1}/{self.max_attempts}",
                )

                try:
                    match signals.fix_route:
                        case "DIRECT":
                            fixed = await self._direct_fix(error, artifact, signals)
                        case "COMPOUND_EYE":
                            fixed = await self._compound_eye_fix(
                                error, artifact, signals
                            )
                        case "VORTEX":
                            fixed = await self._vortex_fix(error, artifact, signals)
                        case _:
                            # ESCALATE - can't auto-fix
                            fixed = False

                    if fixed:
                        fixed_count += 1
                        yield AgentEvent(
                            EventType.FIX_COMPLETE,
                            {
                                "error_type": signals.error_type,
                                "file": error.file,
                                "attempts": attempt_num + 1,
                            },
                        )
                        break

                except Exception as e:
                    yield fix_progress_event(
                        stage="error",
                        progress=((i + 1) / len(errors)),
                        detail=str(e),
                    )

            else:
                # Max attempts reached
                remaining_errors.append(error)
                yield AgentEvent(
                    EventType.FIX_FAILED,
                    {
                        "error_type": signals.error_type,
                        "file": error.file,
                        "attempts": self.max_attempts,
                    },
                )

        # Summary
        if remaining_errors:
            remaining = len(remaining_errors)
            # Build informative message for UI
            if fixed_count > 0:
                msg = f"Fixed {fixed_count} errors but {remaining} remain unfixable"
            else:
                msg = f"{remaining} error{'s' if remaining > 1 else ''} could not be auto-fixed"
            
            yield AgentEvent(
                EventType.ESCALATE,
                {
                    "reason": "unfixable_errors",
                    "message": msg,
                    "fixed": fixed_count,
                    "remaining": remaining,
                    "errors": [e.message for e in remaining_errors[:5]],  # First 5 errors
                },
            )
        else:
            yield AgentEvent(
                EventType.FIX_COMPLETE,
                {"total_fixed": fixed_count},
            )

    async def _direct_fix(
        self,
        error: ValidationError,
        artifact: Artifact,
        signals: ErrorSignals,
    ) -> bool:
        """Direct fix for syntax/lint errors.

        Uses deterministic tools (ruff --fix) first,
        then LLM for remaining issues.
        """
        from sunwell.models.protocol import GenerateOptions

        # Try ruff --fix for lint errors
        if signals.error_type == "lint":
            # ruff --fix already runs in cascade, so if we're here
            # it's an unfixable lint error - use LLM
            pass

        # For syntax errors, use LLM
        prompt = SYNTAX_FIX_PROMPT.format(
            error_message=error.message,
            line=error.line or 1,
            code=artifact.content,
        )

        result = await self.model.generate(
            prompt,
            options=GenerateOptions(temperature=0.2, max_tokens=2000),
        )

        if result.text:
            # Update artifact content
            artifact.content = result.text.strip()
            # Write to file
            artifact.path.write_text(artifact.content)
            return True

        return False

    async def _compound_eye_fix(
        self,
        error: ValidationError,
        artifact: Artifact,
        signals: ErrorSignals,
    ) -> bool:
        """Use Compound Eye to find hotspot, then targeted fix.

        For type/import errors where we need to find the exact region.
        """
        from sunwell.models.protocol import GenerateOptions

        # Find the error region
        lines = artifact.content.split("\n")
        error_line = error.line or 1

        # Get context (5 lines before and after)
        start = max(0, error_line - 6)
        end = min(len(lines), error_line + 5)
        code_region = "\n".join(lines[start:end])

        # Use targeted fix prompt
        if signals.error_type == "type":
            prompt = TYPE_FIX_PROMPT.format(
                error_message=error.message,
                file_path=error.file,
                line=error_line,
                code_region=code_region,
            )
        else:
            prompt = TARGETED_FIX_PROMPT.format(
                error_type=signals.error_type,
                error_message=error.message,
                file_path=error.file,
                line=error_line,
                code_region=code_region,
                context=f"Likely cause: {signals.likely_cause}",
            )

        result = await self.model.generate(
            prompt,
            options=GenerateOptions(temperature=0.3, max_tokens=1000),
        )

        if result.text:
            # Replace the region in the original content
            fixed_region = result.text.strip()

            # Reconstruct file
            new_lines = lines[:start] + fixed_region.split("\n") + lines[end:]
            artifact.content = "\n".join(new_lines)
            artifact.path.write_text(artifact.content)
            return True

        return False

    async def _vortex_fix(
        self,
        error: ValidationError,
        artifact: Artifact,
        signals: ErrorSignals,
    ) -> bool:
        """Use Vortex pipeline for multiple fix candidates.

        For runtime errors where we need to explore solutions.
        """
        # Import vortex components
        try:
            from sunwell.features.vortex.pipeline import VortexPipeline
        except ImportError:
            # Fallback to compound eye if vortex not available
            return await self._compound_eye_fix(error, artifact, signals)

        # Find error region
        lines = artifact.content.split("\n")
        error_line = error.line or 1
        start = max(0, error_line - 10)
        end = min(len(lines), error_line + 10)
        code_region = "\n".join(lines[start:end])

        # Create fix task for vortex
        task = f"""Fix this runtime error:

ERROR: {error.message}
FILE: {error.file}
LINE: {error_line}

CODE REGION:
```python
{code_region}
```

Likely cause: {signals.likely_cause}

Provide the corrected code region."""

        # Run vortex pipeline
        pipeline = VortexPipeline(model=self.model)
        result = await pipeline.solve(task)

        if result.synthesis:
            # Extract code from synthesis
            fixed_code = self._extract_code(result.synthesis)
            if fixed_code:
                # Replace region
                new_lines = lines[:start] + fixed_code.split("\n") + lines[end:]
                artifact.content = "\n".join(new_lines)
                artifact.path.write_text(artifact.content)
                return True

        return False

    def _extract_code(self, text: str) -> str | None:
        """Extract code from LLM response."""
        # Try to find code block
        code_match = _RE_CODE_BLOCK.search(text)
        if code_match:
            return code_match.group(1)

        # If no code block, assume entire response is code
        if text.strip() and not text.startswith(("I ", "The ", "This ", "Here")):
            return text.strip()

        return None


# =============================================================================
# Static Analysis Fixer
# =============================================================================


class StaticAnalysisFixer:
    """Fixes lint and type errors at gates.

    Runs deterministic fixes (ruff --fix) first,
    then uses LLM for remaining issues.
    """

    def __init__(
        self,
        model: ModelProtocol,
        cwd: Path | None = None,
    ):
        self.model = model
        self.cwd = cwd or Path.cwd()

    async def fix_at_gate(
        self,
        artifacts: list[Artifact],
        lint_errors: list[dict[str, Any]],
        type_errors: list[dict[str, Any]],
    ) -> AsyncIterator[AgentEvent]:
        """Fix static analysis errors at a gate.

        Args:
            artifacts: Artifacts to fix
            lint_errors: Lint errors from ruff
            type_errors: Type errors from ty/mypy

        Yields:
            AgentEvent for fix progress
        """
        from sunwell.agent.toolchain import PYTHON_TOOLCHAIN, ToolchainRunner

        runner = ToolchainRunner(PYTHON_TOOLCHAIN, self.cwd)

        yield fix_progress_event(
            stage="lint_autofix",
            progress=0.0,
            detail=f"Auto-fixing {len(lint_errors)} lint errors",
        )

        # Step 1: Ruff auto-fix (deterministic, no LLM needed)
        files = [a.path for a in artifacts]
        await runner.check_lint(files, auto_fix=True)

        yield fix_progress_event(
            stage="lint_check",
            progress=0.25,
            detail="Checking remaining lint errors",
        )

        # Step 2: Check for remaining lint errors
        lint_result = await runner.check_lint(files, auto_fix=False)

        # Step 3: Type check
        yield fix_progress_event(
            stage="type_check",
            progress=0.5,
            detail="Running type checker",
        )

        type_result = await runner.check_types(files)

        # Step 4: If errors remain, use LLM
        remaining_lint = lint_result.lint_errors
        remaining_type = type_result.type_errors

        if remaining_lint or remaining_type:
            yield fix_progress_event(
                stage="llm_fix",
                progress=0.75,
                detail=f"LLM fixing {len(remaining_lint)} lint, {len(remaining_type)} type errors",
            )

            for artifact in artifacts:
                await self._llm_fix_artifact(
                    artifact,
                    [e for e in remaining_lint if e.file == str(artifact.path)],
                    [e for e in remaining_type if e.file == str(artifact.path)],
                )

        yield fix_progress_event(
            stage="complete",
            progress=1.0,
            detail="Static analysis fix complete",
        )

    async def _llm_fix_artifact(
        self,
        artifact: Artifact,
        lint_errors: list,
        type_errors: list,
    ) -> None:
        """Use LLM to fix errors in an artifact."""
        from sunwell.models.protocol import GenerateOptions

        if not lint_errors and not type_errors:
            return

        # Build fix prompt
        lint_desc = "\n".join(
            f"- Line {e.line}: [{e.code}] {e.message}" for e in lint_errors
        )
        type_desc = "\n".join(
            f"- Line {e.line}: {e.message}" for e in type_errors
        )

        prompt = f"""Fix these errors in the code:

Lint errors (ruff):
{lint_desc or "None"}

Type errors (ty):
{type_desc or "None"}

CODE:
```python
{artifact.content}
```

Rules:
- Use Python 3.14 syntax (list[str] not List[str])
- Use X | None not Optional[X]
- All public functions need type annotations
- Follow ruff rules

Output ONLY the fixed code (no explanation, no markdown fences):"""

        result = await self.model.generate(
            prompt,
            options=GenerateOptions(temperature=0.2, max_tokens=4000),
        )

        if result.text:
            artifact.content = result.text.strip()
            artifact.path.write_text(artifact.content)
