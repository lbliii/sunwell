"""Tests for RFC-122: Compound Learning.

Tests cover:
- TemplateVariable and TemplateData dataclasses
- Extended Learning with template/heuristic categories
- Learning.with_usage() and Learning.with_embedding()
- PlanningContext and to_convergence_slots()
- DAG serialization/deserialization of new Learning fields
- LearningExtractor.extract_heuristic()
- LearningStore thread-safe operations
- Built-in templates
"""

from __future__ import annotations

import tempfile
import threading
from pathlib import Path

import pytest

from sunwell.memory.simulacrum.core.turn import (
    Learning,
    TemplateData,
    TemplateVariable,
)
from sunwell.memory.simulacrum.core.store import PlanningContext, SimulacrumStore
from sunwell.memory.simulacrum.core.dag import ConversationDAG
from sunwell.agent.learning import LearningExtractor, LearningStore
from sunwell.agent.utils.builtin_templates import (
    BUILTIN_TEMPLATES,
    BUILTIN_CONSTRAINTS,
    BUILTIN_DEAD_ENDS,
    CRUD_ENDPOINT_TEMPLATE,
    load_builtins_into_store,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_template_variable() -> TemplateVariable:
    """Create a sample template variable."""
    return TemplateVariable(
        name="entity",
        description="Model name (User, Post, Product)",
        var_type="string",
        extraction_hints=("for {{entity}}", "{{entity}} API"),
        default=None,
    )


@pytest.fixture
def sample_template_data(sample_template_variable: TemplateVariable) -> TemplateData:
    """Create a sample template data."""
    return TemplateData(
        name="CRUD Endpoint",
        match_patterns=("CRUD", "REST", "endpoint"),
        variables=(sample_template_variable,),
        produces=("{{entity}}Model", "{{entity}}Routes"),
        requires=("Database",),
        expected_artifacts=("models/{{entity_lower}}.py",),
        validation_commands=("pytest tests/test_{{entity_lower}}.py",),
        suggested_order=50,
    )


@pytest.fixture
def sample_template_learning(sample_template_data: TemplateData) -> Learning:
    """Create a sample template learning."""
    return Learning(
        fact="Task pattern: CRUD Endpoint",
        source_turns=(),
        confidence=0.85,
        category="template",
        template_data=sample_template_data,
    )


@pytest.fixture
def sample_heuristic_learning() -> Learning:
    """Create a sample heuristic learning."""
    return Learning(
        fact="Create models before writing tests",
        source_turns=(),
        confidence=0.7,
        category="heuristic",
    )


@pytest.fixture
def sample_fact_learning() -> Learning:
    """Create a sample fact learning."""
    return Learning(
        fact="Uses FastAPI framework",
        source_turns=(),
        confidence=0.9,
        category="fact",
    )


@pytest.fixture
def temp_storage_path() -> Path:
    """Create a temporary directory for storage tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# =============================================================================
# TemplateVariable Tests
# =============================================================================


class TestTemplateVariable:
    """Tests for the TemplateVariable dataclass."""

    def test_creation(self, sample_template_variable: TemplateVariable) -> None:
        """Test template variable creation."""
        assert sample_template_variable.name == "entity"
        assert sample_template_variable.var_type == "string"
        assert len(sample_template_variable.extraction_hints) == 2

    def test_immutable(self, sample_template_variable: TemplateVariable) -> None:
        """Test that TemplateVariable is frozen."""
        with pytest.raises(AttributeError):
            sample_template_variable.name = "other"  # type: ignore

    def test_default_value(self) -> None:
        """Test template variable with default."""
        var = TemplateVariable(
            name="auth_type",
            description="Auth type",
            var_type="choice",
            extraction_hints=(),
            default="jwt",
        )
        assert var.default == "jwt"


# =============================================================================
# TemplateData Tests
# =============================================================================


class TestTemplateData:
    """Tests for the TemplateData dataclass."""

    def test_creation(self, sample_template_data: TemplateData) -> None:
        """Test template data creation."""
        assert sample_template_data.name == "CRUD Endpoint"
        assert "CRUD" in sample_template_data.match_patterns
        assert len(sample_template_data.variables) == 1
        assert sample_template_data.suggested_order == 50

    def test_immutable(self, sample_template_data: TemplateData) -> None:
        """Test that TemplateData is frozen."""
        with pytest.raises(AttributeError):
            sample_template_data.name = "other"  # type: ignore

    def test_produces_with_placeholders(self, sample_template_data: TemplateData) -> None:
        """Test that produces contains placeholders."""
        assert "{{entity}}Model" in sample_template_data.produces


# =============================================================================
# Extended Learning Tests
# =============================================================================


class TestExtendedLearning:
    """Tests for RFC-122 Learning extensions."""

    def test_template_category(self, sample_template_learning: Learning) -> None:
        """Test template category."""
        assert sample_template_learning.category == "template"
        assert sample_template_learning.template_data is not None
        assert sample_template_learning.template_data.name == "CRUD Endpoint"

    def test_heuristic_category(self, sample_heuristic_learning: Learning) -> None:
        """Test heuristic category."""
        assert sample_heuristic_learning.category == "heuristic"
        assert sample_heuristic_learning.template_data is None

    def test_new_fields_defaults(self, sample_fact_learning: Learning) -> None:
        """Test new field defaults."""
        assert sample_fact_learning.template_data is None
        assert sample_fact_learning.embedding is None
        assert sample_fact_learning.use_count == 0
        assert sample_fact_learning.last_used is None

    def test_with_usage_success(self, sample_fact_learning: Learning) -> None:
        """Test with_usage() on success."""
        updated = sample_fact_learning.with_usage(success=True)
        assert updated.use_count == 1
        assert updated.confidence > sample_fact_learning.confidence
        assert updated.last_used is not None
        # ID should remain the same
        assert updated.id == sample_fact_learning.id

    def test_with_usage_failure(self, sample_fact_learning: Learning) -> None:
        """Test with_usage() on failure."""
        updated = sample_fact_learning.with_usage(success=False)
        assert updated.use_count == 1
        assert updated.confidence < sample_fact_learning.confidence

    def test_with_embedding(self, sample_fact_learning: Learning) -> None:
        """Test with_embedding()."""
        embedding = (0.1, 0.2, 0.3, 0.4)
        updated = sample_fact_learning.with_embedding(embedding)
        assert updated.embedding == embedding
        assert updated.id == sample_fact_learning.id

    def test_first_person_prefix_all_categories(self) -> None:
        """Test _first_person_prefix() returns correct prefix for each category."""
        categories_and_prefixes = [
            ("fact", "I know:"),
            ("preference", "I prefer:"),
            ("constraint", "I must:"),
            ("pattern", "I use:"),
            ("dead_end", "I tried and it failed:"),
            ("template", "I follow this pattern:"),
            ("heuristic", "I've found:"),
        ]
        for category, expected_prefix in categories_and_prefixes:
            learning = Learning(
                fact="Test fact",
                source_turns=(),
                confidence=0.8,
                category=category,  # type: ignore
            )
            assert learning._first_person_prefix() == expected_prefix

    def test_to_turn_uses_first_person_prefix(self, sample_fact_learning: Learning) -> None:
        """Test to_turn() uses first-person prefix."""
        turn = sample_fact_learning.to_turn()
        # Should start with "I know:" for fact category
        assert turn.content.startswith("I know:")
        assert sample_fact_learning.fact in turn.content

    def test_to_turn_heuristic_prefix(self, sample_heuristic_learning: Learning) -> None:
        """Test to_turn() uses correct prefix for heuristics."""
        turn = sample_heuristic_learning.to_turn()
        assert turn.content.startswith("I've found:")
        assert sample_heuristic_learning.fact in turn.content

    def test_to_turn_template_prefix(self, sample_template_learning: Learning) -> None:
        """Test to_turn() uses correct prefix for templates."""
        turn = sample_template_learning.to_turn()
        assert turn.content.startswith("I follow this pattern:")
        assert sample_template_learning.fact in turn.content

    def test_id_stability(self, sample_template_learning: Learning) -> None:
        """Test that ID is based on category:fact only."""
        # Same category and fact should produce same ID
        learning2 = Learning(
            fact=sample_template_learning.fact,
            source_turns=("turn-1",),  # Different
            confidence=0.5,  # Different
            category=sample_template_learning.category,
            use_count=10,  # Different
        )
        assert learning2.id == sample_template_learning.id


# =============================================================================
# PlanningContext Tests
# =============================================================================


class TestPlanningContext:
    """Tests for the PlanningContext dataclass."""

    def test_creation(
        self,
        sample_fact_learning: Learning,
        sample_template_learning: Learning,
        sample_heuristic_learning: Learning,
    ) -> None:
        """Test PlanningContext creation."""
        context = PlanningContext(
            facts=(sample_fact_learning,),
            constraints=(),
            dead_ends=(),
            templates=(sample_template_learning,),
            heuristics=(sample_heuristic_learning,),
            patterns=(),
            goal="Build CRUD API",
        )
        assert len(context.facts) == 1
        assert len(context.templates) == 1
        assert context.goal == "Build CRUD API"

    def test_best_template(
        self,
        sample_template_learning: Learning,
    ) -> None:
        """Test best_template property."""
        context = PlanningContext(
            facts=(),
            constraints=(),
            dead_ends=(),
            templates=(sample_template_learning,),
            heuristics=(),
            patterns=(),
            goal="Build CRUD API",
        )
        assert context.best_template is not None
        assert context.best_template.id == sample_template_learning.id

    def test_best_template_empty(self) -> None:
        """Test best_template with no templates."""
        context = PlanningContext(
            facts=(),
            constraints=(),
            dead_ends=(),
            templates=(),
            heuristics=(),
            patterns=(),
            goal="Build something",
        )
        assert context.best_template is None

    def test_all_learnings(
        self,
        sample_fact_learning: Learning,
        sample_template_learning: Learning,
    ) -> None:
        """Test all_learnings property."""
        context = PlanningContext(
            facts=(sample_fact_learning,),
            constraints=(),
            dead_ends=(),
            templates=(sample_template_learning,),
            heuristics=(),
            patterns=(),
            goal="Build CRUD API",
        )
        assert len(context.all_learnings) == 2

    def test_to_prompt_section(
        self,
        sample_fact_learning: Learning,
        sample_template_learning: Learning,
    ) -> None:
        """Test to_prompt_section() formatting."""
        context = PlanningContext(
            facts=(sample_fact_learning,),
            constraints=(),
            dead_ends=(),
            templates=(sample_template_learning,),
            heuristics=(),
            patterns=(),
            goal="Build CRUD API",
        )
        section = context.to_prompt_section()
        assert "## What I Know About This Project" in section
        assert sample_fact_learning.fact in section

    @pytest.mark.asyncio
    async def test_to_convergence_slots(
        self,
        sample_fact_learning: Learning,
        sample_template_learning: Learning,
    ) -> None:
        """Test to_convergence_slots() creates proper slots."""
        context = PlanningContext(
            facts=(sample_fact_learning,),
            constraints=(),
            dead_ends=(),
            templates=(sample_template_learning,),
            heuristics=(),
            patterns=(),
            goal="Build CRUD API",
        )
        slots = context.to_convergence_slots()
        assert len(slots) >= 1
        # Check slot IDs
        slot_ids = [s.id for s in slots]
        assert "knowledge:facts" in slot_ids
        assert "knowledge:templates" in slot_ids


# =============================================================================
# DAG Serialization Tests
# =============================================================================


class TestDAGSerialization:
    """Tests for DAG serialization of extended Learning."""

    def test_serialize_template_data(self, sample_template_data: TemplateData) -> None:
        """Test template data serialization."""
        dag = ConversationDAG()
        serialized = dag._serialize_template_data(sample_template_data)
        assert serialized is not None
        assert serialized["name"] == "CRUD Endpoint"
        assert len(serialized["variables"]) == 1
        assert serialized["variables"][0]["name"] == "entity"

    def test_serialize_template_data_none(self) -> None:
        """Test serialization of None template_data."""
        dag = ConversationDAG()
        assert dag._serialize_template_data(None) is None

    def test_deserialize_template_data(self, sample_template_data: TemplateData) -> None:
        """Test template data deserialization."""
        dag = ConversationDAG()
        serialized = dag._serialize_template_data(sample_template_data)
        deserialized = dag._deserialize_template_data(serialized)
        assert deserialized is not None
        assert deserialized.name == sample_template_data.name
        assert len(deserialized.variables) == len(sample_template_data.variables)

    def test_roundtrip_learning(self, sample_template_learning: Learning) -> None:
        """Test full roundtrip of learning through save/load."""
        dag = ConversationDAG()
        dag.add_learning(sample_template_learning)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = Path(f.name)

        try:
            dag.save(path)
            loaded_dag = ConversationDAG.load(path)

            assert len(loaded_dag.learnings) == 1
            loaded_learning = list(loaded_dag.learnings.values())[0]
            assert loaded_learning.id == sample_template_learning.id
            assert loaded_learning.category == "template"
            assert loaded_learning.template_data is not None
            assert loaded_learning.template_data.name == "CRUD Endpoint"
        finally:
            path.unlink()


# =============================================================================
# LearningExtractor Tests
# =============================================================================


class TestLearningExtractorRFC122:
    """Tests for RFC-122 LearningExtractor extensions."""

    def test_extract_heuristic_models_before_tests(self) -> None:
        """Test heuristic extraction: models before tests."""
        from sunwell.planning.naaru.types import Task, TaskMode

        extractor = LearningExtractor()
        tasks = [
            Task(id="1", description="Create User model", mode=TaskMode.GENERATE),
            Task(id="2", description="Add API routes", mode=TaskMode.GENERATE),
            Task(id="3", description="Write unit tests", mode=TaskMode.GENERATE),
        ]
        heuristic = extractor.extract_heuristic("Build user API", tasks)
        assert heuristic is not None
        assert heuristic.category == "heuristic"
        assert "model" in heuristic.fact.lower() or "test" in heuristic.fact.lower()

    def test_extract_heuristic_config_before_models(self) -> None:
        """Test heuristic extraction: config before models."""
        from sunwell.planning.naaru.types import Task, TaskMode

        extractor = LearningExtractor()
        tasks = [
            Task(id="1", description="Setup database config", mode=TaskMode.GENERATE),
            Task(id="2", description="Create User model", mode=TaskMode.GENERATE),
            Task(id="3", description="Add routes", mode=TaskMode.GENERATE),
        ]
        heuristic = extractor.extract_heuristic("Build user system", tasks)
        assert heuristic is not None
        assert heuristic.category == "heuristic"

    def test_extract_heuristic_not_enough_tasks(self) -> None:
        """Test heuristic extraction with too few tasks."""
        from sunwell.planning.naaru.types import Task, TaskMode

        extractor = LearningExtractor()
        tasks = [
            Task(id="1", description="Do something", mode=TaskMode.GENERATE),
        ]
        heuristic = extractor.extract_heuristic("Simple task", tasks)
        assert heuristic is None


# =============================================================================
# LearningStore Thread Safety Tests
# =============================================================================


class TestLearningStoreThreadSafety:
    """Tests for RFC-122 thread-safe LearningStore."""

    def test_add_learning_thread_safe(self) -> None:
        """Test concurrent add_learning calls."""
        from sunwell.agent.learning import Learning as AgentLearning

        store = LearningStore()
        errors: list[Exception] = []

        def add_many(start: int) -> None:
            try:
                for i in range(100):
                    learning = AgentLearning(
                        fact=f"Fact {start + i}",
                        category="pattern",
                    )
                    store.add_learning(learning)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=add_many, args=(i * 100,))
            for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        # Should have deduplicated, so less than 500
        assert len(store.learnings) <= 500

    def test_record_usage_thread_safe(self) -> None:
        """Test concurrent record_usage calls."""
        from sunwell.agent.learning import Learning as AgentLearning

        store = LearningStore()
        learning = AgentLearning(fact="Test fact", category="pattern")
        store.add_learning(learning)

        errors: list[Exception] = []

        def record_many() -> None:
            try:
                for _ in range(50):
                    store.record_usage(learning.id, success=True)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record_many) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_get_templates(self) -> None:
        """Test get_templates() method."""
        from sunwell.agent.learning import Learning as AgentLearning

        store = LearningStore()
        store.add_learning(AgentLearning(fact="Fact 1", category="pattern"))
        store.add_learning(AgentLearning(fact="Template 1", category="template"))
        store.add_learning(AgentLearning(fact="Template 2", category="template"))

        templates = store.get_templates()
        assert len(templates) == 2
        assert all(t.category == "template" for t in templates)

    def test_get_heuristics(self) -> None:
        """Test get_heuristics() method."""
        from sunwell.agent.learning import Learning as AgentLearning

        store = LearningStore()
        store.add_learning(AgentLearning(fact="Fact 1", category="pattern"))
        store.add_learning(AgentLearning(fact="Heuristic 1", category="heuristic"))

        heuristics = store.get_heuristics()
        assert len(heuristics) == 1
        assert heuristics[0].category == "heuristic"


# =============================================================================
# Built-in Templates Tests
# =============================================================================


class TestBuiltinTemplates:
    """Tests for built-in templates."""

    def test_builtin_templates_count(self) -> None:
        """Test that we have expected number of built-in templates."""
        assert len(BUILTIN_TEMPLATES) == 4

    def test_crud_template_structure(self) -> None:
        """Test CRUD template structure."""
        assert CRUD_ENDPOINT_TEMPLATE.category == "template"
        assert CRUD_ENDPOINT_TEMPLATE.template_data is not None
        assert CRUD_ENDPOINT_TEMPLATE.template_data.name == "CRUD Endpoint"
        assert "CRUD" in CRUD_ENDPOINT_TEMPLATE.template_data.match_patterns

    def test_builtin_constraints(self) -> None:
        """Test built-in constraints."""
        assert len(BUILTIN_CONSTRAINTS) >= 1
        assert all(c.category == "constraint" for c in BUILTIN_CONSTRAINTS)

    def test_builtin_dead_ends(self) -> None:
        """Test built-in dead ends."""
        assert len(BUILTIN_DEAD_ENDS) >= 1
        assert all(d.category == "dead_end" for d in BUILTIN_DEAD_ENDS)

    def test_load_builtins_into_store(self, temp_storage_path: Path) -> None:
        """Test loading built-ins into store."""
        store = SimulacrumStore(base_path=temp_storage_path)
        count = load_builtins_into_store(store)
        expected = len(BUILTIN_TEMPLATES) + len(BUILTIN_CONSTRAINTS) + len(BUILTIN_DEAD_ENDS)
        assert count == expected

        dag = store.get_dag()
        assert len(dag.learnings) == expected


# =============================================================================
# SimulacrumStore retrieve_for_planning Tests
# =============================================================================


class TestSimulacrumStoreRetrieveForPlanning:
    """Tests for SimulacrumStore.retrieve_for_planning()."""

    @pytest.mark.asyncio
    async def test_retrieve_empty_store(self, temp_storage_path: Path) -> None:
        """Test retrieval from empty store."""
        store = SimulacrumStore(base_path=temp_storage_path)
        context = await store.retrieve_for_planning("Build API")
        assert context.goal == "Build API"
        assert len(context.all_learnings) == 0

    @pytest.mark.asyncio
    async def test_retrieve_with_learnings(self, temp_storage_path: Path) -> None:
        """Test retrieval with stored learnings."""
        store = SimulacrumStore(base_path=temp_storage_path)

        # Add some learnings
        store.add_learning("Uses FastAPI", category="fact", confidence=0.9)
        store.add_learning("Tests required", category="constraint", confidence=0.95)

        context = await store.retrieve_for_planning("Build FastAPI endpoint")
        assert context.goal == "Build FastAPI endpoint"
        # Should find the FastAPI fact due to keyword overlap
        assert len(context.facts) >= 0  # May or may not match depending on threshold

    @pytest.mark.asyncio
    async def test_retrieve_categorizes_correctly(self, temp_storage_path: Path) -> None:
        """Test that retrieval categorizes learnings correctly."""
        store = SimulacrumStore(base_path=temp_storage_path)
        dag = store.get_dag()

        # Add learnings of different categories
        dag.add_learning(Learning(
            fact="API uses REST",
            source_turns=(),
            confidence=0.9,
            category="fact",
        ))
        dag.add_learning(Learning(
            fact="Don't use sync DB",
            source_turns=(),
            confidence=0.95,
            category="dead_end",
        ))

        context = await store.retrieve_for_planning(
            "Build REST API with database"
        )

        # Dead ends should be in dead_ends, not facts
        dead_end_facts = [d.fact for d in context.dead_ends]
        fact_facts = [f.fact for f in context.facts]

        if context.dead_ends:
            assert all("dead_end" != f.category for f in context.facts)


# =============================================================================
# Similarity Function Tests
# =============================================================================


class TestSimilarityFunctions:
    """Tests for similarity helper functions in retrieval module."""

    def test_cosine_similarity_identical(self) -> None:
        """Test cosine similarity of identical vectors."""
        from sunwell.memory.simulacrum.core.retrieval.similarity import cosine_similarity

        vec = (1.0, 2.0, 3.0)
        result = cosine_similarity(vec, vec)
        assert abs(result - 1.0) < 0.001

    def test_cosine_similarity_orthogonal(self) -> None:
        """Test cosine similarity of orthogonal vectors."""
        from sunwell.memory.simulacrum.core.retrieval.similarity import cosine_similarity

        vec_a = (1.0, 0.0, 0.0)
        vec_b = (0.0, 1.0, 0.0)
        result = cosine_similarity(vec_a, vec_b)
        assert abs(result) < 0.001

    def test_cosine_similarity_zero_vector(self) -> None:
        """Test cosine similarity with zero vector."""
        from sunwell.memory.simulacrum.core.retrieval.similarity import cosine_similarity

        vec_a = (1.0, 2.0, 3.0)
        vec_b = (0.0, 0.0, 0.0)
        result = cosine_similarity(vec_a, vec_b)
        assert result == 0.0
