"""Channel protocol definitions for inbound/outbound messaging.

Defines the core types for channel adapters: InboundMessage, ChannelReply,
OutboundAdapter, and ChannelPlugin. Session keys use format channel:peer_id.
"""

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class InboundMessage:
    """Message received from a channel (user -> agent)."""

    channel: str
    peer_id: str
    text: str
    media_url: str | None = None
    metadata: dict[str, Any] | None = None

    @property
    def session_key(self) -> str:
        """Session key for routing: channel:peer_id."""
        return f"{self.channel}:{self.peer_id}"


@dataclass(frozen=True, slots=True)
class ChannelReply:
    """Reply to send back through a channel (agent -> user)."""

    text: str
    media_url: str | None = None
    metadata: dict[str, Any] | None = None


class OutboundAdapter(Protocol):
    """Protocol for sending replies to a channel peer."""

    async def send_text(self, peer_id: str, text: str) -> None:
        """Send text to peer. Handles formatting and chunking per channel limits."""
        ...

    async def send_media(self, peer_id: str, media_url: str, caption: str = "") -> None:
        """Send media (image, file) to peer."""
        ...


class ChannelPlugin(Protocol):
    """Protocol for a channel plugin (config + outbound + monitor)."""

    @property
    def channel_id(self) -> str:
        """Unique channel identifier (e.g. 'telegram')."""
        ...

    @property
    def outbound(self) -> OutboundAdapter:
        """Adapter for sending replies."""
        ...

    async def start(self) -> None:
        """Start the channel monitor (long polling, webhook, etc.)."""
        ...

    async def stop(self) -> None:
        """Stop the channel monitor."""
        ...
