"""Pytest fixtures for Sunwell tests."""

from pathlib import Path

import pytest

from sunwell.core.lens import Lens, LensMetadata
from sunwell.core.heuristic import Heuristic, Example
from sunwell.core.persona import Persona
from sunwell.core.validator import HeuristicValidator
from sunwell.core.types import SemanticVersion, Severity, ValidationMethod
from sunwell.models.mock import MockModel
from sunwell.schema.loader import LensLoader


@pytest.fixture
def sample_heuristic() -> Heuristic:
    """Create a sample heuristic for testing."""
    return Heuristic(
        name="Test Heuristic",
        rule="Always test your code",
        test="Are there tests?",
        always=("Write unit tests", "Write integration tests"),
        never=("Skip tests", "Ignore failures"),
        examples=Example(
            good=("def test_something(): ...",),
            bad=("# TODO: add tests",),
        ),
        priority=5,
    )


@pytest.fixture
def sample_persona() -> Persona:
    """Create a sample persona for testing."""
    return Persona(
        name="test_user",
        description="A test user persona",
        background="Knows basics, learning advanced topics",
        goals=("Understand quickly", "Get working code"),
        friction_points=("Complex jargon", "Missing examples"),
        attack_vectors=("What does this mean?", "Show me an example"),
    )


@pytest.fixture
def sample_validator() -> HeuristicValidator:
    """Create a sample validator for testing."""
    return HeuristicValidator(
        name="test_validator",
        check="Content should be clear and concise",
        method=ValidationMethod.PATTERN_MATCH,
        confidence_threshold=0.8,
        severity=Severity.WARNING,
    )


@pytest.fixture
def sample_lens(
    sample_heuristic: Heuristic,
    sample_persona: Persona,
    sample_validator: HeuristicValidator,
) -> Lens:
    """Create a sample lens for testing."""
    return Lens(
        metadata=LensMetadata(
            name="Test Lens",
            domain="testing",
            version=SemanticVersion(1, 0, 0),
            description="A lens for testing",
        ),
        heuristics=(sample_heuristic,),
        personas=(sample_persona,),
        heuristic_validators=(sample_validator,),
    )


@pytest.fixture
def mock_model() -> MockModel:
    """Create a mock model for testing."""
    return MockModel(
        responses=[
            "This is a mock response.",
            "PASS|0.95|Content meets the criterion",
        ]
    )


@pytest.fixture
def lens_loader() -> LensLoader:
    """Create a lens loader for testing."""
    return LensLoader()


@pytest.fixture
def lenses_dir() -> Path:
    """Get the path to the lenses directory."""
    return Path(__file__).parent.parent / "lenses"


@pytest.fixture
def tech_writer_lens(lens_loader: LensLoader, lenses_dir: Path) -> Lens:
    """Load the tech-writer lens for testing."""
    return lens_loader.load(lenses_dir / "tech-writer.lens")
