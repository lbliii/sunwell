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


import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sunwell.agent.events import (
    AgentEvent,
    EventType,
    fix_progress_event,
)
from sunwell.agent.signals import ErrorSignals, classify_error
from sunwell.agent.validation import Artifact, ValidationError
from sunwell.planning.naaru.expertise.language import Language, language_from_extension

if TYPE_CHECKING:
    from sunwell.models import ModelProtocol

# Pre-compiled regex for code block extraction (avoid recompiling per call)
_RE_CODE_BLOCK = re.compile(r"```(?:\w+)?\s*\n(.*?)\n```", re.DOTALL)


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
# Language-Specific Fix Prompts
# =============================================================================

# Prompt templates organized by language and error type
FIX_PROMPTS: dict[Language, dict[str, str]] = {
    Language.PYTHON: {
        "targeted": """Fix the following error in this code region.

ERROR TYPE: {error_type}
ERROR MESSAGE: {error_message}
FILE: {file_path}
LINE: {line}

CODE REGION:
```python
{code_region}
```

CONTEXT: {context}

Output ONLY the fixed code region (no explanation, no markdown fences):""",
        "syntax": """Fix the syntax error in this Python code.

ERROR: {error_message}
LINE: {line}

CODE:
```python
{code}
```

Output ONLY the corrected code (no explanation, no markdown fences):""",
        "type": """Fix this type error.

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

Output ONLY the fixed code (no explanation):""",
        "lint": """Fix these lint errors in the Python code:

Lint errors (ruff):
{lint_desc}

Type errors (ty):
{type_desc}

CODE:
```python
{code}
```

Rules:
- Use Python 3.14 syntax (list[str] not List[str])
- Use X | None not Optional[X]
- All public functions need type annotations
- Follow ruff rules

Output ONLY the fixed code (no explanation, no markdown fences):""",
    },
    Language.TYPESCRIPT: {
        "targeted": """Fix the following error in this code region.

ERROR TYPE: {error_type}
ERROR MESSAGE: {error_message}
FILE: {file_path}
LINE: {line}

CODE REGION:
```typescript
{code_region}
```

CONTEXT: {context}

Output ONLY the fixed code region (no explanation, no markdown fences):""",
        "syntax": """Fix the syntax error in this TypeScript code.

ERROR: {error_message}
LINE: {line}

CODE:
```typescript
{code}
```

Output ONLY the corrected code (no explanation, no markdown fences):""",
        "type": """Fix this type error.

ERROR: {error_message}
FILE: {file_path}
LINE: {line}

CODE REGION:
```typescript
{code_region}
```

Rules:
- Use strict TypeScript patterns
- Prefer explicit type annotations over inference for public APIs
- Use discriminated unions for type narrowing
- Fix the specific type issue mentioned

Output ONLY the fixed code (no explanation):""",
        "lint": """Fix these errors in the TypeScript code:

ESLint errors:
{lint_desc}

Type errors (tsc):
{type_desc}

CODE:
```typescript
{code}
```

Rules:
- Use strict TypeScript patterns
- Prefer explicit types over 'any'
- Follow ESLint rules

Output ONLY the fixed code (no explanation, no markdown fences):""",
    },
    Language.JAVASCRIPT: {
        "targeted": """Fix the following error in this code region.

ERROR TYPE: {error_type}
ERROR MESSAGE: {error_message}
FILE: {file_path}
LINE: {line}

CODE REGION:
```javascript
{code_region}
```

CONTEXT: {context}

Output ONLY the fixed code region (no explanation, no markdown fences):""",
        "syntax": """Fix the syntax error in this JavaScript code.

ERROR: {error_message}
LINE: {line}

CODE:
```javascript
{code}
```

Output ONLY the corrected code (no explanation, no markdown fences):""",
        "type": """Fix this error.

ERROR: {error_message}
FILE: {file_path}
LINE: {line}

CODE REGION:
```javascript
{code_region}
```

Output ONLY the fixed code (no explanation):""",
        "lint": """Fix these errors in the JavaScript code:

ESLint errors:
{lint_desc}

CODE:
```javascript
{code}
```

Rules:
- Follow ESLint rules
- Use modern JavaScript (ES2020+)

Output ONLY the fixed code (no explanation, no markdown fences):""",
    },
    Language.RUST: {
        "targeted": """Fix the following error in this code region.

ERROR TYPE: {error_type}
ERROR MESSAGE: {error_message}
FILE: {file_path}
LINE: {line}

CODE REGION:
```rust
{code_region}
```

CONTEXT: {context}

Output ONLY the fixed code region (no explanation, no markdown fences):""",
        "syntax": """Fix the syntax error in this Rust code.

ERROR: {error_message}
LINE: {line}

CODE:
```rust
{code}
```

Output ONLY the corrected code (no explanation, no markdown fences):""",
        "type": """Fix this type/borrow checker error.

ERROR: {error_message}
FILE: {file_path}
LINE: {line}

CODE REGION:
```rust
{code_region}
```

Rules:
- Follow Rust ownership and borrowing rules
- Use appropriate lifetimes
- Prefer &str over String for function parameters where possible
- Fix the specific error mentioned

Output ONLY the fixed code (no explanation):""",
        "lint": """Fix these errors in the Rust code:

Clippy warnings:
{lint_desc}

Compiler errors:
{type_desc}

CODE:
```rust
{code}
```

Rules:
- Follow clippy suggestions
- Use idiomatic Rust patterns

Output ONLY the fixed code (no explanation, no markdown fences):""",
    },
    Language.GO: {
        "targeted": """Fix the following error in this code region.

ERROR TYPE: {error_type}
ERROR MESSAGE: {error_message}
FILE: {file_path}
LINE: {line}

CODE REGION:
```go
{code_region}
```

CONTEXT: {context}

Output ONLY the fixed code region (no explanation, no markdown fences):""",
        "syntax": """Fix the syntax error in this Go code.

ERROR: {error_message}
LINE: {line}

CODE:
```go
{code}
```

Output ONLY the corrected code (no explanation, no markdown fences):""",
        "type": """Fix this type error.

ERROR: {error_message}
FILE: {file_path}
LINE: {line}

CODE REGION:
```go
{code_region}
```

Rules:
- Use proper Go types
- Handle errors explicitly
- Follow Go naming conventions

Output ONLY the fixed code (no explanation):""",
        "lint": """Fix these errors in the Go code:

golangci-lint errors:
{lint_desc}

Compiler errors:
{type_desc}

CODE:
```go
{code}
```

Rules:
- Follow golangci-lint suggestions
- Use idiomatic Go patterns
- Handle errors properly

Output ONLY the fixed code (no explanation, no markdown fences):""",
    },
}

# Default to Python for unknown languages (backwards compatibility)
DEFAULT_LANGUAGE = Language.PYTHON


def get_fix_prompt(
    language: Language,
    prompt_type: str,
    **kwargs: str,
) -> str:
    """Get a language-appropriate fix prompt.

    Args:
        language: The detected language
        prompt_type: Type of fix prompt ("targeted", "syntax", "type", "lint")
        **kwargs: Template variables to substitute

    Returns:
        Formatted prompt string
    """
    # Get language-specific prompts or fall back to Python
    lang_prompts = FIX_PROMPTS.get(language, FIX_PROMPTS[DEFAULT_LANGUAGE])
    template = lang_prompts.get(prompt_type, lang_prompts.get("targeted", ""))
    return template.format(**kwargs)


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
        from sunwell.models import GenerateOptions

        # Try ruff --fix for lint errors
        if signals.error_type == "lint":
            # ruff --fix already runs in cascade, so if we're here
            # it's an unfixable lint error - use LLM
            pass

        # Detect language from file extension for language-appropriate prompts
        language = language_from_extension(artifact.path.suffix)

        # For syntax errors, use LLM with language-appropriate prompt
        prompt = get_fix_prompt(
            language,
            "syntax",
            error_message=error.message,
            line=str(error.line or 1),
            code=artifact.content,
        )

        result = await self.model.generate(
            prompt,
            options=GenerateOptions(temperature=0.2, max_tokens=2000),
        )

        if result.text:
            # Write fixed content directly to file
            # (Artifact is frozen, so we write to disk instead of mutating)
            fixed_content = result.text.strip()
            artifact.path.write_text(fixed_content)
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
        from sunwell.models import GenerateOptions

        # Find the error region
        lines = artifact.content.split("\n")
        error_line = error.line or 1

        # Get context (5 lines before and after)
        start = max(0, error_line - 6)
        end = min(len(lines), error_line + 5)
        code_region = "\n".join(lines[start:end])

        # Detect language from file extension
        language = language_from_extension(artifact.path.suffix)

        # Use targeted fix prompt with language-appropriate formatting
        if signals.error_type == "type":
            prompt = get_fix_prompt(
                language,
                "type",
                error_message=error.message,
                file_path=str(error.file),
                line=str(error_line),
                code_region=code_region,
            )
        else:
            prompt = get_fix_prompt(
                language,
                "targeted",
                error_type=signals.error_type,
                error_message=error.message,
                file_path=str(error.file),
                line=str(error_line),
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

            # Reconstruct file and write directly
            # (Artifact is frozen, so we write to disk instead of mutating)
            new_lines = lines[:start] + fixed_region.split("\n") + lines[end:]
            artifact.path.write_text("\n".join(new_lines))
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
        Currently falls back to compound eye approach.
        """
        # VortexPipeline not yet implemented - fall back to compound eye
        # TODO: Implement VortexPipeline for multi-candidate exploration
        return await self._compound_eye_fix(error, artifact, signals)

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
        from sunwell.agent.utils.toolchain import ToolchainRunner, detect_toolchain

        # Detect the appropriate toolchain based on the project
        toolchain = detect_toolchain(self.cwd)
        runner = ToolchainRunner(toolchain, self.cwd)

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
        from sunwell.models import GenerateOptions

        if not lint_errors and not type_errors:
            return

        # Detect language from file extension for language-appropriate prompts
        language = language_from_extension(artifact.path.suffix)

        # Build fix prompt
        lint_desc = "\n".join(
            f"- Line {e.line}: [{e.code}] {e.message}" for e in lint_errors
        )
        type_desc = "\n".join(
            f"- Line {e.line}: {e.message}" for e in type_errors
        )

        # Use language-specific lint prompt
        prompt = get_fix_prompt(
            language,
            "lint",
            lint_desc=lint_desc or "None",
            type_desc=type_desc or "None",
            code=artifact.content,
        )

        result = await self.model.generate(
            prompt,
            options=GenerateOptions(temperature=0.2, max_tokens=4000),
        )

        if result.text:
            # Write fixed content directly to file
            # (Artifact is frozen, so we write to disk instead of mutating)
            artifact.path.write_text(result.text.strip())
