"""Integration tests for Compound Eye experiments (RFC-042).

Tests the bio-inspired multi-model patterns:
- Lateral Inhibition: Edge detection via neighbor signal suppression
- Temporal Differencing: Uncertainty detection via multiple runs
- Attention Folding: Resolution of flickering regions
"""

from __future__ import annotations

import pytest
from dataclasses import dataclass

from sunwell.experiments.compound import (
    OmmatidiumSignal,
    LateralInhibitionResult,
    TemporalFrame,
    RegionStability,
    TemporalDiffResult,
    CompoundEyeResult,
    SignalStability,
    TemporalSignalResult,
    FoldStrategy,
    FoldedRegion,
    AttentionFoldResult,
    chunk_code_by_function,
    chunk_by_lines,
    render_lateral_map,
    render_temporal_map,
    render_compound_map,
    render_signal_stability_map,
    render_attention_fold_map,
)
from sunwell.experiments.compound.lateral import _apply_lateral_inhibition
from sunwell.experiments.compound.temporal import (
    _split_into_regions,
    _compute_region_similarity,
    _hash_content,
)


# =============================================================================
# Data Structure Tests
# =============================================================================


class TestOmmatidiumSignal:
    """Tests for OmmatidiumSignal data structure."""

    def test_signal_creation(self):
        signal = OmmatidiumSignal(
            index=0,
            region="test code",
            raw_signal=0.8,
            inhibited_signal=0.5,
            response="2",
        )
        assert signal.index == 0
        assert signal.region == "test code"
        assert signal.raw_signal == 0.8
        assert signal.inhibited_signal == 0.5
        assert signal.response == "2"

    def test_signal_is_frozen(self):
        signal = OmmatidiumSignal(
            index=0,
            region="test",
            raw_signal=0.5,
            inhibited_signal=0.3,
            response="1",
        )
        with pytest.raises(Exception):  # FrozenInstanceError
            signal.raw_signal = 0.9


class TestLateralInhibitionResult:
    """Tests for LateralInhibitionResult."""

    def test_result_creation(self):
        signals = (
            OmmatidiumSignal(0, "a", 0.5, 0.3, "1"),
            OmmatidiumSignal(1, "b", 0.9, 0.6, "2"),
            OmmatidiumSignal(2, "c", 0.1, 0.0, "0"),
        )
        result = LateralInhibitionResult(
            signals=signals,
            edge_indices=(1,),
            edge_threshold=0.3,
            total_regions=3,
            edges_found=1,
        )
        assert result.edges_found == 1
        assert result.total_regions == 3
        assert result.edge_ratio == pytest.approx(1 / 3)

    def test_get_edge_regions(self):
        signals = (
            OmmatidiumSignal(0, "safe code", 0.2, 0.1, "0"),
            OmmatidiumSignal(1, "dangerous code", 0.9, 0.7, "2"),
        )
        result = LateralInhibitionResult(
            signals=signals,
            edge_indices=(1,),
            edge_threshold=0.3,
            total_regions=2,
            edges_found=1,
        )
        assert result.get_edge_regions() == ["dangerous code"]

    def test_empty_result(self):
        result = LateralInhibitionResult(
            signals=(),
            edge_indices=(),
            edge_threshold=0.3,
            total_regions=0,
            edges_found=0,
        )
        assert result.edge_ratio == 0.0
        assert result.get_edge_regions() == []


class TestTemporalFrame:
    """Tests for TemporalFrame."""

    def test_frame_creation(self):
        frame = TemporalFrame(
            frame_id=0,
            content_hash="abc123",
            content="This is the output",
        )
        assert frame.frame_id == 0
        assert frame.content == "This is the output"
        assert frame.content_hash == "abc123"


class TestRegionStability:
    """Tests for RegionStability."""

    def test_stable_region(self):
        region = RegionStability(
            index=0,
            region_text="Consistent output",
            frame_hashes=("hash1", "hash1"),
            stability_score=0.95,
            is_stable=True,
        )
        assert region.is_stable
        assert region.stability_score == 0.95

    def test_unstable_region(self):
        region = RegionStability(
            index=1,
            region_text="Flickering output",
            frame_hashes=("hash1", "hash2", "hash3"),
            stability_score=0.3,
            is_stable=False,
        )
        assert not region.is_stable
        assert len(region.frame_hashes) == 3


class TestTemporalDiffResult:
    """Tests for TemporalDiffResult."""

    def test_result_creation(self):
        regions = (
            RegionStability(
                index=0,
                region_text="stable",
                frame_hashes=("hash1", "hash1"),
                stability_score=0.9,
                is_stable=True,
            ),
            RegionStability(
                index=1,
                region_text="unstable",
                frame_hashes=("hash1", "hash2", "hash3"),
                stability_score=0.3,
                is_stable=False,
            ),
        )
        result = TemporalDiffResult(
            frames=(),
            regions=regions,
            unstable_regions=(1,),
            overall_stability=0.6,
            n_frames=3,
            stability_threshold=0.85,
        )
        assert result.overall_stability == 0.6
        assert len(result.unstable_regions) == 1


class TestSignalStability:
    """Tests for SignalStability (trit-based)."""

    def test_unanimous_signals(self):
        stability = SignalStability(
            index=0,
            region="test",
            signals=(2, 2, 2),
            mode_signal=2,
            stability=1.0,
            is_stable=True,
        )
        assert stability.is_unanimous
        assert stability.spread == 0

    def test_mixed_signals(self):
        stability = SignalStability(
            index=1,
            region="test",
            signals=(0, 1, 2),
            mode_signal=1,
            stability=0.33,
            is_stable=False,
        )
        assert not stability.is_unanimous
        assert stability.spread == 2


class TestTemporalSignalResult:
    """Tests for TemporalSignalResult."""

    def test_result_creation(self):
        regions = (
            SignalStability(0, "a", (1, 1, 1), 1, 1.0, True),
            SignalStability(1, "b", (0, 1, 2), 1, 0.33, False),
        )
        result = TemporalSignalResult(
            regions=regions,
            n_frames=3,
            stable_indices=(0,),
            unstable_indices=(1,),
            overall_stability=0.665,
        )
        assert result.unanimous_count == 1
        assert result.high_spread_indices == (1,)


class TestCompoundEyeResult:
    """Tests for CompoundEyeResult."""

    def test_hotspots_detection(self):
        lateral = LateralInhibitionResult(
            signals=(),
            edge_indices=(1, 2),
            edge_threshold=0.3,
            total_regions=3,
            edges_found=2,
        )
        temporal = TemporalDiffResult(
            frames=(),
            regions=(),
            unstable_regions=(2,),
            overall_stability=0.5,
            n_frames=3,
            stability_threshold=0.85,
        )
        result = CompoundEyeResult(
            lateral=lateral,
            temporal=temporal,
            hotspots=(2,),  # Both edge AND unstable
        )
        assert len(result.hotspots) > 0
        assert 2 in result.hotspots


# =============================================================================
# Algorithm Tests
# =============================================================================


class TestLateralInhibition:
    """Tests for lateral inhibition algorithm."""

    def test_uniform_signal_suppression(self):
        """Uniform signals should be suppressed (no edges)."""
        raw = [0.5, 0.5, 0.5, 0.5, 0.5]
        inhibited = _apply_lateral_inhibition(raw, inhibition_strength=0.3)
        
        # All signals should be reduced by neighbor average
        for signal in inhibited:
            assert signal < 0.5  # Suppressed

    def test_edge_enhancement(self):
        """Edges (signal spikes) should be enhanced."""
        # Low, HIGH, low pattern
        raw = [0.1, 0.9, 0.1]
        inhibited = _apply_lateral_inhibition(raw, inhibition_strength=0.3)
        
        # Middle signal should remain high after inhibition
        assert inhibited[1] > inhibited[0]
        assert inhibited[1] > inhibited[2]

    def test_empty_input(self):
        """Empty input should return empty output."""
        assert _apply_lateral_inhibition([]) == []

    def test_single_element(self):
        """Single element should not change much."""
        raw = [0.5]
        inhibited = _apply_lateral_inhibition(raw, inhibition_strength=0.3)
        # With itself as neighbor, signal - 0.3*signal = 0.35
        assert len(inhibited) == 1
        assert inhibited[0] == pytest.approx(0.35)


class TestRegionSplitting:
    """Tests for text region splitting."""

    def test_split_by_sentence(self):
        text = "First sentence. Second sentence! Third sentence?"
        regions = _split_into_regions(text, method="sentence")
        assert len(regions) == 3
        assert "First" in regions[0]
        assert "Second" in regions[1]
        assert "Third" in regions[2]

    def test_split_by_paragraph(self):
        text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
        regions = _split_into_regions(text, method="paragraph")
        assert len(regions) == 3

    def test_split_by_line(self):
        text = "Line 1\nLine 2\nLine 3"
        regions = _split_into_regions(text, method="line")
        assert len(regions) == 3

    def test_empty_text(self):
        """Empty text should return original text."""
        regions = _split_into_regions("", method="sentence")
        assert regions == [""]


class TestRegionSimilarity:
    """Tests for region similarity computation."""

    def test_identical_regions(self):
        a = ["hello", "world"]
        b = ["hello", "world"]
        similarities = _compute_region_similarity(a, b)
        assert similarities == [1.0, 1.0]

    def test_different_regions(self):
        a = ["hello"]
        b = ["goodbye"]
        similarities = _compute_region_similarity(a, b)
        assert similarities[0] < 0.5  # Very different

    def test_mismatched_lengths(self):
        a = ["hello", "world"]
        b = ["hello"]
        similarities = _compute_region_similarity(a, b)
        assert len(similarities) == 2
        assert similarities[0] == 1.0  # Same
        assert similarities[1] == 0.0  # b missing


class TestHashContent:
    """Tests for content hashing."""

    def test_consistent_hash(self):
        content = "test content"
        hash1 = _hash_content(content)
        hash2 = _hash_content(content)
        assert hash1 == hash2

    def test_different_content_different_hash(self):
        hash1 = _hash_content("content A")
        hash2 = _hash_content("content B")
        assert hash1 != hash2


class TestCodeChunking:
    """Tests for code chunking utilities."""

    def test_chunk_by_function(self):
        code = """
def foo():
    pass

def bar():
    pass

class Baz:
    pass
"""
        chunks = chunk_code_by_function(code)
        assert len(chunks) == 3  # foo, bar, Baz

    def test_chunk_by_lines(self):
        text = "\n".join([f"line {i}" for i in range(25)])
        chunks = chunk_by_lines(text, chunk_size=10)
        assert len(chunks) == 3  # 10 + 10 + 5

    def test_chunk_empty_code(self):
        """Empty code should return the original."""
        chunks = chunk_code_by_function("")
        assert chunks == [""]


# =============================================================================
# Rendering Tests
# =============================================================================


class TestRendering:
    """Tests for visualization rendering."""

    def test_render_lateral_map(self):
        signals = (
            OmmatidiumSignal(0, "safe code", 0.1, 0.05, "0"),
            OmmatidiumSignal(1, "risky code", 0.9, 0.7, "2"),
        )
        result = LateralInhibitionResult(
            signals=signals,
            edge_indices=(1,),
            edge_threshold=0.3,
            total_regions=2,
            edges_found=1,
        )
        output = render_lateral_map(result)
        assert "Lateral Inhibition" in output
        assert "[E]" in output  # Edge marker
        assert "Edges: 1/2" in output

    def test_render_temporal_map(self):
        regions = (
            RegionStability(
                index=0,
                region_text="stable region",
                frame_hashes=(),
                stability_score=0.95,
                is_stable=True,
            ),
            RegionStability(
                index=1,
                region_text="unstable region",
                frame_hashes=(),
                stability_score=0.3,
                is_stable=False,
            ),
        )
        result = TemporalDiffResult(
            frames=(),
            regions=regions,
            unstable_regions=(1,),
            overall_stability=0.625,
            n_frames=3,
            stability_threshold=0.85,
        )
        output = render_temporal_map(result)
        assert "Temporal Stability" in output
        assert "Flickering: 1/2" in output

    def test_render_signal_stability_map(self):
        regions = (
            SignalStability(0, "region A", (1, 1, 1), 1, 1.0, True),
            SignalStability(1, "region B", (0, 1, 2), 1, 0.33, False),
        )
        result = TemporalSignalResult(
            regions=regions,
            n_frames=3,
            stable_indices=(0,),
            unstable_indices=(1,),
            overall_stability=0.665,
        )
        output = render_signal_stability_map(result)
        assert "Temporal Signal Stability" in output
        assert "1,1,1" in output  # Unanimous signals
        assert "0,1,2" in output  # Mixed signals
        assert "⚠️" in output  # High spread warning

    def test_render_compound_map(self):
        signals = (OmmatidiumSignal(0, "test", 0.5, 0.3, "1"),)
        lateral = LateralInhibitionResult(
            signals=signals,
            edge_indices=(0,),
            edge_threshold=0.3,
            total_regions=1,
            edges_found=1,
        )
        temporal = TemporalDiffResult(
            frames=(),
            regions=(),
            unstable_regions=(0,),
            overall_stability=0.5,
            n_frames=3,
            stability_threshold=0.85,
        )
        result = CompoundEyeResult(
            lateral=lateral,
            temporal=temporal,
            hotspots=(0,),
        )
        output = render_compound_map(result)
        assert "Compound Eye" in output
        assert "HOTSPOTS" in output

    def test_render_attention_fold_map(self):
        folded = FoldedRegion(
            index=0,
            region="test region",
            original_signals=(0, 1, 2),
            resolved_signal=1,
            confidence=0.8,
            strategy_used=FoldStrategy.VOTE,
            details={},
        )
        result = AttentionFoldResult(
            stable_regions=(),
            folded_regions=(folded,),
            final_signals=(1,),
            total_regions=1,
            folded_count=1,
            avg_confidence=0.8,
        )
        output = render_attention_fold_map(result)
        assert "Attention Fold" in output
        assert "0,1,2" in output
        assert "→ 1" in output  # Resolved signal


# =============================================================================
# Integration Tests (Require Model - Mark as slow)
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.slow
class TestLateralInhibitionScanIntegration:
    """Integration tests for lateral_inhibition_scan (require model)."""

    async def test_scan_with_mock_model(self):
        """Test scan with a mock model."""
        from unittest.mock import AsyncMock
        from sunwell.experiments.compound import lateral_inhibition_scan

        # Create mock model
        mock_model = AsyncMock()
        mock_result = AsyncMock()
        mock_result.text = "1"
        mock_model.generate.return_value = mock_result

        regions = ["code chunk 1", "code chunk 2", "code chunk 3"]
        result = await lateral_inhibition_scan(
            regions=regions,
            question="Rate danger 0-2",
            model=mock_model,
        )

        assert result.total_regions == 3
        assert len(result.signals) == 3
        # All signals should be 0.5 (normalized from 1)
        assert all(s.raw_signal == 0.5 for s in result.signals)


@pytest.mark.asyncio
@pytest.mark.slow
class TestTemporalDiffScanIntegration:
    """Integration tests for temporal_diff_scan (require model)."""

    async def test_scan_with_mock_model(self):
        """Test temporal scan with mock model returning consistent output."""
        from unittest.mock import AsyncMock
        from sunwell.experiments.compound import temporal_diff_scan

        # Create mock model that returns consistent output
        mock_model = AsyncMock()
        mock_result = AsyncMock()
        mock_result.text = "This is a consistent response."
        mock_model.generate.return_value = mock_result

        result = await temporal_diff_scan(
            prompt="Explain this",
            model=mock_model,
            n_frames=3,
        )

        assert result.n_frames == 3
        assert len(result.frames) == 3
        # All frames should be identical
        assert all(f.content == result.frames[0].content for f in result.frames)
        assert result.overall_stability == 1.0  # Perfectly stable


@pytest.mark.asyncio
@pytest.mark.slow
class TestTemporalSignalScanIntegration:
    """Integration tests for temporal_signal_scan (require model)."""

    async def test_scan_with_mock_model_consistent(self):
        """Test with mock model returning consistent signals."""
        from unittest.mock import AsyncMock
        from sunwell.experiments.compound import temporal_signal_scan

        # Mock model always returns "2"
        mock_model = AsyncMock()
        mock_result = AsyncMock()
        mock_result.text = "2"
        mock_model.generate.return_value = mock_result

        regions = ["region 1", "region 2"]
        result = await temporal_signal_scan(
            regions=regions,
            question="Is this dangerous?",
            model=mock_model,
            n_frames=3,
        )

        assert result.n_frames == 3
        assert len(result.regions) == 2
        # All should be unanimous at signal 2
        assert all(r.is_unanimous for r in result.regions)
        assert all(r.mode_signal == 2 for r in result.regions)


@pytest.mark.asyncio
@pytest.mark.slow
class TestAttentionFoldIntegration:
    """Integration tests for attention_fold (require model)."""

    async def test_fold_stable_regions(self):
        """Test that stable regions pass through unchanged."""
        from unittest.mock import AsyncMock
        from sunwell.experiments.compound import attention_fold

        # Create initial scan with all stable regions
        regions = [
            SignalStability(0, "region 0", (1, 1, 1), 1, 1.0, True),
            SignalStability(1, "region 1", (2, 2, 2), 2, 1.0, True),
        ]
        initial_scan = TemporalSignalResult(
            regions=tuple(regions),
            n_frames=3,
            stable_indices=(0, 1),
            unstable_indices=(),
            overall_stability=1.0,
        )

        mock_model = AsyncMock()
        result = await attention_fold(
            initial_scan=initial_scan,
            regions=["text 0", "text 1"],
            question="Test?",
            model=mock_model,
        )

        # All regions should be stable (no folding needed)
        assert result.folded_count == 0
        assert len(result.stable_regions) == 2
        assert result.final_signals == (1, 2)


# =============================================================================
# Fold Strategy Tests
# =============================================================================


class TestFoldStrategy:
    """Tests for FoldStrategy enum."""

    def test_strategy_values(self):
        assert FoldStrategy.VOTE.value == "vote"
        assert FoldStrategy.ESCALATE.value == "escalate"
        assert FoldStrategy.TRIANGULATE.value == "triangulate"
        assert FoldStrategy.DECOMPOSE.value == "decompose"
        assert FoldStrategy.ENSEMBLE.value == "ensemble"


class TestFoldedRegion:
    """Tests for FoldedRegion data structure."""

    def test_folded_region_creation(self):
        folded = FoldedRegion(
            index=0,
            region="test code",
            original_signals=(0, 1, 2),
            resolved_signal=1,
            confidence=0.75,
            strategy_used=FoldStrategy.VOTE,
            details={"votes": [0, 1, 1, 1, 2]},
        )
        assert folded.resolved_signal == 1
        assert folded.confidence == 0.75
        assert folded.strategy_used == FoldStrategy.VOTE
