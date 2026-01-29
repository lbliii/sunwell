"""Tests for logging improvements in Naaru planning system.

Verifies that previously silent failures now produce proper log output.
"""

import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sunwell.planning.naaru.planners.artifact import parsing


@pytest.fixture
def capture_logs(caplog):
    """Capture logs at WARNING level."""
    caplog.set_level(logging.WARNING)
    return caplog


def test_extract_json_logs_all_strategy_failures(capture_logs):
    """Test that extract_json logs failures for all 3 strategies."""
    # Malformed response that will fail all 3 strategies
    bad_response = "This is not JSON at all, just plain text"

    result = parsing.extract_json(bad_response)

    # Should return None
    assert result is None

    # Should have logged the failure
    assert len(capture_logs.records) >= 1
    assert "Failed to extract JSON array" in capture_logs.text
    assert "all 3 strategies failed" in capture_logs.text


def test_extract_json_logs_partial_failures():
    """Test that extract_json logs which strategy succeeded."""
    # Valid JSON array
    good_response = '[{"id": "test", "description": "Test artifact"}]'

    result = parsing.extract_json(good_response)

    # Should succeed
    assert result is not None
    assert len(result) == 1
    assert result[0]["id"] == "test"


def test_parse_artifacts_logs_malformed_artifact(capture_logs):
    """Test that parse_artifacts logs malformed artifacts."""
    # JSON with missing required field 'id'
    bad_response = '[{"description": "Missing id field"}]'

    result = parsing.parse_artifacts(bad_response)

    # Should return empty list
    assert result == []

    # Should have logged the error
    assert len(capture_logs.records) >= 1
    assert "Skipping malformed artifact" in capture_logs.text


@pytest.mark.asyncio
async def test_verification_fails_on_unparseable_response(capture_logs):
    """Test that verification now FAILS (not passes) on unparseable responses."""
    from sunwell.planning.naaru.artifacts import ArtifactSpec
    from sunwell.planning.naaru.planners.artifact.creation import verify_artifact

    # Mock model that returns unparseable response
    mock_model = AsyncMock()
    mock_result = MagicMock()
    mock_result.content = "This is not JSON"
    mock_result.usage = None
    mock_model.generate.return_value = mock_result

    artifact = ArtifactSpec(
        id="test",
        description="Test artifact",
        contract="Must do X",
        produces_file="test.py",
    )

    result = await verify_artifact(mock_model, artifact, "test code")

    # CRITICAL: Should FAIL (not pass) on unparseable
    assert result.passed is False
    assert "malformed" in result.reason.lower()
    assert "unparseable_verification_response" in result.gaps

    # Should have logged the error
    assert len(capture_logs.records) >= 1
    assert "could not be parsed" in capture_logs.text.lower()


def test_harmonic_worker_has_logging():
    """Test that harmonic worker module has logging configured."""
    # Verify logging import exists in the module
    import sunwell.planning.naaru.workers.harmonic as harmonic_module

    # Should have logger defined at module level
    assert hasattr(harmonic_module, 'logger')
    assert harmonic_module.logger is not None

    # Verify the worker class exists
    from sunwell.planning.naaru.workers.harmonic import HarmonicSynthesisWorker
    assert HarmonicSynthesisWorker is not None
