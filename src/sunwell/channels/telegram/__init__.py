"""Telegram channel plugin: config + outbound + monitor."""

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING

from sunwell.channels.telegram.outbound import TelegramOutbound

if TYPE_CHECKING:
    from sunwell.channels.router import ChannelRouter

logger = logging.getLogger(__name__)

CHANNEL_ID = "telegram"


class TelegramPlugin:
    """Telegram channel plugin assembling config + outbound + monitor."""

    def __init__(
        self,
        token: str,
        router: ChannelRouter,
    ) -> None:
        self._token = token
        self._router = router
        self._application = None
        self._poll_task: asyncio.Task[None] | None = None
        self._outbound: TelegramOutbound | None = None

    @property
    def channel_id(self) -> str:
        return CHANNEL_ID

    @property
    def outbound(self) -> TelegramOutbound:
        if self._outbound is None:
            from telegram import Bot

            self._outbound = TelegramOutbound(Bot(token=self._token))
        return self._outbound

    async def start(self) -> None:
        """Start long polling in background task."""
        from sunwell.channels.telegram.monitor import create_telegram_application

        self._application = create_telegram_application(self._token, self._router)
        await self._application.initialize()
        await self._application.start()

        async def run_polling() -> None:
            await self._application.run_polling(
                allowed_updates=["message"],
                drop_pending_updates=True,
            )

        self._poll_task = asyncio.create_task(run_polling())
        logger.info("Telegram long polling started")

    async def stop(self) -> None:
        """Stop long polling."""
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._poll_task
            self._poll_task = None

        if self._application:
            await self._application.stop()
            await self._application.shutdown()
            self._application = None

        logger.info("Telegram channel stopped")
