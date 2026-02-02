"""Validation Gates for Adaptive Agent (RFC-042).

Gates are checkpoints in the task graph where we validate before continuing.
Key insight: Don't validate at the end — build validation INTO the task graph.

Benefits:
- Early error detection (catch issues before wasting tokens)
- Incremental confidence (each gate pass = checkpoint save)
- Smaller fix scope (only fix what's broken)
- Resume capability (restart from last passed gate)
- Parallelization (tasks before a gate can run concurrently)

Gate types:
- SYNTAX: Can Python parse it? (py_compile)
- LINT: Does it pass ruff? (ruff check --fix)
- TYPE: Does it pass type checking? (ty/mypy)
- IMPORT: Can we import it?
- INSTANTIATE: Can we create instances?
- SCHEMA: Can we create DB schema?
- SERVE: Can we start the server?
- ENDPOINT: Do endpoints respond?
- INTEGRATION: Does everything work together?
"""


from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sunwell.planning.naaru.types import Task


class GateType(Enum):
    """Types of validation gates in task decomposition."""

    # Static analysis (instant, free)
    SYNTAX = "syntax"
    """Can we parse it? (py_compile)"""

    LINT = "lint"
    """Does it pass ruff? (ruff check --fix)"""

    TYPE = "type"
    """Does it pass type checking? (ty/mypy)"""

    # Import/instantiation (fast)
    IMPORT = "import"
    """Can we import it?"""

    INSTANTIATE = "instantiate"
    """Can we create instances?"""

    # Runtime (slower but comprehensive)
    SCHEMA = "schema"
    """Can we create DB schema?"""

    SERVE = "serve"
    """Can we start the server?"""

    ENDPOINT = "endpoint"
    """Do endpoints respond?"""

    INTEGRATION = "integration"
    """Does everything work together?"""

    # Custom
    TEST = "test"
    """Run specific test(s)."""

    COMMAND = "command"
    """Run arbitrary command."""

    # Semantic verification (RFC-047)
    SEMANTIC = "semantic"
    """Deep verification — does it do the right thing?"""

    # Contract verification (RFC-034)
    CONTRACT = "contract"
    """Does implementation satisfy its Protocol contract?"""


@dataclass(frozen=True, slots=True)
class ValidationGate:
    """A checkpoint in the task graph where we validate.

    Gates are auto-detected by the planner at "runnable milestones" —
    points where we have something we can actually validate.

    Attributes:
        id: Unique gate identifier (e.g., "gate_protocols")
        gate_type: Type of validation to perform
        depends_on: Task IDs that must complete before this gate
        validation: What to check (import statement, command, etc.)
        blocks: Task IDs blocked until this gate passes
        is_runnable_milestone: Whether we can actually run something
        timeout_s: Timeout for validation in seconds
        contract_protocol: For CONTRACT gates, the Protocol name to verify against
        contract_file: For CONTRACT gates, path to file containing the Protocol
    """

    id: str
    """Unique gate identifier."""

    gate_type: GateType
    """Type of validation to perform."""

    depends_on: tuple[str, ...]
    """Task IDs that must complete before this gate."""

    validation: str
    """What to check (import statement, command, etc.)."""

    blocks: tuple[str, ...] = ()
    """Task IDs blocked until this gate passes."""

    is_runnable_milestone: bool = True
    """Whether completing depends_on gives us something we can run."""

    timeout_s: int = 30
    """Timeout for validation in seconds."""

    description: str = ""
    """Human-readable description of what this gate checks."""

    # RFC-034: Contract validation fields
    contract_protocol: str = ""
    """For CONTRACT gates: Protocol name to verify against."""

    contract_file: str = ""
    """For CONTRACT gates: Path to file containing the Protocol definition."""

    def __post_init__(self) -> None:
        # Ensure description is set
        if not self.description:
            gate_name = self.gate_type.value.capitalize()
            if self.depends_on:
                desc = f"{gate_name} check for {', '.join(self.depends_on)}"
            else:
                desc = f"{gate_name} check"
            object.__setattr__(self, "description", desc)


@dataclass(frozen=True, slots=True)
class GateStepResult:
    """Result of a single step within gate validation."""

    step: str
    """Step name (syntax, lint, type, import, etc.)."""

    passed: bool
    """Whether the step passed."""

    message: str = ""
    """Status message or error details."""

    duration_ms: int = 0
    """Duration of this step in milliseconds."""

    auto_fixed: bool = False
    """Whether ruff --fix or similar auto-fixed issues."""

    errors: tuple[dict[str, Any], ...] = ()
    """Detailed errors if any."""


@dataclass(frozen=True, slots=True)
class GateResult:
    """Result of passing through a validation gate."""

    gate: ValidationGate
    """The gate that was validated."""

    passed: bool
    """Whether all steps passed."""

    steps: tuple[GateStepResult, ...] = ()
    """Results of each validation step."""

    duration_ms: int = 0
    """Total duration in milliseconds."""

    # For resume capability
    checkpoint_hash: str = ""
    """Hash of all artifacts at this point."""

    artifacts_snapshot: tuple[tuple[str, str], ...] = ()
    """(path, content_hash) pairs for resume verification."""

    # For debugging
    commands_run: tuple[str, ...] = ()
    """Commands that were run."""

    errors: tuple[str, ...] = ()
    """Error messages if validation failed."""

    @property
    def auto_fixed_count(self) -> int:
        """Number of issues auto-fixed by tools like ruff --fix."""
        return sum(1 for s in self.steps if s.auto_fixed)


# =============================================================================
# Public Factory Functions
# =============================================================================


def create_syntax_gate(
    id: str,
    depends_on: tuple[str, ...] = (),
    description: str = "",
) -> ValidationGate:
    """Create a syntax validation gate.

    Use this for post-write validation or any syntax checking gate.

    Args:
        id: Unique gate identifier
        depends_on: Task IDs that must complete before this gate
        description: Human-readable description (auto-generated if empty)

    Returns:
        ValidationGate configured for syntax validation
    """
    return ValidationGate(
        id=id,
        gate_type=GateType.SYNTAX,
        depends_on=depends_on,
        validation="",
        description=description or "Syntax validation",
    )


def create_contract_gate(
    id: str,
    protocol_name: str,
    contract_file: str = "",
    depends_on: tuple[str, ...] = (),
    timeout_s: int = 60,
) -> ValidationGate:
    """Create a contract validation gate.

    Use this to verify an implementation satisfies a Protocol contract.

    Args:
        id: Unique gate identifier
        protocol_name: Name of the Protocol to verify against
        contract_file: Path to file containing the Protocol definition
        depends_on: Task IDs that must complete before this gate
        timeout_s: Timeout for validation (contract checks can be slower)

    Returns:
        ValidationGate configured for contract verification
    """
    return ValidationGate(
        id=id,
        gate_type=GateType.CONTRACT,
        depends_on=depends_on,
        validation=protocol_name,
        contract_protocol=protocol_name,
        contract_file=contract_file,
        timeout_s=timeout_s,
        description=f"Verify implementation satisfies {protocol_name}",
    )


# =============================================================================
# Gate Detection (stateless functions)
# =============================================================================


def detect_gates(tasks: list[Task]) -> list[ValidationGate]:
    """Find runnable milestones in task graph.

    Detects natural validation boundaries based on task patterns:
    - Protocol/Interface completion → IMPORT gate
    - Model/Schema completion → SCHEMA gate
    - Route/Endpoint completion → ENDPOINT gate
    - Test task → TEST gate
    - Entry point → INTEGRATION gate

    Args:
        tasks: List of tasks from the planner

    Returns:
        List of ValidationGates at natural checkpoints
    """
    gates: list[ValidationGate] = []

    # Pattern 1: Protocol/Interface completion
    protocols = [t for t in tasks if _is_protocol_task(t)]
    if protocols:
        gates.append(_make_import_gate(protocols, tasks))

    # Pattern 2: Model/Schema completion
    models = [t for t in tasks if _is_model_task(t)]
    if models:
        gates.append(_make_schema_gate(models, tasks))

    # Pattern 3: Route/Endpoint completion
    routes = [t for t in tasks if _is_route_task(t)]
    if routes:
        gates.append(_make_endpoint_gate(routes, tasks))

    # Pattern 4: Entry point / App factory
    entry_points = [t for t in tasks if _is_entry_point(t)]
    if entry_points:
        gates.append(_make_integration_gate(entry_points))

    # Pattern 5: Explicit test tasks
    tests = [t for t in tasks if _is_test_task(t)]
    for test_task in tests:
        gates.append(_make_test_gate(test_task))

    # Pattern 6: Contract implementation tasks (RFC-034)
    contract_tasks = [t for t in tasks if _has_contract(t)]
    for contract_task in contract_tasks:
        gates.append(_make_contract_gate(contract_task, tasks))

    return gates


def _matches_task_pattern(
    task: Task,
    keywords: tuple[str, ...],
) -> bool:
    """Check if task matches any of the given keywords.

    Searches both task.description and task.id (case-insensitive).

    Args:
        task: Task to check
        keywords: Keywords to search for

    Returns:
        True if any keyword found in description or id
    """
    desc_lower = task.description.lower()
    id_lower = task.id.lower()
    return any(kw in desc_lower or kw in id_lower for kw in keywords)


def _is_protocol_task(task: Task) -> bool:
    """Check if task produces a protocol/interface."""
    return (
        _matches_task_pattern(task, ("protocol", "interface"))
        or task.is_contract
    )


def _is_model_task(task: Task) -> bool:
    """Check if task produces a database model."""
    return _matches_task_pattern(task, ("model", "schema", "table"))


def _is_route_task(task: Task) -> bool:
    """Check if task produces routes/endpoints."""
    return _matches_task_pattern(task, ("route", "endpoint", "handler", "controller"))


def _is_entry_point(task: Task) -> bool:
    """Check if task is an entry point."""
    return _matches_task_pattern(task, ("factory", "main", "app", "entry"))


def _is_test_task(task: Task) -> bool:
    """Check if task is a test."""
    return _matches_task_pattern(task, ("test",))


def _find_blocked_tasks(
    source_tasks: list[Task],
    all_tasks: list[Task],
) -> tuple[str, ...]:
    """Find tasks blocked by dependencies on source tasks.

    A task is blocked if:
    - It's not one of the source tasks
    - It depends on any of the source tasks

    Args:
        source_tasks: Tasks that may block others
        all_tasks: All tasks to search

    Returns:
        Tuple of task IDs that are blocked
    """
    source_ids = {t.id for t in source_tasks}
    return tuple(
        t.id for t in all_tasks
        if t.id not in source_ids
        and any(src.id in t.depends_on for src in source_tasks)
    )


def _make_import_gate(
    protocols: list[Task],
    all_tasks: list[Task],
) -> ValidationGate:
    """Create an import gate for protocol tasks."""
    task_ids = tuple(t.id for t in protocols)
    blocked = _find_blocked_tasks(protocols, all_tasks)

    # Build import validation string
    imports = []
    for t in protocols:
        if t.target_path:
            module = t.target_path.replace("/", ".").replace(".py", "")
            imports.append(f"import {module}")
        else:
            imports.append(f"# Check {t.id}")

    return ValidationGate(
        id="gate_protocols",
        gate_type=GateType.IMPORT,
        depends_on=task_ids,
        validation="; ".join(imports),
        blocks=blocked,
        description="Import all protocols/interfaces",
    )


def _make_schema_gate(
    models: list[Task],
    all_tasks: list[Task],
) -> ValidationGate:
    """Create a schema gate for model tasks."""
    task_ids = tuple(t.id for t in models)
    blocked = _find_blocked_tasks(models, all_tasks)

    return ValidationGate(
        id="gate_models",
        gate_type=GateType.SCHEMA,
        depends_on=task_ids,
        validation="Base.metadata.create_all(engine)",
        blocks=blocked,
        description="Create database schema",
    )


def _make_endpoint_gate(
    routes: list[Task],
    all_tasks: list[Task],
) -> ValidationGate:
    """Create an endpoint gate for route tasks."""
    task_ids = tuple(t.id for t in routes)
    blocked = _find_blocked_tasks(routes, all_tasks)

    return ValidationGate(
        id="gate_routes",
        gate_type=GateType.ENDPOINT,
        depends_on=task_ids,
        validation="curl http://localhost:5000/health",
        blocks=blocked,
        description="Test endpoint accessibility",
    )


def _make_integration_gate(entry_points: list[Task]) -> ValidationGate:
    """Create an integration gate for entry points."""
    task_ids = tuple(t.id for t in entry_points)

    return ValidationGate(
        id="gate_integration",
        gate_type=GateType.INTEGRATION,
        depends_on=task_ids,
        validation="pytest tests/integration/",
        blocks=(),
        description="Run integration tests",
    )


def _make_test_gate(test_task: Task) -> ValidationGate:
    """Create a test gate for a specific test task."""
    return ValidationGate(
        id=f"gate_{test_task.id}",
        gate_type=GateType.TEST,
        depends_on=(test_task.id,),
        validation=test_task.verification_command or f"pytest {test_task.target_path}",
        blocks=(),
        description=f"Run {test_task.id}",
    )


def is_runnable_milestone(tasks: list[Task]) -> bool:
    """Check if completing these tasks gives us something we can run.

    Heuristic: If tasks produce importable modules, we can validate.
    Returns False for empty task list (nothing to run).
    """
    if not tasks:
        return False
    return all(
        t.target_path and t.target_path.endswith(".py")
        for t in tasks
    )


# =============================================================================
# Contract Gate Detection (RFC-034)
# =============================================================================


def _has_contract(task: Task) -> bool:
    """Check if task has a contract to verify against."""
    return bool(task.contract) and not task.is_contract


def _make_contract_gate(
    task: Task,
    all_tasks: list[Task],
) -> ValidationGate:
    """Create a contract validation gate for an implementation task.

    Args:
        task: The implementation task with a contract
        all_tasks: All tasks for finding the contract definition

    Returns:
        ValidationGate configured for contract verification
    """
    # Find the contract definition task
    contract_name = task.contract or ""
    contract_file = ""

    # Look for the task that produces this contract
    for t in all_tasks:
        if t.is_contract and contract_name in t.produces:
            contract_file = t.target_path or ""
            break
        # Also check if the contract name matches the task description
        if t.is_contract and contract_name.lower() in t.description.lower():
            contract_file = t.target_path or ""
            break

    return ValidationGate(
        id=f"gate_contract_{task.id}",
        gate_type=GateType.CONTRACT,
        depends_on=(task.id,),
        validation=contract_name,  # Protocol name to verify
        blocks=(),
        is_runnable_milestone=True,
        timeout_s=60,  # Contract verification can take longer with mypy
        description=f"Verify {task.id} implements {contract_name}",
        contract_protocol=contract_name,
        contract_file=contract_file,
    )
