"""Artifact-first planning model for RFC-036.

This module implements the core artifact model for declarative, dependency-driven
planning. Instead of decomposing goals into steps, we identify what artifacts
must exist when the goal is complete and let dependency resolution determine
execution order.

Key insight: Planning is a DAG problem. Instead of decomposing from trunk (goal)
to leaves (tasks), we identify all leaves (artifacts) and let them converge
upward to the trunk (completed goal).

Example:
    >>> spec = ArtifactSpec(
    ...     id="UserProtocol",
    ...     description="Protocol defining User entity",
    ...     contract="Protocol with fields: id, email, password_hash",
    ...     produces_file="src/protocols/user.py",
    ... )
    >>> graph = ArtifactGraph()
    >>> graph.add(spec)
    >>> order = graph.topological_sort()
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

from sunwell.naaru.types import Task, TaskMode, TaskStatus

# =============================================================================
# Exceptions
# =============================================================================


class ArtifactError(Exception):
    """Base exception for artifact-related errors."""

    pass


class CyclicDependencyError(ArtifactError):
    """Raised when artifact dependencies form a cycle."""

    def __init__(self, cycle: list[str]) -> None:
        self.cycle = cycle
        cycle_str = " → ".join(cycle + [cycle[0]])
        super().__init__(f"Cyclic dependency detected: {cycle_str}")


class GraphExplosionError(ArtifactError):
    """Raised when discovery produces too many artifacts."""

    def __init__(self, count: int, limit: int) -> None:
        self.count = count
        self.limit = limit
        super().__init__(
            f"Discovery produced {count} artifacts (max: {limit}). "
            f"Consider breaking goal into smaller subgoals."
        )


class MissingDependencyError(ArtifactError):
    """Raised when an artifact requires a non-existent artifact."""

    def __init__(self, artifact_id: str, missing_ids: set[str]) -> None:
        self.artifact_id = artifact_id
        self.missing_ids = missing_ids
        super().__init__(
            f"Artifact '{artifact_id}' requires non-existent artifacts: {missing_ids}"
        )


class DiscoveryFailedError(ArtifactError):
    """Raised when artifact discovery fails after retries."""

    pass


class ArtifactCreationError(ArtifactError):
    """Raised when an artifact cannot be created."""

    def __init__(self, artifact_id: str, cause: Exception) -> None:
        self.artifact_id = artifact_id
        self.cause = cause
        super().__init__(f"Failed to create artifact '{artifact_id}': {cause}")


# =============================================================================
# Operational Limits (Decision 5)
# =============================================================================


@dataclass(frozen=True, slots=True)
class ArtifactLimits:
    """Operational limits for artifact-first planning.

    These limits prevent runaway graphs and infinite expansion.
    Users can override with --force or config settings.
    """

    max_artifacts: int = 50
    """Maximum artifacts per discovery. Exceeding requires --force."""

    max_discovery_rounds: int = 5
    """Maximum dynamic discovery iterations before forced stop."""

    max_depth: int = 10
    """Maximum dependency chain depth. Deeper suggests poor decomposition."""

    discovery_timeout_seconds: float = 60.0
    """Timeout for a single discovery LLM call."""

    execution_timeout_seconds: float = 1800.0
    """Timeout for full graph execution (30 minutes)."""


DEFAULT_LIMITS = ArtifactLimits()


# =============================================================================
# ArtifactSpec: The Core Model
# =============================================================================


@dataclass(frozen=True, slots=True)
class ArtifactSpec:
    """Specification for an artifact that must exist.

    An artifact has an identity and a contract (specification).
    The contract defines what the artifact must provide/satisfy.

    Think of it like a Protocol/Interface in code:
    - The spec is the CONTRACT (what it must do)
    - The artifact is the IMPLEMENTATION (the actual file/content)

    Attributes:
        id: Unique identifier (e.g., "UserProtocol", "Chapter1", "Hypothesis_A")
        description: Human-readable description of this artifact
        contract: What this artifact must satisfy (type signature, outline, spec)
        produces_file: Optional file path this artifact creates/modifies
        requires: Other artifact IDs that must exist before this can be created
        domain_type: RFC-035 schema type (e.g., "character", "protocol")
        metadata: Additional domain-specific data

    Example:
        >>> spec = ArtifactSpec(
        ...     id="UserProtocol",
        ...     description="Protocol defining User entity",
        ...     contract="Protocol with fields: id (UUID), email (str), password_hash (str)",
        ...     produces_file="src/protocols/user.py",
        ...     requires=frozenset(),  # No dependencies - this is a leaf
        ... )
    """

    id: str
    """Unique identifier: 'UserProtocol', 'Chapter1', 'Hypothesis_A'."""

    description: str
    """Human-readable: 'Protocol defining User with id, email, password_hash'."""

    contract: str
    """What this artifact must satisfy.

    For code: type signature, protocol definition
    For prose: outline, requirements
    For research: hypothesis statement, methodology spec
    """

    produces_file: str | None = None
    """File path this artifact creates/modifies."""

    requires: frozenset[str] = field(default_factory=frozenset)
    """Other artifact IDs that must exist before this can be created."""

    domain_type: str | None = None
    """RFC-035 schema type: 'character', 'protocol', 'hypothesis', etc."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Additional domain-specific data."""

    def is_leaf(self) -> bool:
        """Check if this artifact has no dependencies (is a leaf)."""
        return len(self.requires) == 0

    def is_contract(self) -> bool:
        """Check if this artifact defines an interface.

        Contract artifacts:
        - Have domain_type in ("protocol", "interface", "schema", "spec")
        - OR have no requirements (leaves are often contracts)
        """
        contract_types = ("protocol", "interface", "schema", "spec", "outline")
        return self.domain_type in contract_types or self.is_leaf()

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "id": self.id,
            "description": self.description,
            "contract": self.contract,
            "produces_file": self.produces_file,
            "requires": list(self.requires),
            "domain_type": self.domain_type,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ArtifactSpec:
        """Create from dict."""
        return cls(
            id=data["id"],
            description=data["description"],
            contract=data["contract"],
            produces_file=data.get("produces_file"),
            requires=frozenset(data.get("requires", [])),
            domain_type=data.get("domain_type"),
            metadata=data.get("metadata", {}),
        )


# =============================================================================
# Verification Results
# =============================================================================


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """Result of verifying an artifact against its contract.

    Attributes:
        passed: Whether the artifact satisfies its contract
        reason: Explanation of the result
        gaps: List of missing or incorrect elements (if any)
        confidence: Confidence score (0.0 - 1.0)
    """

    passed: bool
    reason: str
    gaps: tuple[str, ...] = ()
    confidence: float = 1.0


# =============================================================================
# ArtifactGraph: Dependency Management
# =============================================================================


@dataclass
class ArtifactGraph:
    """Directed acyclic graph of artifacts with dependency resolution.

    The graph tracks:
    - All artifacts and their specifications
    - Dependency relationships (requires)
    - Execution waves (parallel groups)

    Execution proceeds from leaves (no dependencies) to roots
    (nothing depends on them). All leaves can execute in parallel.

    Example:
        >>> graph = ArtifactGraph()
        >>> graph.add(ArtifactSpec(id="A", description="A", contract="A"))
        >>> graph.add(ArtifactSpec(
        ...     id="B", description="B", contract="B", requires=frozenset(["A"])
        ... ))
        >>> waves = graph.execution_waves()
        >>> waves
        [["A"], ["B"]]  # A first, then B
    """

    _artifacts: dict[str, ArtifactSpec] = field(default_factory=dict)
    """Mapping from artifact ID to specification."""

    _dependents: dict[str, set[str]] = field(default_factory=dict)
    """Mapping from artifact ID to IDs of artifacts that depend on it."""

    def __post_init__(self) -> None:
        """Initialize dependents tracking."""
        if not self._dependents:
            self._dependents = {}

    def add(self, artifact: ArtifactSpec) -> None:
        """Add an artifact to the graph.

        Args:
            artifact: The artifact to add

        Raises:
            ValueError: If artifact ID already exists
        """
        if artifact.id in self._artifacts:
            raise ValueError(f"Artifact '{artifact.id}' already exists in graph")

        self._artifacts[artifact.id] = artifact
        self._dependents.setdefault(artifact.id, set())

        # Update dependents for all requirements
        for req_id in artifact.requires:
            self._dependents.setdefault(req_id, set()).add(artifact.id)

    def add_all(self, artifacts: list[ArtifactSpec]) -> None:
        """Add multiple artifacts to the graph.

        Args:
            artifacts: List of artifacts to add
        """
        for artifact in artifacts:
            self.add(artifact)

    def get(self, artifact_id: str) -> ArtifactSpec | None:
        """Get an artifact by ID."""
        return self._artifacts.get(artifact_id)

    def __getitem__(self, artifact_id: str) -> ArtifactSpec:
        """Get an artifact by ID, raising KeyError if not found."""
        return self._artifacts[artifact_id]

    def __contains__(self, artifact_id: str) -> bool:
        """Check if an artifact exists in the graph."""
        return artifact_id in self._artifacts

    def __len__(self) -> int:
        """Return the number of artifacts in the graph."""
        return len(self._artifacts)

    def __iter__(self):
        """Iterate over artifact IDs."""
        return iter(self._artifacts)

    @property
    def artifacts(self) -> dict[str, ArtifactSpec]:
        """Get all artifacts (read-only view)."""
        return dict(self._artifacts)

    def leaves(self) -> list[str]:
        """Get all leaf artifact IDs (no dependencies).

        Leaves are artifacts with empty requires set.
        They can all be executed in parallel as the first wave.
        """
        return [aid for aid, spec in self._artifacts.items() if spec.is_leaf()]

    def roots(self) -> list[str]:
        """Get all root artifact IDs (nothing depends on them).

        Roots are the final convergence points. In a goal-oriented
        graph, the goal artifact is typically the sole root.
        """
        return [
            aid for aid in self._artifacts
            if not self._dependents.get(aid)
        ]

    def depth(self, artifact_id: str) -> int:
        """Calculate the depth of an artifact (longest path from any leaf).

        Depth 0 = leaf (no dependencies)
        Depth 1 = depends only on leaves
        Depth n = longest dependency chain is n

        This is useful for model selection (deeper = more complex).

        Args:
            artifact_id: The artifact to calculate depth for

        Returns:
            Depth as integer (0 for leaves)
        """
        if artifact_id not in self._artifacts:
            return -1

        spec = self._artifacts[artifact_id]
        if spec.is_leaf():
            return 0

        return 1 + max(self.depth(req) for req in spec.requires)

    def fan_in(self, artifact_id: str) -> int:
        """Get the number of direct dependencies for an artifact."""
        spec = self._artifacts.get(artifact_id)
        return len(spec.requires) if spec else 0

    def fan_out(self, artifact_id: str) -> int:
        """Get the number of artifacts that depend on this one."""
        return len(self._dependents.get(artifact_id, set()))

    def get_dependents(self, artifact_id: str) -> set[str]:
        """Get artifacts that depend on this artifact.

        Used for invalidation cascade in incremental rebuilds (RFC-040).

        Args:
            artifact_id: The artifact to find dependents for

        Returns:
            Set of artifact IDs that have this artifact in their requires
        """
        return self._dependents.get(artifact_id, set()).copy()

    def validate(self) -> list[str]:
        """Validate the graph for completeness and consistency.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check for missing dependencies
        for artifact_id, spec in self._artifacts.items():
            missing = spec.requires - set(self._artifacts.keys())
            if missing:
                errors.append(
                    f"Artifact '{artifact_id}' requires non-existent artifacts: {missing}"
                )

        # Check for cycles
        try:
            self.topological_sort()
        except CyclicDependencyError as e:
            errors.append(str(e))

        # Check for orphans (artifacts not connected to any root)
        orphans = self.find_orphans()
        if orphans:
            errors.append(f"Orphan artifacts (not connected to any path): {orphans}")

        return errors

    def detect_cycle(self) -> list[str] | None:
        """Detect if there's a cycle in the dependency graph.

        Returns:
            List of artifact IDs in the cycle, or None if no cycle
        """
        white, gray, black = 0, 1, 2
        color: dict[str, int] = dict.fromkeys(self._artifacts, white)
        parent: dict[str, str | None] = dict.fromkeys(self._artifacts)

        def dfs(node: str) -> list[str] | None:
            color[node] = gray
            spec = self._artifacts[node]

            for req in spec.requires:
                if req not in color:
                    # Missing dependency - not a cycle issue
                    continue

                if color[req] == gray:
                    # Found cycle - reconstruct it
                    cycle = [req, node]
                    current = parent.get(node)
                    while current and current != req:
                        cycle.append(current)
                        current = parent.get(current)
                    return list(reversed(cycle))

                if color[req] == white:
                    parent[req] = node
                    result = dfs(req)
                    if result:
                        return result

            color[node] = black
            return None

        for aid in self._artifacts:
            if color[aid] == white:
                cycle = dfs(aid)
                if cycle:
                    return cycle

        return None

    def topological_sort(self) -> list[str]:
        """Return artifacts in dependency order (Kahn's algorithm).

        Returns:
            List of artifact IDs where all dependencies appear before dependents

        Raises:
            CyclicDependencyError: If the graph contains a cycle
        """
        # Count incoming edges (dependencies)
        in_degree: dict[str, int] = dict.fromkeys(self._artifacts, 0)
        for spec in self._artifacts.values():
            for req in spec.requires:
                if req in in_degree:
                    in_degree[spec.id] = in_degree.get(spec.id, 0)  # Ensure exists

        # Actually count: each artifact's in-degree is len(requires) that exist
        in_degree = {
            aid: len([r for r in spec.requires if r in self._artifacts])
            for aid, spec in self._artifacts.items()
        }

        # Start with leaves (in_degree = 0)
        queue = deque([aid for aid, deg in in_degree.items() if deg == 0])
        result = []

        while queue:
            node = queue.popleft()
            result.append(node)

            # Reduce in-degree of dependents
            for dependent in self._dependents.get(node, set()):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(result) != len(self._artifacts):
            # Cycle detected - find it
            cycle = self.detect_cycle()
            if cycle:
                raise CyclicDependencyError(cycle)
            else:
                # Shouldn't happen, but provide useful error
                remaining = set(self._artifacts.keys()) - set(result)
                raise CyclicDependencyError(list(remaining)[:3])

        return result

    def execution_waves(self) -> list[list[str]]:
        """Group artifacts into parallel execution waves.

        Each wave contains artifacts that:
        1. Have all dependencies satisfied by previous waves
        2. Can execute in parallel with other artifacts in the same wave

        Returns:
            List of waves, each wave is a list of artifact IDs

        Example:
            >>> graph.execution_waves()
            [
                ["UserProtocol", "AuthInterface"],  # Wave 1: all leaves
                ["UserModel", "AuthService"],       # Wave 2: depend on wave 1
                ["App"],                            # Wave 3: convergence
            ]
        """
        completed: set[str] = set()
        pending = set(self._artifacts.keys())
        waves = []

        while pending:
            # Find all artifacts whose dependencies are satisfied
            ready = [
                aid for aid in pending
                if all(req in completed for req in self._artifacts[aid].requires)
            ]

            if not ready:
                # Deadlock - should have been caught by cycle detection
                cycle = self.detect_cycle()
                if cycle:
                    raise CyclicDependencyError(cycle)
                else:
                    raise ArtifactError(f"Execution deadlock with pending: {pending}")

            waves.append(ready)

            for aid in ready:
                completed.add(aid)
                pending.remove(aid)

        return waves

    def find_orphans(self) -> set[str]:
        """Find artifacts not connected to any root.

        Orphans are artifacts that:
        1. Are not roots themselves
        2. Have no path to any root

        These may indicate incomplete discovery or unused artifacts.
        """
        roots = set(self.roots())
        if not roots:
            return set()  # No roots means everything might be orphaned

        # BFS from all roots backward through dependencies
        connected: set[str] = set(roots)
        queue = deque(roots)

        while queue:
            node = queue.popleft()
            spec = self._artifacts.get(node)
            if spec:
                for req in spec.requires:
                    if req in self._artifacts and req not in connected:
                        connected.add(req)
                        queue.append(req)

        return set(self._artifacts.keys()) - connected

    def has_root(self) -> bool:
        """Check if the graph has at least one root."""
        return len(self.roots()) > 0

    def subgraph(self, artifact_ids: set[str]) -> ArtifactGraph:
        """Create a subgraph containing only specified artifacts.

        Args:
            artifact_ids: Set of artifact IDs to include

        Returns:
            New ArtifactGraph with only the specified artifacts
        """
        subgraph = ArtifactGraph()
        for aid in artifact_ids:
            if aid in self._artifacts:
                spec = self._artifacts[aid]
                # Filter requires to only include artifacts in subgraph
                filtered_requires = spec.requires & artifact_ids
                if filtered_requires != spec.requires:
                    # Create new spec with filtered requires
                    spec = ArtifactSpec(
                        id=spec.id,
                        description=spec.description,
                        contract=spec.contract,
                        produces_file=spec.produces_file,
                        requires=filtered_requires,
                        domain_type=spec.domain_type,
                        metadata=spec.metadata,
                    )
                subgraph.add(spec)
        return subgraph

    def max_depth(self) -> int:
        """Get the maximum depth of the graph."""
        if not self._artifacts:
            return 0
        return max(self.depth(aid) for aid in self._artifacts)

    def to_mermaid(self) -> str:
        """Generate Mermaid diagram of the graph.

        Returns:
            Mermaid diagram string for visualization
        """
        lines = ["graph TD"]

        for aid, spec in self._artifacts.items():
            # Node with description
            desc = spec.description
            label = desc[:30] + "..." if len(desc) > 30 else desc
            safe_label = label.replace('"', "'")
            lines.append(f'    {aid}["{aid}: {safe_label}"]')

            # Edges for dependencies
            for req in spec.requires:
                lines.append(f"    {req} --> {aid}")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "artifacts": {aid: spec.to_dict() for aid, spec in self._artifacts.items()},
            "waves": self.execution_waves() if self._artifacts else [],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ArtifactGraph:
        """Create from dict."""
        graph = cls()
        for spec_data in data.get("artifacts", {}).values():
            graph.add(ArtifactSpec.from_dict(spec_data))
        return graph


# =============================================================================
# Artifact → Task Conversion (RFC-034 Compatibility)
# =============================================================================


def artifact_to_task(artifact: ArtifactSpec, graph: ArtifactGraph | None = None) -> Task:
    """Convert an artifact specification to an RFC-034 Task.

    This provides compatibility with the existing execution infrastructure.
    The artifact's contract becomes the task's specification.

    Args:
        artifact: The artifact specification
        graph: Optional graph for depth/complexity analysis

    Returns:
        RFC-034 Task that creates this artifact
    """
    # Determine parallel group based on depth
    if graph:
        depth = graph.depth(artifact.id)
        if depth == 0:
            parallel_group = "contracts"
        elif depth <= 2:
            parallel_group = "implementations"
        else:
            parallel_group = "integration"
    else:
        parallel_group = "contracts" if artifact.is_leaf() else "implementations"

    return Task(
        id=artifact.id,
        description=f"Create {artifact.description}",
        mode=TaskMode.GENERATE,
        # RFC-034 fields map directly
        produces=frozenset([artifact.id]),
        requires=artifact.requires,
        modifies=frozenset([artifact.produces_file]) if artifact.produces_file else frozenset(),
        target_path=artifact.produces_file,
        # Contract information
        is_contract=artifact.is_contract(),
        contract=artifact.contract,
        parallel_group=parallel_group,
        # Metadata
        details={
            "domain_type": artifact.domain_type,
            "artifact_metadata": artifact.metadata,
        },
        status=TaskStatus.PENDING,
    )


def artifacts_to_tasks(graph: ArtifactGraph) -> list[Task]:
    """Convert all artifacts in a graph to RFC-034 Tasks.

    Tasks are ordered by execution waves for optimal parallelization.

    Args:
        graph: The artifact graph

    Returns:
        List of Tasks in execution order
    """
    tasks = []
    for wave in graph.execution_waves():
        for artifact_id in wave:
            artifact = graph[artifact_id]
            tasks.append(artifact_to_task(artifact, graph))
    return tasks


# =============================================================================
# Model Selection Based on Graph Structure
# =============================================================================


def select_model_tier(artifact: ArtifactSpec, graph: ArtifactGraph) -> str:
    """Select model tier based on artifact complexity.

    The artifact structure tells us which tasks are simple:
    - Leaves: No context needed, simple specs → small model
    - Shallow deps: Reference contracts → medium model
    - Convergence: Full context needed → large model

    Args:
        artifact: The artifact specification
        graph: The artifact graph for depth analysis

    Returns:
        Model tier: "small", "medium", or "large"
    """
    depth = graph.depth(artifact.id)
    fan_in = len(artifact.requires)

    if depth == 0:
        return "small"  # Leaves: simple, no context
    elif fan_in <= 2:
        return "medium"  # Shallow deps: moderate complexity
    else:
        return "large"  # Convergence: needs full context


def get_model_distribution(graph: ArtifactGraph) -> dict[str, int]:
    """Get distribution of model tiers for a graph.

    Useful for cost estimation and planning.

    Args:
        graph: The artifact graph

    Returns:
        Dict mapping tier to count: {"small": 5, "medium": 3, "large": 1}
    """
    distribution: dict[str, int] = {"small": 0, "medium": 0, "large": 0}

    for artifact_id in graph:
        artifact = graph[artifact_id]
        tier = select_model_tier(artifact, graph)
        distribution[tier] += 1

    return distribution
