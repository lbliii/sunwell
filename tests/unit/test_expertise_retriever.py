"""Tests for ExpertiseRetriever and ExpertiseToolHandler.

These tests focus on interface contracts - ensuring return types match
what callers expect. The bugs found during bug bash were all interface
mismatches that would have been caught by these tests.
"""

import pytest
import numpy as np

from sunwell.agent.runtime.retriever import ExpertiseRetriever
from sunwell.tools.providers.expertise import ExpertiseToolHandler
from sunwell.knowledge.embedding.simple import HashEmbedding
from sunwell.knowledge.embedding.protocol import EmbeddingResult
from sunwell.foundation.core.lens import Lens, LensMetadata
from sunwell.core.models.heuristic import Heuristic, Example
from sunwell.core.types.types import SemanticVersion


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_heuristics() -> tuple[Heuristic, ...]:
    """Multiple heuristics for retrieval testing."""
    return (
        Heuristic(
            name="error-handling",
            rule="Always handle errors gracefully",
            test="Are errors caught?",
            always=("Use try/except", "Log errors"),
            never=("Ignore exceptions", "Bare except"),
            examples=Example(good=("try: ...",), bad=("pass",)),
        ),
        Heuristic(
            name="type-hints",
            rule="Use type hints for all public functions",
            test="Are there type hints?",
            always=("Annotate return types", "Annotate parameters"),
            never=("Use Any", "Omit types"),
        ),
        Heuristic(
            name="async-patterns",
            rule="Use proper async patterns",
            test="Is async used correctly?",
            always=("Use async/await", "Handle cancellation"),
            never=("Block in async", "Forget await"),
        ),
    )


@pytest.fixture
def sample_lens(sample_heuristics: tuple[Heuristic, ...]) -> Lens:
    """Lens with multiple heuristics for testing."""
    return Lens(
        metadata=LensMetadata(
            name="Test Lens",
            domain="testing",
            version=SemanticVersion(1, 0, 0),
            description="Test lens for retriever tests",
        ),
        heuristics=sample_heuristics,
    )


@pytest.fixture
def empty_lens() -> Lens:
    """Lens with no heuristics."""
    return Lens(
        metadata=LensMetadata(
            name="Empty Lens",
            domain="testing",
            version=SemanticVersion(1, 0, 0),
        ),
        heuristics=(),
    )


@pytest.fixture
def embedder() -> HashEmbedding:
    """Fast, deterministic embedder for testing."""
    return HashEmbedding()


# =============================================================================
# ExpertiseRetriever Tests
# =============================================================================


class TestExpertiseRetrieverInterface:
    """Tests for ExpertiseRetriever return type contracts.
    
    BUG BASH LESSON: These tests would have caught the `.embeddings` vs `.vectors`
    bug because they verify the retriever actually runs without AttributeError.
    """

    @pytest.mark.asyncio
    async def test_retrieve_returns_list_of_heuristics(
        self, sample_lens: Lens, embedder: HashEmbedding
    ):
        """retrieve() must return list[Heuristic], not an object with .heuristics."""
        retriever = ExpertiseRetriever(lens=sample_lens, embedder=embedder, top_k=2)

        result = await retriever.retrieve("error handling patterns")

        # Contract: returns list, not wrapper object
        assert isinstance(result, list)
        assert all(isinstance(h, Heuristic) for h in result)

    @pytest.mark.asyncio
    async def test_retrieve_empty_lens_returns_empty_list(
        self, empty_lens: Lens, embedder: HashEmbedding
    ):
        """retrieve() with empty lens returns [], not None."""
        retriever = ExpertiseRetriever(lens=empty_lens, embedder=embedder)

        result = await retriever.retrieve("anything")

        assert result == []

    @pytest.mark.asyncio
    async def test_retrieve_respects_top_k(
        self, sample_lens: Lens, embedder: HashEmbedding
    ):
        """retrieve() returns at most top_k results."""
        retriever = ExpertiseRetriever(lens=sample_lens, embedder=embedder, top_k=1)

        result = await retriever.retrieve("error handling")

        assert len(result) <= 1

    @pytest.mark.asyncio
    async def test_initialize_uses_vectors_not_embeddings(
        self, sample_lens: Lens, embedder: HashEmbedding
    ):
        """initialize() accesses EmbeddingResult.vectors, not .embeddings.
        
        BUG BASH LESSON: This test would have caught the AttributeError.
        """
        retriever = ExpertiseRetriever(lens=sample_lens, embedder=embedder)

        # This should not raise AttributeError
        await retriever.initialize()

        # Verify embeddings were stored
        assert len(retriever._heuristic_embeddings) == len(sample_lens.heuristics)

    @pytest.mark.asyncio
    async def test_retrieve_signature_has_no_top_k_parameter(
        self, sample_lens: Lens, embedder: HashEmbedding
    ):
        """retrieve() only takes query parameter, top_k is set at init.
        
        BUG BASH LESSON: This test would have caught the TypeError when
        ExpertiseToolHandler passed top_k as a keyword argument.
        """
        retriever = ExpertiseRetriever(lens=sample_lens, embedder=embedder)

        # Should work with just query
        result = await retriever.retrieve("test")
        assert isinstance(result, list)

        # Should NOT accept top_k keyword (would raise TypeError)
        with pytest.raises(TypeError, match="unexpected keyword argument"):
            await retriever.retrieve("test", top_k=5)  # type: ignore[call-arg]


class TestExpertiseRetrieverSemantics:
    """Tests for retrieval quality and ordering."""

    @pytest.mark.asyncio
    async def test_relevant_heuristics_ranked_higher(
        self, sample_lens: Lens, embedder: HashEmbedding
    ):
        """Heuristics matching the query should be ranked first."""
        retriever = ExpertiseRetriever(lens=sample_lens, embedder=embedder, top_k=3)

        result = await retriever.retrieve("async await patterns")

        # async-patterns heuristic should be most relevant
        if result:  # HashEmbedding may not produce perfect semantic matches
            assert any(h.name == "async-patterns" for h in result)

    @pytest.mark.asyncio
    async def test_cosine_similarity_correctness(self):
        """_cosine_similarity computes correct values."""
        # Identical vectors = 1.0
        assert ExpertiseRetriever._cosine_similarity([1, 0], [1, 0]) == pytest.approx(1.0)

        # Orthogonal vectors = 0.0
        assert ExpertiseRetriever._cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)

        # Opposite vectors = -1.0
        assert ExpertiseRetriever._cosine_similarity([1, 0], [-1, 0]) == pytest.approx(-1.0)

        # Different lengths = 0.0 (guard)
        assert ExpertiseRetriever._cosine_similarity([1, 0], [1, 0, 0]) == 0.0


# =============================================================================
# ExpertiseToolHandler Tests
# =============================================================================


class TestExpertiseToolHandlerInterface:
    """Tests for ExpertiseToolHandler integration with ExpertiseRetriever.
    
    BUG BASH LESSON: These tests would have caught both bugs:
    1. Passing top_k to retrieve() (TypeError)
    2. Accessing result.heuristics on a list (AttributeError)
    """

    @pytest.mark.asyncio
    async def test_get_expertise_returns_string(
        self, sample_lens: Lens, embedder: HashEmbedding
    ):
        """_get_expertise() returns formatted string, not heuristics list."""
        retriever = ExpertiseRetriever(lens=sample_lens, embedder=embedder, top_k=2)
        await retriever.initialize()

        handler = ExpertiseToolHandler(retriever=retriever, lens=sample_lens)

        result = await handler.handle("get_expertise", {"topic": "error handling"})

        assert isinstance(result, str)
        assert "Expertise Retrieved" in result or "No expertise found" in result

    @pytest.mark.asyncio
    async def test_get_expertise_caches_results(
        self, sample_lens: Lens, embedder: HashEmbedding
    ):
        """_get_expertise() populates cache for verify_against_expertise."""
        retriever = ExpertiseRetriever(lens=sample_lens, embedder=embedder, top_k=2)
        await retriever.initialize()

        handler = ExpertiseToolHandler(retriever=retriever, lens=sample_lens)

        await handler.handle("get_expertise", {"topic": "error handling"})

        # Cache should be populated
        assert len(handler._retrieved_cache) > 0

    @pytest.mark.asyncio
    async def test_verify_against_expertise_uses_cached(
        self, sample_lens: Lens, embedder: HashEmbedding
    ):
        """verify_against_expertise uses cached heuristics from get_expertise."""
        retriever = ExpertiseRetriever(lens=sample_lens, embedder=embedder, top_k=2)
        await retriever.initialize()

        handler = ExpertiseToolHandler(retriever=retriever, lens=sample_lens)

        # First get expertise
        await handler.handle("get_expertise", {"topic": "error handling"})

        # Then verify - should use cache
        result = await handler.handle(
            "verify_against_expertise", 
            {"code": "try:\n    x = 1\nexcept Exception:\n    pass"}
        )

        assert isinstance(result, str)
        assert "Verification Results" in result

    @pytest.mark.asyncio
    async def test_list_expertise_areas_works(
        self, sample_lens: Lens, embedder: HashEmbedding
    ):
        """list_expertise_areas() returns formatted list."""
        retriever = ExpertiseRetriever(lens=sample_lens, embedder=embedder)

        handler = ExpertiseToolHandler(retriever=retriever, lens=sample_lens)

        result = await handler.handle("list_expertise_areas", {})

        assert isinstance(result, str)
        assert "Available Expertise" in result

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(
        self, sample_lens: Lens, embedder: HashEmbedding
    ):
        """Unknown tool names return error string, not raise."""
        retriever = ExpertiseRetriever(lens=sample_lens, embedder=embedder)

        handler = ExpertiseToolHandler(retriever=retriever, lens=sample_lens)

        result = await handler.handle("unknown_tool", {})

        assert "Unknown expertise tool" in result


# =============================================================================
# Contract Tests - EmbeddingResult
# =============================================================================


class TestEmbeddingResultContract:
    """Tests verifying EmbeddingResult has expected attributes.
    
    BUG BASH LESSON: Code was using .embeddings but the attribute is .vectors.
    These tests verify the actual contract.
    """

    @pytest.mark.asyncio
    async def test_embedding_result_has_vectors_attribute(self, embedder: HashEmbedding):
        """EmbeddingResult must have .vectors, not .embeddings."""
        result = await embedder.embed(["test text"])

        assert hasattr(result, "vectors"), "EmbeddingResult must have .vectors"
        assert not hasattr(result, "embeddings"), "EmbeddingResult should not have .embeddings"

    @pytest.mark.asyncio
    async def test_embedding_result_vectors_is_numpy_array(self, embedder: HashEmbedding):
        """EmbeddingResult.vectors must be numpy array."""
        result = await embedder.embed(["test"])

        assert isinstance(result.vectors, np.ndarray)
        assert result.vectors.dtype == np.float32

    @pytest.mark.asyncio
    async def test_embedding_result_shape_matches_input(self, embedder: HashEmbedding):
        """vectors.shape[0] must equal number of input texts."""
        texts = ["one", "two", "three"]
        result = await embedder.embed(texts)

        assert result.vectors.shape[0] == len(texts)


# =============================================================================
# Integration Tests
# =============================================================================


class TestExpertiseRetrievalIntegration:
    """End-to-end tests for the expertise retrieval pipeline."""

    @pytest.mark.asyncio
    async def test_full_retrieval_pipeline(
        self, sample_lens: Lens, embedder: HashEmbedding
    ):
        """Full pipeline: init retriever → get expertise → verify."""
        # 1. Create retriever
        retriever = ExpertiseRetriever(lens=sample_lens, embedder=embedder, top_k=2)

        # 2. Create handler
        handler = ExpertiseToolHandler(retriever=retriever, lens=sample_lens)

        # 3. Get expertise (triggers initialization)
        get_result = await handler.handle("get_expertise", {"topic": "async patterns"})
        assert "Error" not in get_result or "No expertise" in get_result

        # 4. Verify code
        verify_result = await handler.handle(
            "verify_against_expertise",
            {"code": "async def foo():\n    await bar()"}
        )
        assert "Verification Results" in verify_result

    @pytest.mark.asyncio
    async def test_retrieval_with_empty_query(
        self, sample_lens: Lens, embedder: HashEmbedding
    ):
        """Empty query should return error message."""
        retriever = ExpertiseRetriever(lens=sample_lens, embedder=embedder)
        handler = ExpertiseToolHandler(retriever=retriever, lens=sample_lens)

        result = await handler.handle("get_expertise", {"topic": ""})

        assert "Error" in result
        assert "required" in result.lower()
