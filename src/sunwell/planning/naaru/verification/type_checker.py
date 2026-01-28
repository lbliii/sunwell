"""Static type checker integration using mypy.

Provides subprocess wrapper to run mypy for Protocol compliance verification.
"""

import asyncio
import re
import time
from pathlib import Path
from shutil import which

from sunwell.planning.naaru.verification.types import TypeCheckResult


def _find_mypy() -> str | None:
    """Find mypy executable."""
    # Check common locations
    mypy_path = which("mypy")
    if mypy_path:
        return mypy_path

    # Try python -m mypy as fallback
    return None


def _parse_mypy_output(stdout: str, stderr: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Parse mypy output into errors and warnings.

    Args:
        stdout: Standard output from mypy
        stderr: Standard error from mypy

    Returns:
        Tuple of (errors, warnings)
    """
    errors = []
    warnings = []

    # Combine stdout and stderr
    output = stdout + stderr

    for line in output.strip().split("\n"):
        line = line.strip()
        if not line:
            continue

        # Skip summary lines
        if line.startswith("Found") or line.startswith("Success"):
            continue

        # Categorize by type
        if ": error:" in line:
            errors.append(line)
        elif ": warning:" in line or ": note:" in line:
            warnings.append(line)
        elif line and not line.startswith("--"):
            # Include other diagnostic lines as errors
            errors.append(line)

    return tuple(errors), tuple(warnings)


def _build_protocol_check_stub(
    impl_path: Path,
    impl_class: str,
    protocol_path: Path,
    protocol_name: str,
    temp_dir: Path,
) -> Path:
    """Build a temporary stub file that imports and type-checks the implementation.

    Creates a file that:
    1. Imports the Protocol
    2. Imports the implementation
    3. Uses a type annotation to trigger Protocol compliance check

    Args:
        impl_path: Path to implementation file
        impl_class: Name of implementing class
        protocol_path: Path to Protocol file
        protocol_name: Name of the Protocol
        temp_dir: Directory to write stub file

    Returns:
        Path to the stub file
    """
    # Compute relative imports or use absolute paths
    # For simplicity, we'll use absolute imports
    impl_module = impl_path.stem
    protocol_module = protocol_path.stem

    stub_content = f'''"""Type checking stub - auto-generated."""
import sys
from pathlib import Path

# Add paths to allow imports
sys.path.insert(0, str(Path({str(impl_path.parent)!r})))
sys.path.insert(0, str(Path({str(protocol_path.parent)!r})))

from {protocol_module} import {protocol_name}
from {impl_module} import {impl_class}

# This assignment triggers Protocol compliance check
_check: {protocol_name} = {impl_class}()
'''

    stub_path = temp_dir / "_contract_check.py"
    stub_path.write_text(stub_content, encoding="utf-8")
    return stub_path


async def run_mypy_check(
    implementation_file: Path,
    protocol_file: Path,
    protocol_name: str | None = None,
    impl_class_name: str | None = None,
    strict: bool = False,
    timeout_seconds: float = 30.0,
) -> TypeCheckResult:
    """Run mypy type checker on an implementation file.

    Uses mypy --no-incremental to ensure fresh checking without cache.

    Args:
        implementation_file: Path to the implementation file
        protocol_file: Path to the Protocol definition file
        protocol_name: Name of Protocol (if checking specific Protocol compliance)
        impl_class_name: Name of implementing class
        strict: Whether to use strict mode
        timeout_seconds: Maximum time to wait for mypy

    Returns:
        TypeCheckResult with pass/fail status and any error messages
    """
    start_time = time.perf_counter()

    mypy_path = _find_mypy()
    use_module = mypy_path is None

    # Build mypy command
    if use_module:
        cmd = ["python", "-m", "mypy"]
    else:
        cmd = [mypy_path]

    cmd.extend([
        "--no-incremental",
        "--no-error-summary",
        "--show-error-codes",
    ])

    if strict:
        cmd.append("--strict")

    # Add the files to check
    cmd.append(str(implementation_file))

    # If we have protocol info, we could generate a stub file
    # For now, just check the implementation file directly
    # The implementation should import and use the Protocol

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=implementation_file.parent,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return TypeCheckResult(
                passed=False,
                errors=("mypy timed out",),
                exit_code=-1,
                duration_ms=int((time.perf_counter() - start_time) * 1000),
            )

        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")

        errors, warnings = _parse_mypy_output(stdout, stderr)
        exit_code = process.returncode or 0

        duration_ms = int((time.perf_counter() - start_time) * 1000)

        return TypeCheckResult(
            passed=exit_code == 0 and len(errors) == 0,
            errors=errors,
            warnings=warnings,
            exit_code=exit_code,
            duration_ms=duration_ms,
        )

    except FileNotFoundError:
        return TypeCheckResult(
            passed=False,
            errors=("mypy not found - install with: pip install mypy",),
            exit_code=-1,
            duration_ms=int((time.perf_counter() - start_time) * 1000),
        )
    except OSError as e:
        return TypeCheckResult(
            passed=False,
            errors=(f"Failed to run mypy: {e}",),
            exit_code=-1,
            duration_ms=int((time.perf_counter() - start_time) * 1000),
        )


async def check_protocol_compliance(
    implementation_file: Path,
    protocol_file: Path,
    protocol_name: str,
    impl_class_name: str,
    timeout_seconds: float = 30.0,
) -> TypeCheckResult:
    """Check if implementation satisfies Protocol using mypy.

    Creates a temporary type check file that assigns the implementation
    to a variable typed as the Protocol, then runs mypy on it.

    Args:
        implementation_file: Path to implementation file
        protocol_file: Path to Protocol definition
        protocol_name: Name of the Protocol class
        impl_class_name: Name of the implementing class
        timeout_seconds: Maximum time to wait for mypy

    Returns:
        TypeCheckResult with compliance status
    """
    import tempfile

    start_time = time.perf_counter()

    # Create temporary directory for stub file
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Build stub file
        stub_path = _build_protocol_check_stub(
            impl_path=implementation_file,
            impl_class=impl_class_name,
            protocol_path=protocol_file,
            protocol_name=protocol_name,
            temp_dir=temp_path,
        )

        mypy_path = _find_mypy()
        use_module = mypy_path is None

        if use_module:
            cmd = ["python", "-m", "mypy"]
        else:
            cmd = [mypy_path]

        cmd.extend([
            "--no-incremental",
            "--no-error-summary",
            "--show-error-codes",
            str(stub_path),
        ])

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout_seconds,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return TypeCheckResult(
                    passed=False,
                    errors=("mypy timed out",),
                    exit_code=-1,
                    duration_ms=int((time.perf_counter() - start_time) * 1000),
                )

            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")

            # Filter out errors about the stub file path
            errors, warnings = _parse_mypy_output(stdout, stderr)

            # Clean up stub file references in error messages
            clean_errors = []
            stub_name = stub_path.name
            for err in errors:
                # Replace stub path with more meaningful context
                err = err.replace(str(stub_path), f"<{impl_class_name} as {protocol_name}>")
                clean_errors.append(err)

            exit_code = process.returncode or 0
            duration_ms = int((time.perf_counter() - start_time) * 1000)

            return TypeCheckResult(
                passed=exit_code == 0 and len(clean_errors) == 0,
                errors=tuple(clean_errors),
                warnings=warnings,
                exit_code=exit_code,
                duration_ms=duration_ms,
            )

        except FileNotFoundError:
            return TypeCheckResult(
                passed=False,
                errors=("mypy not found - install with: pip install mypy",),
                exit_code=-1,
                duration_ms=int((time.perf_counter() - start_time) * 1000),
            )
        except OSError as e:
            return TypeCheckResult(
                passed=False,
                errors=(f"Failed to run mypy: {e}",),
                exit_code=-1,
                duration_ms=int((time.perf_counter() - start_time) * 1000),
            )


def parse_protocol_errors(mypy_output: str) -> list[str]:
    """Extract Protocol-specific errors from mypy output.

    Filters mypy output to only include errors related to Protocol compliance.

    Args:
        mypy_output: Raw mypy output text

    Returns:
        List of Protocol-related error messages
    """
    protocol_errors = []

    # Patterns that indicate Protocol compliance issues
    patterns = [
        r"is not compatible with.*Protocol",
        r"missing.*method",
        r"incompatible.*signature",
        r"incompatible.*return type",
        r"incompatible.*argument type",
        r'Cannot instantiate.*Protocol',
        r"has no attribute",
    ]

    for line in mypy_output.split("\n"):
        for pattern in patterns:
            if re.search(pattern, line, re.IGNORECASE):
                protocol_errors.append(line.strip())
                break

    return protocol_errors
