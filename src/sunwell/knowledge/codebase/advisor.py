"""Task Graph Advisor - Graph-Powered Goal Analysis.

Uses structural graph algorithms to advise on task decomposition:
- Complexity estimation via fan-out analysis
- Impact scope via transitive reachability
- Focused context via subgraph extraction
- Execution order via topological sort

Maps task types to appropriate algorithms:
- ADD_FEATURE: Fan-out + Impact (complexity + testing scope)
- FIX_BUG: Subgraph + Path (focused context + trace flow)
- REFACTOR: SCC + Fan-In/Out (coupled code + god objects)
- UNDERSTAND: Subgraph + Topo Sort (context + dependency order)
- DELETE: Impact (what breaks if removed)
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path

from sunwell.knowledge.codebase.algorithms import (
    FanMetrics,
    GraphAlgorithms,
    SubgraphResult,
)
from sunwell.knowledge.codebase.codebase import (
    CodebaseGraph,
    EdgeType,
    NodeType,
    StructuralNode,
)


class TaskType(Enum):
    """Types of tasks that benefit from graph analysis."""

    ADD_FEATURE = auto()  # Adding new functionality
    FIX_BUG = auto()  # Fixing a bug or issue
    REFACTOR = auto()  # Restructuring code
    UNDERSTAND = auto()  # Understanding how code works
    DELETE = auto()  # Removing code
    MODIFY = auto()  # Modifying existing code
    TEST = auto()  # Writing tests


@dataclass(frozen=True, slots=True)
class ComplexityEstimate:
    """Estimated complexity of a task based on graph analysis."""

    score: float  # 0.0 (trivial) to 1.0 (very complex)
    fan_out: int  # Number of outgoing dependencies
    fan_in: int  # Number of incoming dependencies (things that depend on target)
    depth: int  # Estimated depth of changes
    rationale: str  # Human-readable explanation

    @property
    def level(self) -> str:
        """Complexity level as a string."""
        if self.score < 0.2:
            return "trivial"
        if self.score < 0.4:
            return "simple"
        if self.score < 0.6:
            return "moderate"
        if self.score < 0.8:
            return "complex"
        return "very_complex"


@dataclass(frozen=True, slots=True)
class ImpactScope:
    """Scope of impact for a change."""

    affected_nodes: tuple[StructuralNode, ...]
    affected_files: tuple[Path, ...]
    direct_dependents: int  # Things directly depending on target
    transitive_dependents: int  # Total things affected (transitively)
    rationale: str


@dataclass(frozen=True, slots=True)
class FocusedContext:
    """Focused context extracted for a task."""

    center_node: StructuralNode | None
    relevant_nodes: tuple[StructuralNode, ...]
    relevant_files: tuple[Path, ...]
    edges: int  # Number of relationships in context
    rationale: str


@dataclass(frozen=True, slots=True)
class ExecutionOrder:
    """Suggested execution order for a task."""

    ordered_nodes: tuple[StructuralNode, ...]
    has_cycles: bool
    rationale: str


@dataclass(slots=True)
class TaskAdvice:
    """Complete advice for a task based on graph analysis."""

    task_type: TaskType
    target: str
    target_nodes: list[StructuralNode] = field(default_factory=list)

    # Analysis results
    complexity: ComplexityEstimate | None = None
    impact: ImpactScope | None = None
    context: FocusedContext | None = None
    execution_order: ExecutionOrder | None = None

    # Suggested decomposition
    subtask_hints: list[str] = field(default_factory=list)

    # Related findings
    potential_issues: list[str] = field(default_factory=list)
    suggested_tests: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """Generate a human-readable summary of the advice."""
        lines: list[str] = []
        lines.append(f"Task: {self.task_type.name} on '{self.target}'")

        if self.target_nodes:
            lines.append(f"Found {len(self.target_nodes)} matching node(s)")

        if self.complexity:
            lines.append(
                f"Complexity: {self.complexity.level} "
                f"(score={self.complexity.score:.2f}, "
                f"fan_out={self.complexity.fan_out}, "
                f"fan_in={self.complexity.fan_in})"
            )
            lines.append(f"  → {self.complexity.rationale}")

        if self.impact:
            lines.append(
                f"Impact: {self.impact.transitive_dependents} affected nodes "
                f"in {len(self.impact.affected_files)} files"
            )
            lines.append(f"  → {self.impact.rationale}")

        if self.context:
            lines.append(
                f"Context: {len(self.context.relevant_nodes)} relevant nodes "
                f"in {len(self.context.relevant_files)} files"
            )

        if self.subtask_hints:
            lines.append("Suggested subtasks:")
            for hint in self.subtask_hints:
                lines.append(f"  - {hint}")

        if self.potential_issues:
            lines.append("Potential issues:")
            for issue in self.potential_issues:
                lines.append(f"  ⚠ {issue}")

        return "\n".join(lines)


class TaskGraphAdvisor:
    """Use graph analysis to advise on task decomposition.

    Maps task types to appropriate graph algorithms and provides
    actionable advice for goal analysis and planning.

    Usage:
        advisor = TaskGraphAdvisor(codebase_graph)
        advice = advisor.analyze(TaskType.ADD_FEATURE, "UserService")
        print(advice.summary())
    """

    def __init__(self, graph: CodebaseGraph) -> None:
        self.graph = graph
        self.algorithms = GraphAlgorithms(graph)

    def analyze(self, task_type: TaskType, target: str) -> TaskAdvice:
        """Analyze a task and return comprehensive advice.

        Args:
            task_type: Type of task (ADD_FEATURE, FIX_BUG, etc.)
            target: Name of target entity (partial match supported)

        Returns:
            TaskAdvice with complexity, impact, context, and suggestions
        """
        advice = TaskAdvice(
            task_type=task_type,
            target=target,
            target_nodes=self.graph.find_structural_nodes(target),
        )

        # Run task-type-specific analysis
        match task_type:
            case TaskType.ADD_FEATURE:
                self._analyze_add_feature(advice)
            case TaskType.FIX_BUG:
                self._analyze_fix_bug(advice)
            case TaskType.REFACTOR:
                self._analyze_refactor(advice)
            case TaskType.UNDERSTAND:
                self._analyze_understand(advice)
            case TaskType.DELETE:
                self._analyze_delete(advice)
            case TaskType.MODIFY:
                self._analyze_modify(advice)
            case TaskType.TEST:
                self._analyze_test(advice)

        return advice

    def _analyze_add_feature(self, advice: TaskAdvice) -> None:
        """Analyze for adding a new feature."""
        # Complexity via fan-out
        advice.complexity = self.estimate_complexity(advice.target)

        # Impact scope (what needs testing)
        advice.impact = self.get_impact_scope(advice.target)

        # Context for implementation
        advice.context = self.get_focused_context(advice.target, depth=2)

        # Suggest subtasks based on complexity
        if advice.complexity and advice.complexity.fan_out > 10:
            advice.subtask_hints.append(
                "Consider breaking into smaller functions (high fan-out)"
            )

        if advice.impact and advice.impact.transitive_dependents > 20:
            advice.subtask_hints.append(
                "Add integration tests for affected components"
            )
            advice.suggested_tests.extend(
                [f"Test {n.name}" for n in advice.impact.affected_nodes[:5]]
            )

    def _analyze_fix_bug(self, advice: TaskAdvice) -> None:
        """Analyze for fixing a bug."""
        # Focused context for debugging
        advice.context = self.get_focused_context(advice.target, depth=2)

        # Impact to understand blast radius
        advice.impact = self.get_impact_scope(advice.target)

        # Complexity estimate
        advice.complexity = self.estimate_complexity(advice.target)

        # Suggest debugging approach
        if advice.context and len(advice.context.relevant_nodes) > 10:
            advice.subtask_hints.append(
                "Narrow down by tracing call flow"
            )

        if advice.impact and advice.impact.transitive_dependents > 5:
            advice.potential_issues.append(
                f"Fix may affect {advice.impact.transitive_dependents} dependents"
            )

    def _analyze_refactor(self, advice: TaskAdvice) -> None:
        """Analyze for refactoring."""
        # Find tightly coupled code
        sccs = self.algorithms.find_sccs(EdgeType.CALLS, min_size=2)
        if sccs:
            advice.potential_issues.append(
                f"Found {len(sccs)} tightly coupled clusters"
            )
            for scc in sccs[:3]:
                names = [n.name for n in scc[:5]]
                advice.subtask_hints.append(
                    f"Consider extracting cluster: {', '.join(names)}"
                )

        # Find high fan-out (orchestrators)
        complex_nodes = self.algorithms.most_complex(top_n=5)
        for metrics in complex_nodes:
            if metrics.fan_out > 20:
                advice.potential_issues.append(
                    f"{metrics.node.name} has high fan-out ({metrics.fan_out}) - "
                    "consider decomposition"
                )

        # Find high fan-in (god objects)
        depended = self.algorithms.most_depended_on(top_n=5)
        for metrics in depended:
            if metrics.fan_in > 20:
                advice.potential_issues.append(
                    f"{metrics.node.name} has high fan-in ({metrics.fan_in}) - "
                    "potential god object"
                )

        # Impact scope
        advice.impact = self.get_impact_scope(advice.target)
        advice.complexity = self.estimate_complexity(advice.target)

    def _analyze_understand(self, advice: TaskAdvice) -> None:
        """Analyze for understanding code."""
        # Get focused context with more depth
        advice.context = self.get_focused_context(advice.target, depth=3)

        # Get execution order for understanding dependencies
        advice.execution_order = self.get_execution_order([advice.target])

        # Complexity gives overview
        advice.complexity = self.estimate_complexity(advice.target)

        if advice.context:
            advice.subtask_hints.append(
                f"Start with {len(advice.context.relevant_files)} relevant files"
            )

    def _analyze_delete(self, advice: TaskAdvice) -> None:
        """Analyze for deleting code."""
        # Impact is critical - what breaks?
        advice.impact = self.get_impact_scope(advice.target)

        if advice.impact:
            if advice.impact.transitive_dependents > 0:
                advice.potential_issues.append(
                    f"Deleting will break {advice.impact.transitive_dependents} dependents"
                )
                for node in advice.impact.affected_nodes[:5]:
                    advice.subtask_hints.append(
                        f"Update or remove reference in {node.name}"
                    )
            else:
                advice.subtask_hints.append("Safe to delete - no dependents found")

    def _analyze_modify(self, advice: TaskAdvice) -> None:
        """Analyze for modifying existing code."""
        # Similar to fix_bug but focused on impact
        advice.complexity = self.estimate_complexity(advice.target)
        advice.impact = self.get_impact_scope(advice.target)
        advice.context = self.get_focused_context(advice.target, depth=1)

        if advice.impact and advice.impact.transitive_dependents > 10:
            advice.potential_issues.append(
                "High-impact change - consider feature flag"
            )

    def _analyze_test(self, advice: TaskAdvice) -> None:
        """Analyze for writing tests."""
        # Get dependencies to understand what to mock
        deps = self.algorithms.get_dependencies(advice.target, max_depth=2)

        advice.context = self.get_focused_context(advice.target, depth=2)
        advice.complexity = self.estimate_complexity(advice.target)

        # Suggest what to test and mock
        external_deps = [n for n in deps if not n.file_path]
        internal_deps = [n for n in deps if n.file_path]

        if external_deps:
            advice.subtask_hints.append(
                f"Mock {len(external_deps)} external dependencies"
            )

        if internal_deps:
            advice.subtask_hints.append(
                f"Consider {len(internal_deps)} internal dependencies for integration tests"
            )

        # Suggest test cases based on fan-out
        if advice.complexity and advice.complexity.fan_out > 5:
            advice.suggested_tests.append("Test happy path")
            advice.suggested_tests.append("Test error handling")
            advice.suggested_tests.append("Test edge cases")

    # -------------------------------------------------------------------------
    # Core Analysis Methods
    # -------------------------------------------------------------------------

    def estimate_complexity(self, target: str) -> ComplexityEstimate:
        """Estimate task complexity via fan-out analysis.

        Args:
            target: Name of target entity

        Returns:
            ComplexityEstimate with score and rationale
        """
        nodes = self.graph.find_structural_nodes(target)
        if not nodes:
            return ComplexityEstimate(
                score=0.5,
                fan_out=0,
                fan_in=0,
                depth=1,
                rationale=f"Target '{target}' not found in graph",
            )

        total_fan_out = 0
        total_fan_in = 0

        for node in nodes:
            metrics = self.algorithms.get_fan_metrics(node.id)
            if metrics:
                total_fan_out += metrics.call_out
                total_fan_in += metrics.call_in

        # Normalize to 0-1 score
        # Fan-out > 50 is very complex, < 5 is simple
        fan_out_score = min(1.0, total_fan_out / 50)
        fan_in_score = min(1.0, total_fan_in / 50)

        # Weight fan-out more (complexity of implementation)
        score = 0.7 * fan_out_score + 0.3 * fan_in_score

        # Depth estimate based on fan-out
        depth = 1 + (total_fan_out // 10)

        rationale = self._complexity_rationale(total_fan_out, total_fan_in)

        return ComplexityEstimate(
            score=score,
            fan_out=total_fan_out,
            fan_in=total_fan_in,
            depth=depth,
            rationale=rationale,
        )

    def _complexity_rationale(self, fan_out: int, fan_in: int) -> str:
        """Generate human-readable complexity rationale."""
        parts: list[str] = []

        if fan_out > 30:
            parts.append("very high fan-out (orchestrator function)")
        elif fan_out > 15:
            parts.append("high fan-out (complex coordination)")
        elif fan_out > 5:
            parts.append("moderate fan-out")
        else:
            parts.append("low fan-out (focused function)")

        if fan_in > 20:
            parts.append("widely used (high impact)")
        elif fan_in > 5:
            parts.append("moderately used")

        return "; ".join(parts) if parts else "standard complexity"

    def get_impact_scope(self, target: str) -> ImpactScope:
        """Get testing/validation scope via reachability.

        Args:
            target: Name of target entity

        Returns:
            ImpactScope with affected nodes and files
        """
        affected = self.algorithms.get_impact(target, max_depth=5)

        # Get files
        affected_files: set[Path] = set()
        for node in affected:
            if node.file_path:
                affected_files.add(node.file_path)

        # Count direct vs transitive
        nodes = self.graph.find_structural_nodes(target)
        direct = 0
        for node in nodes:
            direct += len(self.graph.structural_edges_in.get(node.id, []))

        rationale = self._impact_rationale(len(affected), len(affected_files), direct)

        return ImpactScope(
            affected_nodes=tuple(affected),
            affected_files=tuple(sorted(affected_files)),
            direct_dependents=direct,
            transitive_dependents=len(affected),
            rationale=rationale,
        )

    def _impact_rationale(
        self, total_affected: int, file_count: int, direct: int
    ) -> str:
        """Generate human-readable impact rationale."""
        if total_affected == 0:
            return "No dependents found - isolated code"
        if total_affected > 50:
            return f"Very high impact - {total_affected} nodes across {file_count} files"
        if total_affected > 20:
            return f"High impact - consider staged rollout"
        if total_affected > 5:
            return f"Moderate impact - test {direct} direct dependents"
        return "Low impact - localized change"

    def get_focused_context(self, target: str, depth: int = 2) -> FocusedContext:
        """Extract relevant code context via subgraph.

        Args:
            target: Name of target entity
            depth: How many hops to include

        Returns:
            FocusedContext with relevant nodes and files
        """
        subgraph = self.algorithms.get_subgraph(target, depth=depth)

        # Get files
        relevant_files: set[Path] = set()
        for node in subgraph.nodes.values():
            if node.file_path:
                relevant_files.add(node.file_path)

        center_node = None
        if subgraph.center_node_id:
            center_node = subgraph.nodes.get(subgraph.center_node_id)

        rationale = (
            f"Extracted {len(subgraph.nodes)} nodes within {depth} hops "
            f"across {len(relevant_files)} files"
        )

        return FocusedContext(
            center_node=center_node,
            relevant_nodes=tuple(subgraph.nodes.values()),
            relevant_files=tuple(sorted(relevant_files)),
            edges=len(subgraph.edges),
            rationale=rationale,
        )

    def get_execution_order(self, targets: list[str]) -> ExecutionOrder:
        """Get dependency-aware execution order via topo sort.

        Args:
            targets: Names of target entities

        Returns:
            ExecutionOrder with ordered nodes
        """
        # Try topological sort
        ordered = self.algorithms.topological_sort(EdgeType.CALLS)

        if ordered is None:
            # Cycle detected
            cycles = self.algorithms.find_cycles(EdgeType.CALLS, max_cycles=3)
            cycle_info = ""
            if cycles:
                cycle_names = [n.name for n in cycles[0][:5]]
                cycle_info = f" Cycle: {' → '.join(cycle_names)}"

            return ExecutionOrder(
                ordered_nodes=(),
                has_cycles=True,
                rationale=f"Circular dependencies detected.{cycle_info}",
            )

        # Filter to relevant nodes
        target_set: set[str] = set()
        for target in targets:
            for node in self.graph.find_structural_nodes(target):
                target_set.add(node.id)

        # Include targets and their dependencies
        relevant: list[StructuralNode] = []
        for node in ordered:
            if node.id in target_set:
                relevant.append(node)

        return ExecutionOrder(
            ordered_nodes=tuple(relevant),
            has_cycles=False,
            rationale=f"Dependency order for {len(relevant)} nodes",
        )
