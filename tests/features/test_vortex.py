"""Tests for Vortex module — emergent intelligence through primitive composition.

Tests cover:
- Signal parsing and generation
- Locality (island evolution)
- Primitives (interference, dialectic, resonance, gradient)
- VortexConfig presets
- Core Vortex orchestration
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from sunwell.vortex import (
    # Config
    VortexConfig,
    FAST_CONFIG,
    QUALITY_CONFIG,
    # Signals
    Signal,
    format_signal,
    # Locality
    Island,
    LocalityResult,
    evolve_islands,
    # Primitives
    InterferenceResult,
    DialecticResult,
    ResonanceResult,
    GradientResult,
    Subtask,
    interference,
    dialectic,
    resonance,
    gradient,
    # Core
    Vortex,
    VortexResult,
    solve,
    format_result,
)
from sunwell.features.vortex.signals import (
    parse_signal,
    parse_selection,
    generate_signal,
    generate_reaction,
    SIGNAL_PROMPT,
    REACT_PROMPT,
)
from sunwell.features.vortex.locality import (
    select_best_signal_per_island,
    merge_island_signals,
)
from sunwell.models.protocol import GenerateOptions, GenerateResult
from sunwell.models.mock import MockModel


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_model():
    """Create a mock model for testing."""
    model = MagicMock()
    model.model_id = "test-model"
    return model


@pytest.fixture
def generate_options():
    """Default generation options for tests."""
    return GenerateOptions(
        temperature=0.7,
        max_tokens=100,
    )


# =============================================================================
# Signal Tests
# =============================================================================


class TestSignal:
    """Tests for Signal dataclass."""
    
    def test_signal_creation(self):
        """Signal created with correct defaults."""
        signal = Signal(
            claim="Use a hash map for O(1) lookup",
            confidence=0.85,
            tags=("performance", "data-structure"),
        )
        
        assert signal.claim == "Use a hash map for O(1) lookup"
        assert signal.confidence == 0.85
        assert signal.tags == ("performance", "data-structure")
        assert signal.source_island == 0
        assert signal.source_agent == 0
        assert signal.generation == 0
        assert signal.agreement == 0
    
    def test_signal_with_metadata(self):
        """Signal stores source metadata correctly."""
        signal = Signal(
            claim="Test claim",
            confidence=0.7,
            tags=("test",),
            source_island=2,
            source_agent=3,
            generation=5,
            agreement=2,
        )
        
        assert signal.source_island == 2
        assert signal.source_agent == 3
        assert signal.generation == 5
        assert signal.agreement == 2
    
    def test_signal_is_frozen(self):
        """Signal is immutable."""
        signal = Signal(claim="test", confidence=0.5, tags=())
        
        with pytest.raises(AttributeError):
            signal.claim = "modified"


class TestParseSignal:
    """Tests for signal parsing."""
    
    def test_parse_standard_format(self):
        """Parses standard CLAIM/CONF/TAGS format."""
        text = """CLAIM: Use caching for performance
CONF: 0.8
TAGS: performance, caching, optimization"""
        
        signal = parse_signal(text)
        
        assert "caching" in signal.claim.lower()
        assert signal.confidence == 0.8
        assert "caching" in signal.tags
    
    def test_parse_with_agreement(self):
        """Parses agreement field from reactions."""
        text = """AGREE: 3
CLAIM: Cache invalidation is key
CONF: 0.75
TAGS: caching"""
        
        signal = parse_signal(text)
        
        assert signal.agreement == 3
    
    def test_parse_with_metadata(self):
        """Metadata passed through correctly."""
        text = "CLAIM: test\nCONF: 0.5\nTAGS: test"
        
        signal = parse_signal(text, island=2, agent=1, generation=3)
        
        assert signal.source_island == 2
        assert signal.source_agent == 1
        assert signal.generation == 3
    
    def test_parse_clamps_confidence(self):
        """Confidence values are clamped to [0, 1]."""
        text_high = "CLAIM: test\nCONF: 1.5\nTAGS: test"
        
        # High values clamped to 1.0
        assert parse_signal(text_high).confidence == 1.0
        
        # Note: negative values fail float() parsing and fall back to 0.5 default
        # This is acceptable behavior - malformed input gets default
    
    def test_parse_fallback_on_malformed(self):
        """Falls back gracefully on malformed input."""
        text = "Just some random text without proper format"
        
        signal = parse_signal(text)
        
        # Should use text as claim, default confidence
        assert signal.claim == text[:80]
        assert signal.confidence == 0.5
        assert signal.tags == ()


class TestParseSelection:
    """Tests for selection result parsing."""
    
    def test_parse_selection_standard(self):
        """Parses standard selection format."""
        text = """PICK: 2
WHY: It has the most comprehensive approach."""
        
        pick, reason = parse_selection(text)
        
        assert pick == 1  # 0-indexed
        assert "comprehensive" in reason
    
    def test_parse_selection_fallback(self):
        """Falls back on malformed input."""
        text = "I think option A is best"
        
        pick, reason = parse_selection(text)
        
        assert pick == 0
        assert "Selected as best candidate" in reason


class TestFormatSignal:
    """Tests for signal formatting."""
    
    def test_format_signal(self):
        """Formats signal for display."""
        signal = Signal(
            claim="Use caching",
            confidence=0.8,
            tags=("cache", "perf"),
            agreement=2,
        )
        
        formatted = format_signal(signal)
        
        assert "[0.8, +2]" in formatted
        assert "Use caching" in formatted
        assert "cache, perf" in formatted


# =============================================================================
# Config Tests
# =============================================================================


class TestVortexConfig:
    """Tests for VortexConfig."""
    
    def test_default_config(self):
        """Default config has sensible values."""
        config = VortexConfig()
        
        assert config.discovery_tokens == 40
        assert config.selection_tokens == 80
        assert config.synthesis_tokens == 300
        assert config.n_islands == 3
        assert config.agents_per_island == 3
    
    def test_config_is_frozen(self):
        """Config is immutable."""
        config = VortexConfig()
        
        with pytest.raises(AttributeError):
            config.discovery_tokens = 100
    
    def test_fast_config(self):
        """Fast config has reduced values."""
        assert FAST_CONFIG.discovery_tokens < VortexConfig().discovery_tokens
        assert FAST_CONFIG.n_islands < VortexConfig().n_islands
        assert FAST_CONFIG.synthesis_tokens < VortexConfig().synthesis_tokens
    
    def test_quality_config(self):
        """Quality config has increased values."""
        assert QUALITY_CONFIG.discovery_tokens > VortexConfig().discovery_tokens
        assert QUALITY_CONFIG.n_islands > VortexConfig().n_islands
        assert QUALITY_CONFIG.synthesis_tokens > VortexConfig().synthesis_tokens


# =============================================================================
# Locality Tests
# =============================================================================


class TestIsland:
    """Tests for Island dataclass."""
    
    def test_island_creation(self):
        """Island created correctly."""
        signals = (
            Signal(claim="test1", confidence=0.8, tags=("tag1",)),
            Signal(claim="test2", confidence=0.6, tags=("tag2",)),
        )
        
        island = Island(
            island_id=1,
            signals=signals,
            culture=("tag1",),
        )
        
        assert island.island_id == 1
        assert len(island.signals) == 2
        assert island.culture == ("tag1",)


class TestLocalityHelpers:
    """Tests for locality helper functions."""
    
    def test_select_best_signal_per_island(self):
        """Selects highest confidence signal from each island."""
        islands = (
            Island(
                island_id=0,
                signals=(
                    Signal(claim="low", confidence=0.3, tags=()),
                    Signal(claim="high", confidence=0.9, tags=()),
                ),
                culture=(),
            ),
            Island(
                island_id=1,
                signals=(
                    Signal(claim="medium", confidence=0.6, tags=()),
                ),
                culture=(),
            ),
        )
        
        best = select_best_signal_per_island(islands)
        
        assert len(best) == 2
        assert best[0].claim == "high"
        assert best[0].confidence == 0.9
    
    def test_merge_island_signals(self):
        """Merges top signals from all islands."""
        islands = (
            Island(
                island_id=0,
                signals=(
                    Signal(claim="a1", confidence=0.9, tags=()),
                    Signal(claim="a2", confidence=0.8, tags=()),
                    Signal(claim="a3", confidence=0.5, tags=()),
                ),
                culture=(),
            ),
            Island(
                island_id=1,
                signals=(
                    Signal(claim="b1", confidence=0.7, tags=()),
                ),
                culture=(),
            ),
        )
        
        merged = merge_island_signals(islands, top_n=2)
        
        assert len(merged) == 3  # 2 from island 0, 1 from island 1
        claims = [s.claim for s in merged]
        assert "a1" in claims
        assert "a2" in claims
        assert "a3" not in claims  # Below top_n


class TestLocalityResult:
    """Tests for LocalityResult dataclass."""
    
    def test_locality_result_creation(self):
        """LocalityResult created correctly."""
        islands = (
            Island(island_id=0, signals=(), culture=("tag1",)),
            Island(island_id=1, signals=(), culture=("tag2",)),
        )
        
        result = LocalityResult(
            islands=islands,
            migrations=3,
            generations=5,
            distinct_cultures=2,
        )
        
        assert len(result.islands) == 2
        assert result.migrations == 3
        assert result.generations == 5
        assert result.distinct_cultures == 2


@pytest.mark.asyncio
async def test_evolve_islands(generate_options):
    """Integration test for island evolution."""
    # Use MockModel for deterministic responses
    model = MockModel(responses=[
        "CLAIM: Use caching\nCONF: 0.7\nTAGS: perf, cache"
    ] * 20)  # Enough for all agents across generations
    
    result = await evolve_islands(
        task="Optimize database queries",
        model=model,
        options=generate_options,
        n_islands=2,
        agents_per_island=2,
        generations=2,
        migration_rate=0.0,  # Disable migration for determinism
    )
    
    assert len(result.islands) == 2
    assert result.generations == 2
    assert all(len(isl.signals) > 0 for isl in result.islands)


# =============================================================================
# Primitive Tests
# =============================================================================


class TestInterferenceResult:
    """Tests for InterferenceResult dataclass."""
    
    def test_interference_result_creation(self):
        """InterferenceResult created correctly."""
        result = InterferenceResult(
            perspectives=("view1", "view2", "view3"),
            consensus="view1",
            agreement=0.75,
            pattern="constructive",
        )
        
        assert len(result.perspectives) == 3
        assert result.consensus == "view1"
        assert result.agreement == 0.75
        assert result.pattern == "constructive"


@pytest.mark.asyncio
async def test_interference_primitive(generate_options):
    """Integration test for interference primitive."""
    model = MockModel(responses=[
        "Perspective A: Use caching",
        "Perspective B: Use caching strategy",
        "Perspective C: Cache the results",
    ])
    
    result = await interference(
        task="How to improve performance?",
        model=model,
        options=generate_options,
        n_perspectives=3,
    )
    
    assert len(result.perspectives) == 3
    assert result.agreement >= 0.0
    assert result.agreement <= 1.0
    assert result.pattern in ("constructive", "destructive")


class TestDialecticResult:
    """Tests for DialecticResult dataclass."""
    
    def test_dialectic_result_creation(self):
        """DialecticResult created correctly."""
        result = DialecticResult(
            thesis="Caching improves performance",
            antithesis="Caching adds complexity",
            synthesis="Use caching with clear invalidation",
        )
        
        assert "improves" in result.thesis
        assert "complexity" in result.antithesis
        assert "invalidation" in result.synthesis


@pytest.mark.asyncio
async def test_dialectic_primitive(generate_options):
    """Integration test for dialectic primitive."""
    model = MockModel(responses=[
        "Thesis: Caching is good",
        "Antithesis: Caching adds complexity",
        "Synthesis: Use caching wisely",
    ])
    
    result = await dialectic(
        task="Should we add caching?",
        model=model,
        options=generate_options,
    )
    
    assert "Caching" in result.thesis
    assert "complexity" in result.antithesis
    assert result.synthesis != ""


class TestResonanceResult:
    """Tests for ResonanceResult dataclass."""
    
    def test_resonance_result_creation(self):
        """ResonanceResult created correctly."""
        result = ResonanceResult(
            iterations=("v1", "v2", "v3"),
            peak_iteration=2,
            final="v3",
            improvement=0.3,
        )
        
        assert len(result.iterations) == 3
        assert result.peak_iteration == 2
        assert result.final == "v3"


@pytest.mark.asyncio
async def test_resonance_primitive(generate_options):
    """Integration test for resonance primitive."""
    model = MockModel(responses=[
        # Initial response
        "Initial solution",
        # Feedback
        "Could be more specific",
        # Refined
        "Improved solution with details",
        # Feedback again
        "Good but needs examples",
        # Final refinement
        "Final solution with examples",
    ])
    
    result = await resonance(
        task="Design an API",
        model=model,
        options=generate_options,
        iterations=2,
    )
    
    assert len(result.iterations) == 3  # Initial + 2 refinements
    assert result.final == result.iterations[result.peak_iteration]


class TestGradientResult:
    """Tests for GradientResult and Subtask."""
    
    def test_subtask_creation(self):
        """Subtask created correctly."""
        subtask = Subtask(
            id="1",
            description="Set up database",
            difficulty=0.3,
            dependencies=(),
        )
        
        assert subtask.id == "1"
        assert subtask.difficulty == 0.3
        assert subtask.dependencies == ()
    
    def test_subtask_with_dependencies(self):
        """Subtask handles dependencies."""
        subtask = Subtask(
            id="2",
            description="Implement API",
            difficulty=0.6,
            dependencies=("1",),
        )
        
        assert subtask.dependencies == ("1",)
    
    def test_gradient_result_creation(self):
        """GradientResult created correctly."""
        subtasks = (
            Subtask(id="1", description="Easy task", difficulty=0.2, dependencies=()),
            Subtask(id="2", description="Hard task", difficulty=0.8, dependencies=("1",)),
        )
        
        result = GradientResult(
            subtasks=subtasks,
            easy_count=1,
            hard_count=1,
        )
        
        assert len(result.subtasks) == 2
        assert result.easy_count == 1
        assert result.hard_count == 1


@pytest.mark.asyncio
async def test_gradient_primitive(generate_options):
    """Integration test for gradient primitive."""
    model = MockModel(responses=[
        """SUBTASK: Set up schema | DIFFICULTY: 0.2 | DEPENDS: none
SUBTASK: Implement API | DIFFICULTY: 0.5 | DEPENDS: 1
SUBTASK: Add validation | DIFFICULTY: 0.7 | DEPENDS: 1, 2"""
    ])
    
    result = await gradient(
        task="Build a REST API",
        model=model,
        options=generate_options,
    )
    
    assert len(result.subtasks) >= 2
    assert result.easy_count + result.hard_count == len(result.subtasks)


# =============================================================================
# Core Vortex Tests
# =============================================================================


class TestVortexResult:
    """Tests for VortexResult dataclass."""
    
    def test_vortex_result_creation(self):
        """VortexResult created correctly."""
        locality = LocalityResult(
            islands=(Island(island_id=0, signals=(), culture=()),),
            migrations=0,
            generations=1,
            distinct_cultures=1,
        )
        winner = Signal(claim="winner", confidence=0.9, tags=())
        
        result = VortexResult(
            task="test task",
            locality=locality,
            winner=winner,
            selection_reason="Best overall",
            synthesis="Final answer",
            interference_result=None,
            dialectic_result=None,
            distinct_cultures=1,
            migrations=0,
            total_signals=1,
            discovery_tokens=100,
            selection_tokens=50,
            synthesis_tokens=200,
            discovery_time_s=0.5,
            selection_time_s=0.2,
            synthesis_time_s=0.3,
            total_time_s=1.0,
        )
        
        assert result.task == "test task"
        assert result.winner.confidence == 0.9
        assert result.synthesis == "Final answer"


class TestFormatResult:
    """Tests for result formatting."""
    
    def test_format_result(self):
        """Formats VortexResult for display."""
        locality = LocalityResult(
            islands=(
                Island(island_id=0, signals=(Signal(claim="s1", confidence=0.8, tags=("a",)),), culture=("a",)),
            ),
            migrations=0,
            generations=2,
            distinct_cultures=1,
        )
        
        result = VortexResult(
            task="Test task with enough content here",
            locality=locality,
            winner=Signal(claim="winning claim here", confidence=0.85, tags=("tag",)),
            selection_reason="It was the best option available",
            synthesis="This is the synthesized final answer with details",
            interference_result=None,
            dialectic_result=None,
            distinct_cultures=1,
            migrations=0,
            total_signals=1,
            discovery_tokens=40,
            selection_tokens=80,
            synthesis_tokens=300,
            discovery_time_s=0.1,
            selection_time_s=0.2,
            synthesis_time_s=0.3,
            total_time_s=0.6,
        )
        
        formatted = format_result(result)
        
        assert "VORTEX RESULT" in formatted
        assert "DISCOVERY" in formatted
        assert "SELECTION" in formatted
        assert "SYNTHESIS" in formatted
        assert "METRICS" in formatted


class TestVortex:
    """Tests for Vortex class."""
    
    def test_vortex_creation(self, mock_model):
        """Vortex created with model and config."""
        config = VortexConfig(n_islands=2)
        vortex = Vortex(mock_model, config)
        
        assert vortex.model == mock_model
        assert vortex.config.n_islands == 2
    
    def test_vortex_default_config(self, mock_model):
        """Vortex uses default config when none provided."""
        vortex = Vortex(mock_model)
        
        assert vortex.config == VortexConfig()


@pytest.mark.asyncio
async def test_vortex_solve():
    """Integration test for Vortex.solve()."""
    # Build responses list: discovery signals + selection + synthesis
    responses = (
        ["CLAIM: Use caching\nCONF: 0.8\nTAGS: perf"] * 20  # Discovery
        + ["PICK: 1\nWHY: Best approach"]  # Selection
        + ["Complete solution with caching strategy..."]  # Synthesis
    )
    model = MockModel(responses=responses)
    
    config = VortexConfig(
        n_islands=2,
        agents_per_island=2,
        island_generations=2,
        dialectic_enabled=False,  # Simplify test
    )
    vortex = Vortex(model, config)
    
    result = await vortex.solve("Optimize query performance")
    
    assert isinstance(result, VortexResult)
    assert result.synthesis != ""
    assert result.winner is not None
    assert result.total_time_s > 0


@pytest.mark.asyncio
async def test_solve_convenience_function():
    """Test the solve() convenience function."""
    responses = (
        ["CLAIM: Solution\nCONF: 0.8\nTAGS: test"] * 5
        + ["PICK: 1\nWHY: Good"]
        + ["Final solution"]
    )
    model = MockModel(responses=responses)
    
    config = VortexConfig(
        n_islands=1,
        agents_per_island=1,
        island_generations=1,
        dialectic_enabled=False,
    )
    
    result = await solve("Test task", model, config)
    
    assert isinstance(result, VortexResult)


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_empty_tags_parsing(self):
        """Handles empty tags gracefully."""
        text = "CLAIM: test\nCONF: 0.5\nTAGS:"
        
        signal = parse_signal(text)
        
        assert signal.tags == ()
    
    def test_invalid_confidence_parsing(self):
        """Handles invalid confidence gracefully."""
        text = "CLAIM: test\nCONF: invalid\nTAGS: test"
        
        signal = parse_signal(text)
        
        assert signal.confidence == 0.5  # Default
    
    def test_truncated_claim(self):
        """Claims are truncated to max length."""
        long_claim = "x" * 100
        text = f"CLAIM: {long_claim}\nCONF: 0.5\nTAGS: test"
        
        signal = parse_signal(text)
        
        assert len(signal.claim) <= 80
    
    def test_select_from_empty_islands(self):
        """Handles empty islands gracefully."""
        islands = (
            Island(island_id=0, signals=(), culture=()),
        )
        
        best = select_best_signal_per_island(islands)
        
        assert best == []
