"""Skill dependency graph for DAG-based execution (RFC-087).

This module implements the Skill Graph component of RFC-087: Skill-Lens DAG.
It provides:
1. DAG representation of skill dependencies
2. Topological ordering for execution
3. Parallel wave computation
4. Cycle detection
5. Subgraph extraction

Follows the same patterns as ArtifactGraph (src/sunwell/naaru/artifacts.py).
"""


import hashlib
import threading
from collections import deque
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sunwell.planning.skills.types import Skill
else:
    Skill = object


# =============================================================================
# EXCEPTIONS
# =============================================================================


class SkillGraphError(Exception):
    """Base exception for skill graph errors."""


class CircularDependencyError(SkillGraphError):
    """Raised when skill dependencies form a cycle."""

    def __init__(self, cycle: list[str]) -> None:
        self.cycle = cycle
        cycle_str = " → ".join(cycle + [cycle[0]])
        super().__init__(f"Circular dependency detected: {cycle_str}")


class MissingDependencyError(SkillGraphError):
    """Raised when a skill depends on a non-existent skill."""

    def __init__(self, skill_name: str, missing: set[str]) -> None:
        self.skill_name = skill_name
        self.missing = missing
        super().__init__(
            f"Skill '{skill_name}' depends on non-existent skills: {missing}"
        )


class UnsatisfiedRequiresError(SkillGraphError):
    """Raised when a skill's requires aren't satisfied by upstream produces."""

    def __init__(
        self, skill_name: str, unsatisfied: set[str], available: set[str]
    ) -> None:
        self.skill_name = skill_name
        self.unsatisfied = unsatisfied
        self.available = available
        super().__init__(
            f"Skill '{skill_name}' requires {unsatisfied} but upstream only produces {available}"
        )


# =============================================================================
# SKILL GRAPH
# =============================================================================


@dataclass(slots=True)
class SkillGraph:
    """DAG of skills with dependency resolution.

    Thread-safe for concurrent reads. Mutations require external synchronization
    or should only happen during initial construction.

    Follows the same patterns as ArtifactGraph (src/sunwell/naaru/artifacts.py).
    """

    _skills: dict[str, Skill] = field(default_factory=dict)
    """Mapping from skill name to Skill object."""

    _edges: dict[str, frozenset[str]] = field(default_factory=dict)
    """Mapping from skill name to its dependencies (immutable for thread safety)."""

    _dependents: dict[str, set[str]] = field(default_factory=dict)
    """Reverse mapping: skill → skills that depend on it."""

    _lock: threading.Lock = field(default_factory=threading.Lock)
    """Lock for mutation operations."""

    def add_skill(self, skill: Skill) -> None:
        """Add a skill to the graph.

        Thread-safe: acquires lock during mutation.

        Args:
            skill: The skill to add

        Raises:
            ValueError: If skill name already exists
        """
        with self._lock:
            if skill.name in self._skills:
                raise ValueError(f"Skill '{skill.name}' already exists in graph")

            self._skills[skill.name] = skill
            deps = frozenset(dep.skill_name for dep in skill.depends_on)
            self._edges[skill.name] = deps

            # Update reverse mapping
            self._dependents.setdefault(skill.name, set())
            for dep_name in deps:
                self._dependents.setdefault(dep_name, set()).add(skill.name)

    def get(self, name: str) -> Skill | None:
        """Get a skill by name."""
        return self._skills.get(name)

    def __contains__(self, name: str) -> bool:
        return name in self._skills

    def __len__(self) -> int:
        return len(self._skills)

    def __iter__(self) -> Iterator[Skill]:
        return iter(self._skills.values())

    @property
    def skills(self) -> dict[str, Skill]:
        """Read-only view of all skills."""
        return dict(self._skills)

    @property
    def skill_names(self) -> set[str]:
        """Set of all skill names in the graph."""
        return set(self._skills.keys())

    def dependencies(self, name: str) -> frozenset[str]:
        """Get direct dependencies of a skill."""
        return self._edges.get(name, frozenset())

    def dependents(self, name: str) -> set[str]:
        """Get skills that directly depend on this skill."""
        return self._dependents.get(name, set()).copy()

    def validate(self) -> list[str]:
        """Validate the graph for completeness and consistency.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check for missing dependencies
        for name, deps in self._edges.items():
            missing = deps - set(self._skills.keys())
            if missing:
                errors.append(f"Skill '{name}' depends on non-existent: {missing}")

        # Check for cycles
        try:
            self.topological_order()
        except CircularDependencyError as e:
            errors.append(str(e))

        # Validate requires/produces flow
        for name, skill in self._skills.items():
            if skill.requires:
                available = self._upstream_produces(name)
                unsatisfied = set(skill.requires) - available
                if unsatisfied:
                    errors.append(
                        f"Skill '{name}' requires {unsatisfied} not produced by dependencies"
                    )

        return errors

    def _upstream_produces(self, skill_name: str) -> set[str]:
        """Get all context keys produced by upstream skills (transitive)."""
        visited: set[str] = set()
        produces: set[str] = set()

        def visit(name: str) -> None:
            if name in visited:
                return
            visited.add(name)

            skill = self._skills.get(name)
            if skill:
                produces.update(skill.produces)
                for dep in self._edges.get(name, frozenset()):
                    visit(dep)

        # Visit all direct dependencies
        for dep in self._edges.get(skill_name, frozenset()):
            visit(dep)

        return produces

    def topological_order(self) -> list[str]:
        """Return skills in execution order (dependencies first).

        Uses Kahn's algorithm, same as ArtifactGraph.

        Returns:
            List of skill names in dependency order

        Raises:
            CircularDependencyError: If cycle detected
        """
        # Calculate in-degree for each node (only count deps that exist in graph)
        in_degree = {
            name: len(deps & set(self._skills.keys()))
            for name, deps in self._edges.items()
        }

        # Start with nodes that have no dependencies
        queue: deque[str] = deque(
            [name for name, deg in in_degree.items() if deg == 0]
        )
        order: list[str] = []

        while queue:
            name = queue.popleft()
            order.append(name)

            for dependent in self._dependents.get(name, set()):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(order) != len(self._skills):
            # Find the cycle
            remaining = set(self._skills.keys()) - set(order)
            cycle = self._detect_cycle(remaining)
            raise CircularDependencyError(cycle or list(remaining)[:3])

        return order

    def _detect_cycle(self, nodes: set[str]) -> list[str] | None:
        """Detect cycle in a subset of nodes using DFS."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color = dict.fromkeys(nodes, WHITE)
        parent: dict[str, str | None] = dict.fromkeys(nodes)

        def dfs(node: str) -> list[str] | None:
            color[node] = GRAY
            for dep in self._edges.get(node, frozenset()):
                if dep not in color:
                    continue
                if color[dep] == GRAY:
                    # Found cycle
                    cycle = [dep, node]
                    curr = parent.get(node)
                    while curr and curr != dep:
                        cycle.append(curr)
                        curr = parent.get(curr)
                    return list(reversed(cycle))
                if color[dep] == WHITE:
                    parent[dep] = node
                    if result := dfs(dep):
                        return result
            color[node] = BLACK
            return None

        for node in nodes:
            if color[node] == WHITE:
                if cycle := dfs(node):
                    return cycle
        return None

    def execution_waves(self) -> list[list[str]]:
        """Group skills into parallel execution waves.

        Each wave contains skills that can execute in parallel because
        all their dependencies are satisfied by previous waves.

        Returns:
            List of waves, each wave is a list of skill names
        """
        completed: set[str] = set()
        pending = set(self._skills.keys())
        waves: list[list[str]] = []

        while pending:
            wave = [
                name
                for name in pending
                if (
                    self._edges.get(name, frozenset()) & set(self._skills.keys())
                ).issubset(completed)
            ]

            if not wave:
                cycle = self._detect_cycle(pending)
                raise CircularDependencyError(cycle or list(pending)[:3])

            waves.append(wave)
            completed.update(wave)
            pending -= set(wave)

        return waves

    def subgraph_for(self, skill_names: set[str]) -> SkillGraph:
        """Extract subgraph containing specified skills and their dependencies.

        Args:
            skill_names: Skills to include (dependencies added automatically)

        Returns:
            New SkillGraph with only the required skills
        """
        needed: set[str] = set()
        to_visit = list(skill_names)

        while to_visit:
            name = to_visit.pop()
            if name in needed or name not in self._skills:
                continue
            needed.add(name)
            to_visit.extend(self._edges.get(name, frozenset()))

        subgraph = SkillGraph()
        for name in needed:
            subgraph.add_skill(self._skills[name])

        return subgraph

    def content_hash(self) -> str:
        """Compute a content hash for cache invalidation.

        Hash includes:
        - All skill names and their instruction content
        - Dependency structure
        - produces/requires declarations

        Returns:
            SHA-256 hex digest
        """
        hasher = hashlib.sha256()

        for name in sorted(self._skills.keys()):
            skill = self._skills[name]
            hasher.update(name.encode())
            hasher.update((skill.instructions or "").encode())
            hasher.update(",".join(sorted(skill.produces)).encode())
            hasher.update(",".join(sorted(skill.requires)).encode())
            hasher.update(
                ",".join(sorted(d.source for d in skill.depends_on)).encode()
            )

        return hasher.hexdigest()

    def to_mermaid(self) -> str:
        """Generate Mermaid diagram of the skill graph."""
        lines = ["graph TD"]

        for name, skill in self._skills.items():
            desc = (
                skill.description[:30] + "..."
                if len(skill.description) > 30
                else skill.description
            )
            safe_desc = desc.replace('"', "'")
            lines.append(f'    {name.replace("-", "_")}["{name}: {safe_desc}"]')

            for dep in self._edges.get(name, frozenset()):
                dep_safe = dep.replace("-", "_")
                name_safe = name.replace("-", "_")
                lines.append(f"    {dep_safe} --> {name_safe}")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Serialize graph to dictionary for JSON export."""
        return {
            "skills": {
                name: {
                    "name": skill.name,
                    "description": skill.description,
                    "depends_on": [d.source for d in skill.depends_on],
                    "produces": list(skill.produces),
                    "requires": list(skill.requires),
                }
                for name, skill in self._skills.items()
            },
            "waves": self.execution_waves() if self._skills else [],
            "content_hash": self.content_hash() if self._skills else "",
        }

    @classmethod
    def from_skills(cls, skills: tuple[Skill, ...] | list[Skill]) -> SkillGraph:
        """Create a SkillGraph from a collection of skills.

        Args:
            skills: Skills to add to the graph

        Returns:
            New SkillGraph containing all skills
        """
        graph = cls()
        for skill in skills:
            graph.add_skill(skill)
        return graph
