"""Journey type definitions for E2E behavioral testing.

Defines the schema for journey YAML files that describe test scenarios:
- SingleTurnJourney: One input, one expected behavior
- MultiTurnJourney: Multiple turns with conversation state
- Expectation: What behaviors to check
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Literal

import yaml


class JourneyType(str, Enum):
    """Type of journey test."""

    SINGLE_TURN = "single_turn"
    """Single input → single response."""

    MULTI_TURN = "multi_turn"
    """Multiple conversation turns with state."""


@dataclass(frozen=True, slots=True)
class FileSetup:
    """A file to create during setup."""

    path: str
    """Relative path within workspace."""

    content: str
    """File content."""


@dataclass(frozen=True, slots=True)
class Setup:
    """Journey setup configuration."""

    workspace: str = "/tmp/sunwell-test-{uuid}"
    """Workspace path template. {uuid} is replaced with unique ID."""

    env: dict[str, str] = field(default_factory=dict)
    """Environment variables to set."""

    files: tuple[FileSetup, ...] = ()
    """Files to create before running."""


@dataclass(frozen=True, slots=True)
class SignalExpectation:
    """Expected signal values with optional ranges.

    All signal fields support tuple for multiple acceptable values.
    """

    needs_tools: tuple[str, ...] | str | None = None
    """Expected needs_tools signal. Can be single or tuple for alternatives."""

    complexity: tuple[str, ...] | str | None = None
    """Expected complexity. Can be single value or tuple for alternatives."""

    is_ambiguous: tuple[str, ...] | str | None = None
    """Expected is_ambiguous signal. Can be single or tuple for alternatives."""

    is_dangerous: tuple[str, ...] | str | None = None
    """Expected is_dangerous signal. Can be single or tuple for alternatives."""

    is_epic: tuple[str, ...] | str | None = None
    """Expected is_epic signal. Can be single or tuple for alternatives."""

    domain: tuple[str, ...] | str | None = None
    """Expected domain classification. Can be single or tuple for alternatives."""


@dataclass(frozen=True, slots=True)
class ToolExpectation:
    """Expected tool call with pattern matching."""

    name: str
    """Tool name (e.g., "write_file", "shell")."""

    args_contain: dict[str, Any] = field(default_factory=dict)
    """Arguments that must be present (supports glob patterns for strings)."""


@dataclass(frozen=True, slots=True)
class FileExpectation:
    """Expected file state after execution."""

    pattern: str | None = None
    """Glob pattern for file path (e.g., "*.py")."""

    path: str | None = None
    """Exact file path (relative to workspace)."""

    contains: tuple[str, ...] = ()
    """Strings that must be present in file content."""

    not_contains: tuple[str, ...] = ()
    """Strings that must NOT be present in file content."""


@dataclass(frozen=True, slots=True)
class Expectation:
    """Expected behaviors for a turn or journey."""

    intent: str | tuple[str, ...] | None = None
    """Expected intent: TASK, CONVERSATION, COMMAND, or tuple for alternatives."""

    signals: SignalExpectation | None = None
    """Expected signal values."""

    tools_called: tuple[ToolExpectation, ...] = ()
    """Expected tool calls (order doesn't matter)."""

    tools_called_any: tuple[str, ...] = ()
    """At least ONE of these tools must be called (flexible matching)."""

    tools_called_min: int = 0
    """Minimum total tool calls expected."""

    tools_not_called: tuple[str, ...] = ()
    """Tools that must NOT be called."""

    files_created: tuple[FileExpectation, ...] = ()
    """Files expected to be created."""

    files_modified: tuple[FileExpectation, ...] = ()
    """Files expected to be modified."""

    output_contains: tuple[str, ...] = ()
    """Patterns that must be in output (case-insensitive substring match)."""

    output_matches: tuple[str, ...] = ()
    """Regex patterns that must match in output."""

    output_not_contains: tuple[str, ...] = ()
    """Patterns that must NOT be in output."""

    # Observability expectations
    routing_strategy: str | tuple[str, ...] | None = None
    """Expected routing strategy: "vortex", "interference", "single_shot"."""

    validation_must_pass: bool | None = None
    """If True, all validation gates must pass."""

    no_reliability_issues: bool | None = None
    """If True, no reliability warnings/hallucinations allowed."""

    max_tokens: int | None = None
    """Maximum token budget for the turn."""


@dataclass(frozen=True, slots=True)
class Turn:
    """A single turn in a multi-turn journey."""

    input: str
    """User input for this turn."""

    expect: Expectation
    """Expected behaviors after this turn."""


@dataclass(slots=True)
class SingleTurnJourney:
    """A single-turn test journey."""

    id: str
    """Unique journey identifier."""

    input: str
    """User input to test."""

    expect: Expectation
    """Expected behaviors."""

    setup: Setup = field(default_factory=Setup)
    """Setup configuration."""

    timeout_seconds: int = 300
    """Maximum execution time (increased for slower but more capable models)."""

    allow_flaky_retry: int = 0
    """Number of retries on behavioral failure."""

    description: str = ""
    """Human-readable description."""

    tags: tuple[str, ...] = ()
    """Tags for filtering (e.g., "agentic", "qa", "memory")."""

    @property
    def journey_type(self) -> JourneyType:
        return JourneyType.SINGLE_TURN


@dataclass(slots=True)
class MultiTurnJourney:
    """A multi-turn conversation test journey."""

    id: str
    """Unique journey identifier."""

    turns: tuple[Turn, ...]
    """Sequence of conversation turns."""

    setup: Setup = field(default_factory=Setup)
    """Setup configuration."""

    timeout_seconds: int = 300
    """Maximum total execution time."""

    allow_flaky_retry: int = 0
    """Number of retries on behavioral failure."""

    description: str = ""
    """Human-readable description."""

    tags: tuple[str, ...] = ()
    """Tags for filtering."""

    @property
    def journey_type(self) -> JourneyType:
        return JourneyType.MULTI_TURN


# Type alias for any journey
Journey = SingleTurnJourney | MultiTurnJourney


def _parse_setup(data: dict[str, Any]) -> Setup:
    """Parse setup section from YAML."""
    if not data:
        return Setup()

    files = []
    for f in data.get("files", []):
        files.append(FileSetup(path=f["path"], content=f.get("content", "")))

    return Setup(
        workspace=data.get("workspace", "/tmp/sunwell-test-{uuid}"),
        env=data.get("env", {}),
        files=tuple(files),
    )


def _parse_signal_expectation(data: dict[str, Any] | None) -> SignalExpectation | None:
    """Parse signal expectations from YAML."""
    if not data:
        return None

    def normalize_signal(value: Any) -> tuple[str, ...] | str | None:
        """Convert list to tuple for signal values."""
        if value is None:
            return None
        if isinstance(value, list):
            return tuple(value)
        return value

    return SignalExpectation(
        needs_tools=normalize_signal(data.get("needs_tools")),
        complexity=normalize_signal(data.get("complexity")),
        is_ambiguous=normalize_signal(data.get("is_ambiguous")),
        is_dangerous=normalize_signal(data.get("is_dangerous")),
        is_epic=normalize_signal(data.get("is_epic")),
        domain=normalize_signal(data.get("domain")),
    )


def _parse_tool_expectations(data: list[dict[str, Any]]) -> tuple[ToolExpectation, ...]:
    """Parse tool call expectations from YAML."""
    tools = []
    for t in data:
        tools.append(ToolExpectation(
            name=t["name"],
            args_contain=t.get("args_contain", {}),
        ))
    return tuple(tools)


def _parse_file_expectations(data: list[dict[str, Any]]) -> tuple[FileExpectation, ...]:
    """Parse file expectations from YAML."""
    files = []
    for f in data:
        contains = f.get("contains", [])
        if isinstance(contains, str):
            contains = [contains]
        not_contains = f.get("not_contains", [])
        if isinstance(not_contains, str):
            not_contains = [not_contains]

        files.append(FileExpectation(
            pattern=f.get("pattern"),
            path=f.get("path"),
            contains=tuple(contains),
            not_contains=tuple(not_contains),
        ))
    return tuple(files)


def _parse_expectation(data: dict[str, Any]) -> Expectation:
    """Parse expectation from YAML."""
    intent = data.get("intent")
    if isinstance(intent, list):
        intent = tuple(intent)

    output_contains = data.get("output_contains", [])
    if isinstance(output_contains, str):
        output_contains = [output_contains]

    output_matches = data.get("output_matches", [])
    if isinstance(output_matches, str):
        output_matches = [output_matches]

    output_not_contains = data.get("output_not_contains", [])
    if isinstance(output_not_contains, str):
        output_not_contains = [output_not_contains]

    tools_not_called = data.get("tools_not_called", [])
    if isinstance(tools_not_called, str):
        tools_not_called = [tools_not_called]

    tools_called_any = data.get("tools_called_any", [])
    if isinstance(tools_called_any, str):
        tools_called_any = [tools_called_any]

    # Parse routing strategy (single or tuple)
    routing_strategy = data.get("routing_strategy")
    if isinstance(routing_strategy, list):
        routing_strategy = tuple(routing_strategy)

    return Expectation(
        intent=intent,
        signals=_parse_signal_expectation(data.get("signals")),
        tools_called=_parse_tool_expectations(data.get("tools_called", [])),
        tools_called_any=tuple(tools_called_any),
        tools_called_min=data.get("tools_called_min", 0),
        tools_not_called=tuple(tools_not_called),
        files_created=_parse_file_expectations(data.get("files_created", [])),
        files_modified=_parse_file_expectations(data.get("files_modified", [])),
        output_contains=tuple(output_contains),
        output_matches=tuple(output_matches),
        output_not_contains=tuple(output_not_contains),
        # Observability expectations
        routing_strategy=routing_strategy,
        validation_must_pass=data.get("validation_must_pass"),
        no_reliability_issues=data.get("no_reliability_issues"),
        max_tokens=data.get("max_tokens"),
    )


def _parse_turns(data: list[dict[str, Any]]) -> tuple[Turn, ...]:
    """Parse conversation turns from YAML."""
    turns = []
    for t in data:
        turns.append(Turn(
            input=t["input"],
            expect=_parse_expectation(t.get("expect", {})),
        ))
    return tuple(turns)


def load_journey(path: str | Path) -> Journey:
    """Load a journey from YAML file.

    Args:
        path: Path to journey YAML file.

    Returns:
        SingleTurnJourney or MultiTurnJourney.

    Raises:
        ValueError: If journey format is invalid.
    """
    path = Path(path)
    with open(path) as f:
        data = yaml.safe_load(f)

    if "journey" not in data:
        msg = f"Missing 'journey' key in {path}"
        raise ValueError(msg)

    j = data["journey"]
    journey_id = j.get("id", path.stem)
    journey_type = j.get("type", "single_turn")
    setup = _parse_setup(j.get("setup", {}))

    tags = j.get("tags", [])
    if isinstance(tags, str):
        tags = [tags]

    if journey_type == "multi_turn":
        if "turns" not in j:
            msg = f"Multi-turn journey {journey_id} missing 'turns'"
            raise ValueError(msg)

        return MultiTurnJourney(
            id=journey_id,
            turns=_parse_turns(j["turns"]),
            setup=setup,
            timeout_seconds=j.get("timeout_seconds", 300),
            allow_flaky_retry=j.get("allow_flaky_retry", 0),
            description=j.get("description", ""),
            tags=tuple(tags),
        )
    else:
        if "input" not in j:
            msg = f"Single-turn journey {journey_id} missing 'input'"
            raise ValueError(msg)

        return SingleTurnJourney(
            id=journey_id,
            input=j["input"],
            expect=_parse_expectation(j.get("expect", {})),
            setup=setup,
            timeout_seconds=j.get("timeout_seconds", 300),
            allow_flaky_retry=j.get("allow_flaky_retry", 0),
            description=j.get("description", ""),
            tags=tuple(tags),
        )


def load_journeys_from_directory(
    directory: str | Path,
    pattern: str = "**/*.yaml",
) -> list[Journey]:
    """Load all journeys from a directory.

    Args:
        directory: Directory containing journey YAML files.
        pattern: Glob pattern for finding journey files.

    Returns:
        List of loaded journeys.
    """
    directory = Path(directory)
    journeys = []

    for path in directory.glob(pattern):
        try:
            journeys.append(load_journey(path))
        except Exception as e:
            # Log but continue loading other journeys
            import logging
            logging.getLogger(__name__).warning(
                "Failed to load journey %s: %s", path, e
            )

    return journeys
