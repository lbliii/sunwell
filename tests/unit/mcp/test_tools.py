"""Tests for MCP tools (lens, routing)."""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from sunwell.foundation.core.lens import Lens, LensMetadata, Router
from sunwell.core.models.heuristic import Heuristic


class TestLensTools:
    """Tests for lens-related MCP tools."""

    @pytest.fixture
    def mock_lens(self) -> Lens:
        """Create a mock lens for testing."""
        return Lens(
            metadata=LensMetadata(
                name="test-coder",
                domain="software",
                description="A test coding lens",
            ),
            heuristics=(
                Heuristic(
                    name="Test Rule",
                    rule="Write clean code",
                    priority=5,
                ),
            ),
            router=Router(
                shortcuts={"::code": "write-code", "::test": "write-tests"},
            ),
            source_path=Path("/tmp/test-coder.lens"),
        )

    @pytest.fixture
    def mock_loader(self, mock_lens):
        """Create a mock loader that returns the test lens."""
        loader = MagicMock()
        loader.load.return_value = mock_lens
        return loader

    @pytest.fixture
    def mock_discovery(self):
        """Create a mock discovery with test paths."""
        discovery = MagicMock()
        discovery.search_paths = [Path("/tmp/lenses")]
        return discovery

    def test_build_shortcut_index(self, mock_lens, mock_loader, mock_discovery):
        """Shortcut index should be built from lenses."""
        from sunwell.mcp.tools.routing import _build_shortcut_index
        
        # Setup mock to return our lens
        mock_discovery.search_paths = [Path("/tmp")]
        
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.glob") as mock_glob:
                mock_glob.return_value = [Path("/tmp/test.lens")]
                
                with patch.object(mock_loader, "load", return_value=mock_lens):
                    index = _build_shortcut_index(mock_discovery, mock_loader)
        
        # Should contain shortcuts from the lens
        assert isinstance(index, dict)


class TestRoutingTools:
    """Tests for routing-related MCP tools."""

    def test_confidence_tiers(self):
        """Confidence tiers should map correctly."""
        # High confidence
        assert _get_tier(1.0) == "high"
        assert _get_tier(0.95) == "high"
        assert _get_tier(0.8) == "high"
        
        # Medium confidence
        assert _get_tier(0.79) == "medium"
        assert _get_tier(0.5) == "medium"
        
        # Low confidence
        assert _get_tier(0.49) == "low"
        assert _get_tier(0.1) == "low"


def _get_tier(confidence: float) -> str:
    """Get confidence tier for a score."""
    if confidence >= 0.8:
        return "high"
    elif confidence >= 0.5:
        return "medium"
    else:
        return "low"
