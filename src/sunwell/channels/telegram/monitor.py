"""Telegram monitor: python-telegram-bot v21 long polling, message handler -> router."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from telegram import Update
    from telegram.ext import Application, ContextTypes

    from sunwell.channels.router import ChannelRouter

logger = logging.getLogger(__name__)

CHANNEL_ID = "telegram"


async def _message_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    router: ChannelRouter,
) -> None:
    """Handle incoming Telegram message; route to ChatService."""
    if not update.message or not update.message.text:
        return

    chat_id = str(update.effective_chat.id) if update.effective_chat else ""
    if not chat_id:
        return

    from sunwell.channels.protocol import InboundMessage

    msg = InboundMessage(
        channel=CHANNEL_ID,
        peer_id=chat_id,
        text=update.message.text,
    )
    await router.handle(msg)


def create_telegram_application(
    token: str,
    router: ChannelRouter,
) -> Application:
    """Create python-telegram-bot Application with message handler."""
    from telegram import Update  # noqa: F401
    from telegram.ext import Application, ContextTypes, MessageHandler, filters  # noqa: F401

    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await _message_handler(update, context, router)

    app = (
        Application.builder()
        .token(token)
        .post_init(lambda a: logger.info("Telegram bot initialized"))
        .build()
    )
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handler))
    return app
