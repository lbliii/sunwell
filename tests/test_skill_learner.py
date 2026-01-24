"""Tests for SkillLearner and SkillLibrary (RFC-111 Phase 5)."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from sunwell.skills.learner import (
    ExecutionPattern,
    LearnedSkillMetadata,
    SkillLearner,
    SkillLearningResult,
)
from sunwell.skills.library import SkillLibrary, SkillProvenance
from sunwell.skills.types import Skill, SkillDependency, SkillMetadata, SkillType


# =============================================================================
# SkillLearner Tests
# =============================================================================


class TestExecutionPattern:
    """Tests for ExecutionPattern data class."""

    def test_creation(self):
        """Test basic pattern creation."""
        pattern = ExecutionPattern(
            goal="Audit the API documentation",
            steps_description="User: audit\nCalled: read_file\nCalled: grep",
            tools_used=("read_file", "grep", "write_file"),
            context_keys=("file_content", "search_results"),
            turn_ids=("turn1", "turn2", "turn3"),
        )

        assert pattern.goal == "Audit the API documentation"
        assert len(pattern.tools_used) == 3
        assert "read_file" in pattern.tools_used
        assert len(pattern.context_keys) == 2

    def test_success_indicators(self):
        """Test pattern with success indicators."""
        pattern = ExecutionPattern(
            goal="Build REST API",
            steps_description="steps",
            tools_used=("write_file",),
            context_keys=(),
            turn_ids=(),
            success_indicators=("API working", "tests passing"),
        )

        assert len(pattern.success_indicators) == 2


class TestSkillLearner:
    """Tests for SkillLearner class."""

    def test_init_defaults(self):
        """Test default initialization."""
        learner = SkillLearner()

        assert learner.model is None
        assert learner.min_turns_for_learning == 5
        assert learner.min_tool_calls == 2

    def test_slugify(self):
        """Test skill name slugification."""
        learner = SkillLearner()

        # Basic slugification
        assert learner._slugify("Hello World") == "hello-world"
        assert learner._slugify("Audit API Documentation") == "audit-api-documentation"

        # Numbers at start
        assert learner._slugify("123 Test").startswith("skill-")

        # Special characters
        assert learner._slugify("Test! @#$ Skill") == "test-skill"

        # Empty/whitespace
        assert learner._slugify("   ") == "learned-skill"

    def test_extract_triggers(self):
        """Test trigger extraction from goal."""
        learner = SkillLearner()

        triggers = learner._extract_triggers("Audit the API documentation for errors")

        # Should filter stopwords
        assert "the" not in triggers
        assert "for" not in triggers

        # Should include meaningful words
        assert "audit" in triggers or "documentation" in triggers or "errors" in triggers

        # Should be limited
        assert len(triggers) <= 5

    def test_extract_tool_name_json_format(self):
        """Test tool name extraction from JSON format."""
        learner = SkillLearner()

        # JSON format: {"tool": "tool_name", ...}
        content = '{"tool": "read_file", "args": {"path": "test.py"}}'
        assert learner._extract_tool_name(content) == "read_file"

    def test_extract_tool_name_function_format(self):
        """Test tool name extraction from function call format."""
        learner = SkillLearner()

        # Function format: tool_name(...)
        content = "grep(pattern='test', path='.')"
        assert learner._extract_tool_name(content) == "grep"

    def test_extract_tool_name_name_field(self):
        """Test tool name extraction from name field."""
        learner = SkillLearner()

        # Name field format
        content = '{"name": "write_file", "arguments": {}}'
        assert learner._extract_tool_name(content) == "write_file"

    def test_extract_context_keys(self):
        """Test context key extraction from tool results."""
        learner = SkillLearner()

        content = '{"file_content": "...", "analysis": {...}, "status": "ok"}'
        keys = learner._extract_context_keys(content)

        # Should include meaningful keys
        assert "file_content" in keys
        assert "analysis" in keys

        # Should exclude common noise
        assert "status" not in keys  # common noise

    def test_generate_skill_heuristic(self):
        """Test heuristic skill generation."""
        learner = SkillLearner()

        pattern = ExecutionPattern(
            goal="Audit API docs",
            steps_description="User: audit docs\nCalled: read_file\nCalled: grep",
            tools_used=("read_file", "grep"),
            context_keys=("file_content",),
            turn_ids=("t1", "t2"),
        )

        skill = learner._generate_skill_heuristic(pattern, "Documentation validated")

        assert skill.name == "audit-api-docs"
        assert skill.skill_type == SkillType.INLINE
        assert skill.instructions is not None
        assert "Audit API docs" in skill.instructions
        assert "read_file" in skill.allowed_tools
        assert "grep" in skill.allowed_tools

    def test_generate_skill_infers_requires(self):
        """Test that heuristic generation infers requires from tools."""
        learner = SkillLearner()

        pattern = ExecutionPattern(
            goal="Search codebase",
            steps_description="steps",
            tools_used=("read_file", "grep"),
            context_keys=(),
            turn_ids=(),
        )

        skill = learner._generate_skill_heuristic(pattern, "Found results")

        # Should infer file_path requirement from read-file
        assert "file_path" in skill.requires or "search_query" in skill.requires


class TestSkillLearnerPatternExtraction:
    """Tests for pattern extraction from DAG."""

    def test_topological_sort_empty_dag(self):
        """Test topological sort with empty DAG."""
        from sunwell.simulacrum.core.dag import ConversationDAG

        learner = SkillLearner()
        dag = ConversationDAG()

        result = learner._topological_sort(dag)
        assert result == []

    def test_topological_sort_linear(self):
        """Test topological sort with linear conversation."""
        from sunwell.simulacrum.core.dag import ConversationDAG
        from sunwell.simulacrum.core.turn import Turn, TurnType

        learner = SkillLearner()
        dag = ConversationDAG()

        # Add turns linearly
        t1 = Turn(content="Hello", turn_type=TurnType.USER)
        t2 = Turn(content="Hi", turn_type=TurnType.ASSISTANT, parent_ids=(t1.id,))

        dag.add_turn(t1)
        dag.add_turn(t2)

        result = learner._topological_sort(dag)

        # Should be in order
        assert len(result) == 2
        assert result[0].id == t1.id
        assert result[1].id == t2.id

    def test_summarize_steps(self):
        """Test step summarization."""
        from sunwell.simulacrum.core.dag import ConversationDAG
        from sunwell.simulacrum.core.turn import Turn, TurnType

        learner = SkillLearner()
        dag = ConversationDAG()

        t1 = Turn(content="Audit the docs", turn_type=TurnType.USER)
        t2 = Turn(
            content='{"tool": "read_file"}',
            turn_type=TurnType.TOOL_CALL,
            parent_ids=(t1.id,),
        )

        dag.add_turn(t1)
        dag.add_turn(t2)

        summary = learner._summarize_steps(dag)

        assert "User: Audit the docs" in summary
        assert "Called: read_file" in summary


# =============================================================================
# SkillLibrary Tests
# =============================================================================


class TestSkillLibrary:
    """Tests for SkillLibrary class."""

    def test_init_creates_directories(self):
        """Test that init creates library directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lib_path = Path(tmpdir) / "skills"
            library = SkillLibrary(lib_path)

            assert (lib_path / "learned").exists()
            assert (lib_path / "composed").exists()
            assert (lib_path / "imported").exists()

    def test_save_and_load_skill(self):
        """Test saving and loading a skill."""
        with tempfile.TemporaryDirectory() as tmpdir:
            library = SkillLibrary(Path(tmpdir) / "skills")

            skill = Skill(
                name="test-skill",
                description="A test skill",
                skill_type=SkillType.INLINE,
                instructions="Do the thing",
                produces=("result",),
                requires=("input",),
            )

            # Save
            path = library.save_skill(skill, source="learned", session_id="sess123")
            assert path.exists()
            assert (path / "SKILL.yaml").exists()
            assert (path / "META.yaml").exists()

            # Clear cache to test loading from disk
            library._skill_cache.clear()

            # Load
            loaded = library.load_skill("test-skill")
            assert loaded is not None
            assert loaded.name == "test-skill"
            assert loaded.description == "A test skill"
            assert "result" in loaded.produces
            assert "input" in loaded.requires

    def test_discover_skills(self):
        """Test skill discovery."""
        with tempfile.TemporaryDirectory() as tmpdir:
            library = SkillLibrary(Path(tmpdir) / "skills")

            # Save multiple skills
            skill1 = Skill(
                name="skill-one",
                description="First skill",
                skill_type=SkillType.INLINE,
                instructions="Do one",
            )
            skill2 = Skill(
                name="skill-two",
                description="Second skill",
                skill_type=SkillType.INLINE,
                instructions="Do two",
            )

            library.save_skill(skill1, source="learned")
            library.save_skill(skill2, source="composed")

            # Discover all
            all_skills = library.discover_skills()
            assert len(all_skills) == 2

            # Filter by source
            learned = library.discover_skills(source_filter="learned")
            assert len(learned) == 1
            assert learned[0].name == "skill-one"

    def test_list_skills(self):
        """Test listing skills with summary info."""
        with tempfile.TemporaryDirectory() as tmpdir:
            library = SkillLibrary(Path(tmpdir) / "skills")

            skill = Skill(
                name="list-test",
                description="Test for listing",
                skill_type=SkillType.INLINE,
                instructions="Instructions",
            )

            library.save_skill(skill, source="learned")

            skills = library.list_skills()
            assert len(skills) == 1
            assert skills[0]["name"] == "list-test"
            assert skills[0]["source"] == "learned"
            assert "created_at" in skills[0]

    def test_delete_skill(self):
        """Test skill deletion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            library = SkillLibrary(Path(tmpdir) / "skills")

            skill = Skill(
                name="delete-me",
                description="To be deleted",
                skill_type=SkillType.INLINE,
                instructions="Gone soon",
            )

            library.save_skill(skill, source="learned")
            assert library.load_skill("delete-me") is not None

            # Delete
            result = library.delete_skill("delete-me")
            assert result is True

            # Should be gone
            assert library.load_skill("delete-me") is None

            # Deleting non-existent should return False
            assert library.delete_skill("nonexistent") is False

    def test_get_provenance(self):
        """Test provenance retrieval."""
        with tempfile.TemporaryDirectory() as tmpdir:
            library = SkillLibrary(Path(tmpdir) / "skills")

            skill = Skill(
                name="prov-test",
                description="Provenance test",
                skill_type=SkillType.INLINE,
                instructions="Test",
            )

            library.save_skill(
                skill,
                source="composed",
                parent_skills=("skill-a", "skill-b"),
            )

            prov = library.get_provenance("prov-test")
            assert prov is not None
            assert prov.source == "composed"
            assert "skill-a" in prov.parent_skills
            assert "skill-b" in prov.parent_skills

    def test_stats(self):
        """Test library statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            library = SkillLibrary(Path(tmpdir) / "skills")

            # Empty stats
            stats = library.stats()
            assert stats["total_skills"] == 0

            # Add some skills
            for i, source in enumerate(["learned", "learned", "composed"]):
                skill = Skill(
                    name=f"stat-skill-{i}",
                    description=f"Skill {i}",
                    skill_type=SkillType.INLINE,
                    instructions="Test",
                )
                library.save_skill(skill, source=source)

            stats = library.stats()
            assert stats["total_skills"] == 3
            assert stats["by_source"]["learned"] == 2
            assert stats["by_source"]["composed"] == 1

    def test_load_metadata(self):
        """Test loading lightweight metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            library = SkillLibrary(Path(tmpdir) / "skills")

            skill = Skill(
                name="meta-test",
                description="Metadata test",
                skill_type=SkillType.INLINE,
                instructions="Full instructions here",
                produces=("output",),
                triggers=("test", "meta"),
            )

            library.save_skill(skill, source="learned")
            library._metadata_cache.clear()

            meta = library.load_metadata("meta-test")
            assert meta is not None
            assert meta.name == "meta-test"
            assert "output" in meta.produces
            assert "test" in meta.triggers


class TestSkillLibraryImport:
    """Tests for skill import functionality."""

    def test_import_from_yaml(self):
        """Test importing from SKILL.yaml."""
        import yaml

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            library = SkillLibrary(tmpdir / "skills")

            # Create external skill file
            external_dir = tmpdir / "external"
            external_dir.mkdir()

            skill_data = {
                "name": "external-skill",
                "description": "An external skill",
                "type": "inline",
                "instructions": "Do external things",
                "produces": ["external_output"],
            }

            with open(external_dir / "SKILL.yaml", "w") as f:
                yaml.dump(skill_data, f)

            # Import
            skill = library.import_skill(external_dir)
            assert skill is not None
            assert skill.name == "external-skill"

            # Should be in library
            loaded = library.load_skill("external-skill")
            assert loaded is not None

            # Check provenance
            prov = library.get_provenance("external-skill")
            assert prov is not None
            assert prov.source == "imported"
            assert str(external_dir) in prov.imported_from

    def test_import_with_name_override(self):
        """Test importing with name override."""
        import yaml

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            library = SkillLibrary(tmpdir / "skills")

            external_dir = tmpdir / "external"
            external_dir.mkdir()

            with open(external_dir / "SKILL.yaml", "w") as f:
                yaml.dump({
                    "name": "original-name",
                    "description": "Test",
                    "type": "inline",
                    "instructions": "Test",
                }, f)

            skill = library.import_skill(external_dir, name="new-name")
            assert skill is not None
            assert skill.name == "new-name"


class TestSkillProvenance:
    """Tests for SkillProvenance data class."""

    def test_creation(self):
        """Test provenance creation."""
        prov = SkillProvenance(
            source="learned",
            created_at="2026-01-23T12:00:00",
            version="1.0.0",
            session_id="sess123",
        )

        assert prov.source == "learned"
        assert prov.session_id == "sess123"

    def test_composed_provenance(self):
        """Test composed skill provenance."""
        prov = SkillProvenance(
            source="composed",
            created_at="2026-01-23T12:00:00",
            parent_skills=("skill-a", "skill-b", "skill-c"),
        )

        assert prov.source == "composed"
        assert len(prov.parent_skills) == 3


# =============================================================================
# Integration Tests
# =============================================================================


class TestSkillLearnerLibraryIntegration:
    """Integration tests for SkillLearner + SkillLibrary."""

    @pytest.mark.asyncio
    async def test_learn_and_save_workflow(self):
        """Test the full learn -> save workflow."""
        from sunwell.simulacrum.core.dag import ConversationDAG
        from sunwell.simulacrum.core.turn import Turn, TurnType

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            library = SkillLibrary(tmpdir / "skills")
            learner = SkillLearner(min_turns_for_learning=2, min_tool_calls=1)

            # Create a mock DAG with tool calls
            dag = ConversationDAG()

            t1 = Turn(content="Audit the API", turn_type=TurnType.USER)
            t2 = Turn(
                content='{"tool": "read_file", "path": "api.py"}',
                turn_type=TurnType.TOOL_CALL,
                parent_ids=(t1.id,),
            )
            t3 = Turn(
                content='{"file_content": "def api(): pass"}',
                turn_type=TurnType.TOOL_RESULT,
                parent_ids=(t2.id,),
            )
            t4 = Turn(
                content='{"tool": "grep", "pattern": "def"}',
                turn_type=TurnType.TOOL_CALL,
                parent_ids=(t3.id,),
            )
            t5 = Turn(
                content='{"matches": ["def api"]}',
                turn_type=TurnType.TOOL_RESULT,
                parent_ids=(t4.id,),
            )

            for t in [t1, t2, t3, t4, t5]:
                dag.add_turn(t)

            # Extract pattern
            pattern = learner.extract_pattern_from_dag(dag, "Audit the API")
            assert pattern is not None
            assert "read_file" in pattern.tools_used
            assert "grep" in pattern.tools_used

            # Generate skill
            skill = learner._generate_skill_heuristic(pattern, "API audited successfully")
            assert skill is not None

            # Save to library
            path = library.save_skill(skill, source="learned", session_id="test-session")
            assert path.exists()

            # Verify saved correctly
            loaded = library.load_skill(skill.name)
            assert loaded is not None
            assert "read_file" in loaded.allowed_tools
