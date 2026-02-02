"""Tests for merge module."""

import pytest

from sunwell.agent.isolation.merge import MergeResult, MergeStrategy


class TestMergeStrategy:
    """Tests for MergeStrategy enum."""

    def test_values(self) -> None:
        """MergeStrategy should have expected values."""
        assert MergeStrategy.FAST_FORWARD.value == "fast_forward"
        assert MergeStrategy.THREE_WAY.value == "three_way"
        assert MergeStrategy.ABORT_ON_CONFLICT.value == "abort"


class TestMergeResult:
    """Tests for MergeResult dataclass."""

    def test_successful_merge(self) -> None:
        """Successful merge should have success=True."""
        result = MergeResult(
            success=True,
            strategy_used=MergeStrategy.FAST_FORWARD,
            files_merged=("a.py", "b.py"),
        )

        assert result.success
        assert result.strategy_used == MergeStrategy.FAST_FORWARD
        assert result.files_merged == ("a.py", "b.py")
        assert result.conflicts == ()
        assert result.error is None
        assert not result.has_conflicts
        assert result.file_count == 2

    def test_failed_merge(self) -> None:
        """Failed merge should have success=False and conflicts."""
        result = MergeResult(
            success=False,
            strategy_used=MergeStrategy.THREE_WAY,
            files_merged=(),
            conflicts=("conflict.py",),
            error="Merge conflict in conflict.py",
        )

        assert not result.success
        assert result.has_conflicts
        assert result.conflicts == ("conflict.py",)
        assert result.error is not None
        assert result.file_count == 1

    def test_str_success(self) -> None:
        """String representation for successful merge."""
        result = MergeResult(
            success=True,
            strategy_used=MergeStrategy.FAST_FORWARD,
            files_merged=("a.py", "b.py"),
        )
        s = str(result)
        assert "Merged 2 file(s)" in s
        assert "fast_forward" in s

    def test_str_failure(self) -> None:
        """String representation for failed merge."""
        result = MergeResult(
            success=False,
            strategy_used=MergeStrategy.THREE_WAY,
            files_merged=(),
            conflicts=("a.py", "b.py"),
        )
        s = str(result)
        assert "Merge failed" in s
        assert "2 conflict(s)" in s

    def test_frozen(self) -> None:
        """MergeResult should be frozen (immutable)."""
        result = MergeResult(
            success=True,
            strategy_used=MergeStrategy.FAST_FORWARD,
            files_merged=(),
        )

        with pytest.raises(AttributeError):
            result.success = False
