"""ChannelManager - registers plugins, handles start/stop lifecycle."""

import logging
from collections.abc import Sequence

from sunwell.channels.protocol import ChannelPlugin

logger = logging.getLogger(__name__)


class ChannelManager:
    """Manages channel plugins: registration, start, stop."""

    def __init__(self) -> None:
        self._plugins: dict[str, ChannelPlugin] = {}
        self._started: set[str] = set()

    def register(self, plugin: ChannelPlugin) -> None:
        """Register a channel plugin."""
        cid = plugin.channel_id
        if cid in self._plugins:
            logger.warning("Channel %s already registered, replacing", cid)
        self._plugins[cid] = plugin
        logger.info("Registered channel plugin: %s", cid)

    def unregister(self, channel_id: str) -> None:
        """Unregister a channel plugin."""
        if channel_id in self._started:
            logger.warning("Channel %s still started, stop before unregister", channel_id)
        self._plugins.pop(channel_id, None)

    def get(self, channel_id: str) -> ChannelPlugin | None:
        """Get plugin by channel id."""
        return self._plugins.get(channel_id)

    def list_plugins(self) -> list[str]:
        """List registered channel ids."""
        return list(self._plugins)

    def list_started(self) -> list[str]:
        """List channel ids that are currently running."""
        return list(self._started)

    async def start_all(self, channel_ids: Sequence[str] | None = None) -> None:
        """Start channel monitors.

        Args:
            channel_ids: If provided, start only these channels. Otherwise start all.
        """
        to_start = channel_ids if channel_ids is not None else list(self._plugins)
        for cid in to_start:
            plugin = self._plugins.get(cid)
            if plugin is None:
                logger.warning("Channel %s not registered, skipping start", cid)
                continue
            if cid in self._started:
                logger.debug("Channel %s already started", cid)
                continue
            try:
                await plugin.start()
                self._started.add(cid)
                logger.info("Started channel: %s", cid)
            except Exception as e:
                logger.exception("Failed to start channel %s: %s", cid, e)

    async def stop_all(self) -> None:
        """Stop all channel monitors."""
        for cid in list(self._started):
            plugin = self._plugins.get(cid)
            if plugin is None:
                self._started.discard(cid)
                continue
            try:
                await plugin.stop()
                self._started.discard(cid)
                logger.info("Stopped channel: %s", cid)
            except Exception as e:
                logger.exception("Failed to stop channel %s: %s", cid, e)
