"""Unit tests for RFC-135 Artifact Validation.

Tests for:
- Artifact validation (meta-artifacts, boundary checks)
- Schema-based validation

Note: Intent classification tests moved to tests/unit/agent/intent/test_dag.py
"""

import pytest

from sunwell.planning.naaru.artifacts import ArtifactSpec
from sunwell.planning.naaru.planners.artifact.parsing import (
    validate_artifact,
    validate_artifact_path,
    _is_meta_artifact,
)


# =============================================================================
# Artifact Validation Tests
# =============================================================================


class TestArtifactValidation:
    """Tests for artifact validation."""

    def test_meta_artifact_learning(self):
        """Meta-artifact with 'learning' in name should be detected."""
        assert _is_meta_artifact("KeyLearnings", None)
        assert _is_meta_artifact("learning_summary", None)
        assert _is_meta_artifact("normal_id", "key_learnings.md")

    def test_meta_artifact_reflection(self):
        """Meta-artifact with 'reflection' should be detected."""
        assert _is_meta_artifact("PersonalReflection", None)
        assert _is_meta_artifact("normal", "personal_reflection.md")

    def test_meta_artifact_summary(self):
        """Meta-artifact with 'summary' should be detected."""
        assert _is_meta_artifact("Summary", None)
        assert _is_meta_artifact("TaskSummary", None)

    def test_meta_artifact_generated_code(self):
        """Meta-artifact 'generated_code.py' should be detected."""
        assert _is_meta_artifact("normal", "generated_code.py")
        # Note: "GeneratedCode" matches "generated_code" pattern (both lowercase)
        assert _is_meta_artifact("generated_code_output", None)

    def test_valid_artifact_not_meta(self):
        """Normal artifacts should not be detected as meta."""
        assert not _is_meta_artifact("UserModel", "src/models/user.py")
        assert not _is_meta_artifact("AuthService", "src/services/auth.py")
        assert not _is_meta_artifact("Pipeline", "src/pipeline.py")


class TestValidateArtifact:
    """Tests for validate_artifact function."""

    def test_valid_artifact_passes(self):
        """Valid artifacts should pass validation."""
        artifact = ArtifactSpec(
            id="UserModel",
            description="User model",
            contract="User entity",
            produces_file="src/models/user.py",
        )
        is_valid, reason = validate_artifact(artifact)
        assert is_valid
        assert reason is None

    def test_sunwell_path_rejected(self):
        """Artifacts writing to .sunwell/ should be rejected."""
        artifact = ArtifactSpec(
            id="Config",
            description="Config",
            contract="Config",
            produces_file=".sunwell/config.yaml",
        )
        is_valid, reason = validate_artifact(artifact)
        assert not is_valid
        assert ".sunwell/" in reason

    def test_git_path_rejected(self):
        """Artifacts writing to .git/ should be rejected."""
        artifact = ArtifactSpec(
            id="Hook",
            description="Hook",
            contract="Hook",
            produces_file=".git/hooks/pre-commit",
        )
        is_valid, reason = validate_artifact(artifact)
        assert not is_valid
        assert ".git/" in reason

    def test_pycache_path_rejected(self):
        """Artifacts writing to __pycache__/ should be rejected."""
        artifact = ArtifactSpec(
            id="Cache",
            description="Cache",
            contract="Cache",
            produces_file="__pycache__/file.pyc",
        )
        is_valid, reason = validate_artifact(artifact)
        assert not is_valid

    def test_meta_artifact_rejected(self):
        """Meta-artifacts should be rejected."""
        artifact = ArtifactSpec(
            id="KeyLearnings",
            description="Learnings from task",
            contract="Learnings",
            produces_file="key_learnings.md",
        )
        is_valid, reason = validate_artifact(artifact)
        assert not is_valid
        assert "Meta-artifacts" in reason


class TestValidateArtifactPath:
    """Tests for validate_artifact_path function."""

    def test_valid_path(self):
        """Normal paths should be valid."""
        is_valid, reason = validate_artifact_path("src/models/user.py")
        assert is_valid
        assert reason is None

    def test_sunwell_path_invalid(self):
        """Paths starting with .sunwell/ should be invalid."""
        is_valid, reason = validate_artifact_path(".sunwell/intelligence/x.json")
        assert not is_valid

    def test_node_modules_invalid(self):
        """Paths in node_modules/ should be invalid."""
        is_valid, reason = validate_artifact_path("node_modules/package/index.js")
        assert not is_valid

    def test_venv_invalid(self):
        """Paths in .venv/ should be invalid."""
        is_valid, reason = validate_artifact_path(".venv/lib/python/site.py")
        assert not is_valid


# =============================================================================
# Schema Validation Tests
# =============================================================================


class TestSchemaValidation:
    """Tests for schema-based validation."""

    @pytest.fixture
    def mock_schema(self):
        """Create a mock ProjectSchema."""
        from sunwell.knowledge.project.schema import (
            ProjectSchema,
            ArtifactType,
            ArtifactField,
        )

        return ProjectSchema(
            name="test",
            project_type="python",
            artifact_types={
                "model": ArtifactType(
                    name="model",
                    description="Data model",
                    fields=ArtifactField(),
                    produces_pattern="{name}_model.py",
                ),
                "service": ArtifactType(
                    name="service",
                    description="Service",
                    fields=ArtifactField(),
                    produces_pattern="{name}_service.py",
                ),
            },
        )

    def test_valid_type_passes(self, mock_schema):
        """Artifacts with valid domain_type should pass."""
        artifact = ArtifactSpec(
            id="UserModel",
            description="User model",
            contract="User",
            domain_type="model",
        )
        is_valid, reason = validate_artifact(artifact, schema=mock_schema)
        assert is_valid

    def test_invalid_type_rejected(self, mock_schema):
        """Artifacts with invalid domain_type should be rejected."""
        artifact = ArtifactSpec(
            id="UserWidget",
            description="User widget",
            contract="Widget",
            domain_type="widget",  # Not in schema
        )
        is_valid, reason = validate_artifact(artifact, schema=mock_schema)
        assert not is_valid
        assert "widget" in reason
        assert "model" in reason or "service" in reason  # Shows valid types

    def test_no_type_passes(self, mock_schema):
        """Artifacts without domain_type should pass."""
        artifact = ArtifactSpec(
            id="Helper",
            description="Helper",
            contract="Helper",
            domain_type=None,
        )
        is_valid, reason = validate_artifact(artifact, schema=mock_schema)
        assert is_valid
