"""Tests for RFC-035: Domain-Agnostic Project Framework."""

import tempfile
from pathlib import Path

import pytest

from sunwell.project.schema import (
    ProjectSchema,
    ArtifactType,
    ArtifactField,
    ValidatorConfig,
    PlanningConfig,
    PlanningPhase,
)
from sunwell.project.dsl import ConstraintDSL, ConstraintEvaluator, ParsedRule
from sunwell.project.validators import ConstraintValidator, ConstraintViolation
from sunwell.project.resolver import SchemaResolver, ArtifactLoader
from sunwell.project.compatibility import is_lens_compatible, get_compatibility_error
from sunwell.core.lens import Lens, LensMetadata
from sunwell.core.validator import SchemaValidator, SchemaValidationMethod
from sunwell.core.types import Severity


# =============================================================================
# Schema Loading Tests
# =============================================================================


class TestProjectSchema:
    """Tests for ProjectSchema loading and parsing."""

    def test_load_fiction_schema(self, tmp_path: Path) -> None:
        """Test loading a fiction schema from YAML."""
        schema_dir = tmp_path / ".sunwell"
        schema_dir.mkdir()
        
        schema_content = """
project:
  name: "The London Conspiracy"
  type: fiction
  version: "1.0.0"

artifact_types:
  character:
    description: "A person in the story"
    fields:
      required: [name, traits]
      optional: [age, backstory]
    produces: "Character_{id}"
    
  scene:
    description: "A unit of narrative action"
    fields:
      required: [summary, pov, location]
      optional: [characters_present]
    requires:
      - "Character_{pov}"
    produces: "Scene_{id}"

validators:
  - name: timeline_consistency
    description: "No character can be in two places at once"
    rule: |
      FOR scene IN artifacts.scenes
      ASSERT scene.pov != None
    severity: error
    method: constraint

planning:
  default_strategy: contract_first
  phases:
    - name: worldbuilding
      artifact_types: [character]
      parallel: true
      maps_to: contracts
    - name: drafting
      artifact_types: [scene]
      parallel: false
"""
        (schema_dir / "schema.yaml").write_text(schema_content)
        
        schema = ProjectSchema.load(tmp_path)
        
        assert schema.name == "The London Conspiracy"
        assert schema.project_type == "fiction"
        assert "character" in schema.artifact_types
        assert "scene" in schema.artifact_types
        
        character_type = schema.artifact_types["character"]
        assert character_type.description == "A person in the story"
        assert "name" in character_type.fields.required
        assert character_type.produces_pattern == "Character_{id}"
        
        scene_type = schema.artifact_types["scene"]
        assert "Character_{pov}" in scene_type.requires_patterns
        
        assert len(schema.validators) == 1
        assert schema.validators[0].name == "timeline_consistency"
        
        assert len(schema.planning_config.phases) == 2
        assert schema.planning_config.phases[0].name == "worldbuilding"
        assert schema.planning_config.phases[0].parallel is True

    def test_load_or_default_returns_none(self, tmp_path: Path) -> None:
        """Test that load_or_default returns None when no schema exists."""
        result = ProjectSchema.load_or_default(tmp_path)
        assert result is None

    def test_get_phase_for_artifact_type(self, tmp_path: Path) -> None:
        """Test getting the planning phase for an artifact type."""
        schema_dir = tmp_path / ".sunwell"
        schema_dir.mkdir()
        
        (schema_dir / "schema.yaml").write_text("""
project:
  name: Test
  type: test

artifact_types:
  item:
    description: "Test item"
    produces: "Item_{id}"

planning:
  phases:
    - name: phase1
      artifact_types: [item]
      maps_to: contracts
""")
        
        schema = ProjectSchema.load(tmp_path)
        phase = schema.get_phase_for_artifact_type("item")
        
        assert phase is not None
        assert phase.name == "phase1"
        assert phase.maps_to == "contracts"


# =============================================================================
# DSL Tests
# =============================================================================


class TestConstraintDSL:
    """Tests for the constraint DSL parser."""

    def test_parse_simple_rule(self) -> None:
        """Test parsing a simple FOR/ASSERT rule."""
        dsl = ConstraintDSL()
        
        rule = """
        FOR item IN artifacts.items
        ASSERT item.name != ''
        """
        
        parsed = dsl.parse(rule)
        
        assert len(parsed.for_clauses) == 1
        assert parsed.for_clauses[0].variables == ("item",)
        assert parsed.for_clauses[0].collection == "artifacts.items"
        assert parsed.where_clause is None
        assert "item.name != ''" in parsed.assert_clause

    def test_parse_rule_with_where(self) -> None:
        """Test parsing a rule with WHERE clause."""
        dsl = ConstraintDSL()
        
        rule = """
        FOR char IN artifacts.characters
        WHERE char.role == 'major'
        ASSERT char.arc != None
        """
        
        parsed = dsl.parse(rule)
        
        assert parsed.where_clause is not None
        assert "char.role == 'major'" in parsed.where_clause
        assert "char.arc != None" in parsed.assert_clause

    def test_parse_multiple_for_clauses(self) -> None:
        """Test parsing a rule with multiple FOR clauses."""
        dsl = ConstraintDSL()
        
        rule = """
        FOR scene_a, scene_b IN artifacts.scenes
        FOR char IN artifacts.characters
        WHERE char IN scene_a.characters
        ASSERT scene_a.id != scene_b.id
        """
        
        parsed = dsl.parse(rule)
        
        assert len(parsed.for_clauses) == 2
        assert parsed.for_clauses[0].variables == ("scene_a", "scene_b")
        assert parsed.for_clauses[1].variables == ("char",)


class TestConstraintEvaluator:
    """Tests for the constraint evaluator."""

    def test_evaluate_equality(self) -> None:
        """Test evaluating equality conditions."""
        evaluator = ConstraintEvaluator()
        
        bindings = {"x": {"name": "John"}, "y": "John"}
        
        assert evaluator.evaluate_condition("x.name == y", bindings) is True
        assert evaluator.evaluate_condition("x.name != y", bindings) is False

    def test_evaluate_membership(self) -> None:
        """Test evaluating IN membership."""
        evaluator = ConstraintEvaluator()
        
        bindings = {"item": "apple", "fruits": ["apple", "banana"]}
        
        assert evaluator.evaluate_condition("item IN fruits", bindings) is True
        assert evaluator.evaluate_condition("'orange' IN fruits", bindings) is False

    def test_evaluate_and_or(self) -> None:
        """Test evaluating AND/OR conditions."""
        evaluator = ConstraintEvaluator()
        
        bindings = {"a": True, "b": False}
        
        assert evaluator.evaluate_condition("a AND b", bindings) is False
        assert evaluator.evaluate_condition("a OR b", bindings) is True

    def test_enumerate_bindings(self) -> None:
        """Test enumerating variable bindings."""
        evaluator = ConstraintEvaluator()
        dsl = ConstraintDSL()
        
        parsed = dsl.parse("FOR item IN artifacts.items ASSERT item.id != None")
        
        artifacts = {
            "items": [
                {"id": "1", "name": "A"},
                {"id": "2", "name": "B"},
            ]
        }
        
        bindings_list = list(evaluator.enumerate_bindings(parsed.for_clauses, artifacts))
        
        assert len(bindings_list) == 2
        assert bindings_list[0]["item"]["id"] == "1"
        assert bindings_list[1]["item"]["id"] == "2"


# =============================================================================
# Validator Tests
# =============================================================================


class TestConstraintValidator:
    """Tests for the constraint validator."""

    def test_validate_passes(self) -> None:
        """Test validation that passes."""
        validator = ConstraintValidator()
        
        rule = """
        FOR item IN artifacts.items
        ASSERT item.name != ''
        """
        
        artifacts = {
            "items": [
                {"id": "1", "name": "Valid Item"},
            ]
        }
        
        violations = validator.validate(rule, artifacts)
        
        assert len(violations) == 0

    def test_validate_fails(self) -> None:
        """Test validation that catches a violation."""
        validator = ConstraintValidator()
        
        rule = """
        FOR item IN artifacts.items
        ASSERT item.name != ''
        """
        
        artifacts = {
            "items": [
                {"id": "1", "name": "Valid"},
                {"id": "2", "name": ""},  # Violation!
            ]
        }
        
        violations = validator.validate(
            rule,
            artifacts,
            rule_name="non_empty_name",
            severity="error",
        )
        
        assert len(violations) == 1
        assert violations[0].rule_name == "non_empty_name"
        assert violations[0].severity == "error"

    def test_validate_with_where_filter(self) -> None:
        """Test validation with WHERE filtering."""
        validator = ConstraintValidator()
        
        rule = """
        FOR char IN artifacts.characters
        WHERE char.role == 'major'
        ASSERT char.arc != None
        """
        
        artifacts = {
            "characters": [
                {"id": "1", "name": "John", "role": "major", "arc": "growth"},
                {"id": "2", "name": "Mary", "role": "minor", "arc": None},  # Should be filtered
            ]
        }
        
        violations = validator.validate(rule, artifacts)
        
        # Mary is filtered out by WHERE, so no violations
        assert len(violations) == 0


# =============================================================================
# Resolver Tests
# =============================================================================


class TestSchemaResolver:
    """Tests for the schema to task resolver."""

    def test_resolve_artifact(self, tmp_path: Path) -> None:
        """Test resolving a single artifact to a task."""
        # Create schema
        schema_dir = tmp_path / ".sunwell"
        schema_dir.mkdir()
        
        (schema_dir / "schema.yaml").write_text("""
project:
  name: Test
  type: test

artifact_types:
  character:
    description: "A character"
    fields:
      required: [name]
    produces: "Character_{id}"
    is_contract: true

planning:
  phases:
    - name: worldbuilding
      artifact_types: [character]
      maps_to: contracts
""")
        
        # Create artifact
        artifacts_dir = tmp_path / "artifacts" / "characters"
        artifacts_dir.mkdir(parents=True)
        
        (artifacts_dir / "john.yaml").write_text("""
type: character
id: john
name: "John Hartwell"
""")
        
        schema = ProjectSchema.load(tmp_path)
        resolver = SchemaResolver(schema)
        
        task = resolver.resolve_artifact(artifacts_dir / "john.yaml")
        
        assert task.id == "john"
        assert "Character_john" in task.produces
        assert task.parallel_group == "contracts"
        assert task.is_contract is True

    def test_resolve_artifact_with_dependencies(self, tmp_path: Path) -> None:
        """Test resolving artifact with requires."""
        schema_dir = tmp_path / ".sunwell"
        schema_dir.mkdir()
        
        (schema_dir / "schema.yaml").write_text("""
project:
  name: Test
  type: fiction

artifact_types:
  character:
    description: "A character"
    produces: "Character_{id}"
    
  scene:
    description: "A scene"
    fields:
      required: [pov]
    requires:
      - "Character_{pov}"
    produces: "Scene_{id}"
""")
        
        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()
        
        (artifacts_dir / "scene1.yaml").write_text("""
type: scene
id: scene1
pov: john
""")
        
        schema = ProjectSchema.load(tmp_path)
        resolver = SchemaResolver(schema)
        
        task = resolver.resolve_artifact(artifacts_dir / "scene1.yaml")
        
        assert "Character_john" in task.requires


# =============================================================================
# Compatibility Tests
# =============================================================================


class TestLensCompatibility:
    """Tests for lens-schema compatibility checking."""

    def test_universal_lens_compatible(self) -> None:
        """Test that universal lens (no compatible_schemas) works with any schema."""
        lens = Lens(
            metadata=LensMetadata(
                name="Universal Lens",
                compatible_schemas=(),  # Universal
            )
        )
        
        schema = ProjectSchema(
            name="Test",
            project_type="fiction",
        )
        
        assert is_lens_compatible(lens, schema) is True
        assert is_lens_compatible(lens, None) is True

    def test_domain_lens_compatible(self) -> None:
        """Test domain-specific lens compatibility."""
        lens = Lens(
            metadata=LensMetadata(
                name="Fiction Editor",
                compatible_schemas=("fiction", "screenplay"),
            )
        )
        
        fiction_schema = ProjectSchema(name="Novel", project_type="fiction")
        research_schema = ProjectSchema(name="Paper", project_type="research")
        
        assert is_lens_compatible(lens, fiction_schema) is True
        assert is_lens_compatible(lens, research_schema) is False

    def test_compatibility_error_message(self) -> None:
        """Test error message generation."""
        lens = Lens(
            metadata=LensMetadata(
                name="Fiction Editor",
                compatible_schemas=("fiction",),
            )
        )
        
        schema = ProjectSchema(name="Paper", project_type="research")
        
        error = get_compatibility_error(lens, schema)
        
        assert error is not None
        assert "Fiction Editor" in error
        assert "research" in error
        assert "fiction" in error


# =============================================================================
# Schema Validator Tests
# =============================================================================


class TestSchemaValidator:
    """Tests for SchemaValidator in lenses."""

    def test_schema_validator_to_prompt(self) -> None:
        """Test generating validation prompt from SchemaValidator."""
        validator = SchemaValidator(
            name="character_arc",
            check="Character must have a clear arc",
            applies_to="character",
            severity=Severity.WARNING,
        )
        
        artifact = {"id": "john", "name": "John", "arc": "growth"}
        prompt = validator.to_prompt(artifact)
        
        assert "Character must have a clear arc" in prompt
        assert "john" in prompt
        assert "PASS or FAIL" in prompt

    def test_lens_with_schema_validators(self) -> None:
        """Test creating lens with schema validators."""
        lens = Lens(
            metadata=LensMetadata(
                name="Developmental Editor",
                compatible_schemas=("fiction",),
            ),
            schema_validators=(
                SchemaValidator(
                    name="character_arc",
                    check="Every major character must show growth",
                    applies_to="character",
                    condition="character.role == 'major'",
                ),
            ),
        )
        
        assert len(lens.schema_validators) == 1
        assert lens.schema_validators[0].applies_to == "character"


# =============================================================================
# Integration Tests
# =============================================================================


class TestSchemaIntegration:
    """Integration tests for the full schema workflow."""

    def test_fiction_workflow(self, tmp_path: Path) -> None:
        """Test complete fiction project workflow."""
        # Setup project structure
        schema_dir = tmp_path / ".sunwell"
        schema_dir.mkdir()
        
        (schema_dir / "schema.yaml").write_text("""
project:
  name: "Test Novel"
  type: fiction
  version: "1.0.0"

artifact_types:
  character:
    description: "A person in the story"
    fields:
      required: [name, traits]
    produces: "Character_{id}"
    is_contract: true
    
  scene:
    description: "A narrative scene"
    fields:
      required: [pov, location]
    requires:
      - "Character_{pov}"
    produces: "Scene_{id}"

validators:
  - name: character_has_traits
    description: "All characters must have traits"
    rule: |
      FOR char IN artifacts.characters
      ASSERT char.traits != None
    severity: error
    method: constraint

planning:
  default_strategy: contract_first
  phases:
    - name: worldbuilding
      artifact_types: [character]
      parallel: true
      maps_to: contracts
    - name: drafting
      artifact_types: [scene]
      parallel: false
      maps_to: implementations
""")
        
        # Create artifacts
        characters_dir = tmp_path / "artifacts" / "characters"
        characters_dir.mkdir(parents=True)
        
        (characters_dir / "john.yaml").write_text("""
type: character
id: john
name: "John"
traits: ["brave", "stubborn"]
""")
        
        (characters_dir / "mary.yaml").write_text("""
type: character
id: mary
name: "Mary"
traits: ["clever", "kind"]
""")
        
        scenes_dir = tmp_path / "artifacts" / "scenes"
        scenes_dir.mkdir(parents=True)
        
        (scenes_dir / "ch01.yaml").write_text("""
type: scene
id: ch01
pov: john
location: london
""")
        
        # Load and validate
        schema = ProjectSchema.load(tmp_path)
        loader = ArtifactLoader(schema)
        artifacts = loader.load_all_artifacts(tmp_path)
        
        assert len(artifacts["character"]) == 2
        assert len(artifacts["scene"]) == 1
        
        # Run validators
        validator = ConstraintValidator()
        for v in schema.validators:
            violations = validator.validate(
                v.rule,
                artifacts,
                rule_name=v.name,
            )
            # Should pass - all characters have traits
            assert len(violations) == 0
        
        # Resolve to tasks
        resolver = SchemaResolver(schema)
        tasks = resolver.resolve_all_artifacts(tmp_path / "artifacts")
        tasks = resolver.build_task_graph(tasks)
        
        # Verify task graph
        assert len(tasks) == 3
        
        # Find scene task
        scene_task = next(t for t in tasks if t.id == "ch01")
        assert "Character_john" in scene_task.requires
        # Should have john as dependency
        assert "john" in scene_task.depends_on
