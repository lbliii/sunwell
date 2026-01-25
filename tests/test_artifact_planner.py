"""Tests for ArtifactPlanner functionality.

Tests cover:
- Artifact discovery
- Artifact creation (the create_artifact method)
- Verification
- Trivial goal handling

These tests catch regressions like the missing create_artifact method.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from sunwell.planning.naaru.artifacts import ArtifactGraph, ArtifactSpec
from sunwell.planning.naaru.planners.artifact import ArtifactPlanner


# =============================================================================
# Mock Model
# =============================================================================


class MockModel:
    """Mock model for testing without actual LLM calls."""

    def __init__(self, response: str = ""):
        self.response = response
        self.calls: list[str] = []

    async def generate(self, prompt: str, options=None):
        """Mock generate that records calls and returns preset response."""
        self.calls.append(prompt)

        class MockResult:
            def __init__(self, content: str):
                self.content = content
                self.text = content

        return MockResult(self.response)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_model() -> MockModel:
    """Create a mock model."""
    return MockModel()


@pytest.fixture
def sample_artifact() -> ArtifactSpec:
    """Create a sample artifact for testing."""
    return ArtifactSpec(
        id="UserProtocol",
        description="Protocol defining User entity",
        contract="Protocol with fields: id, email, password_hash, created_at",
        produces_file="src/protocols/user.py",
        domain_type="protocol",
        requires=frozenset(),
    )


# =============================================================================
# Test: ArtifactPlanner Creation
# =============================================================================


def test_artifact_planner_creation(mock_model: MockModel) -> None:
    """ArtifactPlanner should be creatable with a model."""
    planner = ArtifactPlanner(model=mock_model)

    assert planner.model is mock_model
    assert planner.max_retries == 3


def test_artifact_planner_has_create_artifact_method(mock_model: MockModel) -> None:
    """ArtifactPlanner MUST have create_artifact method.

    This test catches the regression where create_artifact was called
    but never implemented.
    """
    planner = ArtifactPlanner(model=mock_model)

    # Method must exist
    assert hasattr(planner, "create_artifact")
    assert callable(planner.create_artifact)


# =============================================================================
# Test: create_artifact Method
# =============================================================================


@pytest.mark.asyncio
async def test_create_artifact_basic(sample_artifact: ArtifactSpec) -> None:
    """create_artifact should generate content from artifact spec."""
    expected_code = '''from typing import Protocol

class UserProtocol(Protocol):
    id: int
    email: str
    password_hash: str
    created_at: str
'''
    mock_model = MockModel(response=f"```python\n{expected_code}```")
    planner = ArtifactPlanner(model=mock_model)

    result = await planner.create_artifact(sample_artifact)

    # Should extract code from markdown block
    assert "class UserProtocol" in result
    assert "id: int" in result


@pytest.mark.asyncio
async def test_create_artifact_extracts_from_markdown() -> None:
    """create_artifact should extract code from markdown code blocks."""
    mock_model = MockModel(response="Here's the code:\n```python\ndef hello():\n    pass\n```")
    planner = ArtifactPlanner(model=mock_model)

    artifact = ArtifactSpec(
        id="Test",
        description="Test artifact",
        contract="Test contract",
        produces_file="test.py",
    )

    result = await planner.create_artifact(artifact)

    assert result == "def hello():\n    pass"


@pytest.mark.asyncio
async def test_create_artifact_handles_plain_code() -> None:
    """create_artifact should handle plain code without markdown."""
    plain_code = "import os\n\ndef main():\n    print('hello')"
    mock_model = MockModel(response=plain_code)
    planner = ArtifactPlanner(model=mock_model)

    artifact = ArtifactSpec(
        id="Test",
        description="Test",
        contract="Test",
        produces_file="test.py",
    )

    result = await planner.create_artifact(artifact)

    assert "import os" in result
    assert "def main():" in result


@pytest.mark.asyncio
async def test_create_artifact_prompt_includes_spec(sample_artifact: ArtifactSpec) -> None:
    """create_artifact prompt should include artifact specification."""
    mock_model = MockModel(response="```python\npass\n```")
    planner = ArtifactPlanner(model=mock_model)

    await planner.create_artifact(sample_artifact)

    # Check prompt includes key info
    prompt = mock_model.calls[0]
    assert "UserProtocol" in prompt
    assert "Protocol defining User entity" in prompt
    assert "Protocol with fields: id, email" in prompt
    assert "src/protocols/user.py" in prompt


@pytest.mark.asyncio
async def test_create_artifact_with_context() -> None:
    """create_artifact should include context in prompt."""
    mock_model = MockModel(response="```python\npass\n```")
    planner = ArtifactPlanner(model=mock_model)

    artifact = ArtifactSpec(
        id="UserModel",
        description="SQLAlchemy model",
        contract="Implements UserProtocol",
        produces_file="models/user.py",
        requires=frozenset(["UserProtocol"]),
    )

    context = {
        "completed": {
            "UserProtocol": {"description": "Protocol for User"},
        }
    }

    await planner.create_artifact(artifact, context)

    prompt = mock_model.calls[0]
    assert "COMPLETED DEPENDENCIES" in prompt
    assert "UserProtocol" in prompt


# =============================================================================
# Test: Code Extraction Edge Cases
# =============================================================================


@pytest.mark.asyncio
async def test_extract_code_unclosed_markdown() -> None:
    """Should handle unclosed markdown blocks."""
    # LLM sometimes doesn't close code blocks
    mock_model = MockModel(response="```python\ndef foo():\n    return 42")
    planner = ArtifactPlanner(model=mock_model)

    artifact = ArtifactSpec(id="Test", description="Test", contract="Test")
    result = await planner.create_artifact(artifact)

    assert "def foo():" in result


@pytest.mark.asyncio
async def test_extract_code_json_file() -> None:
    """Should handle JSON file generation."""
    json_content = '{"name": "test", "version": "1.0"}'
    mock_model = MockModel(response=f"```json\n{json_content}\n```")
    planner = ArtifactPlanner(model=mock_model)

    artifact = ArtifactSpec(
        id="Config",
        description="Config file",
        contract="JSON config",
        produces_file="config.json",
    )

    result = await planner.create_artifact(artifact)

    assert '"name": "test"' in result


# =============================================================================
# Test: Verify Artifact Method Exists
# =============================================================================


def test_verify_artifact_method_exists(mock_model: MockModel) -> None:
    """verify_artifact method should exist for contract verification."""
    planner = ArtifactPlanner(model=mock_model)

    assert hasattr(planner, "verify_artifact")
    assert callable(planner.verify_artifact)


# =============================================================================
# Test: Trivial Artifact Handling
# =============================================================================


def test_trivial_artifact_single_file() -> None:
    """Trivial goals should produce single-artifact graphs."""
    mock_model = MockModel()
    planner = ArtifactPlanner(model=mock_model)

    # The _trivial_artifact method should extract filename from goal
    graph = planner._trivial_artifact("Create hello.py that prints Hello")

    assert len(graph) == 1
    artifact = graph["main"]
    assert artifact.produces_file == "hello.py"


def test_trivial_artifact_extracts_filename() -> None:
    """Trivial artifact should extract filename from goal."""
    mock_model = MockModel()
    planner = ArtifactPlanner(model=mock_model)

    graph = planner._trivial_artifact("Make a settings.yaml file")
    artifact = graph["main"]

    assert artifact.produces_file == "settings.yaml"
