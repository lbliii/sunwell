"""Tests for ContextEnricher integration with TaskGraphAdvisor."""

from pathlib import Path

import pytest

from sunwell.knowledge.codebase import (
    CodebaseGraph,
    EdgeType,
    NodeType,
    StructuralEdge,
    StructuralNode,
    TaskGraphAdvisor,
)
from sunwell.planning.reasoning.decisions import DecisionType
from sunwell.planning.reasoning.enrichment import ContextEnricher


@pytest.fixture
def sample_graph() -> CodebaseGraph:
    """Create a sample graph for testing."""
    graph = CodebaseGraph()
    test_file = Path("user_service.py")

    # Module
    module = StructuralNode(
        id="module:user_service.py",
        node_type=NodeType.MODULE,
        name="user_service",
        file_path=test_file,
        line=1,
        end_line=100,
    )
    graph.add_structural_node(module)

    # Class: UserService
    user_service = StructuralNode(
        id="class:UserService:user_service.py",
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
            source_id="module:user_service.py",
            target_id="class:UserService:user_service.py",
            edge_type=EdgeType.CONTAINS,
            line=10,
        )
    )

    # Method: get_user
    get_user = StructuralNode(
        id="method:get_user:user_service.py:20",
        node_type=NodeType.METHOD,
        name="get_user",
        file_path=test_file,
        line=20,
        end_line=30,
        signature="def get_user(self, user_id: int):",
    )
    graph.add_structural_node(get_user)
    graph.add_structural_edge(
        StructuralEdge(
            source_id="class:UserService:user_service.py",
            target_id="method:get_user:user_service.py:20",
            edge_type=EdgeType.DEFINES,
            line=20,
        )
    )

    # Add a call to external function
    validate_id = StructuralNode(
        id="func:validate_id:unknown",
        node_type=NodeType.FUNCTION,
        name="validate_id",
    )
    graph.add_structural_node(validate_id)
    graph.add_structural_edge(
        StructuralEdge(
            source_id="method:get_user:user_service.py:20",
            target_id="func:validate_id:unknown",
            edge_type=EdgeType.CALLS,
            line=25,
        )
    )

    return graph


@pytest.fixture
def task_advisor(sample_graph: CodebaseGraph) -> TaskGraphAdvisor:
    """Create task advisor with sample graph."""
    return TaskGraphAdvisor(sample_graph)


@pytest.fixture
def enricher(task_advisor: TaskGraphAdvisor) -> ContextEnricher:
    """Create enricher with task advisor."""
    return ContextEnricher(task_advisor=task_advisor)


class TestInferTargetEntity:
    """Tests for target entity inference."""

    def test_explicit_target_entity(self, enricher: ContextEnricher) -> None:
        """Test that explicit target_entity is used."""
        context = {"target_entity": "UserService"}
        target = enricher._infer_target_entity(context)
        assert target == "UserService"

    def test_infer_from_symbol_name(self, enricher: ContextEnricher) -> None:
        """Test inference from symbol_name."""
        context = {"symbol_name": "get_user"}
        target = enricher._infer_target_entity(context)
        assert target == "get_user"

    def test_infer_from_function_name(self, enricher: ContextEnricher) -> None:
        """Test inference from function_name."""
        context = {"function_name": "validate_input"}
        target = enricher._infer_target_entity(context)
        assert target == "validate_input"

    def test_infer_from_class_name(self, enricher: ContextEnricher) -> None:
        """Test inference from class_name."""
        context = {"class_name": "UserService"}
        target = enricher._infer_target_entity(context)
        assert target == "UserService"

    def test_infer_from_file_path(self, enricher: ContextEnricher) -> None:
        """Test inference from file_path (uses stem)."""
        context = {"file_path": "/path/to/user_service.py"}
        target = enricher._infer_target_entity(context)
        assert target == "user_service"

    def test_infer_from_content_camelcase(self, enricher: ContextEnricher) -> None:
        """Test inference from content with CamelCase."""
        context = {"content": "The UserService class handles authentication"}
        target = enricher._infer_target_entity(context)
        assert target == "UserService"

    def test_infer_from_content_snake_case(self, enricher: ContextEnricher) -> None:
        """Test inference from content with snake_case."""
        context = {"content": "Check the validate_user_input function"}
        target = enricher._infer_target_entity(context)
        assert target == "validate_user_input"

    def test_infer_from_description(self, enricher: ContextEnricher) -> None:
        """Test inference from description field."""
        context = {"description": "Fix the PaymentProcessor bug"}
        target = enricher._infer_target_entity(context)
        assert target == "PaymentProcessor"

    def test_no_target_found(self, enricher: ContextEnricher) -> None:
        """Test when no target can be inferred."""
        context = {"some_other_key": "value"}
        target = enricher._infer_target_entity(context)
        assert target is None

    def test_priority_explicit_over_symbol(self, enricher: ContextEnricher) -> None:
        """Test that explicit target_entity takes priority."""
        context = {
            "target_entity": "ExplicitTarget",
            "symbol_name": "other_symbol",
            "file_path": "/path/to/file.py",
        }
        target = enricher._infer_target_entity(context)
        assert target == "ExplicitTarget"

    def test_priority_symbol_over_file(self, enricher: ContextEnricher) -> None:
        """Test that symbol_name takes priority over file_path."""
        context = {
            "symbol_name": "important_function",
            "file_path": "/path/to/module.py",
        }
        target = enricher._infer_target_entity(context)
        assert target == "important_function"


class TestInferTaskType:
    """Tests for task type inference."""

    def test_explicit_task_type(self, enricher: ContextEnricher) -> None:
        """Test that explicit task_type is used."""
        from sunwell.knowledge.codebase.advisor import TaskType

        context = {"task_type": "ADD_FEATURE"}
        task_type = enricher._infer_task_type(context)
        assert task_type == TaskType.ADD_FEATURE

    def test_infer_add_feature(self, enricher: ContextEnricher) -> None:
        """Test inference of ADD_FEATURE from goal."""
        from sunwell.knowledge.codebase.advisor import TaskType

        context = {"goal": "Add new authentication endpoint"}
        task_type = enricher._infer_task_type(context)
        assert task_type == TaskType.ADD_FEATURE

    def test_infer_fix_bug(self, enricher: ContextEnricher) -> None:
        """Test inference of FIX_BUG from description."""
        from sunwell.knowledge.codebase.advisor import TaskType

        context = {"description": "Fix the null pointer bug in UserService"}
        task_type = enricher._infer_task_type(context)
        assert task_type == TaskType.FIX_BUG

    def test_infer_refactor(self, enricher: ContextEnricher) -> None:
        """Test inference of REFACTOR."""
        from sunwell.knowledge.codebase.advisor import TaskType

        context = {"goal": "Refactor the payment module"}
        task_type = enricher._infer_task_type(context)
        assert task_type == TaskType.REFACTOR

    def test_infer_understand(self, enricher: ContextEnricher) -> None:
        """Test inference of UNDERSTAND."""
        from sunwell.knowledge.codebase.advisor import TaskType

        context = {"goal": "How does the authentication flow work?"}
        task_type = enricher._infer_task_type(context)
        assert task_type == TaskType.UNDERSTAND

    def test_infer_delete(self, enricher: ContextEnricher) -> None:
        """Test inference of DELETE."""
        from sunwell.knowledge.codebase.advisor import TaskType

        context = {"goal": "Remove the deprecated API endpoints"}
        task_type = enricher._infer_task_type(context)
        assert task_type == TaskType.DELETE

    def test_infer_test(self, enricher: ContextEnricher) -> None:
        """Test inference of TEST."""
        from sunwell.knowledge.codebase.advisor import TaskType

        context = {"goal": "Write tests for UserService"}
        task_type = enricher._infer_task_type(context)
        assert task_type == TaskType.TEST

    def test_default_to_modify(self, enricher: ContextEnricher) -> None:
        """Test that unknown patterns default to MODIFY."""
        from sunwell.knowledge.codebase.advisor import TaskType

        context = {"goal": "Something ambiguous"}
        task_type = enricher._infer_task_type(context)
        assert task_type == TaskType.MODIFY


class TestTaskAdvisorEnrichment:
    """Tests for task advisor enrichment flow."""

    @pytest.mark.asyncio
    async def test_enrichment_adds_complexity(self, enricher: ContextEnricher) -> None:
        """Test that enrichment adds complexity metrics."""
        context = {"target_entity": "UserService"}
        enriched = await enricher.enrich(DecisionType.SEVERITY_ASSESSMENT, context)

        # Should have complexity metrics
        assert "complexity_score" in enriched
        assert "complexity_level" in enriched
        assert enriched["complexity_score"] >= 0
        assert enriched["complexity_score"] <= 1

    @pytest.mark.asyncio
    async def test_enrichment_adds_impact(self, enricher: ContextEnricher) -> None:
        """Test that enrichment adds impact metrics."""
        context = {"target_entity": "get_user"}
        enriched = await enricher.enrich(DecisionType.SEVERITY_ASSESSMENT, context)

        # Should have impact metrics
        assert "impact_affected_count" in enriched

    @pytest.mark.asyncio
    async def test_enrichment_with_file_path(self, enricher: ContextEnricher) -> None:
        """Test enrichment using file_path for target inference."""
        context = {"file_path": "/path/to/user_service.py"}
        enriched = await enricher.enrich(DecisionType.SEVERITY_ASSESSMENT, context)

        # Should still get enrichment via inferred target
        # user_service matches the module name in our graph
        assert "complexity_score" in enriched or "impact_affected_count" in enriched

    @pytest.mark.asyncio
    async def test_enrichment_no_target(self, enricher: ContextEnricher) -> None:
        """Test enrichment when no target can be inferred."""
        context = {"unrelated_key": "value"}
        enriched = await enricher.enrich(DecisionType.SEVERITY_ASSESSMENT, context)

        # Should still work, just without task advisor enrichment
        assert "unrelated_key" in enriched
        # No complexity/impact added since no target
        assert "complexity_score" not in enriched

    @pytest.mark.asyncio
    async def test_enrichment_without_advisor(self) -> None:
        """Test enrichment works without task advisor."""
        enricher = ContextEnricher()  # No advisor
        context = {"target_entity": "SomeClass", "file_path": "/path/to/file.py"}
        enriched = await enricher.enrich(DecisionType.SEVERITY_ASSESSMENT, context)

        # Should work, just without task advisor metrics
        assert "target_entity" in enriched
        assert "complexity_score" not in enriched


class TestEnricherWithEmptyGraph:
    """Tests for enricher with empty structural graph."""

    @pytest.mark.asyncio
    async def test_empty_graph_no_crash(self) -> None:
        """Test that empty graph doesn't cause crashes."""
        graph = CodebaseGraph()  # Empty graph
        advisor = TaskGraphAdvisor(graph)
        enricher = ContextEnricher(task_advisor=advisor)

        context = {"target_entity": "NonExistent"}
        enriched = await enricher.enrich(DecisionType.SEVERITY_ASSESSMENT, context)

        # Should complete without error
        assert "target_entity" in enriched
        # Complexity should use default for not found
        if "complexity_score" in enriched:
            assert enriched["complexity_score"] == 0.5  # Default
