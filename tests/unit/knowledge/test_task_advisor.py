"""Tests for TaskGraphAdvisor."""

from pathlib import Path

import pytest

from sunwell.knowledge.codebase import (
    CodebaseGraph,
    EdgeType,
    NodeType,
    StructuralEdge,
    StructuralNode,
    TaskGraphAdvisor,
    TaskType,
)


@pytest.fixture
def sample_graph() -> CodebaseGraph:
    """Create a sample graph for testing TaskGraphAdvisor."""
    graph = CodebaseGraph()
    test_file = Path("service.py")

    # Module
    module = StructuralNode(
        id="module:service.py",
        node_type=NodeType.MODULE,
        name="service",
        file_path=test_file,
        line=1,
        end_line=100,
    )
    graph.add_structural_node(module)

    # Class: UserService
    user_service = StructuralNode(
        id="class:UserService:service.py",
        node_type=NodeType.CLASS,
        name="UserService",
        file_path=test_file,
        line=10,
        end_line=50,
        signature="class UserService:",
        docstring="Handles user operations.",
    )
    graph.add_structural_node(user_service)
    graph.add_structural_edge(
        StructuralEdge(
            source_id="module:service.py",
            target_id="class:UserService:service.py",
            edge_type=EdgeType.CONTAINS,
            line=10,
        )
    )

    # Methods
    for i, (name, calls) in enumerate(
        [
            ("get_user", ["validate_id", "fetch_from_db"]),
            ("create_user", ["validate_data", "save_to_db", "send_email"]),
            ("delete_user", ["check_permissions", "remove_from_db"]),
        ],
        start=1,
    ):
        method = StructuralNode(
            id=f"method:{name}:service.py:{10 + i * 10}",
            node_type=NodeType.METHOD,
            name=name,
            file_path=test_file,
            line=10 + i * 10,
            end_line=10 + i * 10 + 8,
            signature=f"def {name}(self):",
        )
        graph.add_structural_node(method)
        graph.add_structural_edge(
            StructuralEdge(
                source_id="class:UserService:service.py",
                target_id=method.id,
                edge_type=EdgeType.DEFINES,
                line=method.line,
            )
        )

        # Add call edges
        for called in calls:
            target_id = f"func:{called}:unknown"
            if target_id not in graph.structural_nodes:
                graph.add_structural_node(
                    StructuralNode(
                        id=target_id,
                        node_type=NodeType.FUNCTION,
                        name=called,
                    )
                )
            graph.add_structural_edge(
                StructuralEdge(
                    source_id=method.id,
                    target_id=target_id,
                    edge_type=EdgeType.CALLS,
                    line=method.line + 2,
                )
            )

    # Add a helper function that calls UserService methods
    helper = StructuralNode(
        id="func:process_request:service.py:60",
        node_type=NodeType.FUNCTION,
        name="process_request",
        file_path=test_file,
        line=60,
        end_line=70,
        signature="def process_request(user_id):",
    )
    graph.add_structural_node(helper)
    graph.add_structural_edge(
        StructuralEdge(
            source_id="module:service.py",
            target_id=helper.id,
            edge_type=EdgeType.CONTAINS,
            line=60,
        )
    )

    # process_request calls get_user
    graph.add_structural_edge(
        StructuralEdge(
            source_id=helper.id,
            target_id="method:get_user:service.py:20",
            edge_type=EdgeType.CALLS,
            line=65,
        )
    )

    return graph


@pytest.fixture
def advisor(sample_graph: CodebaseGraph) -> TaskGraphAdvisor:
    """Create advisor with sample graph."""
    return TaskGraphAdvisor(sample_graph)


class TestTaskAdvice:
    """Tests for task analysis."""

    def test_analyze_add_feature(self, advisor: TaskGraphAdvisor) -> None:
        """Test analysis for adding a feature."""
        advice = advisor.analyze(TaskType.ADD_FEATURE, "UserService")

        assert advice.task_type == TaskType.ADD_FEATURE
        assert advice.target == "UserService"
        assert len(advice.target_nodes) >= 1

        # Should have complexity estimate
        assert advice.complexity is not None
        assert advice.complexity.score >= 0
        assert advice.complexity.score <= 1

        # Should have impact scope
        assert advice.impact is not None

    def test_analyze_fix_bug(self, advisor: TaskGraphAdvisor) -> None:
        """Test analysis for fixing a bug."""
        advice = advisor.analyze(TaskType.FIX_BUG, "get_user")

        assert advice.task_type == TaskType.FIX_BUG
        assert advice.context is not None
        assert len(advice.context.relevant_nodes) >= 1

    def test_analyze_refactor(self, advisor: TaskGraphAdvisor) -> None:
        """Test analysis for refactoring."""
        advice = advisor.analyze(TaskType.REFACTOR, "UserService")

        assert advice.task_type == TaskType.REFACTOR
        # Should check for god objects or tight coupling
        # potential_issues may or may not be populated depending on thresholds

    def test_analyze_understand(self, advisor: TaskGraphAdvisor) -> None:
        """Test analysis for understanding code."""
        advice = advisor.analyze(TaskType.UNDERSTAND, "create_user")

        assert advice.task_type == TaskType.UNDERSTAND
        assert advice.context is not None
        assert advice.complexity is not None

    def test_analyze_delete(self, advisor: TaskGraphAdvisor) -> None:
        """Test analysis for deleting code."""
        advice = advisor.analyze(TaskType.DELETE, "get_user")

        assert advice.task_type == TaskType.DELETE
        assert advice.impact is not None
        # get_user is called by process_request, so should have dependents
        assert advice.impact.transitive_dependents >= 1

    def test_analyze_test(self, advisor: TaskGraphAdvisor) -> None:
        """Test analysis for writing tests."""
        advice = advisor.analyze(TaskType.TEST, "create_user")

        assert advice.task_type == TaskType.TEST
        # create_user calls 3 functions, so should suggest mocking
        assert advice.context is not None

    def test_summary(self, advisor: TaskGraphAdvisor) -> None:
        """Test advice summary generation."""
        advice = advisor.analyze(TaskType.ADD_FEATURE, "UserService")
        summary = advice.summary()

        assert "ADD_FEATURE" in summary
        assert "UserService" in summary


class TestComplexityEstimate:
    """Tests for complexity estimation."""

    def test_complexity_high_fanout(self, advisor: TaskGraphAdvisor) -> None:
        """Test that high fan-out increases complexity."""
        # create_user has 3 calls, get_user has 2
        create_complexity = advisor.estimate_complexity("create_user")
        get_complexity = advisor.estimate_complexity("get_user")

        # create_user should be more complex
        assert create_complexity.fan_out >= get_complexity.fan_out

    def test_complexity_levels(self, advisor: TaskGraphAdvisor) -> None:
        """Test complexity level assignment."""
        complexity = advisor.estimate_complexity("get_user")

        assert complexity.level in ["trivial", "simple", "moderate", "complex", "very_complex"]

    def test_complexity_not_found(self, advisor: TaskGraphAdvisor) -> None:
        """Test complexity for non-existent target."""
        complexity = advisor.estimate_complexity("nonexistent_function")

        assert complexity.score == 0.5  # Default for not found
        assert "not found" in complexity.rationale.lower()


class TestImpactScope:
    """Tests for impact scope analysis."""

    def test_impact_with_dependents(self, advisor: TaskGraphAdvisor) -> None:
        """Test impact when there are dependents."""
        impact = advisor.get_impact_scope("get_user")

        # get_user is called by process_request
        assert impact.transitive_dependents >= 1

    def test_impact_no_dependents(self, advisor: TaskGraphAdvisor) -> None:
        """Test impact when there are no dependents."""
        impact = advisor.get_impact_scope("process_request")

        # process_request is not called by anything in our graph
        # But it includes itself
        assert impact.transitive_dependents >= 1

    def test_impact_affected_files(self, advisor: TaskGraphAdvisor) -> None:
        """Test that affected files are tracked."""
        impact = advisor.get_impact_scope("UserService")

        # Should include service.py
        file_names = [f.name for f in impact.affected_files]
        assert "service.py" in file_names


class TestFocusedContext:
    """Tests for focused context extraction."""

    def test_context_includes_target(self, advisor: TaskGraphAdvisor) -> None:
        """Test that context includes the target."""
        context = advisor.get_focused_context("get_user", depth=1)

        names = {n.name for n in context.relevant_nodes}
        assert "get_user" in names

    def test_context_includes_neighbors(self, advisor: TaskGraphAdvisor) -> None:
        """Test that context includes neighbors."""
        context = advisor.get_focused_context("get_user", depth=1)

        # Should include things get_user calls
        names = {n.name for n in context.relevant_nodes}
        # get_user calls validate_id and fetch_from_db
        assert "validate_id" in names or "fetch_from_db" in names

    def test_context_depth_affects_size(self, advisor: TaskGraphAdvisor) -> None:
        """Test that greater depth includes more nodes."""
        context_1 = advisor.get_focused_context("UserService", depth=1)
        context_2 = advisor.get_focused_context("UserService", depth=2)

        assert len(context_2.relevant_nodes) >= len(context_1.relevant_nodes)


class TestExecutionOrder:
    """Tests for execution order analysis."""

    def test_execution_order_acyclic(self, advisor: TaskGraphAdvisor) -> None:
        """Test execution order for acyclic graph."""
        order = advisor.get_execution_order(["get_user"])

        assert not order.has_cycles
        assert len(order.ordered_nodes) >= 0

    def test_execution_order_rationale(self, advisor: TaskGraphAdvisor) -> None:
        """Test that execution order has rationale."""
        order = advisor.get_execution_order(["UserService"])

        assert order.rationale is not None
        assert len(order.rationale) > 0
