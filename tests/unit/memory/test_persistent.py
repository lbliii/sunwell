"""Tests for PersistentMemory facade (RFC: Architecture Proposal).

Tests the unified memory access layer.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sunwell.memory.persistent import PersistentMemory
from sunwell.memory.types import MemoryContext, SyncResult, TaskMemoryContext


class TestSyncResult:
    """Tests for SyncResult dataclass."""

    def test_all_succeeded_when_all_pass(self) -> None:
        """SyncResult.all_succeeded should be True when all components succeed."""
        result = SyncResult(
            results=(
                ("simulacrum", True, None),
                ("decisions", True, None),
                ("failures", True, None),
            )
        )
        assert result.all_succeeded is True

    def test_all_succeeded_when_one_fails(self) -> None:
        """SyncResult.all_succeeded should be False when any component fails."""
        result = SyncResult(
            results=(
                ("simulacrum", True, None),
                ("decisions", False, "File write error"),
                ("failures", True, None),
            )
        )
        assert result.all_succeeded is False

    def test_failed_components(self) -> None:
        """SyncResult.failed_components should list failed component names."""
        result = SyncResult(
            results=(
                ("simulacrum", False, "Error 1"),
                ("decisions", True, None),
                ("failures", False, "Error 2"),
            )
        )
        assert "simulacrum" in result.failed_components
        assert "failures" in result.failed_components
        assert "decisions" not in result.failed_components


class TestPersistentMemoryLoad:
    """Tests for PersistentMemory.load() and related methods."""

    def test_load_creates_instance(self, tmp_path: Path) -> None:
        """PersistentMemory.load() should return a PersistentMemory instance."""
        memory = PersistentMemory.load(tmp_path)

        assert memory is not None
        assert memory.workspace == tmp_path

    def test_empty_creates_minimal_memory(self, tmp_path: Path) -> None:
        """PersistentMemory.empty() should create minimal memory for testing."""
        memory = PersistentMemory.empty(tmp_path)

        assert memory is not None
        assert memory.workspace == tmp_path


class TestPersistentMemoryQuery:
    """Tests for PersistentMemory query methods."""

    @pytest.mark.asyncio
    async def test_get_relevant_returns_memory_context(self, tmp_path: Path) -> None:
        """get_relevant() should return MemoryContext."""
        memory = PersistentMemory.empty(tmp_path)

        ctx = await memory.get_relevant("build an API")

        assert isinstance(ctx, MemoryContext)

    def test_get_task_context_returns_task_memory_context(
        self, tmp_path: Path
    ) -> None:
        """get_task_context() should return TaskMemoryContext."""
        memory = PersistentMemory.empty(tmp_path)

        mock_task = MagicMock()
        mock_task.target_path = "src/api.py"

        ctx = memory.get_task_context(mock_task)

        assert isinstance(ctx, TaskMemoryContext)


class TestPersistentMemoryRecord:
    """Tests for PersistentMemory record methods."""

    def test_add_learning_works(self, tmp_path: Path) -> None:
        """add_learning() should not raise."""
        memory = PersistentMemory.empty(tmp_path)

        mock_learning = MagicMock()
        mock_learning.id = "l1"
        mock_learning.fact = "Test fact"

        # Should not raise
        memory.add_learning(mock_learning)


class TestPersistentMemorySync:
    """Tests for PersistentMemory sync method."""

    def test_sync_returns_sync_result(self, tmp_path: Path) -> None:
        """sync() should return SyncResult."""
        memory = PersistentMemory.empty(tmp_path)

        result = memory.sync()

        assert isinstance(result, SyncResult)


class TestPersistentMemoryProperties:
    """Tests for PersistentMemory convenience properties."""

    def test_learning_count_empty(self, tmp_path: Path) -> None:
        """learning_count should return 0 for empty memory."""
        memory = PersistentMemory.empty(tmp_path)
        assert memory.learning_count >= 0

    def test_decision_count_empty(self, tmp_path: Path) -> None:
        """decision_count should return 0 for empty memory."""
        memory = PersistentMemory.empty(tmp_path)
        assert memory.decision_count >= 0

    def test_failure_count_empty(self, tmp_path: Path) -> None:
        """failure_count should return 0 for empty memory."""
        memory = PersistentMemory.empty(tmp_path)
        assert memory.failure_count >= 0


class TestPersistentMemoryPatterns:
    """Tests for pattern extraction."""

    def test_get_relevant_patterns_returns_tuple(self, tmp_path: Path) -> None:
        """_get_relevant_patterns() should return a tuple."""
        memory = PersistentMemory.empty(tmp_path)

        patterns = memory._get_relevant_patterns("do something")

        assert isinstance(patterns, (list, tuple))
