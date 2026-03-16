"""Route inbound channel messages to ChatService.

Session key format: channel:peer_id (e.g. telegram:123456789).
Each channel+peer gets its own conversation session.
"""

import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from sunwell.channels.protocol import InboundMessage

if TYPE_CHECKING:
    from sunwell.channels.manager import ChannelManager
    from sunwell.interface.chirp.services.chat import ChatService

logger = logging.getLogger(__name__)

HandleInbound = Callable[[InboundMessage], Awaitable[None]]


def make_router_handle(
    chat_service: ChatService,
    channel_manager: ChannelManager,
) -> HandleInbound:
    """Create a handle that routes to ChatService.run_for_channel via channel outbound."""

    async def handle(msg: InboundMessage) -> None:
        plugin = channel_manager.get(msg.channel)
        if plugin is None:
            logger.warning("No plugin for channel %s, dropping message", msg.channel)
            return
        await chat_service.run_for_channel(msg, plugin.outbound)

    return handle


class ChannelRouter:
    """Routes InboundMessage to ChatService via session key."""

    def __init__(self, handle: HandleInbound) -> None:
        self._handle = handle

    async def handle(self, msg: InboundMessage) -> None:
        """Route message to handler (ChatService.run_for_channel)."""
        logger.debug("ChannelRouter handling %s from %s", msg.session_key, msg.channel)
        await self._handle(msg)
