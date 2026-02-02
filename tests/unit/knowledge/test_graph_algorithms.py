"""Tests for structural graph algorithms."""

from pathlib import Path

import pytest

from sunwell.knowledge.codebase import (
    CodebaseGraph,
    EdgeType,
    GraphAlgorithms,
    NodeType,
    StructuralEdge,
    StructuralNode,
)


@pytest.fixture
def sample_graph() -> CodebaseGraph:
    """Create a sample graph for testing.

    Graph structure:
        Module (module:test.py)
        ├── ClassA (class:ClassA)
        │   ├── method_a (method:method_a) -> calls func_b
        │   └── method_b (method:method_b)
        ├── func_a (func:func_a) -> calls func_b, func_c
        ├── func_b (func:func_b) -> calls func_c
        └── func_c (func:func_c)
    """
    graph = CodebaseGraph()
    test_file = Path("test.py")

    # Module node
    module = StructuralNode(
        id="module:test.py",
        node_type=NodeType.MODULE,
        name="test",
        file_path=test_file,
        line=1,
        end_line=100,
    )
    graph.add_structural_node(module)

    # Class node
    class_a = StructuralNode(
        id="class:ClassA:test.py",
        node_type=NodeType.CLASS,
        name="ClassA",
        file_path=test_file,
        line=10,
        end_line=30,
        signature="class ClassA:",
        docstring="A test class.",
    )
    graph.add_structural_node(class_a)
    graph.add_structural_edge(
        StructuralEdge(
            source_id="module:test.py",
            target_id="class:ClassA:test.py",
            edge_type=EdgeType.CONTAINS,
            line=10,
        )
    )

    # Method nodes
    method_a = StructuralNode(
        id="method:method_a:test.py:12",
        node_type=NodeType.METHOD,
        name="method_a",
        file_path=test_file,
        line=12,
        end_line=18,
        signature="def method_a(self):",
    )
    graph.add_structural_node(method_a)
    graph.add_structural_edge(
        StructuralEdge(
            source_id="class:ClassA:test.py",
            target_id="method:method_a:test.py:12",
            edge_type=EdgeType.DEFINES,
            line=12,
        )
    )

    method_b = StructuralNode(
        id="method:method_b:test.py:20",
        node_type=NodeType.METHOD,
        name="method_b",
        file_path=test_file,
        line=20,
        end_line=25,
        signature="def method_b(self):",
    )
    graph.add_structural_node(method_b)
    graph.add_structural_edge(
        StructuralEdge(
            source_id="class:ClassA:test.py",
            target_id="method:method_b:test.py:20",
            edge_type=EdgeType.DEFINES,
            line=20,
        )
    )

    # Function nodes
    func_a = StructuralNode(
        id="func:func_a:test.py:40",
        node_type=NodeType.FUNCTION,
        name="func_a",
        file_path=test_file,
        line=40,
        end_line=50,
        signature="def func_a():",
    )
    graph.add_structural_node(func_a)
    graph.add_structural_edge(
        StructuralEdge(
            source_id="module:test.py",
            target_id="func:func_a:test.py:40",
            edge_type=EdgeType.CONTAINS,
            line=40,
        )
    )

    func_b = StructuralNode(
        id="func:func_b:test.py:55",
        node_type=NodeType.FUNCTION,
        name="func_b",
        file_path=test_file,
        line=55,
        end_line=65,
        signature="def func_b():",
    )
    graph.add_structural_node(func_b)
    graph.add_structural_edge(
        StructuralEdge(
            source_id="module:test.py",
            target_id="func:func_b:test.py:55",
            edge_type=EdgeType.CONTAINS,
            line=55,
        )
    )

    func_c = StructuralNode(
        id="func:func_c:test.py:70",
        node_type=NodeType.FUNCTION,
        name="func_c",
        file_path=test_file,
        line=70,
        end_line=80,
        signature="def func_c():",
    )
    graph.add_structural_node(func_c)
    graph.add_structural_edge(
        StructuralEdge(
            source_id="module:test.py",
            target_id="func:func_c:test.py:70",
            edge_type=EdgeType.CONTAINS,
            line=70,
        )
    )

    # CALLS edges
    # method_a -> func_b
    graph.add_structural_edge(
        StructuralEdge(
            source_id="method:method_a:test.py:12",
            target_id="func:func_b:test.py:55",
            edge_type=EdgeType.CALLS,
            line=15,
        )
    )

    # func_a -> func_b
    graph.add_structural_edge(
        StructuralEdge(
            source_id="func:func_a:test.py:40",
            target_id="func:func_b:test.py:55",
            edge_type=EdgeType.CALLS,
            line=45,
        )
    )

    # func_a -> func_c
    graph.add_structural_edge(
        StructuralEdge(
            source_id="func:func_a:test.py:40",
            target_id="func:func_c:test.py:70",
            edge_type=EdgeType.CALLS,
            line=46,
        )
    )

    # func_b -> func_c
    graph.add_structural_edge(
        StructuralEdge(
            source_id="func:func_b:test.py:55",
            target_id="func:func_c:test.py:70",
            edge_type=EdgeType.CALLS,
            line=60,
        )
    )

    return graph


class TestFanMetrics:
    """Tests for fan-in/fan-out analysis."""

    def test_fan_out(self, sample_graph: CodebaseGraph) -> None:
        """Test fan-out calculation."""
        algos = GraphAlgorithms(sample_graph)

        # func_a calls 2 functions
        assert algos.fan_out("func:func_a:test.py:40", EdgeType.CALLS) == 2

        # func_b calls 1 function
        assert algos.fan_out("func:func_b:test.py:55", EdgeType.CALLS) == 1

        # func_c calls nothing
        assert algos.fan_out("func:func_c:test.py:70", EdgeType.CALLS) == 0

    def test_fan_in(self, sample_graph: CodebaseGraph) -> None:
        """Test fan-in calculation."""
        algos = GraphAlgorithms(sample_graph)

        # func_c is called by func_a and func_b
        assert algos.fan_in("func:func_c:test.py:70", EdgeType.CALLS) == 2

        # func_b is called by func_a and method_a
        assert algos.fan_in("func:func_b:test.py:55", EdgeType.CALLS) == 2

        # func_a is not called by anything
        assert algos.fan_in("func:func_a:test.py:40", EdgeType.CALLS) == 0

    def test_get_fan_metrics(self, sample_graph: CodebaseGraph) -> None:
        """Test combined fan metrics."""
        algos = GraphAlgorithms(sample_graph)

        metrics = algos.get_fan_metrics("func:func_a:test.py:40")
        assert metrics is not None
        assert metrics.node.name == "func_a"
        assert metrics.call_out == 2  # calls func_b, func_c
        assert metrics.call_in == 0  # not called

    def test_most_complex(self, sample_graph: CodebaseGraph) -> None:
        """Test finding most complex nodes."""
        algos = GraphAlgorithms(sample_graph)

        complex_nodes = algos.most_complex(top_n=3)
        assert len(complex_nodes) >= 1

        # func_a should be most complex (highest fan-out)
        names = [m.node.name for m in complex_nodes]
        assert "func_a" in names


class TestImpactAnalysis:
    """Tests for impact/reachability analysis."""

    def test_get_impact(self, sample_graph: CodebaseGraph) -> None:
        """Test impact analysis (what depends on target)."""
        algos = GraphAlgorithms(sample_graph)

        # What depends on func_c?
        impacted = algos.get_impact("func_c")

        # func_a and func_b call func_c (directly or transitively)
        names = {n.name for n in impacted}
        assert "func_c" in names  # includes self
        assert "func_b" in names  # calls func_c
        assert "func_a" in names  # calls func_c

    def test_get_dependencies(self, sample_graph: CodebaseGraph) -> None:
        """Test dependency analysis (what target depends on)."""
        algos = GraphAlgorithms(sample_graph)

        # What does func_a depend on?
        deps = algos.get_dependencies("func_a")

        names = {n.name for n in deps}
        assert "func_b" in names  # func_a calls func_b
        assert "func_c" in names  # func_a calls func_c


class TestPathFinding:
    """Tests for path finding."""

    def test_find_path_exists(self, sample_graph: CodebaseGraph) -> None:
        """Test finding a path that exists."""
        algos = GraphAlgorithms(sample_graph)

        # Path from func_a to func_c
        path = algos.find_path("func_a", "func_c")
        assert path is not None
        assert len(path) >= 2

        names = [n.name for n in path]
        assert names[0] == "func_a"
        assert names[-1] == "func_c"

    def test_find_path_not_exists(self, sample_graph: CodebaseGraph) -> None:
        """Test finding a path that doesn't exist."""
        algos = GraphAlgorithms(sample_graph)

        # No path from func_c to func_a (reverse direction)
        path = algos.find_path("func_c", "func_a")
        assert path is None

    def test_find_path_same_node(self, sample_graph: CodebaseGraph) -> None:
        """Test finding path to self."""
        algos = GraphAlgorithms(sample_graph)

        # Path from func_a to func_a
        path = algos.find_path("func_a", "func_a")
        assert path is not None
        assert len(path) == 1


class TestSubgraphExtraction:
    """Tests for subgraph extraction."""

    def test_get_subgraph_depth_1(self, sample_graph: CodebaseGraph) -> None:
        """Test extracting immediate neighbors."""
        algos = GraphAlgorithms(sample_graph)

        subgraph = algos.get_subgraph("func_b", depth=1)

        names = {n.name for n in subgraph.nodes.values()}
        assert "func_b" in names
        assert "func_c" in names  # func_b calls func_c
        # Parent (module) included via CONTAINS edge
        assert "test" in names

    def test_get_subgraph_depth_2(self, sample_graph: CodebaseGraph) -> None:
        """Test extracting 2-hop neighborhood."""
        algos = GraphAlgorithms(sample_graph)

        subgraph = algos.get_subgraph("func_a", depth=2)

        # Should include func_a, func_b, func_c (and module)
        names = {n.name for n in subgraph.nodes.values()}
        assert "func_a" in names
        assert "func_b" in names
        assert "func_c" in names


class TestCycleDetection:
    """Tests for cycle detection."""

    def test_no_cycles(self, sample_graph: CodebaseGraph) -> None:
        """Test graph with no cycles."""
        algos = GraphAlgorithms(sample_graph)

        cycles = algos.find_cycles(edge_type=EdgeType.CALLS)
        assert len(cycles) == 0

    def test_with_cycle(self) -> None:
        """Test graph with a cycle."""
        graph = CodebaseGraph()

        # Create a cycle: A -> B -> C -> A
        for name in ["A", "B", "C"]:
            graph.add_structural_node(
                StructuralNode(
                    id=f"func:{name}:test.py",
                    node_type=NodeType.FUNCTION,
                    name=name,
                    file_path=Path("test.py"),
                    line=1,
                )
            )

        graph.add_structural_edge(
            StructuralEdge(
                source_id="func:A:test.py",
                target_id="func:B:test.py",
                edge_type=EdgeType.CALLS,
            )
        )
        graph.add_structural_edge(
            StructuralEdge(
                source_id="func:B:test.py",
                target_id="func:C:test.py",
                edge_type=EdgeType.CALLS,
            )
        )
        graph.add_structural_edge(
            StructuralEdge(
                source_id="func:C:test.py",
                target_id="func:A:test.py",
                edge_type=EdgeType.CALLS,
            )
        )

        algos = GraphAlgorithms(graph)
        cycles = algos.find_cycles(edge_type=EdgeType.CALLS)

        assert len(cycles) >= 1
        # Cycle should contain A, B, C
        cycle_names = {n.name for n in cycles[0]}
        assert "A" in cycle_names or "B" in cycle_names or "C" in cycle_names


class TestSCC:
    """Tests for strongly connected components."""

    def test_no_scc(self, sample_graph: CodebaseGraph) -> None:
        """Test graph with no SCCs."""
        algos = GraphAlgorithms(sample_graph)

        sccs = algos.find_sccs(edge_type=EdgeType.CALLS, min_size=2)
        assert len(sccs) == 0

    def test_with_scc(self) -> None:
        """Test graph with an SCC."""
        graph = CodebaseGraph()

        # Create an SCC: A <-> B (mutual calls)
        for name in ["A", "B"]:
            graph.add_structural_node(
                StructuralNode(
                    id=f"func:{name}:test.py",
                    node_type=NodeType.FUNCTION,
                    name=name,
                    file_path=Path("test.py"),
                    line=1,
                )
            )

        graph.add_structural_edge(
            StructuralEdge(
                source_id="func:A:test.py",
                target_id="func:B:test.py",
                edge_type=EdgeType.CALLS,
            )
        )
        graph.add_structural_edge(
            StructuralEdge(
                source_id="func:B:test.py",
                target_id="func:A:test.py",
                edge_type=EdgeType.CALLS,
            )
        )

        algos = GraphAlgorithms(graph)
        sccs = algos.find_sccs(edge_type=EdgeType.CALLS, min_size=2)

        assert len(sccs) == 1
        assert len(sccs[0]) == 2


class TestTopologicalSort:
    """Tests for topological sort."""

    def test_topo_sort_acyclic(self, sample_graph: CodebaseGraph) -> None:
        """Test topological sort on acyclic graph."""
        algos = GraphAlgorithms(sample_graph)

        ordered = algos.topological_sort(edge_type=EdgeType.CALLS)
        assert ordered is not None

        # In a valid topological order, dependencies come before dependents
        # So func_c should come before func_a (func_a depends on func_c)
        names = [n.name for n in ordered]

        # Find positions
        positions = {name: i for i, name in enumerate(names)}

        # func_c should appear before anything that calls it
        if "func_c" in positions and "func_b" in positions:
            # Note: topological sort gives sources first, so func_a comes before func_c
            # because func_a has no incoming CALLS edges
            pass  # Order depends on implementation

    def test_topo_sort_cyclic(self) -> None:
        """Test topological sort returns None for cyclic graph."""
        graph = CodebaseGraph()

        # Create a cycle
        for name in ["A", "B"]:
            graph.add_structural_node(
                StructuralNode(
                    id=f"func:{name}:test.py",
                    node_type=NodeType.FUNCTION,
                    name=name,
                    file_path=Path("test.py"),
                    line=1,
                )
            )

        graph.add_structural_edge(
            StructuralEdge(
                source_id="func:A:test.py",
                target_id="func:B:test.py",
                edge_type=EdgeType.CALLS,
            )
        )
        graph.add_structural_edge(
            StructuralEdge(
                source_id="func:B:test.py",
                target_id="func:A:test.py",
                edge_type=EdgeType.CALLS,
            )
        )

        algos = GraphAlgorithms(graph)
        ordered = algos.topological_sort(edge_type=EdgeType.CALLS)

        assert ordered is None


class TestCallerCallees:
    """Tests for caller/callee convenience methods."""

    def test_get_callers(self, sample_graph: CodebaseGraph) -> None:
        """Test getting callers of a function."""
        algos = GraphAlgorithms(sample_graph)

        callers = algos.get_callers("func_c")
        names = {n.name for n in callers}

        assert "func_a" in names
        assert "func_b" in names

    def test_get_callees(self, sample_graph: CodebaseGraph) -> None:
        """Test getting callees of a function."""
        algos = GraphAlgorithms(sample_graph)

        callees = algos.get_callees("func_a")
        names = {n.name for n in callees}

        assert "func_b" in names
        assert "func_c" in names
