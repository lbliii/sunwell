"""CLI Error Handler.

Provides unified error handling for the CLI with support for:
- Human-readable output (default)
- JSON output for machine consumption (Tauri/programmatic use)
- Context-aware recovery suggestions

This module bridges the Python error system (core/errors.py) with external
consumers like Tauri Studio.
"""

import json
import os
import shutil
import subprocess
import sys
from typing import NoReturn

from sunwell.foundation.errors import ErrorCode, SunwellError


def _detect_environment() -> dict[str, bool | str]:
    """Detect available services and environment for smarter recovery hints.

    Returns:
        Dict with environment detection results:
        - ollama_running: Whether Ollama service is available
        - has_anthropic_key: Whether ANTHROPIC_API_KEY is set
        - has_openai_key: Whether OPENAI_API_KEY is set
        - has_ollama: Whether ollama binary is installed
        - config_exists: Whether sunwell config file exists
    """
    result: dict[str, bool | str] = {
        "ollama_running": False,
        "has_anthropic_key": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "has_openai_key": bool(os.environ.get("OPENAI_API_KEY")),
        "has_ollama": shutil.which("ollama") is not None,
        "config_exists": False,
    }

    # Check if Ollama is running
    if result["has_ollama"]:
        try:
            proc = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                timeout=2,
            )
            result["ollama_running"] = proc.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass

    # Check config file
    from pathlib import Path

    config_path = Path.home() / ".config" / "sunwell" / "config.yaml"
    result["config_exists"] = config_path.exists()

    return result


def _get_context_aware_hints(error: SunwellError, env: dict[str, bool | str]) -> list[str]:
    """Generate additional context-aware recovery hints based on environment.

    Args:
        error: The error to generate hints for
        env: Environment detection results from _detect_environment()

    Returns:
        List of additional context-aware hints (may be empty)
    """
    hints: list[str] = []

    # Model provider errors
    if error.code == ErrorCode.MODEL_PROVIDER_UNAVAILABLE:
        if env.get("has_ollama") and not env.get("ollama_running"):
            hints.append("Detected: Ollama is installed but not running. Start with: ollama serve")
        if not env.get("has_anthropic_key") and not env.get("has_openai_key"):
            hints.append("No cloud API keys found. Set ANTHROPIC_API_KEY or OPENAI_API_KEY")

    elif error.code == ErrorCode.MODEL_AUTH_FAILED:
        provider = error.context.get("provider", "").lower()
        if provider == "anthropic" and not env.get("has_anthropic_key"):
            hints.append("Detected: ANTHROPIC_API_KEY environment variable not set")
        elif provider == "openai" and not env.get("has_openai_key"):
            hints.append("Detected: OPENAI_API_KEY environment variable not set")

    elif error.code == ErrorCode.MODEL_NOT_FOUND:
        if env.get("has_ollama") and env.get("ollama_running"):
            hints.append("Detected: Ollama is running. Try 'ollama list' to see available models")
        elif env.get("has_ollama") and not env.get("ollama_running"):
            hints.append("Detected: Ollama installed but not running. Start with: ollama serve")

    elif error.code == ErrorCode.CONFIG_MISSING:
        if not env.get("config_exists"):
            hints.append("Detected: No config file found. Run 'sunwell setup' to create one")

    return hints


def handle_error(
    error: SunwellError | Exception,
    json_output: bool = False,
) -> NoReturn:
    """Handle an error with optional JSON output for machine consumption.

    Args:
        error: The error to handle (SunwellError or generic Exception)
        json_output: If True, output JSON to stderr for Tauri/programmatic use

    Raises:
        SystemExit: Always exits with code 1
    """
    # Wrap generic exceptions in SunwellError
    if not isinstance(error, SunwellError):
        from sunwell.foundation.errors import ErrorCode

        error = SunwellError(
            code=ErrorCode.RUNTIME_STATE_INVALID,
            context={"detail": str(error)},
            cause=error if isinstance(error, Exception) else None,
        )

    if json_output:
        # Structured output for Tauri/programmatic use
        error_dict = error.to_dict()
        # Add cause if present (for debugging)
        if error.cause:
            error_dict["cause"] = str(error.cause)
        print(json.dumps(error_dict), file=sys.stderr)
        sys.exit(1)

    # Human-readable output for CLI
    _print_human_error(error)
    sys.exit(1)


def _print_human_error(error: SunwellError) -> None:
    """Print error in human-readable format using rich if available."""
    try:
        from rich.console import Console
        from rich.text import Text

        console = Console(stderr=True)

        # Header with error ID and category icon
        icons = {
            "model": "🤖",
            "lens": "🔍",
            "tool": "🔧",
            "validation": "✓",
            "config": "⚙️",
            "runtime": "⚡",
            "io": "📁",
        }
        icon = icons.get(error.category, "❌")

        # Build error message
        header = Text()
        header.append(f"{icon} ", style="bold")
        header.append(f"{error.error_id}", style="bold red")
        header.append(f" {error.message}")

        console.print(header)

        # Recovery hints (standard + context-aware)
        all_hints = list(error.recovery_hints)

        # Add context-aware hints
        try:
            env = _detect_environment()
            context_hints = _get_context_aware_hints(error, env)
            # Prepend context hints as they're more specific
            all_hints = context_hints + all_hints
        except Exception:
            # Don't let environment detection break error handling
            pass

        if all_hints:
            console.print("\n[bold]What you can do:[/]")
            for i, hint in enumerate(all_hints, 1):
                # Context-aware hints are dimmer
                if hint.startswith("Detected:"):
                    console.print(f"  [dim]{hint}[/]")
                else:
                    console.print(f"  {i}. {hint}")

    except ImportError:
        # Fallback without rich
        print(f"[{error.error_id}] {error.message}", file=sys.stderr)
        if error.recovery_hints:
            print("\nWhat you can do:", file=sys.stderr)
            for i, hint in enumerate(error.recovery_hints, 1):
                print(f"  {i}. {hint}", file=sys.stderr)


def format_error_for_json(error: SunwellError | Exception) -> str:
    """Format an error as JSON string.

    Useful for returning errors from functions that will be parsed by Tauri.

    Args:
        error: The error to format

    Returns:
        JSON string representation of the error
    """
    if not isinstance(error, SunwellError):
        from sunwell.foundation.errors import ErrorCode

        error = SunwellError(
            code=ErrorCode.RUNTIME_STATE_INVALID,
            context={"detail": str(error)},
            cause=error if isinstance(error, Exception) else None,
        )

    error_dict = error.to_dict()
    if error.cause:
        error_dict["cause"] = str(error.cause)

    return json.dumps(error_dict)


def parse_error_from_json(json_str: str) -> SunwellError | None:
    """Parse a SunwellError from JSON string.

    Args:
        json_str: JSON string representation of an error

    Returns:
        SunwellError if parsing succeeded, None otherwise
    """
    try:
        data = json.loads(json_str)

        # Must have required fields
        if not all(k in data for k in ("error_id", "code", "message")):
            return None

        from sunwell.foundation.errors import ErrorCode

        # Try to get ErrorCode from code
        try:
            code = ErrorCode(data["code"])
        except ValueError:
            # Unknown code, use a fallback
            code = ErrorCode.RUNTIME_STATE_INVALID

        return SunwellError(
            code=code,
            context=data.get("context", {}),
        )
    except (json.JSONDecodeError, KeyError):
        return None
