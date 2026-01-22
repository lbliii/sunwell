"""Tests for block actions (RFC-080)."""

import pytest

from sunwell.interface.block_actions import BlockActionExecutor, BlockActionResult


class TestBlockActionResult:
    """Tests for BlockActionResult."""

    def test_success_result(self) -> None:
        """Test creating a success result."""
        result = BlockActionResult(
            success=True,
            message="Action completed.",
            data={"item_id": "123"},
        )
        assert result.success is True
        assert result.message == "Action completed."
        assert result.data == {"item_id": "123"}

    def test_failure_result(self) -> None:
        """Test creating a failure result."""
        result = BlockActionResult(
            success=False,
            message="Action failed.",
        )
        assert result.success is False
        assert result.message == "Action failed."
        assert result.data is None


class TestBlockActionExecutor:
    """Tests for BlockActionExecutor."""

    @pytest.fixture
    def executor(self) -> BlockActionExecutor:
        """Create an executor without providers."""
        return BlockActionExecutor()

    @pytest.mark.asyncio
    async def test_unknown_action(self, executor: BlockActionExecutor) -> None:
        """Test handling of unknown action."""
        result = await executor.execute("unknown_action")
        assert result.success is False
        assert "Unknown action" in result.message

    @pytest.mark.asyncio
    async def test_complete_habit_no_id(self, executor: BlockActionExecutor) -> None:
        """Test completing habit without ID."""
        result = await executor.execute("complete", None)
        assert result.success is False
        assert "No habit specified" in result.message

    @pytest.mark.asyncio
    async def test_complete_habit_no_provider(self, executor: BlockActionExecutor) -> None:
        """Test completing habit without provider."""
        result = await executor.execute("complete", "habit_123")
        assert result.success is False
        assert "provider not configured" in result.message

    @pytest.mark.asyncio
    async def test_skip_habit_no_id(self, executor: BlockActionExecutor) -> None:
        """Test skipping habit without ID."""
        result = await executor.execute("skip", None)
        assert result.success is False
        assert "No habit specified" in result.message

    @pytest.mark.asyncio
    async def test_check_item_no_id(self, executor: BlockActionExecutor) -> None:
        """Test checking item without ID."""
        result = await executor.execute("check", None)
        assert result.success is False
        assert "No item specified" in result.message

    @pytest.mark.asyncio
    async def test_check_item_no_provider(self, executor: BlockActionExecutor) -> None:
        """Test checking item without provider."""
        result = await executor.execute("check", "item_123")
        assert result.success is False
        assert "provider not configured" in result.message

    @pytest.mark.asyncio
    async def test_follow_up_action(self, executor: BlockActionExecutor) -> None:
        """Test follow-up action."""
        result = await executor.execute("follow_up")
        assert result.success is True
        assert result.data == {"action": "show_input"}

    @pytest.mark.asyncio
    async def test_dismiss_action(self, executor: BlockActionExecutor) -> None:
        """Test dismiss action."""
        result = await executor.execute("dismiss")
        assert result.success is True
        assert result.data == {"action": "dismiss"}

    @pytest.mark.asyncio
    async def test_add_event_action(self, executor: BlockActionExecutor) -> None:
        """Test add event action shows dialog."""
        result = await executor.execute("add_event")
        assert result.success is True
        assert result.data == {"action": "show_event_dialog"}

    @pytest.mark.asyncio
    async def test_create_note_action(self, executor: BlockActionExecutor) -> None:
        """Test create note action shows dialog."""
        result = await executor.execute("create")
        assert result.success is True
        assert result.data == {"action": "show_note_dialog"}

    @pytest.mark.asyncio
    async def test_add_item_action(self, executor: BlockActionExecutor) -> None:
        """Test add item action shows dialog."""
        result = await executor.execute("add", "grocery")
        assert result.success is True
        assert result.data == {"action": "show_add_dialog", "list": "grocery"}

    @pytest.mark.asyncio
    async def test_open_action(self, executor: BlockActionExecutor) -> None:
        """Test open action."""
        result = await executor.execute("open", "item_123")
        assert result.success is True
        assert result.data == {"item_id": "item_123", "action": "open"}

    @pytest.mark.asyncio
    async def test_open_action_no_id(self, executor: BlockActionExecutor) -> None:
        """Test open action without ID."""
        result = await executor.execute("open", None)
        assert result.success is False
        assert "No item specified" in result.message
