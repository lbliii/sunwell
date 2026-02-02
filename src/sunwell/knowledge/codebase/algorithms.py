"""Graph Algorithms for Structural Code Analysis.

Provides algorithms for analyzing the structural graph:
- Fan-out/Fan-in: Complexity and dependency analysis
- Impact analysis: Transitive reachability (blast radius)
- Path finding: Trace flow between entities
- Subgraph extraction: Focused context retrieval
- Cycle detection: Circular dependency detection
- SCC (Tarjan): Find tightly coupled code clusters
- Topological sort: Dependency ordering

These algorithms power the TaskGraphAdvisor for goal analysis
and task decomposition.
"""

from collections import deque
from dataclasses import dataclass, field

from sunwell.knowledge.codebase.codebase import (
    CodebaseGraph,
    EdgeType,
    NodeType,
    StructuralEdge,
    StructuralNode,
)


@dataclass(frozen=True, slots=True)
class FanMetrics:
    """Fan-in/fan-out metrics for a node."""

    node: StructuralNode
    fan_in: int  # Incoming edges (things that depend on this)
    fan_out: int  # Outgoing edges (things this depends on)
    call_in: int  # Incoming CALLS edges specifically
    call_out: int  # Outgoing CALLS edges specifically


@dataclass(slots=True)
class SubgraphResult:
    """Result of subgraph extraction."""

    nodes: dict[str, StructuralNode] = field(default_factory=dict)
    edges: list[StructuralEdge] = field(default_factory=list)
    center_node_id: str | None = None
    depth: int = 0


class GraphAlgorithms:
    """Collection of graph algorithms for code analysis.

    Usage:
        algos = GraphAlgorithms(codebase_graph)
        fan = algos.fan_out("class:MyClass:path.py")
        impact = algos.get_impact("func:important_function:path.py")
        path = algos.find_path("func:main", "func:helper")
    """

    def __init__(self, graph: CodebaseGraph) -> None:
        self.graph = graph

    # -------------------------------------------------------------------------
    # Fan-In / Fan-Out Analysis
    # -------------------------------------------------------------------------

    def fan_out(self, node_id: str, edge_type: EdgeType | None = None) -> int:
        """Count outgoing edges from a node.

        High fan-out indicates:
        - Complex orchestrator functions
        - Functions with many dependencies
        - Potential candidates for decomposition
        """
        edges = self.graph.structural_edges_out.get(node_id, [])
        if edge_type is None:
            return len(edges)
        return sum(1 for _, e in edges if e.edge_type == edge_type)

    def fan_in(self, node_id: str, edge_type: EdgeType | None = None) -> int:
        """Count incoming edges to a node.

        High fan-in indicates:
        - Widely used utilities
        - Potential "god objects"
        - High-impact change targets
        """
        edges = self.graph.structural_edges_in.get(node_id, [])
        if edge_type is None:
            return len(edges)
        return sum(1 for _, e in edges if e.edge_type == edge_type)

    def get_fan_metrics(self, node_id: str) -> FanMetrics | None:
        """Get comprehensive fan metrics for a node."""
        node = self.graph.structural_nodes.get(node_id)
        if not node:
            return None

        return FanMetrics(
            node=node,
            fan_in=self.fan_in(node_id),
            fan_out=self.fan_out(node_id),
            call_in=self.fan_in(node_id, EdgeType.CALLS),
            call_out=self.fan_out(node_id, EdgeType.CALLS),
        )

    def most_complex(
        self,
        top_n: int = 20,
        node_type: NodeType | None = None,
        internal_only: bool = True,
    ) -> list[FanMetrics]:
        """Find the most complex nodes by fan-out.

        These are typically orchestrator functions or complex classes.
        """
        results: list[FanMetrics] = []

        for node_id, node in self.graph.structural_nodes.items():
            if node_type and node.node_type != node_type:
                continue
            if internal_only and not node.file_path:
                continue

            metrics = self.get_fan_metrics(node_id)
            if metrics and metrics.fan_out > 0:
                results.append(metrics)

        results.sort(key=lambda m: m.fan_out, reverse=True)
        return results[:top_n]

    def most_depended_on(
        self,
        top_n: int = 20,
        node_type: NodeType | None = None,
        internal_only: bool = True,
    ) -> list[FanMetrics]:
        """Find nodes with highest fan-in (most depended on).

        These are critical shared components - changes have wide impact.
        """
        results: list[FanMetrics] = []

        for node_id, node in self.graph.structural_nodes.items():
            if node_type and node.node_type != node_type:
                continue
            if internal_only and not node.file_path:
                continue

            metrics = self.get_fan_metrics(node_id)
            if metrics and metrics.fan_in > 0:
                results.append(metrics)

        results.sort(key=lambda m: m.fan_in, reverse=True)
        return results[:top_n]

    # -------------------------------------------------------------------------
    # Impact Analysis (Transitive Reachability)
    # -------------------------------------------------------------------------

    def get_impact(
        self,
        name: str,
        max_depth: int = 5,
        edge_types: tuple[EdgeType, ...] | None = None,
    ) -> set[StructuralNode]:
        """Get all nodes transitively reachable from the given node.

        This represents the "blast radius" of a change - what could be affected.
        Uses reverse traversal (incoming edges) to find dependents.

        Args:
            name: Name to search for (partial match)
            max_depth: Maximum traversal depth
            edge_types: Edge types to follow (default: CALLS, USES, INHERITS)

        Returns:
            Set of all nodes that depend on the target (transitively)
        """
        if edge_types is None:
            edge_types = (EdgeType.CALLS, EdgeType.USES, EdgeType.INHERITS)

        start_nodes = self.graph.find_structural_nodes(name)
        if not start_nodes:
            return set()

        impacted: set[StructuralNode] = set()
        visited: set[str] = set()
        queue: deque[tuple[str, int]] = deque()

        for node in start_nodes:
            queue.append((node.id, 0))
            visited.add(node.id)
            impacted.add(node)

        while queue:
            node_id, depth = queue.popleft()

            if depth >= max_depth:
                continue

            # Things that depend on this node (incoming edges)
            for source_id, edge in self.graph.structural_edges_in.get(node_id, []):
                if edge.edge_type in edge_types:
                    if source_id not in visited:
                        visited.add(source_id)
                        source = self.graph.structural_nodes.get(source_id)
                        if source:
                            impacted.add(source)
                            queue.append((source_id, depth + 1))

        return impacted

    def get_dependencies(
        self,
        name: str,
        max_depth: int = 5,
        edge_types: tuple[EdgeType, ...] | None = None,
    ) -> set[StructuralNode]:
        """Get all nodes that the given node depends on (transitively).

        Opposite of get_impact - follows outgoing edges.

        Args:
            name: Name to search for (partial match)
            max_depth: Maximum traversal depth
            edge_types: Edge types to follow (default: CALLS, USES, IMPORTS)

        Returns:
            Set of all nodes that the target depends on
        """
        if edge_types is None:
            edge_types = (EdgeType.CALLS, EdgeType.USES, EdgeType.IMPORTS)

        start_nodes = self.graph.find_structural_nodes(name)
        if not start_nodes:
            return set()

        dependencies: set[StructuralNode] = set()
        visited: set[str] = set()
        queue: deque[tuple[str, int]] = deque()

        for node in start_nodes:
            queue.append((node.id, 0))
            visited.add(node.id)

        while queue:
            node_id, depth = queue.popleft()

            if depth >= max_depth:
                continue

            # Things this node depends on (outgoing edges)
            for target_id, edge in self.graph.structural_edges_out.get(node_id, []):
                if edge.edge_type in edge_types:
                    if target_id not in visited:
                        visited.add(target_id)
                        target = self.graph.structural_nodes.get(target_id)
                        if target:
                            dependencies.add(target)
                            queue.append((target_id, depth + 1))

        return dependencies

    # -------------------------------------------------------------------------
    # Path Finding
    # -------------------------------------------------------------------------

    def find_path(
        self,
        start_name: str,
        end_name: str,
        max_depth: int = 10,
        edge_types: tuple[EdgeType, ...] | None = None,
    ) -> list[StructuralNode] | None:
        """Find shortest path between two nodes (BFS).

        Useful for understanding flow: how does A eventually lead to B?

        Args:
            start_name: Name of start node (partial match)
            end_name: Name of end node (partial match)
            max_depth: Maximum path length
            edge_types: Edge types to follow (default: all)

        Returns:
            List of nodes forming the path, or None if no path exists
        """
        start_nodes = self.graph.find_structural_nodes(start_name)
        end_nodes = self.graph.find_structural_nodes(end_name)

        if not start_nodes or not end_nodes:
            return None

        end_ids = {n.id for n in end_nodes}

        for start in start_nodes:
            # BFS with path tracking
            visited: set[str] = {start.id}
            queue: deque[list[str]] = deque([[start.id]])

            while queue:
                path = queue.popleft()
                if len(path) > max_depth:
                    continue

                current_id = path[-1]

                if current_id in end_ids:
                    # Found path - convert IDs to nodes
                    return [
                        self.graph.structural_nodes[nid]
                        for nid in path
                        if nid in self.graph.structural_nodes
                    ]

                for target_id, edge in self.graph.structural_edges_out.get(
                    current_id, []
                ):
                    if edge_types and edge.edge_type not in edge_types:
                        continue
                    if target_id not in visited:
                        visited.add(target_id)
                        queue.append(path + [target_id])

        return None

    # -------------------------------------------------------------------------
    # Subgraph Extraction (Focused Context)
    # -------------------------------------------------------------------------

    def get_subgraph(self, name: str, depth: int = 1) -> SubgraphResult:
        """Extract a subgraph around a node (BFS to given depth).

        Useful for gathering focused context for a task:
        - Depth 1: Direct neighbors
        - Depth 2: Neighbors of neighbors
        - etc.

        Args:
            name: Name to search for (partial match)
            depth: How many hops to include

        Returns:
            SubgraphResult with nodes and edges in the neighborhood
        """
        result = SubgraphResult(depth=depth)
        start_nodes = self.graph.find_structural_nodes(name)

        if not start_nodes:
            return result

        result.center_node_id = start_nodes[0].id if start_nodes else None

        visited: set[str] = set()
        queue: deque[tuple[str, int]] = deque()

        # Start from all matching nodes
        for node in start_nodes:
            queue.append((node.id, 0))
            visited.add(node.id)

        while queue:
            node_id, current_depth = queue.popleft()
            node = self.graph.structural_nodes.get(node_id)
            if node:
                result.nodes[node_id] = node

            if current_depth >= depth:
                continue

            # Traverse outgoing edges
            for target_id, edge in self.graph.structural_edges_out.get(node_id, []):
                result.edges.append(edge)
                if target_id not in visited:
                    visited.add(target_id)
                    queue.append((target_id, current_depth + 1))

            # Also include incoming CONTAINS/DEFINES for structure
            for source_id, edge in self.graph.structural_edges_in.get(node_id, []):
                if edge.edge_type in (EdgeType.CONTAINS, EdgeType.DEFINES):
                    result.edges.append(edge)
                    if source_id not in visited:
                        visited.add(source_id)
                        queue.append((source_id, current_depth + 1))

        return result

    # -------------------------------------------------------------------------
    # Cycle Detection
    # -------------------------------------------------------------------------

    def find_cycles(
        self,
        edge_type: EdgeType | None = None,
        max_cycles: int = 10,
    ) -> list[list[StructuralNode]]:
        """Find cycles in the graph (circular dependencies).

        Uses DFS with coloring: WHITE (unvisited), GRAY (in stack), BLACK (done).

        Args:
            edge_type: Type of edges to follow (None = all)
            max_cycles: Maximum number of cycles to find

        Returns:
            List of cycles, each cycle is a list of nodes
        """
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {nid: WHITE for nid in self.graph.structural_nodes}
        cycles: list[list[StructuralNode]] = []

        def dfs(node_id: str, path: list[str]) -> None:
            if len(cycles) >= max_cycles:
                return

            color[node_id] = GRAY
            path.append(node_id)

            for target_id, edge in self.graph.structural_edges_out.get(node_id, []):
                if edge_type and edge.edge_type != edge_type:
                    continue

                if color.get(target_id, WHITE) == GRAY:
                    # Found cycle - extract it
                    if target_id in path:
                        cycle_start = path.index(target_id)
                        cycle_ids = path[cycle_start:] + [target_id]
                        cycle_nodes = [
                            self.graph.structural_nodes[nid]
                            for nid in cycle_ids
                            if nid in self.graph.structural_nodes
                        ]
                        if cycle_nodes and len(cycles) < max_cycles:
                            cycles.append(cycle_nodes)
                elif color.get(target_id, WHITE) == WHITE:
                    dfs(target_id, path)

            path.pop()
            color[node_id] = BLACK

        for node_id in self.graph.structural_nodes:
            if color[node_id] == WHITE:
                dfs(node_id, [])
                if len(cycles) >= max_cycles:
                    break

        return cycles

    # -------------------------------------------------------------------------
    # Strongly Connected Components (Tarjan's Algorithm)
    # -------------------------------------------------------------------------

    def find_sccs(
        self,
        edge_type: EdgeType | None = None,
        min_size: int = 2,
    ) -> list[list[StructuralNode]]:
        """Find strongly connected components (tightly coupled code clusters).

        Uses Tarjan's algorithm. Returns SCCs with at least min_size nodes.

        Args:
            edge_type: Type of edges to follow (None = all)
            min_size: Minimum SCC size to return

        Returns:
            List of SCCs, sorted by size (largest first)
        """
        index_counter = [0]
        stack: list[str] = []
        lowlinks: dict[str, int] = {}
        index: dict[str, int] = {}
        on_stack: set[str] = set()
        sccs: list[list[str]] = []

        def strongconnect(node_id: str) -> None:
            index[node_id] = index_counter[0]
            lowlinks[node_id] = index_counter[0]
            index_counter[0] += 1
            stack.append(node_id)
            on_stack.add(node_id)

            for target_id, edge in self.graph.structural_edges_out.get(node_id, []):
                if edge_type and edge.edge_type != edge_type:
                    continue

                if target_id not in index:
                    strongconnect(target_id)
                    lowlinks[node_id] = min(lowlinks[node_id], lowlinks[target_id])
                elif target_id in on_stack:
                    lowlinks[node_id] = min(lowlinks[node_id], index[target_id])

            if lowlinks[node_id] == index[node_id]:
                scc: list[str] = []
                while True:
                    w = stack.pop()
                    on_stack.remove(w)
                    scc.append(w)
                    if w == node_id:
                        break
                if len(scc) >= min_size:
                    sccs.append(scc)

        for node_id in self.graph.structural_nodes:
            if node_id not in index:
                strongconnect(node_id)

        # Convert to nodes and sort by size
        result: list[list[StructuralNode]] = []
        for scc_ids in sccs:
            scc_nodes = [
                self.graph.structural_nodes[nid]
                for nid in scc_ids
                if nid in self.graph.structural_nodes
            ]
            if len(scc_nodes) >= min_size:
                result.append(scc_nodes)

        return sorted(result, key=len, reverse=True)

    # -------------------------------------------------------------------------
    # Topological Sort (Dependency Order)
    # -------------------------------------------------------------------------

    def topological_sort(
        self,
        edge_type: EdgeType = EdgeType.IMPORTS,
        node_type: NodeType | None = None,
    ) -> list[StructuralNode] | None:
        """Topological sort - find dependency order.

        Returns nodes in order such that dependencies come before dependents.
        Returns None if there's a cycle (no valid ordering).

        Args:
            edge_type: Edge type to use for dependencies
            node_type: Filter to specific node type (None = all)

        Returns:
            Ordered list of nodes, or None if cycle exists
        """
        # Filter nodes if needed
        if node_type:
            relevant_nodes = {
                nid
                for nid, n in self.graph.structural_nodes.items()
                if n.node_type == node_type
            }
        else:
            relevant_nodes = set(self.graph.structural_nodes.keys())

        in_degree: dict[str, int] = {nid: 0 for nid in relevant_nodes}

        # Calculate in-degrees for the specified edge type
        for node_id in relevant_nodes:
            for _, edge in self.graph.structural_edges_in.get(node_id, []):
                if edge.edge_type == edge_type:
                    if edge.source_id in relevant_nodes:
                        in_degree[node_id] += 1

        # Start with nodes that have no dependencies
        queue = deque([nid for nid, deg in in_degree.items() if deg == 0])
        result: list[str] = []

        while queue:
            node_id = queue.popleft()
            result.append(node_id)

            for target_id, edge in self.graph.structural_edges_out.get(node_id, []):
                if edge.edge_type == edge_type and target_id in in_degree:
                    in_degree[target_id] -= 1
                    if in_degree[target_id] == 0:
                        queue.append(target_id)

        if len(result) != len(relevant_nodes):
            return None  # Cycle detected

        return [
            self.graph.structural_nodes[nid]
            for nid in result
            if nid in self.graph.structural_nodes
        ]

    # -------------------------------------------------------------------------
    # Callers / Callees (Convenience Methods)
    # -------------------------------------------------------------------------

    def get_callers(self, name: str) -> list[StructuralNode]:
        """Get all functions that call the given function/method."""
        callers: list[StructuralNode] = []
        for node in self.graph.find_structural_nodes(name):
            for source, edge in self.graph.get_incoming_edges(node.id, EdgeType.CALLS):
                callers.append(source)
        return callers

    def get_callees(self, name: str) -> list[StructuralNode]:
        """Get all functions called by the given function/method."""
        callees: list[StructuralNode] = []
        for node in self.graph.find_structural_nodes(name):
            for target, edge in self.graph.get_outgoing_edges(node.id, EdgeType.CALLS):
                callees.append(target)
        return callees
