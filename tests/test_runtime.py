"""Tests for runtime engine."""

import pytest

from sunwell.runtime.engine import RuntimeEngine, ExecutionResult
from sunwell.runtime.classifier import IntentClassifier, ClassificationResult
from sunwell.runtime.retriever import ExpertiseRetriever
from sunwell.core.types import Tier, IntentCategory
from sunwell.core.lens import Lens
from sunwell.models.mock import MockModel
from sunwell.embedding.simple import HashEmbedding


class TestIntentClassifier:
    def test_classify_trivial(self, sample_lens: Lens):
        classifier = IntentClassifier(lens=sample_lens)

        result = classifier.classify("fix the typo in line 5")
        assert result.tier == Tier.FAST_PATH
        assert result.category == IntentCategory.TRIVIAL

    def test_classify_complex(self, sample_lens: Lens):
        classifier = IntentClassifier(lens=sample_lens)

        result = classifier.classify("comprehensive architecture review")
        assert result.tier == Tier.DEEP_LENS
        assert result.category == IntentCategory.COMPLEX

    def test_classify_standard(self, sample_lens: Lens):
        classifier = IntentClassifier(lens=sample_lens)

        result = classifier.classify("write documentation for auth module")
        assert result.tier == Tier.STANDARD


class TestExpertiseRetriever:
    @pytest.mark.asyncio
    async def test_initialize(self, sample_lens: Lens):
        embedder = HashEmbedding()
        retriever = ExpertiseRetriever(
            lens=sample_lens,
            embedder=embedder,
        )

        await retriever.initialize()

        stats = retriever.get_stats()
        assert stats["initialized"]
        assert stats["index_size"] > 0

    @pytest.mark.asyncio
    async def test_retrieve(self, sample_lens: Lens):
        embedder = HashEmbedding()
        retriever = ExpertiseRetriever(
            lens=sample_lens,
            embedder=embedder,
            relevance_threshold=0.0,  # Low threshold for hash embedding
        )

        await retriever.initialize()

        result = await retriever.retrieve("write tests for the code")
        # Should retrieve at least the heuristic
        assert len(result.heuristics) > 0 or len(result.relevance_scores) > 0


class TestRuntimeEngine:
    @pytest.mark.asyncio
    async def test_execute_fast_path(self, sample_lens: Lens, mock_model: MockModel):
        engine = RuntimeEngine(
            model=mock_model,
            lens=sample_lens,
        )

        result = await engine.execute(
            "fix typo",
            force_tier=Tier.FAST_PATH,
        )

        assert isinstance(result, ExecutionResult)
        assert result.tier == Tier.FAST_PATH
        assert len(result.validation_results) == 0  # No validation for fast path

    @pytest.mark.asyncio
    async def test_execute_standard(self, sample_lens: Lens, mock_model: MockModel):
        embedder = HashEmbedding()
        engine = RuntimeEngine(
            model=mock_model,
            lens=sample_lens,
            embedder=embedder,
        )

        result = await engine.execute("write documentation")

        assert isinstance(result, ExecutionResult)
        assert result.content  # Should have content

    @pytest.mark.asyncio
    async def test_execute_stream(self, sample_lens: Lens, mock_model: MockModel):
        engine = RuntimeEngine(
            model=mock_model,
            lens=sample_lens,
        )

        chunks = []
        async for chunk in engine.execute_stream("test prompt"):
            chunks.append(chunk)

        assert len(chunks) > 0
        full_content = "".join(chunks)
        assert full_content  # Should have content

    @pytest.mark.asyncio
    async def test_context_injection(self, tech_writer_lens: Lens, mock_model: MockModel):
        embedder = HashEmbedding()
        engine = RuntimeEngine(
            model=mock_model,
            lens=tech_writer_lens,
            embedder=embedder,
        )

        await engine.execute("write API docs")

        # Check that the prompt included lens context
        assert len(mock_model.prompts) > 0
        prompt = mock_model.prompts[0]
        assert "Technical Writer" in prompt or "Heuristics" in prompt
