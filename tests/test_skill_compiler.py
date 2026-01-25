"""Tests for RFC-111 Skill Compiler."""

import pytest

from sunwell.naaru.types import TaskMode, TaskStatus
from sunwell.planning.skills import (
    CompiledTaskGraph,
    Skill,
    SkillCompilationCache,
    SkillCompilationError,
    SkillCompiler,
    SkillDependency,
    SkillGraph,
    SkillType,
    has_dag_metadata,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def simple_skill() -> Skill:
    """A simple skill with no dependencies."""
    return Skill(
        name="read-file",
        description="Read a file from workspace",
        skill_type=SkillType.INLINE,
        produces=("file_content", "file_path"),
        instructions="Read the file and return its contents.",
    )


@pytest.fixture
def dependent_skill() -> Skill:
    """A skill that depends on read-file."""
    return Skill(
        name="analyze-code",
        description="Analyze source code",
        skill_type=SkillType.INLINE,
        depends_on=(SkillDependency(source="read-file"),),
        requires=("file_content",),
        produces=("analysis_result",),
        instructions="Analyze the code structure.",
    )


@pytest.fixture
def leaf_skill() -> Skill:
    """Another leaf skill (no dependencies)."""
    return Skill(
        name="list-workspace",
        description="List files in workspace",
        skill_type=SkillType.INLINE,
        produces=("file_list",),
        instructions="List all files.",
    )


@pytest.fixture
def convergent_skill() -> Skill:
    """A skill that depends on multiple skills."""
    return Skill(
        name="generate-report",
        description="Generate documentation report",
        skill_type=SkillType.INLINE,
        depends_on=(
            SkillDependency(source="analyze-code"),
            SkillDependency(source="list-workspace"),
        ),
        requires=("analysis_result", "file_list"),
        produces=("report",),
        instructions="Generate comprehensive report.",
    )


@pytest.fixture
def skill_graph(
    simple_skill: Skill,
    dependent_skill: Skill,
    leaf_skill: Skill,
    convergent_skill: Skill,
) -> SkillGraph:
    """A skill graph with multiple waves."""
    return SkillGraph.from_skills([
        simple_skill,
        dependent_skill,
        leaf_skill,
        convergent_skill,
    ])


# =============================================================================
# SKILL COMPILER TESTS
# =============================================================================


class TestSkillCompiler:
    """Tests for SkillCompiler."""

    def test_compile_single_skill(self, simple_skill: Skill) -> None:
        """Compile a single skill to a task."""
        graph = SkillGraph.from_skills([simple_skill])
        compiler = SkillCompiler()

        result = compiler.compile(graph)

        assert isinstance(result, CompiledTaskGraph)
        assert len(result.tasks) == 1
        assert result.tasks[0].id == "skill:read-file"
        assert "read-file" in result.tasks[0].description

    def test_compile_preserves_dependencies(
        self,
        simple_skill: Skill,
        dependent_skill: Skill,
    ) -> None:
        """Dependencies in skills become dependencies in tasks."""
        graph = SkillGraph.from_skills([simple_skill, dependent_skill])
        compiler = SkillCompiler()

        result = compiler.compile(graph)

        assert len(result.tasks) == 2

        # Find the dependent task
        analyze_task = next(t for t in result.tasks if "analyze-code" in t.id)

        # It should depend on read-file task
        assert "skill:read-file" in analyze_task.depends_on

    def test_compile_computes_waves(self, skill_graph: SkillGraph) -> None:
        """Skills are grouped into execution waves."""
        compiler = SkillCompiler()

        result = compiler.compile(skill_graph)

        # Should have 3 waves:
        # Wave 0: read-file, list-workspace (leaves)
        # Wave 1: analyze-code (depends on read-file)
        # Wave 2: generate-report (depends on analyze-code, list-workspace)
        assert len(result.waves) == 3

        # First wave should have leaves
        wave0 = set(result.waves[0])
        assert "skill:read-file" in wave0
        assert "skill:list-workspace" in wave0

        # Last wave should have convergent skill
        wave2 = set(result.waves[2])
        assert "skill:generate-report" in wave2

    def test_compile_with_target_skills(self, skill_graph: SkillGraph) -> None:
        """Compile subgraph for specific target skills."""
        compiler = SkillCompiler()

        # Target only analyze-code (should include read-file dependency)
        result = compiler.compile(
            skill_graph,
            target_skills={"analyze-code"},
        )

        # Should have 2 skills: read-file and analyze-code
        assert len(result.tasks) == 2
        task_ids = {t.id for t in result.tasks}
        assert "skill:read-file" in task_ids
        assert "skill:analyze-code" in task_ids

    def test_compile_with_context(self, simple_skill: Skill) -> None:
        """Context values flow to task details."""
        graph = SkillGraph.from_skills([simple_skill])
        compiler = SkillCompiler()

        result = compiler.compile(graph, context={"target": "docs/"})

        # Task should have context in details
        task = result.tasks[0]
        assert task.details["skill_name"] == "read-file"

    def test_compile_invalid_graph_raises_error(self) -> None:
        """Invalid graph raises SkillCompilationError."""
        # Create skill with missing dependency
        orphan = Skill(
            name="orphan",
            description="Depends on missing skill",
            skill_type=SkillType.INLINE,
            depends_on=(SkillDependency(source="missing"),),
            instructions="...",
        )

        graph = SkillGraph.from_skills([orphan])
        compiler = SkillCompiler()

        with pytest.raises(SkillCompilationError):
            compiler.compile(graph)

    def test_task_produces_from_skill(self, simple_skill: Skill) -> None:
        """Task.produces matches Skill.produces."""
        graph = SkillGraph.from_skills([simple_skill])
        compiler = SkillCompiler()

        result = compiler.compile(graph)
        task = result.tasks[0]

        assert task.produces == frozenset(simple_skill.produces)

    def test_task_mode_is_generate(self, simple_skill: Skill) -> None:
        """Compiled tasks have GENERATE mode."""
        graph = SkillGraph.from_skills([simple_skill])
        compiler = SkillCompiler()

        result = compiler.compile(graph)

        for task in result.tasks:
            assert task.mode == TaskMode.GENERATE

    def test_task_status_is_pending(self, simple_skill: Skill) -> None:
        """Compiled tasks start in PENDING status."""
        graph = SkillGraph.from_skills([simple_skill])
        compiler = SkillCompiler()

        result = compiler.compile(graph)

        for task in result.tasks:
            assert task.status == TaskStatus.PENDING


# =============================================================================
# COMPILATION CACHE TESTS
# =============================================================================


class TestSkillCompilationCache:
    """Tests for SkillCompilationCache."""

    def test_cache_miss_returns_none(self) -> None:
        """Cache miss returns None."""
        cache = SkillCompilationCache()
        result = cache.get("nonexistent")
        assert result is None

    def test_cache_hit_returns_graph(self, skill_graph: SkillGraph) -> None:
        """Cache hit returns stored graph."""
        cache = SkillCompilationCache()
        compiler = SkillCompiler(cache=cache)

        # First compile populates cache
        result1 = compiler.compile(skill_graph)

        # Same key should hit cache
        cache_key = cache.compute_key(skill_graph, {})
        cached = cache.get(cache_key)

        assert cached is not None
        assert cached.content_hash == result1.content_hash

    def test_cache_stats(self, skill_graph: SkillGraph) -> None:
        """Cache tracks hits and misses."""
        cache = SkillCompilationCache()
        compiler = SkillCompiler(cache=cache)

        # First compile is a miss
        compiler.compile(skill_graph)

        # Second compile is a hit
        compiler.compile(skill_graph)

        stats = cache.stats()
        assert stats["misses"] == 1
        assert stats["hits"] == 1
        assert stats["hit_rate"] == 0.5

    def test_cache_lru_eviction(self) -> None:
        """Cache evicts oldest entries when full."""
        cache = SkillCompilationCache(max_size=2)

        # Create 3 different graphs
        skills = [
            Skill(name=f"skill-{i}", description=f"Skill {i}", skill_type=SkillType.INLINE, instructions="...")
            for i in range(3)
        ]

        for skill in skills:
            graph = SkillGraph.from_skills([skill])
            compiler = SkillCompiler(cache=cache)
            compiler.compile(graph)

        # Cache should only have 2 entries
        assert cache.stats()["size"] == 2


# =============================================================================
# UTILITY FUNCTION TESTS
# =============================================================================


class TestHasDagMetadata:
    """Tests for has_dag_metadata helper."""

    def test_no_dag_metadata(self) -> None:
        """Skills without DAG fields return False."""
        skills = [
            Skill(
                name="simple",
                description="Simple skill",
                skill_type=SkillType.INLINE,
                instructions="...",
            ),
        ]

        assert has_dag_metadata(skills) is False

    def test_has_depends_on(self) -> None:
        """Skills with depends_on return True."""
        skills = [
            Skill(
                name="dependent",
                description="Dependent skill",
                skill_type=SkillType.INLINE,
                depends_on=(SkillDependency(source="other"),),
                instructions="...",
            ),
        ]

        assert has_dag_metadata(skills) is True

    def test_has_produces(self) -> None:
        """Skills with produces return True."""
        skills = [
            Skill(
                name="producer",
                description="Producer skill",
                skill_type=SkillType.INLINE,
                produces=("output",),
                instructions="...",
            ),
        ]

        assert has_dag_metadata(skills) is True

    def test_has_requires(self) -> None:
        """Skills with requires return True."""
        skills = [
            Skill(
                name="consumer",
                description="Consumer skill",
                skill_type=SkillType.INLINE,
                requires=("input",),
                instructions="...",
            ),
        ]

        assert has_dag_metadata(skills) is True


# =============================================================================
# COMPILED TASK GRAPH TESTS
# =============================================================================


class TestCompiledTaskGraph:
    """Tests for CompiledTaskGraph."""

    def test_get_ready_tasks(self, skill_graph: SkillGraph) -> None:
        """get_ready_tasks returns tasks with satisfied dependencies."""
        compiler = SkillCompiler()
        result = compiler.compile(skill_graph)

        # Initially, only wave 0 tasks are ready
        ready = result.get_ready_tasks(set())
        ready_ids = {t.id for t in ready}

        assert "skill:read-file" in ready_ids
        assert "skill:list-workspace" in ready_ids
        assert "skill:analyze-code" not in ready_ids

    def test_has_pending_tasks(self, skill_graph: SkillGraph) -> None:
        """has_pending_tasks reflects completion state."""
        compiler = SkillCompiler()
        result = compiler.compile(skill_graph)

        # Initially all pending
        assert result.has_pending_tasks(set())

        # Mark all complete
        all_ids = {t.id for t in result.tasks}
        assert not result.has_pending_tasks(all_ids)

    def test_get_wave_for_task(self, skill_graph: SkillGraph) -> None:
        """get_wave_for_task returns correct wave index."""
        compiler = SkillCompiler()
        result = compiler.compile(skill_graph)

        # Leaf tasks are in wave 0
        assert result.get_wave_for_task("skill:read-file") == 0
        assert result.get_wave_for_task("skill:list-workspace") == 0

        # Convergent task is in last wave
        assert result.get_wave_for_task("skill:generate-report") == 2

        # Unknown task returns -1
        assert result.get_wave_for_task("nonexistent") == -1
