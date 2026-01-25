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


from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sunwell.naaru.types import Task


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

    def __post_init__(self):
        # Ensure description is set
        if not self.description:
            object.__setattr__(
                self,
                "description",
                f"{self.gate_type.value.capitalize()} check for {', '.join(self.depends_on)}",
            )


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

    return gates


def _is_protocol_task(task: Task) -> bool:
    """Check if task produces a protocol/interface."""
    desc_lower = task.description.lower()
    id_lower = task.id.lower()

    return (
        "protocol" in desc_lower
        or "protocol" in id_lower
        or "interface" in desc_lower
        or task.is_contract
    )


def _is_model_task(task: Task) -> bool:
    """Check if task produces a database model."""
    desc_lower = task.description.lower()
    id_lower = task.id.lower()

    return (
        "model" in desc_lower
        or "model" in id_lower
        or "schema" in desc_lower
        or "table" in desc_lower
    )


def _is_route_task(task: Task) -> bool:
    """Check if task produces routes/endpoints."""
    desc_lower = task.description.lower()
    id_lower = task.id.lower()

    return (
        "route" in desc_lower
        or "route" in id_lower
        or "endpoint" in desc_lower
        or "handler" in desc_lower
        or "controller" in desc_lower
    )


def _is_entry_point(task: Task) -> bool:
    """Check if task is an entry point."""
    desc_lower = task.description.lower()
    id_lower = task.id.lower()

    return (
        "factory" in desc_lower
        or "factory" in id_lower
        or "main" in id_lower
        or "app" in id_lower
        or "entry" in desc_lower
    )


def _is_test_task(task: Task) -> bool:
    """Check if task is a test."""
    desc_lower = task.description.lower()
    id_lower = task.id.lower()

    return "test" in desc_lower or "test" in id_lower


def _make_import_gate(
    protocols: list[Task],
    all_tasks: list[Task],
) -> ValidationGate:
    """Create an import gate for protocol tasks."""
    task_ids = tuple(t.id for t in protocols)

    # Find tasks that depend on these protocols
    blocked = tuple(
        t.id for t in all_tasks
        if t.id not in task_ids
        and any(p.id in t.depends_on for p in protocols)
    )

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

    # Find tasks that depend on models
    blocked = tuple(
        t.id for t in all_tasks
        if t.id not in task_ids
        and any(m.id in t.depends_on for m in models)
    )

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

    # Find tasks that depend on routes
    blocked = tuple(
        t.id for t in all_tasks
        if t.id not in task_ids
        and any(r.id in t.depends_on for r in routes)
    )

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
    """
    return all(
        t.target_path and t.target_path.endswith(".py")
        for t in tasks
    )
