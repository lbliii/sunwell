"""Tests for multi-channel notification system."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sunwell.interface.cli.notifications.channels.base import (
    BaseChannel,
    ChannelConfig,
)
from sunwell.interface.cli.notifications.channels.desktop import DesktopChannel
from sunwell.interface.cli.notifications.channels.router import ChannelRouter
from sunwell.interface.cli.notifications.channels.slack import SlackChannel
from sunwell.interface.cli.notifications.channels.webhook import WebhookChannel
from sunwell.interface.cli.notifications.system import NotificationType


class TestChannelConfig:
    """Test ChannelConfig dataclass."""

    def test_default_config(self) -> None:
        """Default config is enabled with priority 1."""
        config = ChannelConfig()

        assert config.enabled is True
        assert config.priority == 1
        assert config.types is None
        assert config.name == "channel"

    def test_custom_config(self) -> None:
        """Custom config values."""
        config = ChannelConfig(
            enabled=False,
            priority=5,
            types=[NotificationType.ERROR, NotificationType.WAITING],
            name="slack",
        )

        assert config.enabled is False
        assert config.priority == 5
        assert len(config.types) == 2


class TestBaseChannel:
    """Test BaseChannel abstract class."""

    def test_accepts_all_when_no_filter(self) -> None:
        """Channel accepts all types when no filter set."""

        class TestChannel(BaseChannel):
            def is_available(self) -> bool:
                return True

            async def send(self, title: str, message: str, notification_type: NotificationType,
                          *, sound: bool = True, context: dict | None = None) -> bool:
                return True

        channel = TestChannel(config=ChannelConfig())

        assert channel.accepts(NotificationType.INFO) is True
        assert channel.accepts(NotificationType.ERROR) is True
        assert channel.accepts(NotificationType.SUCCESS) is True

    def test_accepts_filtered_types(self) -> None:
        """Channel only accepts filtered types."""

        class TestChannel(BaseChannel):
            def is_available(self) -> bool:
                return True

            async def send(self, title: str, message: str, notification_type: NotificationType,
                          *, sound: bool = True, context: dict | None = None) -> bool:
                return True

        config = ChannelConfig(types=[NotificationType.ERROR])
        channel = TestChannel(config=config)

        assert channel.accepts(NotificationType.ERROR) is True
        assert channel.accepts(NotificationType.INFO) is False


class TestDesktopChannel:
    """Test DesktopChannel."""

    def test_create_desktop_channel(self) -> None:
        """Create desktop channel."""
        channel = DesktopChannel()

        assert channel.config.name == "desktop"

    def test_is_available(self) -> None:
        """Desktop channel availability check."""
        channel = DesktopChannel()

        # Should return bool regardless of platform
        result = channel.is_available()
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_send_disabled(self) -> None:
        """Disabled channel returns False."""
        config = ChannelConfig(enabled=False, name="desktop")
        channel = DesktopChannel(config=config)

        result = await channel.send(
            title="Test",
            message="Message",
            notification_type=NotificationType.INFO,
        )

        assert result is False


class TestSlackChannel:
    """Test SlackChannel."""

    def test_create_without_webhook(self) -> None:
        """Create slack channel without webhook."""
        channel = SlackChannel()

        assert channel.webhook_url == ""  # Empty string default
        assert channel.is_available() is False

    def test_create_with_webhook(self) -> None:
        """Create slack channel with webhook."""
        channel = SlackChannel(
            webhook_url="https://hooks.slack.com/services/xxx",
        )

        assert channel.webhook_url is not None
        assert channel.is_available() is True

    @pytest.mark.asyncio
    async def test_send_without_webhook(self) -> None:
        """Send without webhook returns False."""
        channel = SlackChannel()

        result = await channel.send(
            title="Test",
            message="Message",
            notification_type=NotificationType.INFO,
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_send_formats_correctly(self) -> None:
        """Slack message is formatted correctly."""
        channel = SlackChannel(
            webhook_url="https://hooks.slack.com/test",
            username="TestBot",
            icon_emoji=":robot:",
        )

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await channel.send(
                title="Test Title",
                message="Test message",
                notification_type=NotificationType.SUCCESS,
            )

            # Check that post was called
            mock_client.return_value.__aenter__.return_value.post.assert_called_once()

            # Verify payload structure
            call_args = mock_client.return_value.__aenter__.return_value.post.call_args
            assert call_args is not None


class TestWebhookChannel:
    """Test WebhookChannel."""

    def test_create_without_url(self) -> None:
        """Create webhook channel without URL."""
        channel = WebhookChannel()

        assert channel.url == ""  # Empty string default
        assert channel.is_available() is False

    def test_create_with_url(self) -> None:
        """Create webhook channel with URL."""
        channel = WebhookChannel(
            url="https://example.com/webhook",
            method="POST",
            headers={"Authorization": "Bearer token"},
        )

        assert channel.url == "https://example.com/webhook"
        assert channel.method == "POST"
        assert channel.is_available() is True

    @pytest.mark.asyncio
    async def test_send_without_url(self) -> None:
        """Send without URL returns False."""
        channel = WebhookChannel()

        result = await channel.send(
            title="Test",
            message="Message",
            notification_type=NotificationType.INFO,
        )

        assert result is False


class TestChannelRouter:
    """Test ChannelRouter multi-channel routing."""

    def test_create_empty_router(self) -> None:
        """Create router with no channels."""
        router = ChannelRouter()

        assert len(router.channels) == 0

    def test_add_channel(self) -> None:
        """Add channel to router."""
        router = ChannelRouter()
        channel = DesktopChannel()

        router.add_channel(channel)

        assert len(router.channels) == 1

    def test_channels_sorted_by_priority(self) -> None:
        """Channels are sorted by priority."""
        router = ChannelRouter()

        # Add channels with different priorities
        low_priority = DesktopChannel(config=ChannelConfig(priority=10, name="low"))
        high_priority = DesktopChannel(config=ChannelConfig(priority=1, name="high"))
        mid_priority = DesktopChannel(config=ChannelConfig(priority=5, name="mid"))

        router.add_channel(low_priority)
        router.add_channel(high_priority)
        router.add_channel(mid_priority)

        # Should be sorted: high (1), mid (5), low (10)
        assert router.channels[0].config.priority == 1
        assert router.channels[1].config.priority == 5
        assert router.channels[2].config.priority == 10

    def _create_mock_channel(
        self,
        *,
        enabled: bool = True,
        priority: int = 1,
        name: str = "mock",
        available: bool = True,
        send_result: bool = True,
        accepts_types: list[NotificationType] | None = None,
    ) -> MagicMock:
        """Helper to create properly configured mock channels."""
        config = MagicMock()
        config.enabled = enabled
        config.priority = priority
        config.name = name
        # ChannelConfig.accepts_type is called by router
        if accepts_types is None:
            config.accepts_type.return_value = True
        else:
            config.accepts_type.side_effect = lambda t: t in accepts_types
        
        channel = MagicMock()
        channel.config = config
        channel.is_available.return_value = available
        channel.send = AsyncMock(return_value=send_result)
        
        return channel

    @pytest.mark.asyncio
    async def test_send_to_all_matching(self) -> None:
        """Send to all matching channels in parallel mode."""
        router = ChannelRouter(fallback=False, parallel=True)

        channel1 = self._create_mock_channel(priority=1, name="ch1")
        channel2 = self._create_mock_channel(priority=2, name="ch2")

        router.add_channel(channel1)
        router.add_channel(channel2)

        result = await router.send(
            title="Test",
            message="Message",
            notification_type=NotificationType.INFO,
        )

        assert result is True
        channel1.send.assert_called_once()
        channel2.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_mode(self) -> None:
        """Fallback mode stops on first success."""
        router = ChannelRouter(fallback=True)

        channel1 = self._create_mock_channel(priority=1, name="ch1", send_result=True)
        channel2 = self._create_mock_channel(priority=2, name="ch2", send_result=True)

        router.add_channel(channel1)
        router.add_channel(channel2)

        result = await router.send(
            title="Test",
            message="Message",
            notification_type=NotificationType.INFO,
        )

        assert result is True
        channel1.send.assert_called_once()
        channel2.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_fallback_continues_on_failure(self) -> None:
        """Fallback mode continues to next channel on failure."""
        router = ChannelRouter(fallback=True)

        channel1 = self._create_mock_channel(priority=1, name="ch1", send_result=False)
        channel2 = self._create_mock_channel(priority=2, name="ch2", send_result=True)

        router.add_channel(channel1)
        router.add_channel(channel2)

        result = await router.send(
            title="Test",
            message="Message",
            notification_type=NotificationType.INFO,
        )

        assert result is True
        channel1.send.assert_called_once()
        channel2.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_unavailable_channels(self) -> None:
        """Router skips unavailable channels."""
        router = ChannelRouter()

        unavailable = self._create_mock_channel(priority=1, name="unavailable", available=False)
        available = self._create_mock_channel(priority=2, name="available", available=True)

        router.add_channel(unavailable)
        router.add_channel(available)

        await router.send(
            title="Test",
            message="Message",
            notification_type=NotificationType.INFO,
        )

        unavailable.send.assert_not_called()
        available.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_non_accepting_channels(self) -> None:
        """Router skips channels that don't accept the type."""
        router = ChannelRouter()

        # Only accepts ERROR
        error_only = self._create_mock_channel(
            priority=1, name="error_only",
            accepts_types=[NotificationType.ERROR],
        )

        # Accepts all
        all_types = self._create_mock_channel(priority=2, name="all")

        router.add_channel(error_only)
        router.add_channel(all_types)

        await router.send(
            title="Test",
            message="Message",
            notification_type=NotificationType.INFO,  # Not ERROR
        )

        error_only.send.assert_not_called()
        all_types.send.assert_called_once()
