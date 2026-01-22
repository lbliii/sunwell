"""Tests for RFC-087: Skill-Lens DAG (Unified Expertise Graph)."""

import pytest

from sunwell.skills import (
    CircularDependencyError,
    ExecutionContext,
    IncrementalSkillExecutor,
    MissingDependencyError,
    Skill,
    SkillCache,
    SkillCacheKey,
    SkillDependency,
    SkillGraph,
    SkillOutput,
    SkillType,
    UnsatisfiedRequiresError,
)


# =============================================================================
# SkillDependency Tests
# =============================================================================


class TestSkillDependency:
    """Tests for SkillDependency parsing."""

    def test_local_dependency(self):
        """Local dependency without library prefix."""
        dep = SkillDependency(source="analyze-code")
        assert dep.is_local is True
        assert dep.skill_name == "analyze-code"
        assert dep.library is None

    def test_library_dependency(self):
        """Library-prefixed dependency."""
        dep = SkillDependency(source="sunwell/common:format-output")
        assert dep.is_local is False
        assert dep.skill_name == "format-output"
        assert dep.library == "sunwell/common"

    def test_library_with_complex_path(self):
        """Library with multiple path segments."""
        dep = SkillDependency(source="org/team/skills:my-skill")
        assert dep.is_local is False
        assert dep.skill_name == "my-skill"
        assert dep.library == "org/team/skills"


# =============================================================================
# SkillGraph Tests
# =============================================================================


class TestSkillGraph:
    """Tests for SkillGraph DAG operations."""

    def _make_skill(
        self,
        name: str,
        depends_on: list[str] | None = None,
        produces: list[str] | None = None,
        requires: list[str] | None = None,
    ) -> Skill:
        """Helper to create skills with dependencies."""
        return Skill(
            name=name,
            description=f"Skill {name}",
            skill_type=SkillType.INLINE,
            instructions=f"Do {name}",
            depends_on=tuple(SkillDependency(source=d) for d in (depends_on or [])),
            produces=tuple(produces or []),
            requires=tuple(requires or []),
        )

    def test_empty_graph(self):
        """Empty graph should have no skills."""
        graph = SkillGraph()
        assert graph.topological_order() == []
        assert graph.execution_waves() == []

    def test_single_skill(self):
        """Single skill should work."""
        skill = self._make_skill("only-skill")
        graph = SkillGraph.from_skills([skill])

        assert graph.topological_order() == ["only-skill"]
        assert graph.execution_waves() == [["only-skill"]]

    def test_linear_chain(self):
        """A → B → C should execute in order."""
        skill_c = self._make_skill("skill-c", depends_on=["skill-b"])
        skill_b = self._make_skill("skill-b", depends_on=["skill-a"])
        skill_a = self._make_skill("skill-a")

        graph = SkillGraph.from_skills([skill_c, skill_b, skill_a])

        order = graph.topological_order()
        assert order.index("skill-a") < order.index("skill-b")
        assert order.index("skill-b") < order.index("skill-c")

        waves = graph.execution_waves()
        assert len(waves) == 3
        assert waves[0] == ["skill-a"]
        assert waves[1] == ["skill-b"]
        assert waves[2] == ["skill-c"]

    def test_parallel_skills(self):
        """Independent skills should run in parallel."""
        skill_a = self._make_skill("skill-a")
        skill_b = self._make_skill("skill-b")
        skill_c = self._make_skill("skill-c")

        graph = SkillGraph.from_skills([skill_a, skill_b, skill_c])

        waves = graph.execution_waves()
        assert len(waves) == 1  # All in one wave
        assert set(waves[0]) == {"skill-a", "skill-b", "skill-c"}

    def test_diamond_dependency(self):
        """Diamond pattern: A → B,C → D."""
        skill_d = self._make_skill("skill-d", depends_on=["skill-b", "skill-c"])
        skill_b = self._make_skill("skill-b", depends_on=["skill-a"])
        skill_c = self._make_skill("skill-c", depends_on=["skill-a"])
        skill_a = self._make_skill("skill-a")

        graph = SkillGraph.from_skills([skill_d, skill_b, skill_c, skill_a])

        order = graph.topological_order()
        assert order[0] == "skill-a"  # A must be first
        assert "skill-d" == order[-1]  # D must be last

        waves = graph.execution_waves()
        assert len(waves) == 3
        assert waves[0] == ["skill-a"]
        assert set(waves[1]) == {"skill-b", "skill-c"}
        assert waves[2] == ["skill-d"]

    def test_circular_dependency_detection(self):
        """Circular dependencies should raise error."""
        skill_a = self._make_skill("skill-a", depends_on=["skill-c"])
        skill_b = self._make_skill("skill-b", depends_on=["skill-a"])
        skill_c = self._make_skill("skill-c", depends_on=["skill-b"])

        graph = SkillGraph.from_skills([skill_a, skill_b, skill_c])

        with pytest.raises(CircularDependencyError) as exc_info:
            graph.topological_order()

        # Should detect the cycle
        assert exc_info.value.cycle is not None
        assert len(exc_info.value.cycle) >= 2

    def test_missing_dependency_validation(self):
        """Missing dependencies should be caught during validation."""
        skill = self._make_skill("skill-a", depends_on=["nonexistent"])
        graph = SkillGraph.from_skills([skill])

        errors = graph.validate()
        assert len(errors) > 0
        assert "nonexistent" in errors[0]

    def test_subgraph_extraction(self):
        """Extract subgraph for specific skills."""
        skill_d = self._make_skill("skill-d", depends_on=["skill-b", "skill-c"])
        skill_b = self._make_skill("skill-b", depends_on=["skill-a"])
        skill_c = self._make_skill("skill-c", depends_on=["skill-a"])
        skill_a = self._make_skill("skill-a")

        graph = SkillGraph.from_skills([skill_d, skill_b, skill_c, skill_a])

        # Get subgraph for just skill-b
        subgraph = graph.subgraph_for({"skill-b"})
        order = subgraph.topological_order()

        assert "skill-a" in order  # Dependency included
        assert "skill-b" in order
        assert "skill-c" not in order  # Not a dependency of skill-b
        assert "skill-d" not in order

    def test_content_hash_changes(self):
        """Content hash should change when graph changes."""
        skill_a = self._make_skill("skill-a")
        graph1 = SkillGraph.from_skills([skill_a])
        hash1 = graph1.content_hash()

        skill_b = self._make_skill("skill-b")
        graph2 = SkillGraph.from_skills([skill_a, skill_b])
        hash2 = graph2.content_hash()

        assert hash1 != hash2

    def test_content_hash_stable(self):
        """Same graph should produce same hash."""
        skill_a = self._make_skill("skill-a")
        skill_b = self._make_skill("skill-b")

        graph1 = SkillGraph.from_skills([skill_a, skill_b])
        graph2 = SkillGraph.from_skills([skill_b, skill_a])  # Different order

        # Hash should be the same regardless of insertion order
        assert graph1.content_hash() == graph2.content_hash()

    def test_mermaid_output(self):
        """Mermaid diagram generation."""
        skill_b = self._make_skill("skill-b", depends_on=["skill-a"])
        skill_a = self._make_skill("skill-a")

        graph = SkillGraph.from_skills([skill_a, skill_b])
        mermaid = graph.to_mermaid()

        assert "graph TD" in mermaid
        assert "skill-a" in mermaid
        assert "skill-b" in mermaid
        assert "-->" in mermaid

    def test_get_skill(self):
        """Get skill by name."""
        skill_a = self._make_skill("skill-a")
        graph = SkillGraph.from_skills([skill_a])

        assert graph.get("skill-a") == skill_a
        assert graph.get("nonexistent") is None


# =============================================================================
# SkillCache Tests
# =============================================================================


class TestSkillCache:
    """Tests for SkillCache."""

    def _make_skill(
        self, name: str, requires: list[str] | None = None
    ) -> Skill:
        """Helper to create a simple skill with optional requires."""
        return Skill(
            name=name,
            description=f"Skill {name}",
            skill_type=SkillType.INLINE,
            instructions=f"Do {name}",
            requires=tuple(requires or []),
        )

    def _make_output(self, content: str) -> SkillOutput:
        """Helper to create a skill output."""
        return SkillOutput(content=content)

    def test_cache_miss(self):
        """Cache miss returns None."""
        cache = SkillCache(max_size=100)
        skill = self._make_skill("test-skill", requires=["input"])
        key = SkillCacheKey.compute(skill, {"input": "test"})

        assert cache.get(key) is None

    def test_cache_hit(self):
        """Cache hit returns stored entry."""
        cache = SkillCache(max_size=100)
        skill = self._make_skill("test-skill", requires=["input"])
        key = SkillCacheKey.compute(skill, {"input": "test"})
        output = self._make_output("result")

        cache.set(key, output, skill_name="test-skill", execution_time_ms=100)
        entry = cache.get(key)
        assert entry is not None
        assert entry.output.content == "result"

    def test_cache_different_inputs(self):
        """Different inputs produce different cache keys."""
        cache = SkillCache(max_size=100)
        # Skill must declare 'input' in requires for it to affect the cache key
        skill = self._make_skill("test-skill", requires=["input"])

        key1 = SkillCacheKey.compute(skill, {"input": "test1"})
        key2 = SkillCacheKey.compute(skill, {"input": "test2"})

        # Keys should be different
        assert key1 != key2

        cache.set(key1, self._make_output("result1"), "test-skill", 100)
        cache.set(key2, self._make_output("result2"), "test-skill", 100)

        entry1 = cache.get(key1)
        entry2 = cache.get(key2)
        assert entry1 is not None and entry1.output.content == "result1"
        assert entry2 is not None and entry2.output.content == "result2"

    def test_cache_invalidate_skill(self):
        """Invalidate all entries for a skill."""
        cache = SkillCache(max_size=100)
        skill = self._make_skill("test-skill", requires=["input"])

        key1 = SkillCacheKey.compute(skill, {"input": "test1"})
        key2 = SkillCacheKey.compute(skill, {"input": "test2"})

        cache.set(key1, self._make_output("result1"), "test-skill", 100)
        cache.set(key2, self._make_output("result2"), "test-skill", 100)

        count = cache.invalidate_skill("test-skill")
        assert count == 2
        assert cache.get(key1) is None
        assert cache.get(key2) is None

    def test_cache_clear(self):
        """Clear removes all entries."""
        cache = SkillCache(max_size=100)
        skill = self._make_skill("test-skill", requires=["input"])
        key = SkillCacheKey.compute(skill, {"input": "test"})

        cache.set(key, self._make_output("result"), "test-skill", 100)
        cache.clear()

        assert cache.get(key) is None

    def test_cache_stats(self):
        """Cache statistics tracking."""
        cache = SkillCache(max_size=100)
        skill = self._make_skill("test-skill", requires=["input"])
        key = SkillCacheKey.compute(skill, {"input": "test"})

        # Miss
        cache.get(key)
        stats = cache.stats()
        assert stats["misses"] == 1
        assert stats["hits"] == 0

        # Set and hit
        cache.set(key, self._make_output("result"), "test-skill", 100)
        cache.get(key)
        stats = cache.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["size"] == 1

    def test_cache_max_size_eviction(self):
        """Cache evicts oldest entries when full."""
        cache = SkillCache(max_size=2)

        skill1 = self._make_skill("skill-1")
        skill2 = self._make_skill("skill-2")
        skill3 = self._make_skill("skill-3")

        key1 = SkillCacheKey.compute(skill1, {})
        key2 = SkillCacheKey.compute(skill2, {})
        key3 = SkillCacheKey.compute(skill3, {})

        cache.set(key1, self._make_output("result1"), "skill-1", 100)
        cache.set(key2, self._make_output("result2"), "skill-2", 100)
        cache.set(key3, self._make_output("result3"), "skill-3", 100)  # Should evict key1

        stats = cache.stats()
        assert stats["size"] <= 2


# =============================================================================
# SkillCacheKey Tests
# =============================================================================


class TestSkillCacheKey:
    """Tests for SkillCacheKey computation."""

    def _make_skill(
        self,
        name: str,
        instructions: str = "default",
        requires: list[str] | None = None,
    ) -> Skill:
        """Helper to create a skill with optional requires."""
        return Skill(
            name=name,
            description=f"Skill {name}",
            skill_type=SkillType.INLINE,
            instructions=instructions,
            requires=tuple(requires or []),
        )

    def test_same_skill_same_context(self):
        """Same skill and context produce same key."""
        skill = self._make_skill("test", requires=["a"])
        key1 = SkillCacheKey.compute(skill, {"a": 1})
        key2 = SkillCacheKey.compute(skill, {"a": 1})

        assert key1 == key2

    def test_different_context(self):
        """Different context produces different key when skill requires those keys."""
        skill = self._make_skill("test", requires=["a"])
        key1 = SkillCacheKey.compute(skill, {"a": 1})
        key2 = SkillCacheKey.compute(skill, {"a": 2})

        assert key1 != key2

    def test_different_skill_content(self):
        """Different skill content produces different key."""
        skill1 = self._make_skill("test", "instructions v1")
        skill2 = self._make_skill("test", "instructions v2")

        key1 = SkillCacheKey.compute(skill1, {})
        key2 = SkillCacheKey.compute(skill2, {})

        assert key1.skill_hash != key2.skill_hash

    def test_lens_version_affects_key(self):
        """Lens version affects cache key."""
        skill = self._make_skill("test")
        key1 = SkillCacheKey.compute(skill, {}, lens_version="1.0.0")
        key2 = SkillCacheKey.compute(skill, {}, lens_version="2.0.0")

        assert key1 != key2

    def test_context_order_independent(self):
        """Context key order should not affect hash."""
        skill = self._make_skill("test", requires=["a", "b"])
        key1 = SkillCacheKey.compute(skill, {"a": 1, "b": 2})
        key2 = SkillCacheKey.compute(skill, {"b": 2, "a": 1})

        assert key1 == key2


# =============================================================================
# ExecutionContext Tests
# =============================================================================


class TestExecutionContext:
    """Tests for ExecutionContext."""

    def test_get_set(self):
        """Basic get/set operations."""
        ctx = ExecutionContext()
        ctx.set("key", "value")
        assert ctx.get("key") == "value"

    def test_get_missing_returns_none(self):
        """Missing key returns None."""
        ctx = ExecutionContext()
        assert ctx.get("missing") is None

    def test_update_multiple(self):
        """Update with multiple values."""
        ctx = ExecutionContext()
        ctx.update({"a": 1, "b": 2})
        assert ctx.get("a") == 1
        assert ctx.get("b") == 2

    def test_initial_data(self):
        """Initialize with data."""
        ctx = ExecutionContext(data={"initial": "value"})
        assert ctx.get("initial") == "value"

    def test_lens_version(self):
        """Lens version tracking."""
        ctx = ExecutionContext(lens_version="1.2.3")
        assert ctx.lens_version == "1.2.3"


# =============================================================================
# IncrementalSkillExecutor Tests
# =============================================================================


class TestIncrementalSkillExecutor:
    """Tests for IncrementalSkillExecutor.

    Note: Full execution tests require mocked lens and model.
    These tests focus on the planning API which doesn't require execution.
    """

    def _make_skill(
        self,
        name: str,
        depends_on: list[str] | None = None,
        produces: list[str] | None = None,
        requires: list[str] | None = None,
    ) -> Skill:
        """Helper to create skills."""
        return Skill(
            name=name,
            description=f"Skill {name}",
            skill_type=SkillType.INLINE,
            instructions=f"Do {name}",
            depends_on=tuple(SkillDependency(source=d) for d in (depends_on or [])),
            produces=tuple(produces or []),
            requires=tuple(requires or []),
        )

    def test_execution_plan_empty_graph(self):
        """Empty graph produces empty execution plan."""
        from sunwell.skills.executor import SkillExecutionPlan

        plan = SkillExecutionPlan(
            to_execute=[],
            to_skip=[],
            waves=[],
        )
        assert plan.to_execute == []
        assert plan.to_skip == []
        assert plan.skip_percentage == 0.0  # Property, not field

    def test_execution_plan_with_skills(self):
        """Execution plan tracks skills to execute and skip."""
        from sunwell.skills.executor import SkillExecutionPlan

        plan = SkillExecutionPlan(
            to_execute=["skill-a", "skill-c"],
            to_skip=["skill-b"],
            waves=[["skill-a"], ["skill-b", "skill-c"]],
        )
        assert len(plan.to_execute) == 2
        assert len(plan.to_skip) == 1
        assert len(plan.waves) == 2
        # skip_percentage is a property: 1 out of 3 = 33.33%
        assert plan.skip_percentage == pytest.approx(33.33, rel=0.01)


# =============================================================================
# Integration Tests
# =============================================================================


class TestSkillGraphIntegration:
    """Integration tests for skill graph features."""

    def _make_skill(
        self,
        name: str,
        depends_on: list[str] | None = None,
        produces: list[str] | None = None,
        requires: list[str] | None = None,
    ) -> Skill:
        """Helper to create skills."""
        return Skill(
            name=name,
            description=f"Skill {name}",
            skill_type=SkillType.INLINE,
            instructions=f"Do {name}",
            depends_on=tuple(SkillDependency(source=d) for d in (depends_on or [])),
            produces=tuple(produces or []),
            requires=tuple(requires or []),
        )

    def test_produces_requires_flow(self):
        """Context flows from produces to requires."""
        skill_a = self._make_skill("skill-a", produces=["analysis_result"])
        skill_b = self._make_skill(
            "skill-b",
            depends_on=["skill-a"],
            requires=["analysis_result"],
        )

        graph = SkillGraph.from_skills([skill_a, skill_b])

        # Should be valid - skill-a produces what skill-b requires
        errors = graph.validate()
        assert len(errors) == 0

    def test_unsatisfied_requires_validation(self):
        """Unsatisfied requires should be caught."""
        skill_b = self._make_skill(
            "skill-b",
            requires=["missing_context"],
        )

        graph = SkillGraph.from_skills([skill_b])
        errors = graph.validate()

        # Should report unsatisfied requires
        assert any("missing_context" in e for e in errors)

    def test_complex_dag(self):
        """Complex DAG with multiple paths."""
        #     A
        #    / \
        #   B   C
        #   |   |
        #   D   E
        #    \ /
        #     F
        skill_f = self._make_skill("f", depends_on=["d", "e"])
        skill_e = self._make_skill("e", depends_on=["c"])
        skill_d = self._make_skill("d", depends_on=["b"])
        skill_c = self._make_skill("c", depends_on=["a"])
        skill_b = self._make_skill("b", depends_on=["a"])
        skill_a = self._make_skill("a")

        graph = SkillGraph.from_skills([skill_f, skill_e, skill_d, skill_c, skill_b, skill_a])

        order = graph.topological_order()
        waves = graph.execution_waves()

        # A must be first
        assert order[0] == "a"
        # F must be last
        assert order[-1] == "f"

        # Should have 4 waves: A, (B,C), (D,E), F
        assert len(waves) == 4
        assert waves[0] == ["a"]
        assert set(waves[1]) == {"b", "c"}
        assert set(waves[2]) == {"d", "e"}
        assert waves[3] == ["f"]
