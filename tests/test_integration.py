"""Tests for Integration-Aware DAG (RFC-067)."""

import tempfile
from pathlib import Path

import pytest

from sunwell.features.external.integration.decomposer import (
    ArtifactDefinition,
    IntegrationAwareGoal,
    IntegrationCheck,
    IntegrationCheckType,
    IntegrationType,
    ProducedArtifact,
    RequiredIntegration,
    TaskType,
    create_wire_task,
    decompose_with_wiring,
)
from sunwell.features.external.integration.verifier import IntegrationVerifier

# =============================================================================
# Type Tests
# =============================================================================


class TestProducedArtifact:
    """Tests for ProducedArtifact type."""

    def test_create_artifact(self) -> None:
        """Test basic artifact creation."""
        artifact = ProducedArtifact(
            id="UserModel",
            artifact_type="class",
            location="src/models/user.py:User",
            contract="Dataclass with id, email, password_hash",
            exports=frozenset(["User", "UserCreate"]),
        )

        assert artifact.id == "UserModel"
        assert artifact.artifact_type == "class"
        assert "User" in artifact.exports

    def test_artifact_serialization(self) -> None:
        """Test artifact to_dict/from_dict roundtrip."""
        artifact = ProducedArtifact(
            id="UserModel",
            artifact_type="class",
            location="src/models/user.py:User",
            contract="User dataclass",
            exports=frozenset(["User"]),
        )

        data = artifact.to_dict()
        restored = ProducedArtifact.from_dict(data)

        assert restored.id == artifact.id
        assert restored.exports == artifact.exports


class TestRequiredIntegration:
    """Tests for RequiredIntegration type."""

    def test_create_integration(self) -> None:
        """Test basic integration creation."""
        integration = RequiredIntegration(
            artifact_id="UserModel",
            integration_type=IntegrationType.IMPORT,
            contract="User dataclass",
            target_file=Path("src/auth/service.py"),
            verification_pattern="from src.models.user import User",
        )

        assert integration.artifact_id == "UserModel"
        assert integration.integration_type == IntegrationType.IMPORT

    def test_integration_serialization(self) -> None:
        """Test integration to_dict/from_dict roundtrip."""
        integration = RequiredIntegration(
            artifact_id="UserModel",
            integration_type=IntegrationType.CALL,
            contract="User.validate()",
            target_file=Path("src/auth/service.py"),
        )

        data = integration.to_dict()
        restored = RequiredIntegration.from_dict(data)

        assert restored.artifact_id == integration.artifact_id
        assert restored.integration_type == integration.integration_type


class TestIntegrationCheck:
    """Tests for IntegrationCheck type."""

    def test_create_check(self) -> None:
        """Test basic check creation."""
        check = IntegrationCheck(
            check_type=IntegrationCheckType.IMPORT_EXISTS,
            target_file=Path("src/auth/service.py"),
            pattern="from src.models.user import User",
            required=True,
        )

        assert check.check_type == IntegrationCheckType.IMPORT_EXISTS
        assert check.required is True


# =============================================================================
# Verifier Tests
# =============================================================================


class TestIntegrationVerifier:
    """Tests for IntegrationVerifier."""

    @pytest.fixture
    def temp_project(self) -> Path:
        """Create a temporary project directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)

            # Create src/models/user.py
            models_dir = project / "src" / "models"
            models_dir.mkdir(parents=True)
            (models_dir / "__init__.py").write_text("")
            (models_dir / "user.py").write_text('''
from dataclasses import dataclass

@dataclass
class User:
    id: str
    email: str
    password_hash: str
''')

            # Create src/auth/service.py that imports User
            auth_dir = project / "src" / "auth"
            auth_dir.mkdir(parents=True)
            (auth_dir / "__init__.py").write_text("")
            (auth_dir / "service.py").write_text('''
from src.models.user import User

class AuthService:
    def authenticate(self, user: User) -> bool:
        return True
''')

            # Create src/utils/orphan.py (not imported anywhere)
            utils_dir = project / "src" / "utils"
            utils_dir.mkdir(parents=True)
            (utils_dir / "__init__.py").write_text("")
            (utils_dir / "orphan.py").write_text('''
class OrphanedClass:
    """This class is never imported anywhere."""
    pass
''')

            # Create src/stubs.py with stub implementations
            (project / "src" / "stubs.py").write_text('''
def implemented_function():
    return "I work!"

def stub_pass():
    pass

def stub_not_implemented():
    raise NotImplementedError

def stub_ellipsis():
    ...

# TODO: Implement this function
def todo_function():
    return None
''')

            yield project

    @pytest.mark.asyncio
    async def test_check_import_exists_found(self, temp_project: Path) -> None:
        """Test import check finds existing import."""
        verifier = IntegrationVerifier(project_root=temp_project)

        check = IntegrationCheck(
            check_type=IntegrationCheckType.IMPORT_EXISTS,
            target_file=temp_project / "src" / "auth" / "service.py",
            pattern="User",
            required=True,
        )

        result = await verifier.run_check(check)
        assert result.passed is True
        assert "User" in (result.found or "")

    @pytest.mark.asyncio
    async def test_check_import_exists_not_found(self, temp_project: Path) -> None:
        """Test import check fails for missing import."""
        verifier = IntegrationVerifier(project_root=temp_project)

        check = IntegrationCheck(
            check_type=IntegrationCheckType.IMPORT_EXISTS,
            target_file=temp_project / "src" / "models" / "user.py",
            pattern="NonExistent",
            required=True,
        )

        result = await verifier.run_check(check)
        assert result.passed is False
        assert len(result.suggestions) > 0

    @pytest.mark.asyncio
    async def test_detect_stubs(self, temp_project: Path) -> None:
        """Test stub detection finds various stub types."""
        verifier = IntegrationVerifier(project_root=temp_project)

        stubs = await verifier.detect_stubs(temp_project / "src" / "stubs.py")

        # Should find pass, NotImplementedError, ellipsis, and TODO
        stub_types = {s.stub_type for s in stubs}
        assert "pass" in stub_types
        assert "not_implemented" in stub_types
        assert "ellipsis" in stub_types
        assert "todo" in stub_types

        # Should not flag implemented_function
        stub_symbols = {s.symbol for s in stubs}
        assert "implemented_function" not in stub_symbols

    @pytest.mark.asyncio
    async def test_detect_orphans(self, temp_project: Path) -> None:
        """Test orphan detection finds unused artifacts."""
        verifier = IntegrationVerifier(project_root=temp_project)

        # User is imported in auth/service.py - not an orphan
        user_artifact = ProducedArtifact(
            id="User",
            artifact_type="class",
            location="src/models/user.py:User",
            contract="User dataclass",
            exports=frozenset(["User"]),
        )

        # OrphanedClass is never imported - is an orphan
        orphan_artifact = ProducedArtifact(
            id="OrphanedClass",
            artifact_type="class",
            location="src/utils/orphan.py:OrphanedClass",
            contract="Orphaned class",
            exports=frozenset(["OrphanedClass"]),
        )

        orphans = await verifier.detect_orphans([user_artifact, orphan_artifact])

        orphan_ids = {o.artifact.id for o in orphans}
        assert "OrphanedClass" in orphan_ids
        assert "User" not in orphan_ids

    @pytest.mark.asyncio
    async def test_verify_goal(self, temp_project: Path) -> None:
        """Test full goal verification."""
        verifier = IntegrationVerifier(project_root=temp_project)

        checks = [
            IntegrationCheck(
                check_type=IntegrationCheckType.IMPORT_EXISTS,
                target_file=temp_project / "src" / "auth" / "service.py",
                pattern="User",
                required=True,
            ),
            IntegrationCheck(
                check_type=IntegrationCheckType.NO_STUBS,
                target_file=temp_project / "src" / "models" / "user.py",
                pattern="User",
                required=True,
            ),
        ]

        summary = await verifier.verify_goal("test-goal", checks)

        assert summary.goal_id == "test-goal"
        assert summary.total_checks == 2
        assert summary.passed_checks == 2
        assert summary.overall_passed is True


# =============================================================================
# Decomposition Tests
# =============================================================================


class TestDecomposeWithWiring:
    """Tests for decompose_with_wiring function."""

    def test_generates_create_tasks(self) -> None:
        """Test that create tasks are generated for each artifact."""
        artifacts = [
            ArtifactDefinition(
                id="UserModel",
                description="User dataclass",
                artifact_type="class",
                file_path="src/models/user.py",
                exports=["User"],
                depends_on=[],
            ),
            ArtifactDefinition(
                id="AuthService",
                description="Authentication service",
                artifact_type="class",
                file_path="src/auth/service.py",
                exports=["AuthService"],
                depends_on=[],
            ),
        ]

        tasks = decompose_with_wiring("auth", "Add auth", artifacts)

        create_tasks = [t for t in tasks if t.task_type == TaskType.CREATE]
        assert len(create_tasks) == 2

    def test_generates_wire_tasks(self) -> None:
        """Test that wire tasks are generated for dependencies."""
        artifacts = [
            ArtifactDefinition(
                id="UserModel",
                description="User dataclass",
                artifact_type="class",
                file_path="src/models/user.py",
                exports=["User"],
                depends_on=[],
            ),
            ArtifactDefinition(
                id="AuthService",
                description="Authentication service",
                artifact_type="class",
                file_path="src/auth/service.py",
                exports=["AuthService"],
                depends_on=["UserModel"],  # Depends on UserModel
            ),
        ]

        tasks = decompose_with_wiring("auth", "Add auth", artifacts)

        wire_tasks = [t for t in tasks if t.task_type == TaskType.WIRE]
        assert len(wire_tasks) == 1
        assert "UserModel" in wire_tasks[0].title

    def test_generates_verify_task(self) -> None:
        """Test that a verify task is generated at the end."""
        artifacts = [
            ArtifactDefinition(
                id="UserModel",
                description="User dataclass",
                artifact_type="class",
                file_path="src/models/user.py",
                exports=["User"],
                depends_on=[],
            ),
        ]

        tasks = decompose_with_wiring("auth", "Add auth", artifacts)

        verify_tasks = [t for t in tasks if t.task_type == TaskType.VERIFY]
        assert len(verify_tasks) == 1
        assert verify_tasks[0].id == "auth-verify"

    def test_wire_task_has_verification_checks(self) -> None:
        """Test that wire tasks include verification checks."""
        source = ArtifactDefinition(
            id="AuthService",
            description="Auth service",
            artifact_type="class",
            file_path="src/auth/service.py",
            exports=["AuthService"],
            depends_on=["UserModel"],
        )
        target = ArtifactDefinition(
            id="UserModel",
            description="User model",
            artifact_type="class",
            file_path="src/models/user.py",
            exports=["User"],
            depends_on=[],
        )

        wire_task = create_wire_task("wire-1", source, target)

        assert len(wire_task.verification_checks) > 0
        assert wire_task.verification_checks[0].check_type in (
            IntegrationCheckType.IMPORT_EXISTS,
            IntegrationCheckType.CALL_EXISTS,
        )


class TestIntegrationAwareGoal:
    """Tests for IntegrationAwareGoal type."""

    def test_create_goal(self) -> None:
        """Test basic goal creation."""
        goal = IntegrationAwareGoal(
            id="auth-1",
            title="Create User model",
            description="Create User dataclass",
            task_type=TaskType.CREATE,
            produces=(
                ProducedArtifact(
                    id="UserModel",
                    artifact_type="class",
                    location="src/models/user.py:User",
                    contract="User dataclass",
                    exports=frozenset(["User"]),
                ),
            ),
        )

        assert goal.id == "auth-1"
        assert goal.task_type == TaskType.CREATE
        assert len(goal.produces) == 1

    def test_is_wire_task(self) -> None:
        """Test is_wire_task method."""
        create_goal = IntegrationAwareGoal(
            id="create-1",
            title="Create",
            description="Create something",
            task_type=TaskType.CREATE,
        )
        wire_goal = IntegrationAwareGoal(
            id="wire-1",
            title="Wire",
            description="Wire something",
            task_type=TaskType.WIRE,
        )

        assert create_goal.is_wire_task() is False
        assert wire_goal.is_wire_task() is True

    def test_get_produced_symbols(self) -> None:
        """Test getting all produced symbols."""
        goal = IntegrationAwareGoal(
            id="auth-1",
            title="Create models",
            description="Create models",
            produces=(
                ProducedArtifact(
                    id="UserModel",
                    artifact_type="class",
                    location="src/models/user.py:User",
                    contract="User",
                    exports=frozenset(["User", "UserCreate"]),
                ),
            ),
        )

        symbols = goal.get_produced_symbols()
        assert "User" in symbols
        assert "UserCreate" in symbols
        assert "UserModel" in symbols

    def test_serialization(self) -> None:
        """Test goal to_dict/from_dict roundtrip."""
        goal = IntegrationAwareGoal(
            id="auth-1",
            title="Create User model",
            description="Create User dataclass",
            task_type=TaskType.CREATE,
            produces=(
                ProducedArtifact(
                    id="UserModel",
                    artifact_type="class",
                    location="src/models/user.py:User",
                    contract="User dataclass",
                    exports=frozenset(["User"]),
                ),
            ),
            integrations=(
                RequiredIntegration(
                    artifact_id="BaseModel",
                    integration_type=IntegrationType.INHERIT,
                    contract="Base class",
                ),
            ),
        )

        data = goal.to_dict()
        restored = IntegrationAwareGoal.from_dict(data)

        assert restored.id == goal.id
        assert restored.task_type == goal.task_type
        assert len(restored.produces) == 1
        assert len(restored.integrations) == 1
