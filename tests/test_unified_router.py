"""Tests for the Unified Router (RFC-030).

Tests the single-model routing architecture that replaces
CognitiveRouter, TieredAttunement, Discernment, and model routing.
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from sunwell.routing.unified import (
    UnifiedRouter,
    RoutingDecision,
    Intent,
    Complexity,
    UserMood,
    UserExpertise,
    LegacyRoutingAdapter,
    create_unified_router,
    UNIFIED_ROUTER_PROMPT,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_model():
    """Create a mock model for testing."""
    model = MagicMock()
    model.model_id = "mock/test"
    return model


@pytest.fixture
def mock_generate_result():
    """Create a mock generate result factory."""
    def factory(content: str):
        result = MagicMock()
        result.content = content
        return result
    return factory


@pytest.fixture
def router(mock_model):
    """Create a router with mock model."""
    return UnifiedRouter(
        model=mock_model,
        cache_size=10,
        available_lenses=["coder", "tech-writer", "code-reviewer", "helper"],
    )


# =============================================================================
# Basic Routing Tests
# =============================================================================


class TestUnifiedRouterBasics:
    """Test basic UnifiedRouter functionality."""
    
    @pytest.mark.asyncio
    async def test_route_code_request(self, router, mock_model, mock_generate_result):
        """Test routing a code generation request."""
        mock_model.generate = AsyncMock(return_value=mock_generate_result(json.dumps({
            "intent": "code",
            "complexity": "standard",
            "lens": "coder",
            "tools": ["file_read", "file_write"],
            "mood": "neutral",
            "expertise": "intermediate",
            "confidence": 0.85,
            "reasoning": "User wants to write code",
        })))
        
        decision = await router.route("Add a login function to auth.py")
        
        assert decision.intent == Intent.CODE
        assert decision.complexity == Complexity.STANDARD
        assert decision.lens == "coder"
        assert "file_read" in decision.tools
        assert decision.mood == UserMood.NEUTRAL
        assert decision.expertise == UserExpertise.INTERMEDIATE
        assert decision.confidence == 0.85
    
    @pytest.mark.asyncio
    async def test_route_debug_request(self, router, mock_model, mock_generate_result):
        """Test routing a debugging request."""
        mock_model.generate = AsyncMock(return_value=mock_generate_result(json.dumps({
            "intent": "debug",
            "complexity": "trivial",
            "lens": "reviewer",
            "tools": ["terminal"],
            "mood": "frustrated",
            "expertise": "intermediate",
            "confidence": 0.9,
            "reasoning": "User reports broken code",
        })))
        
        decision = await router.route("THIS IS BROKEN fix the bug NOW")
        
        assert decision.intent == Intent.DEBUG
        assert decision.mood == UserMood.FRUSTRATED
        assert decision.confidence == 0.9
    
    @pytest.mark.asyncio
    async def test_route_chat_request(self, router, mock_model, mock_generate_result):
        """Test routing a casual chat request."""
        mock_model.generate = AsyncMock(return_value=mock_generate_result(json.dumps({
            "intent": "chat",
            "complexity": "trivial",
            "lens": "helper",
            "tools": [],
            "mood": "neutral",
            "expertise": "intermediate",
            "confidence": 0.95,
            "reasoning": "Casual greeting",
        })))
        
        decision = await router.route("hey how's it going")
        
        assert decision.intent == Intent.CHAT
        assert decision.lens == "helper"
        assert decision.tools == ()
    
    @pytest.mark.asyncio
    async def test_route_complex_refactor(self, router, mock_model, mock_generate_result):
        """Test routing a complex refactoring request."""
        mock_model.generate = AsyncMock(return_value=mock_generate_result(json.dumps({
            "intent": "code",
            "complexity": "complex",
            "lens": "coder",
            "tools": ["file_read", "file_write", "search", "terminal"],
            "mood": "neutral",
            "expertise": "expert",
            "confidence": 0.75,
            "reasoning": "Large refactoring task",
        })))
        
        decision = await router.route("refactor entire auth module to OAuth2")
        
        assert decision.intent == Intent.CODE
        assert decision.complexity == Complexity.COMPLEX
        assert decision.expertise == UserExpertise.EXPERT


# =============================================================================
# Cache Tests
# =============================================================================


class TestUnifiedRouterCache:
    """Test caching functionality."""
    
    @pytest.mark.asyncio
    async def test_cache_hit(self, router, mock_model, mock_generate_result):
        """Test that repeated requests hit the cache."""
        mock_model.generate = AsyncMock(return_value=mock_generate_result(json.dumps({
            "intent": "code",
            "complexity": "standard",
            "lens": "coder",
            "tools": [],
            "mood": "neutral",
            "expertise": "intermediate",
            "confidence": 0.8,
            "reasoning": "Test",
        })))
        
        # First call - should call model
        decision1 = await router.route("test request")
        assert mock_model.generate.call_count == 1
        
        # Second call - should hit cache
        decision2 = await router.route("test request")
        assert mock_model.generate.call_count == 1  # Still 1
        
        # Same decision
        assert decision1 == decision2
    
    @pytest.mark.asyncio
    async def test_cache_miss_different_request(self, router, mock_model, mock_generate_result):
        """Test that different requests don't hit cache."""
        mock_model.generate = AsyncMock(return_value=mock_generate_result(json.dumps({
            "intent": "code",
            "complexity": "standard",
            "lens": "coder",
            "tools": [],
            "mood": "neutral",
            "expertise": "intermediate",
            "confidence": 0.8,
            "reasoning": "Test",
        })))
        
        await router.route("request 1")
        await router.route("request 2")
        
        assert mock_model.generate.call_count == 2
    
    @pytest.mark.asyncio
    async def test_cache_lru_eviction(self, mock_model, mock_generate_result):
        """Test that cache evicts old entries when full."""
        router = UnifiedRouter(model=mock_model, cache_size=3)
        
        mock_model.generate = AsyncMock(return_value=mock_generate_result(json.dumps({
            "intent": "code",
            "complexity": "standard",
            "lens": "coder",
            "tools": [],
            "mood": "neutral",
            "expertise": "intermediate",
            "confidence": 0.8,
            "reasoning": "Test",
        })))
        
        # Fill cache
        await router.route("request 1")
        await router.route("request 2")
        await router.route("request 3")
        
        assert len(router._cache) == 3
        
        # Add one more - should evict oldest
        await router.route("request 4")
        
        assert len(router._cache) == 3
        assert mock_model.generate.call_count == 4
    
    def test_clear_cache(self, router):
        """Test cache clearing."""
        # Add some fake cache entries
        router._cache[123] = RoutingDecision(
            intent=Intent.CODE,
            complexity=Complexity.STANDARD,
            lens="coder",
            tools=(),
            mood=UserMood.NEUTRAL,
            expertise=UserExpertise.INTERMEDIATE,
            confidence=0.8,
            reasoning="Test",
        )
        router._cache_order.append(123)
        
        assert len(router._cache) == 1
        
        router.clear_cache()
        
        assert len(router._cache) == 0
        assert len(router._cache_order) == 0


# =============================================================================
# Fallback Tests
# =============================================================================


class TestUnifiedRouterFallback:
    """Test heuristic fallback when model fails."""
    
    def test_fallback_code_intent(self):
        """Test fallback detects code intent."""
        decision = UnifiedRouter.fallback_decision("add a new function")
        assert decision.intent == Intent.CODE
        assert decision.confidence == 0.3  # Low confidence for fallback
    
    def test_fallback_debug_intent(self):
        """Test fallback detects debug intent."""
        decision = UnifiedRouter.fallback_decision("fix the bug in auth.py")
        assert decision.intent == Intent.DEBUG
    
    def test_fallback_explain_intent(self):
        """Test fallback detects explain intent."""
        decision = UnifiedRouter.fallback_decision("what is dependency injection?")
        assert decision.intent == Intent.EXPLAIN
    
    def test_fallback_chat_intent(self):
        """Test fallback detects chat intent."""
        decision = UnifiedRouter.fallback_decision("hey hello")
        assert decision.intent == Intent.CHAT
    
    def test_fallback_search_intent(self):
        """Test fallback detects search intent."""
        decision = UnifiedRouter.fallback_decision("find the auth module")
        assert decision.intent == Intent.SEARCH
    
    def test_fallback_review_intent(self):
        """Test fallback detects review intent."""
        decision = UnifiedRouter.fallback_decision("review this code")
        assert decision.intent == Intent.REVIEW
    
    def test_fallback_frustrated_mood(self):
        """Test fallback detects frustrated mood from caps."""
        decision = UnifiedRouter.fallback_decision("THIS IS BROKEN AGAIN")
        assert decision.mood == UserMood.FRUSTRATED
    
    def test_fallback_curious_mood(self):
        """Test fallback detects curious mood."""
        decision = UnifiedRouter.fallback_decision("how does this work?")
        assert decision.mood == UserMood.CURIOUS
    
    def test_fallback_rushed_mood(self):
        """Test fallback detects rushed mood."""
        decision = UnifiedRouter.fallback_decision("fix this asap please")
        assert decision.mood == UserMood.RUSHED
    
    def test_fallback_complex_task(self):
        """Test fallback detects complex tasks."""
        decision = UnifiedRouter.fallback_decision("refactor the entire codebase")
        assert decision.complexity == Complexity.COMPLEX
    
    def test_fallback_trivial_task(self):
        """Test fallback detects trivial tasks."""
        decision = UnifiedRouter.fallback_decision("add comment")
        assert decision.complexity == Complexity.TRIVIAL
    
    @pytest.mark.asyncio
    async def test_fallback_on_model_error(self, router, mock_model):
        """Test that model errors trigger fallback."""
        mock_model.generate = AsyncMock(side_effect=Exception("Model unavailable"))
        
        decision = await router.route("test request")
        
        assert decision.confidence == 0.3  # Fallback confidence
        assert "Model unavailable" in decision.reasoning


# =============================================================================
# JSON Parsing Tests
# =============================================================================


class TestUnifiedRouterParsing:
    """Test JSON response parsing."""
    
    @pytest.mark.asyncio
    async def test_parse_raw_json(self, router, mock_model, mock_generate_result):
        """Test parsing raw JSON response."""
        mock_model.generate = AsyncMock(return_value=mock_generate_result(
            '{"intent": "code", "complexity": "standard", "lens": "coder", '
            '"tools": [], "mood": "neutral", "expertise": "intermediate", '
            '"confidence": 0.8, "reasoning": "Test"}'
        ))
        
        decision = await router.route("test")
        assert decision.intent == Intent.CODE
    
    @pytest.mark.asyncio
    async def test_parse_markdown_code_block(self, router, mock_model, mock_generate_result):
        """Test parsing JSON inside markdown code block."""
        mock_model.generate = AsyncMock(return_value=mock_generate_result(
            '```json\n{"intent": "debug", "complexity": "trivial", "lens": "reviewer", '
            '"tools": [], "mood": "neutral", "expertise": "intermediate", '
            '"confidence": 0.9, "reasoning": "Test"}\n```'
        ))
        
        decision = await router.route("test")
        assert decision.intent == Intent.DEBUG
    
    @pytest.mark.asyncio
    async def test_parse_intent_variants(self, router, mock_model, mock_generate_result):
        """Test parsing various intent names."""
        # Test bug_fixing -> DEBUG
        mock_model.generate = AsyncMock(return_value=mock_generate_result(
            '{"intent": "bug_fixing", "complexity": "standard", "lens": "coder", '
            '"tools": [], "mood": "neutral", "expertise": "intermediate", '
            '"confidence": 0.8, "reasoning": "Test"}'
        ))
        
        decision = await router.route("test")
        assert decision.intent == Intent.DEBUG
    
    @pytest.mark.asyncio
    async def test_parse_invalid_json_fallback(self, router, mock_model, mock_generate_result):
        """Test that invalid JSON triggers fallback."""
        mock_model.generate = AsyncMock(return_value=mock_generate_result(
            "This is not valid JSON at all"
        ))
        
        decision = await router.route("test")
        assert decision.confidence == 0.3  # Fallback confidence


# =============================================================================
# Legacy Adapter Tests
# =============================================================================


class TestLegacyRoutingAdapter:
    """Test backward compatibility adapter."""
    
    @pytest.mark.asyncio
    async def test_adapter_output_format(self, router, mock_model, mock_generate_result):
        """Test that adapter produces legacy-compatible output."""
        mock_model.generate = AsyncMock(return_value=mock_generate_result(json.dumps({
            "intent": "code",
            "complexity": "complex",
            "lens": "coder",
            "tools": ["file_read"],
            "mood": "neutral",
            "expertise": "expert",
            "confidence": 0.85,
            "reasoning": "Test",
        })))
        
        adapter = LegacyRoutingAdapter(router)
        legacy = await adapter.to_cognitive_router_decision("test request")
        
        # Check legacy format fields
        assert "intent" in legacy
        assert "lens" in legacy
        assert "secondary_lenses" in legacy
        assert "focus" in legacy
        assert "complexity" in legacy
        assert "top_k" in legacy
        assert "threshold" in legacy
        assert "confidence" in legacy
        assert "reasoning" in legacy
        
        # Check intent mapping
        assert legacy["intent"] == "code_generation"
        
        # Check complexity -> top_k mapping
        assert legacy["top_k"] == 8  # complex -> top_k=8
        assert legacy["threshold"] == 0.2  # complex -> threshold=0.2


# =============================================================================
# Thread Safety Tests
# =============================================================================


class TestUnifiedRouterThreadSafety:
    """Test thread safety of the router."""
    
    @pytest.mark.asyncio
    async def test_concurrent_routes(self, mock_model, mock_generate_result):
        """Test that concurrent routes don't corrupt cache."""
        router = UnifiedRouter(model=mock_model, cache_size=100)
        
        call_count = 0
        
        async def slow_generate(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)  # Simulate slow model
            return mock_generate_result(json.dumps({
                "intent": "code",
                "complexity": "standard",
                "lens": "coder",
                "tools": [],
                "mood": "neutral",
                "expertise": "intermediate",
                "confidence": 0.8,
                "reasoning": f"Call {call_count}",
            }))
        
        mock_model.generate = slow_generate
        
        # Run many concurrent requests
        tasks = [
            router.route(f"request {i % 5}")  # 5 unique requests
            for i in range(20)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # All should succeed
        assert len(results) == 20
        
        # Cache should have exactly 5 entries (5 unique requests)
        assert len(router._cache) == 5


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestCreateUnifiedRouter:
    """Test the factory function."""
    
    def test_create_with_model(self, mock_model):
        """Test creating router with existing model."""
        router = create_unified_router(
            model=mock_model,
            cache_size=500,
            available_lenses=["test-lens"],
        )
        
        assert router.model == mock_model
        assert router.cache_size == 500
        assert "test-lens" in router.available_lenses
    
    def test_create_with_model_name(self):
        """Test creating router with model name creates OllamaModel."""
        router = create_unified_router(model_name="test-model:1b")
        
        # Verify router was created with an OllamaModel
        assert router.model is not None
        assert "ollama" in router.model.model_id.lower()
        assert router.cache_size == 1000  # default


# =============================================================================
# Stats Tests
# =============================================================================


class TestUnifiedRouterStats:
    """Test router statistics."""
    
    @pytest.mark.asyncio
    async def test_stats_after_routes(self, router, mock_model, mock_generate_result):
        """Test statistics are collected after routing."""
        mock_model.generate = AsyncMock(return_value=mock_generate_result(json.dumps({
            "intent": "code",
            "complexity": "standard",
            "lens": "coder",
            "tools": [],
            "mood": "neutral",
            "expertise": "intermediate",
            "confidence": 0.8,
            "reasoning": "Test",
        })))
        
        await router.route("request 1")
        await router.route("request 2")
        
        stats = router.get_stats()
        
        assert stats["total_routes"] == 2
        assert "intent_distribution" in stats
        assert "mood_distribution" in stats
        assert "avg_confidence" in stats
    
    def test_empty_stats(self, router):
        """Test stats on fresh router."""
        stats = router.get_stats()
        
        assert stats["total_routes"] == 0
        assert stats["avg_confidence"] == 0.0


# =============================================================================
# RoutingDecision Tests
# =============================================================================


class TestRoutingDecision:
    """Test RoutingDecision dataclass."""
    
    def test_to_dict(self):
        """Test serialization to dict."""
        decision = RoutingDecision(
            intent=Intent.CODE,
            complexity=Complexity.STANDARD,
            lens="coder",
            tools=("file_read",),
            mood=UserMood.NEUTRAL,
            expertise=UserExpertise.INTERMEDIATE,
            confidence=0.85,
            reasoning="Test",
        )
        
        d = decision.to_dict()
        
        assert d["intent"] == "code"
        assert d["complexity"] == "standard"
        assert d["lens"] == "coder"
        assert d["tools"] == ["file_read"]
        assert d["mood"] == "neutral"
        assert d["expertise"] == "intermediate"
        assert d["confidence"] == 0.85
    
    def test_from_dict(self):
        """Test deserialization from dict."""
        d = {
            "intent": "debug",
            "complexity": "complex",
            "lens": "reviewer",
            "tools": ["terminal"],
            "mood": "frustrated",
            "expertise": "expert",
            "confidence": 0.9,
            "reasoning": "Test",
        }
        
        decision = RoutingDecision.from_dict(d)
        
        assert decision.intent == Intent.DEBUG
        assert decision.complexity == Complexity.COMPLEX
        assert decision.mood == UserMood.FRUSTRATED
        assert decision.expertise == UserExpertise.EXPERT
    
    def test_immutability(self):
        """Test that RoutingDecision is immutable."""
        decision = RoutingDecision(
            intent=Intent.CODE,
            complexity=Complexity.STANDARD,
            lens="coder",
            tools=(),
            mood=UserMood.NEUTRAL,
            expertise=UserExpertise.INTERMEDIATE,
            confidence=0.8,
            reasoning="Test",
        )
        
        with pytest.raises(AttributeError):
            decision.intent = Intent.DEBUG
