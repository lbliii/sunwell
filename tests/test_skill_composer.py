"""Tests for RFC-111 Phase 4: Skill Composer."""

import pytest

from sunwell.agent.planning.composer import (
    CapabilityAnalysis,
    CompositionResult,
    CompositionType,
    SkillComposer,
)
from sunwell.planning.skills import (
    Skill,
    SkillDependency,
    SkillGraph,
    SkillType,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def read_file_skill() -> Skill:
    """A skill that reads files."""
    return Skill(
        name="read-file",
        description="Read a file from workspace",
        skill_type=SkillType.INLINE,
        triggers=("read", "file", "open"),
        produces=("file_content", "file_path"),
        instructions="Read the file and return its contents.",
    )


@pytest.fixture
def analyze_code_skill() -> Skill:
    """A skill that analyzes code."""
    return Skill(
        name="analyze-code",
        description="Analyze source code structure",
        skill_type=SkillType.INLINE,
        triggers=("analyze", "code", "structure"),
        depends_on=(SkillDependency(source="read-file"),),
        requires=("file_content",),
        produces=("analysis_result", "complexity"),
        instructions="Analyze the code structure.",
    )


@pytest.fixture
def generate_report_skill() -> Skill:
    """A skill that generates reports."""
    return Skill(
        name="generate-report",
        description="Generate documentation report",
        skill_type=SkillType.INLINE,
        triggers=("report", "document", "generate"),
        depends_on=(SkillDependency(source="analyze-code"),),
        requires=("analysis_result",),
        produces=("report",),
        instructions="Generate a comprehensive report.",
    )


@pytest.fixture
def list_files_skill() -> Skill:
    """A skill that lists files."""
    return Skill(
        name="list-files",
        description="List files in directory",
        skill_type=SkillType.INLINE,
        triggers=("list", "files", "directory"),
        produces=("file_list",),
        instructions="List all files matching pattern.",
    )


@pytest.fixture
def skills_library(
    read_file_skill: Skill,
    analyze_code_skill: Skill,
    generate_report_skill: Skill,
    list_files_skill: Skill,
) -> list[Skill]:
    """A library of skills to compose from."""
    return [
        read_file_skill,
        analyze_code_skill,
        generate_report_skill,
        list_files_skill,
    ]


@pytest.fixture
def composer(skills_library: list[Skill]) -> SkillComposer:
    """A SkillComposer with the test skill library."""
    return SkillComposer(skills=skills_library)


# =============================================================================
# COMPOSE SKILLS TESTS
# =============================================================================


class TestComposeSkills:
    """Tests for compose_skills method."""

    def test_compose_sequence(
        self,
        composer: SkillComposer,
    ) -> None:
        """Compose skills as a sequence."""
        result = composer.compose_skills(
            ["read-file", "analyze-code", "generate-report"],
            CompositionType.SEQUENCE,
        )

        assert isinstance(result, CompositionResult)
        assert result.composition_type == CompositionType.SEQUENCE
        assert len(result.source_skills) == 3
        assert "sequence" in result.skill.name

        # Composed skill should have merged produces
        assert "report" in result.skill.produces
        assert "analysis_result" in result.skill.produces
        assert "file_content" in result.skill.produces

    def test_compose_parallel(
        self,
        composer: SkillComposer,
    ) -> None:
        """Compose skills for parallel execution."""
        result = composer.compose_skills(
            ["read-file", "list-files"],
            CompositionType.PARALLEL,
        )

        assert result.composition_type == CompositionType.PARALLEL
        assert "parallel" in result.skill.name

        # Parallel skills merge all produces
        assert "file_content" in result.skill.produces
        assert "file_list" in result.skill.produces

    def test_compose_conditional(
        self,
        composer: SkillComposer,
    ) -> None:
        """Compose skills with conditional execution."""
        result = composer.compose_skills(
            ["read-file", "analyze-code"],
            CompositionType.CONDITIONAL,
        )

        assert result.composition_type == CompositionType.CONDITIONAL
        assert "conditional" in result.skill.name

    def test_compose_fallback(
        self,
        composer: SkillComposer,
    ) -> None:
        """Compose skills as fallback chain."""
        result = composer.compose_skills(
            ["read-file", "list-files"],
            CompositionType.FALLBACK,
        )

        assert result.composition_type == CompositionType.FALLBACK
        assert "fallback" in result.skill.name

    def test_compose_with_custom_name(
        self,
        composer: SkillComposer,
    ) -> None:
        """Compose with custom name and description."""
        result = composer.compose_skills(
            ["read-file", "analyze-code"],
            CompositionType.SEQUENCE,
            name="my-custom-workflow",
            description="A custom workflow for analysis",
        )

        assert result.skill.name == "my-custom-workflow"
        assert result.skill.description == "A custom workflow for analysis"

    def test_compose_invalid_skills_raises(
        self,
        composer: SkillComposer,
    ) -> None:
        """Composing non-existent skills raises error."""
        with pytest.raises(ValueError, match="No valid skills"):
            composer.compose_skills(["nonexistent-skill"], CompositionType.SEQUENCE)

    def test_compose_requires_filtering(
        self,
        composer: SkillComposer,
    ) -> None:
        """Composed skill's requires excludes internally-satisfied keys."""
        # analyze-code requires file_content, which read-file produces
        result = composer.compose_skills(
            ["read-file", "analyze-code"],
            CompositionType.SEQUENCE,
        )

        # file_content should NOT be in external requires
        # (it's satisfied internally by read-file)
        assert "file_content" not in result.skill.requires


# =============================================================================
# HEURISTIC ANALYSIS TESTS
# =============================================================================


class TestHeuristicAnalysis:
    """Tests for heuristic goal analysis (without LLM)."""

    def test_match_by_trigger(
        self,
        composer: SkillComposer,
    ) -> None:
        """Match skills by trigger words."""
        analysis = composer._analyze_goal_heuristic("read the file and analyze code")

        assert "read-file" in analysis.matched_skills
        assert "analyze-code" in analysis.matched_skills

    def test_match_by_name(
        self,
        composer: SkillComposer,
    ) -> None:
        """Match skills by name appearing in goal."""
        analysis = composer._analyze_goal_heuristic("use list-files skill")

        assert "list-files" in analysis.matched_skills

    def test_no_match_returns_empty(
        self,
        composer: SkillComposer,
    ) -> None:
        """No matches returns empty analysis."""
        analysis = composer._analyze_goal_heuristic("do something unrelated")

        assert len(analysis.matched_skills) == 0


# =============================================================================
# DAG BUILDING TESTS
# =============================================================================


class TestDagBuilding:
    """Tests for DAG construction from contracts."""

    def test_infer_dependencies_from_requires(
        self,
        composer: SkillComposer,
        read_file_skill: Skill,
        analyze_code_skill: Skill,
    ) -> None:
        """Dependencies are inferred from requires/produces."""
        # Create skills without explicit depends_on
        skill_a = Skill(
            name="skill-a",
            description="Producer",
            skill_type=SkillType.INLINE,
            produces=("data",),
            instructions="...",
        )
        skill_b = Skill(
            name="skill-b",
            description="Consumer",
            skill_type=SkillType.INLINE,
            requires=("data",),
            produces=("output",),
            instructions="...",
        )

        graph = composer._build_dag_from_contracts([skill_a, skill_b])

        # skill-b should depend on skill-a
        skill_b_in_graph = graph.get("skill-b")
        assert skill_b_in_graph is not None
        assert any(d.skill_name == "skill-a" for d in skill_b_in_graph.depends_on)

    def test_no_self_dependency(
        self,
        composer: SkillComposer,
    ) -> None:
        """Skills don't create self-dependencies."""
        skill = Skill(
            name="self-ref",
            description="Self-referencing",
            skill_type=SkillType.INLINE,
            produces=("output",),
            requires=("output",),  # Requires its own output
            instructions="...",
        )

        graph = composer._build_dag_from_contracts([skill])
        skill_in_graph = graph.get("self-ref")

        assert skill_in_graph is not None
        assert len(skill_in_graph.depends_on) == 0


# =============================================================================
# SKILL PARSING TESTS
# =============================================================================


class TestSkillParsing:
    """Tests for parsing generated skill content."""

    def test_parse_valid_skill(
        self,
        composer: SkillComposer,
    ) -> None:
        """Parse a valid generated skill."""
        content = """
NAME: my-new-skill
DESCRIPTION: A generated skill for testing
REQUIRES: input_data
PRODUCES: output_data, extra_output
INSTRUCTIONS:
1. Process the input data
2. Generate output
3. Return results
"""
        skill = composer._parse_generated_skill(content, "fallback description")

        assert skill is not None
        assert skill.name == "my-new-skill"
        assert skill.description == "A generated skill for testing"
        assert "input_data" in skill.requires
        assert "output_data" in skill.produces
        assert "extra_output" in skill.produces
        assert "Process the input data" in skill.instructions

    def test_parse_skill_with_none_requires(
        self,
        composer: SkillComposer,
    ) -> None:
        """Parse skill with 'none' for requires."""
        content = """
NAME: no-inputs
DESCRIPTION: Skill with no inputs
REQUIRES: none
PRODUCES: output
INSTRUCTIONS:
Generate output without inputs.
"""
        skill = composer._parse_generated_skill(content, "fallback")

        assert skill is not None
        assert len(skill.requires) == 0

    def test_parse_skill_generates_name_if_missing(
        self,
        composer: SkillComposer,
    ) -> None:
        """Generate name from description if not provided."""
        content = """
DESCRIPTION: Analyze something important
PRODUCES: analysis
INSTRUCTIONS:
Analyze the thing.
"""
        skill = composer._parse_generated_skill(content, "fallback description")

        assert skill is not None
        assert skill.name  # Name should be generated


# =============================================================================
# CAPABILITY ANALYSIS PARSING TESTS
# =============================================================================


class TestCapabilityAnalysisParsing:
    """Tests for parsing LLM capability analysis responses."""

    def test_parse_full_analysis(
        self,
        composer: SkillComposer,
    ) -> None:
        """Parse a complete capability analysis."""
        content = """
CAPABILITIES:
- Read source files
- Analyze code structure
- Generate report

MATCHED_SKILLS:
- read-file
- analyze-code

GAPS:
- No skill for formatting output

SUGGESTED_FLOW:
read-file -> analyze-code -> generate-report
"""
        analysis = composer._parse_capability_analysis(content)

        assert "Read source files" in analysis.capabilities
        assert "read-file" in analysis.matched_skills
        assert "analyze-code" in analysis.matched_skills
        assert "No skill for formatting output" in analysis.gaps
        assert "read-file -> analyze-code" in (analysis.suggested_flow or "")

    def test_parse_partial_analysis(
        self,
        composer: SkillComposer,
    ) -> None:
        """Parse analysis with missing sections."""
        content = """
MATCHED_SKILLS:
- read-file
"""
        analysis = composer._parse_capability_analysis(content)

        assert "read-file" in analysis.matched_skills
        assert len(analysis.capabilities) == 0
        assert len(analysis.gaps) == 0


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestComposerIntegration:
    """Integration tests for full composition workflows."""

    def test_compose_then_build_graph(
        self,
        composer: SkillComposer,
    ) -> None:
        """Composed skill can be added to a graph."""
        result = composer.compose_skills(
            ["read-file", "analyze-code"],
            CompositionType.SEQUENCE,
            name="read-and-analyze",
        )

        # Add to a new graph with other skills
        graph = SkillGraph.from_skills([
            result.skill,
            Skill(
                name="use-analysis",
                description="Use the analysis",
                skill_type=SkillType.INLINE,
                depends_on=(SkillDependency(source="read-and-analyze"),),
                requires=("analysis_result",),
                produces=("final_output",),
                instructions="...",
            ),
        ])

        # Graph should be valid
        errors = graph.validate()
        assert len(errors) == 0

        # Should have 2 waves
        waves = graph.execution_waves()
        assert len(waves) == 2

    def test_sync_plan_without_model(
        self,
        composer: SkillComposer,
    ) -> None:
        """plan_sync works without a model."""
        # Import GoalPlanner for sync planning
        from sunwell.agent.planning import GoalPlanner

        planner = GoalPlanner(skills=composer.skills)
        graph = planner.plan_sync("read file and analyze the code")

        # Should match some skills by triggers
        assert len(graph) > 0
