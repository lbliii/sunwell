"""Tests for sunwell.agent.utils.ephemeral_lens module.

Tests cover:
- should_use_delegation function logic
- create_ephemeral_lens functionality
"""

import pytest

from sunwell.agent.utils.ephemeral_lens import should_use_delegation


# =============================================================================
# should_use_delegation Tests
# =============================================================================


class TestShouldUseDelegation:
    """Tests for should_use_delegation function.

    The function decides whether to use smart→dumb model delegation
    based on task characteristics and budget.
    """

    @pytest.mark.asyncio
    async def test_large_token_count_triggers_delegation(self) -> None:
        """Tasks with >2000 estimated tokens should use delegation."""
        result = await should_use_delegation(
            task="simple task",
            estimated_tokens=3000,
            budget_remaining=50_000,
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_exactly_2000_tokens_no_delegation(self) -> None:
        """Tasks with exactly 2000 tokens should NOT trigger delegation."""
        result = await should_use_delegation(
            task="simple task",
            estimated_tokens=2000,
            budget_remaining=50_000,
        )
        # 2000 is not > 2000, so should be False unless other conditions match
        assert result is False

    @pytest.mark.asyncio
    async def test_low_budget_triggers_delegation(self) -> None:
        """Low budget (< tokens * 3) should trigger delegation."""
        result = await should_use_delegation(
            task="task",
            estimated_tokens=1000,
            budget_remaining=2000,  # 2000 < 1000 * 3 = 3000
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_adequate_budget_no_delegation(self) -> None:
        """Adequate budget should not trigger delegation on its own."""
        result = await should_use_delegation(
            task="simple fix",
            estimated_tokens=500,
            budget_remaining=50_000,  # 50000 > 500 * 3 = 1500
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_files_keyword_triggers_delegation(self) -> None:
        """Tasks mentioning 'files' should use delegation."""
        result = await should_use_delegation(
            task="create multiple files for the API",
            estimated_tokens=500,
            budget_remaining=50_000,
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_endpoints_keyword_triggers_delegation(self) -> None:
        """Tasks mentioning 'endpoints' should use delegation."""
        result = await should_use_delegation(
            task="implement REST endpoints",
            estimated_tokens=500,
            budget_remaining=50_000,
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_components_keyword_triggers_delegation(self) -> None:
        """Tasks mentioning 'components' should use delegation."""
        result = await should_use_delegation(
            task="create React components",
            estimated_tokens=500,
            budget_remaining=50_000,
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_modules_keyword_triggers_delegation(self) -> None:
        """Tasks mentioning 'modules' should use delegation."""
        result = await should_use_delegation(
            task="organize into modules",
            estimated_tokens=500,
            budget_remaining=50_000,
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_case_insensitive_keyword_matching(self) -> None:
        """Keyword matching should be case-insensitive."""
        result = await should_use_delegation(
            task="CREATE MULTIPLE FILES",
            estimated_tokens=500,
            budget_remaining=50_000,
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_simple_task_no_delegation(self) -> None:
        """Simple tasks with good budget should not use delegation."""
        result = await should_use_delegation(
            task="fix typo in variable name",
            estimated_tokens=500,
            budget_remaining=50_000,
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_single_file_task_no_delegation(self) -> None:
        """Single file tasks should not trigger delegation."""
        result = await should_use_delegation(
            task="update the config file",  # 'file' singular, not 'files'
            estimated_tokens=500,
            budget_remaining=50_000,
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_combined_conditions(self) -> None:
        """Multiple conditions can trigger delegation."""
        # Large tokens + multi-file
        result = await should_use_delegation(
            task="create multiple files",
            estimated_tokens=3000,
            budget_remaining=50_000,
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_edge_case_empty_task(self) -> None:
        """Empty task should not crash."""
        result = await should_use_delegation(
            task="",
            estimated_tokens=500,
            budget_remaining=50_000,
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_edge_case_zero_tokens(self) -> None:
        """Zero tokens should not trigger delegation."""
        result = await should_use_delegation(
            task="task",
            estimated_tokens=0,
            budget_remaining=50_000,
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_edge_case_zero_budget(self) -> None:
        """Zero budget triggers delegation (any tokens * 3 > 0)."""
        result = await should_use_delegation(
            task="task",
            estimated_tokens=100,
            budget_remaining=0,  # 0 < 100 * 3 = 300
        )
        assert result is True
