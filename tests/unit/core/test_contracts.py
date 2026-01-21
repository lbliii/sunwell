"""API contract tests for core types using Hypothesis.

These tests ensure that API contracts are maintained - if the API changes,
these tests will fail, catching breaking changes automatically.
"""

import pytest
from hypothesis import given, strategies as st

from sunwell.core.types import (
    Confidence,
    LensReference,
    SemanticVersion,
    ValidationExecutionError,
    ModelError,
)
from sunwell.experiments.compound.types import (
    RegionStability,
    TemporalFrame,
)


class TestSemanticVersionContract:
    """Test SemanticVersion API contract."""

    @given(
        major=st.integers(min_value=0),
        minor=st.integers(min_value=0),
        patch=st.integers(min_value=0),
        prerelease=st.one_of(st.none(), st.text()),
    )
    def test_semantic_version_creation(
        self, major: int, minor: int, patch: int, prerelease: str | None
    ) -> None:
        """SemanticVersion accepts any valid parameters."""
        version = SemanticVersion(
            major=major,
            minor=minor,
            patch=patch,
            prerelease=prerelease,
        )
        assert version.major == major
        assert version.minor == minor
        assert version.patch == patch
        assert version.prerelease == prerelease

    @given(version_str=st.text())
    def test_semantic_version_parse(self, version_str: str) -> None:
        """SemanticVersion.parse handles any string (may raise ValueError)."""
        try:
            version = SemanticVersion.parse(version_str)
            # If parsing succeeds, verify it's valid
            assert isinstance(version, SemanticVersion)
            assert version.major >= 0
            assert version.minor >= 0
            assert version.patch >= 0
        except ValueError:
            # Invalid format is expected for random strings
            pass

    @given(
        v1=st.builds(
            SemanticVersion,
            major=st.integers(min_value=0),
            minor=st.integers(min_value=0),
            patch=st.integers(min_value=0),
        ),
        v2=st.builds(
            SemanticVersion,
            major=st.integers(min_value=0),
            minor=st.integers(min_value=0),
            patch=st.integers(min_value=0),
        ),
    )
    def test_semantic_version_comparison(self, v1: SemanticVersion, v2: SemanticVersion) -> None:
        """SemanticVersion comparison operators work correctly."""
        # Comparison should be transitive
        if v1 < v2:
            assert not (v2 < v1)
        if v1 <= v2:
            assert not (v2 < v1) or v1 == v2


class TestLensReferenceContract:
    """Test LensReference API contract."""

    @given(
        source=st.text(),
        version=st.one_of(st.none(), st.text()),
        priority=st.integers(),
    )
    def test_lens_reference_creation(
        self, source: str, version: str | None, priority: int
    ) -> None:
        """LensReference accepts any valid parameters."""
        ref = LensReference(source=source, version=version, priority=priority)
        assert ref.source == source
        assert ref.version == version
        assert ref.priority == priority
        # Properties should work
        assert isinstance(ref.is_local, bool)
        assert isinstance(ref.is_fount, bool)


class TestConfidenceContract:
    """Test Confidence API contract."""

    @given(
        score=st.floats(min_value=0.0, max_value=1.0),
        explanation=st.one_of(st.none(), st.text()),
    )
    def test_confidence_creation(self, score: float, explanation: str | None) -> None:
        """Confidence accepts valid score and explanation."""
        conf = Confidence(score=score, explanation=explanation)
        assert conf.score == score
        assert conf.explanation == explanation
        # Level property should work
        assert isinstance(conf.level, str)
        assert len(conf.level) > 0

    @given(score=st.one_of(st.floats(max_value=-0.1), st.floats(min_value=1.1)))
    def test_confidence_invalid_score(self, score: float) -> None:
        """Confidence rejects invalid scores."""
        with pytest.raises(ValueError, match="Confidence score must be between 0 and 1"):
            Confidence(score=score)


class TestTemporalFrameContract:
    """Test TemporalFrame API contract."""

    @given(
        frame_id=st.integers(min_value=0),
        content_hash=st.text(min_size=1),
        content=st.text(),
    )
    def test_temporal_frame_creation(
        self, frame_id: int, content_hash: str, content: str
    ) -> None:
        """TemporalFrame accepts any valid parameters."""
        frame = TemporalFrame(
            frame_id=frame_id,
            content_hash=content_hash,
            content=content,
        )
        assert frame.frame_id == frame_id
        assert frame.content_hash == content_hash
        assert frame.content == content


class TestRegionStabilityContract:
    """Test RegionStability API contract."""

    @given(
        index=st.integers(min_value=0),
        region_text=st.text(),
        frame_hashes=st.lists(st.text(min_size=1), min_size=1),
        stability_score=st.floats(min_value=0.0, max_value=1.0),
        is_stable=st.booleans(),
    )
    def test_region_stability_creation(
        self,
        index: int,
        region_text: str,
        frame_hashes: list[str],
        stability_score: float,
        is_stable: bool,
    ) -> None:
        """RegionStability accepts any valid parameters."""
        region = RegionStability(
            index=index,
            region_text=region_text,
            frame_hashes=tuple(frame_hashes),
            stability_score=stability_score,
            is_stable=is_stable,
        )
        assert region.index == index
        assert region.region_text == region_text
        assert region.frame_hashes == tuple(frame_hashes)
        assert region.stability_score == stability_score
        assert region.is_stable == is_stable


class TestValidationExecutionErrorContract:
    """Test ValidationExecutionError API contract."""

    @given(
        validator_name=st.text(),
        error_type=st.sampled_from(["script_failed", "timeout", "invalid_output", "sandbox_violation"]),
        message=st.text(),
        exit_code=st.one_of(st.none(), st.integers()),
        stderr=st.one_of(st.none(), st.text()),
        recoverable=st.booleans(),
    )
    def test_validation_execution_error_creation(
        self,
        validator_name: str,
        error_type: str,
        message: str,
        exit_code: int | None,
        stderr: str | None,
        recoverable: bool,
    ) -> None:
        """ValidationExecutionError accepts any valid parameters."""
        error = ValidationExecutionError(
            validator_name=validator_name,
            error_type=error_type,  # type: ignore[arg-type]
            message=message,
            exit_code=exit_code,
            stderr=stderr,
            recoverable=recoverable,
        )
        assert error.validator_name == validator_name
        assert error.error_type == error_type
        assert error.message == message
        assert error.exit_code == exit_code
        assert error.stderr == stderr
        assert error.recoverable == recoverable


class TestModelErrorContract:
    """Test ModelError API contract."""

    @given(
        provider=st.text(),
        error_type=st.sampled_from(
            ["rate_limit", "auth_failed", "context_exceeded", "timeout", "api_error"]
        ),
        message=st.text(),
        retry_after=st.one_of(st.none(), st.floats(min_value=0.0)),
        recoverable=st.booleans(),
    )
    def test_model_error_creation(
        self,
        provider: str,
        error_type: str,
        message: str,
        retry_after: float | None,
        recoverable: bool,
    ) -> None:
        """ModelError accepts any valid parameters."""
        error = ModelError(
            provider=provider,
            error_type=error_type,  # type: ignore[arg-type]
            message=message,
            retry_after=retry_after,
            recoverable=recoverable,
        )
        assert error.provider == provider
        assert error.error_type == error_type
        assert error.message == message
        assert error.retry_after == retry_after
        assert error.recoverable == recoverable
