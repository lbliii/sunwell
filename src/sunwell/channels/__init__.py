"""Channel adapters for inbound/outbound messaging.

Session keys: channel:peer_id (e.g. telegram:123456789).
"""

from sunwell.channels.manager import ChannelManager
from sunwell.channels.protocol import (
    ChannelPlugin,
    ChannelReply,
    InboundMessage,
    OutboundAdapter,
)
from sunwell.channels.router import ChannelRouter, make_router_handle

__all__ = [
    "ChannelManager",
    "ChannelPlugin",
    "ChannelReply",
    "ChannelRouter",
    "InboundMessage",
    "OutboundAdapter",
    "make_router_handle",
]
