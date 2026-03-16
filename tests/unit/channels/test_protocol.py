"""Tests for channel protocol and router."""

import pytest

from sunwell.channels import ChannelManager, ChannelRouter, make_router_handle
from sunwell.channels.protocol import InboundMessage


def test_inbound_message_session_key() -> None:
    msg = InboundMessage(channel="telegram", peer_id="123", text="hello")
    assert msg.session_key == "telegram:123"


def test_channel_manager_register_get() -> None:
    manager = ChannelManager()

    class FakePlugin:
        channel_id = "fake"
        outbound = None

        async def start(self) -> None:
            pass

        async def stop(self) -> None:
            pass

    plugin = FakePlugin()
    manager.register(plugin)
    assert manager.get("fake") is plugin
    assert manager.list_plugins() == ["fake"]


def test_make_router_handle() -> None:
    """make_router_handle returns a callable."""
    from unittest.mock import AsyncMock, MagicMock

    manager = ChannelManager()
    chat_svc = MagicMock()
    chat_svc.run_for_channel = AsyncMock()

    handle = make_router_handle(chat_svc, manager)
    assert callable(handle)
