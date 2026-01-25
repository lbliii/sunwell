"""Run Analyzer — AI-powered project run detection (RFC-066).

This module analyzes projects to determine how to run them in development mode.
It uses AI analysis with a safety-validated command allowlist.

Key features:
- AI-powered framework and tooling detection
- Command safety validation (allowlist + blocklist)
- Prerequisite detection (missing dependencies)
- JSON output for Rust bridge integration

Example:
    >>> from sunwell.tools.run_analyzer import analyze_project_for_run, validate_command_safety
    >>> analysis = await analyze_project_for_run(Path("my-project"), model)
    >>> print(analysis.command)  # "npm run dev"
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from sunwell.models import ModelProtocol

# =============================================================================
# Types
# =============================================================================


@dataclass(frozen=True, slots=True)
class RunCommand:
    """Alternative run command."""

    command: str
    description: str
    when: str | None = None

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        result = {"command": self.command, "description": self.description}
        if self.when:
            result["when"] = self.when
        return result


@dataclass(frozen=True, slots=True)
class Prerequisite:
    """A prerequisite that must be satisfied before running."""

    description: str
    command: str
    satisfied: bool
    required: bool

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "description": self.description,
            "command": self.command,
            "satisfied": self.satisfied,
            "required": self.required,
        }


@dataclass(frozen=True, slots=True)
class RunAnalysis:
    """Result of analyzing how to run a project."""

    project_type: str
    language: str
    command: str
    command_description: str
    confidence: Literal["high", "medium", "low"]
    framework: str | None = None
    working_dir: str | None = None
    alternatives: tuple[RunCommand, ...] = ()
    prerequisites: tuple[Prerequisite, ...] = ()
    expected_port: int | None = None
    expected_url: str | None = None

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict (camelCase for JS interop)."""
        result = {
            "projectType": self.project_type,
            "language": self.language,
            "command": self.command,
            "commandDescription": self.command_description,
            "confidence": self.confidence,
            "framework": self.framework,
            "workingDir": self.working_dir,
            "alternatives": [a.to_dict() for a in self.alternatives],
            "prerequisites": [p.to_dict() for p in self.prerequisites],
            "expectedPort": self.expected_port,
            "expectedUrl": self.expected_url,
            "source": "ai",  # Always AI when coming from this module
            "fromCache": False,
            "userSaved": False,
        }
        return result


# =============================================================================
# Command Safety Validation
# =============================================================================

# Safe command prefixes (binaries that are allowed to execute)
SAFE_COMMAND_PREFIXES: frozenset[str] = frozenset(
    {
        # Node.js ecosystem
        "npm",
        "npx",
        "yarn",
        "pnpm",
        "bun",
        # Python ecosystem
        "python",
        "python3",
        "pip",
        "uv",
        "poetry",
        "pdm",
        # Rust
        "cargo",
        "rustc",
        # Go
        "go",
        # Build tools
        "make",
        "cmake",
        "gradle",
        "mvn",
        # Containers
        "docker",
        "docker-compose",
        "podman",
        # Ruby
        "ruby",
        "bundle",
        "rails",
        # PHP
        "php",
        "composer",
        # .NET
        "dotnet",
        # Elixir
        "mix",
        "elixir",
        # Java
        "java",
        "javac",
    }
)

# Dangerous patterns that should never appear in commands
DANGEROUS_PATTERNS: tuple[str, ...] = (
    "rm ",
    "rm\t",
    "rmdir",
    "sudo",
    "su ",
    "&&",
    "||",
    ";",
    "|",
    ">",
    "<",
    ">>",
    "<<",
    "`",
    "$(",
    "${",
    "eval",
    "exec",
    "source",
    "curl ",
    "wget ",
    "chmod",
    "chown",
    "kill",
    "pkill",
)


class CommandValidationError(ValueError):
    """Raised when a command fails safety validation."""


def validate_command_safety(command: str) -> None:
    """Validate command against allowlist. Raises CommandValidationError if unsafe.

    Args:
        command: The command to validate

    Raises:
        CommandValidationError: If the command is empty, not in allowlist,
            or contains dangerous patterns
    """
    if not command or not command.strip():
        raise CommandValidationError("Empty command")

    parts = command.strip().split()
    if not parts:
        raise CommandValidationError("Empty command")

    binary = parts[0]

    # Check if binary is in allowlist
    if binary not in SAFE_COMMAND_PREFIXES:
        raise CommandValidationError(f"Command '{binary}' not in allowlist")

    # Check for dangerous patterns
    command_lower = command.lower()
    for pattern in DANGEROUS_PATTERNS:
        if pattern in command_lower:
            raise CommandValidationError(f"Command contains dangerous pattern: {pattern.strip()}")


# =============================================================================
# Project Context Gathering
# =============================================================================


def gather_project_context(path: Path) -> dict:
    """Collect relevant files for analysis.

    Args:
        path: Path to the project root

    Returns:
        Dictionary with project context for AI analysis
    """
    context: dict = {
        "files": [],
        "has_node_modules": (path / "node_modules").exists(),
        "has_venv": (path / "venv").exists() or (path / ".venv").exists(),
        "has_target": (path / "target").exists(),  # Rust/Cargo
    }

    # List top-level files
    try:
        for item in path.iterdir():
            if item.is_file() and not item.name.startswith("."):
                context["files"].append(item.name)
            elif item.is_dir() and not item.name.startswith("."):
                context["files"].append(f"{item.name}/")
    except PermissionError:
        pass

    # Key files to include content from
    key_files = [
        "package.json",
        "Cargo.toml",
        "pyproject.toml",
        "requirements.txt",
        "Makefile",
        "docker-compose.yml",
        "docker-compose.yaml",
        "README.md",
        "main.py",
        "app.py",
        "index.js",
        "index.ts",
        "src/main.rs",
        "src/lib.rs",
        "manage.py",  # Django
        "Gemfile",  # Ruby
        "composer.json",  # PHP
        "mix.exs",  # Elixir
        "build.gradle",  # Gradle
        "pom.xml",  # Maven
    ]

    for filename in key_files:
        file_path = path / filename
        if file_path.exists() and file_path.is_file():
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                # Limit size to avoid overwhelming the model
                context[filename] = content[:5000]
            except (PermissionError, OSError):
                pass

    return context


# =============================================================================
# AI Analysis
# =============================================================================

ANALYSIS_PROMPT = """You are analyzing a software project to determine how to run it in dev mode.

PROJECT CONTEXT:
Files in directory: {files}
Has node_modules: {has_node_modules}
Has venv/.venv: {has_venv}
Has target (Rust): {has_target}

{file_contents}

Analyze this project and determine:

1. PROJECT TYPE: What kind of application is this? (e.g., "React web app", "Python CLI")

2. FRAMEWORK: What framework/tooling does it use? (e.g., "Vite + React", "FastAPI", "actix-web")

3. RUN COMMAND: What's the primary command to start it in development mode?
   - For Node.js: Check package.json scripts (dev, start, serve)
   - For Python: Check for main.py, app.py, or framework entry points
   - For Rust: Check Cargo.toml for binary targets

4. PREREQUISITES: What needs to be set up first?
   - Dependencies installed? (node_modules, venv, target)
   - Environment variables? (.env file)
   - Database/services running?

5. EXPECTED URL: If it's a web app, what URL will it be available at?

6. CONFIDENCE: How confident are you?
   - high: Clear signals (package.json scripts, standard framework)
   - medium: Some ambiguity but reasonable guess
   - low: Uncertain, user should verify

IMPORTANT: Only suggest commands from this allowlist:
- npm, npx, yarn, pnpm, bun (Node.js)
- python, python3, pip, uv, poetry, pdm (Python)
- cargo, rustc (Rust)
- go (Go)
- make (Makefiles)
- docker, docker-compose, podman (Containers)
- ruby, bundle, rails (Ruby)
- php, composer (PHP)
- dotnet (.NET)
- mix, elixir (Elixir)
- java, gradle, mvn (Java)

Output ONLY valid JSON (no markdown, no explanation):
{{
  "project_type": "...",
  "framework": "..." or null,
  "language": "...",
  "command": "...",
  "command_description": "...",
  "working_dir": "..." or null,
  "alternatives": [{{"command": "...", "description": "...", "when": "..."}}],
  "prerequisites": [{{"description": "...", "command": "...", "satisfied": bool}}],
  "expected_port": ... or null,
  "expected_url": "..." or null,
  "confidence": "high" | "medium" | "low"
}}"""


def _build_analysis_prompt(context: dict) -> str:
    """Build the analysis prompt from project context."""
    # Format file contents
    file_contents_parts = []
    skip_keys = ("files", "has_node_modules", "has_venv", "has_target")
    for key, value in context.items():
        if key not in skip_keys and isinstance(value, str):
            file_contents_parts.append(f"--- {key} ---\n{value[:2000]}\n")

    file_contents = "\n".join(file_contents_parts) or "(no key files found)"

    return ANALYSIS_PROMPT.format(
        files=", ".join(context.get("files", [])),
        has_node_modules=context.get("has_node_modules", False),
        has_venv=context.get("has_venv", False),
        has_target=context.get("has_target", False),
        file_contents=file_contents,
    )


def _parse_run_analysis(response: str, context: dict) -> RunAnalysis:
    """Parse AI response into RunAnalysis."""
    # Try to extract JSON from response
    text = response.strip()

    # Handle markdown code blocks
    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        text = text[start:end].strip()
    elif "```" in text:
        start = text.find("```") + 3
        end = text.find("```", start)
        text = text[start:end].strip()

    data = json.loads(text)

    # Parse alternatives
    alternatives = tuple(
        RunCommand(
            command=alt.get("command", ""),
            description=alt.get("description", ""),
            when=alt.get("when"),
        )
        for alt in data.get("alternatives", [])
    )

    # Parse prerequisites
    prerequisites = tuple(
        Prerequisite(
            description=prereq.get("description", ""),
            command=prereq.get("command", ""),
            satisfied=prereq.get("satisfied", False),
            required=prereq.get("required", True),
        )
        for prereq in data.get("prerequisites", [])
    )

    # Parse expected_port - AI sometimes returns string instead of int
    raw_port = data.get("expected_port")
    expected_port: int | None = None
    if raw_port is not None:
        try:
            expected_port = int(raw_port)
        except (ValueError, TypeError):
            pass  # Invalid port, leave as None

    return RunAnalysis(
        project_type=data.get("project_type", "Unknown project"),
        framework=data.get("framework"),
        language=data.get("language", "unknown"),
        command=data.get("command", ""),
        command_description=data.get("command_description", ""),
        working_dir=data.get("working_dir"),
        alternatives=alternatives,
        prerequisites=prerequisites,
        expected_port=expected_port,
        expected_url=data.get("expected_url"),
        confidence=data.get("confidence", "low"),
    )


async def analyze_project_for_run(path: Path, model: ModelProtocol) -> RunAnalysis:
    """Use AI to analyze how to run a project.

    Args:
        path: Path to the project root
        model: Model to use for analysis

    Returns:
        RunAnalysis with detected configuration

    Raises:
        CommandValidationError: If the detected command fails safety validation
        json.JSONDecodeError: If AI response isn't valid JSON
    """
    from sunwell.models import GenerateOptions

    # Gather context
    context = gather_project_context(path)

    # Build and send prompt
    prompt = _build_analysis_prompt(context)
    result = await model.generate(
        prompt,
        options=GenerateOptions(temperature=0.1, max_tokens=1500),
    )

    # Parse response
    analysis = _parse_run_analysis(result.text, context)

    # Validate command safety
    validate_command_safety(analysis.command)

    # Validate alternatives too
    for alt in analysis.alternatives:
        validate_command_safety(alt.command)

    return analysis


# =============================================================================
# CLI Entry Point (for Rust subprocess bridge)
# =============================================================================


async def _main() -> None:
    """Entry point for subprocess invocation from Rust."""
    import argparse

    parser = argparse.ArgumentParser(description="Analyze project for run command")
    parser.add_argument("--path", required=True, help="Path to project")
    parser.add_argument("--model", default="ollama", help="Model provider (ollama, anthropic)")
    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        print(json.dumps({"error": f"Path does not exist: {path}"}), file=sys.stderr)
        sys.exit(1)

    # Import model based on provider
    if args.model == "ollama":
        from sunwell.models import OllamaModel

        model = OllamaModel()
    elif args.model == "anthropic":
        from sunwell.models import AnthropicModel

        model = AnthropicModel()
    else:
        print(json.dumps({"error": f"Unknown model provider: {args.model}"}), file=sys.stderr)
        sys.exit(1)

    try:
        result = await analyze_project_for_run(path, model)
        print(json.dumps(result.to_dict()))
    except CommandValidationError as e:
        print(json.dumps({"error": f"Command validation failed: {e}"}), file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Failed to parse AI response: {e}"}), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    import asyncio

    asyncio.run(_main())
