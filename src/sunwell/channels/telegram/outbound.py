"""Telegram outbound adapter: send_text, send_media, 4096-char chunking."""

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from telegram import Bot

logger = logging.getLogger(__name__)

TELEGRAM_MAX_MESSAGE_LENGTH = 4096


def _chunk_text(text: str, max_len: int = TELEGRAM_MAX_MESSAGE_LENGTH) -> list[str]:
    """Split text into chunks under max_len, preferring word boundaries."""
    if len(text) <= max_len:
        return [text] if text else []

    chunks: list[str] = []
    remaining = text

    while len(remaining) > max_len:
        part = remaining[:max_len]
        last_space = part.rfind(" ")
        if last_space > max_len // 2:
            part = part[:last_space]
            remaining = remaining[last_space:].lstrip()
        else:
            remaining = remaining[max_len:]
        chunks.append(part)

    if remaining:
        chunks.append(remaining)

    return chunks


class TelegramOutbound:
    """Outbound adapter for Telegram: send_text, send_media with chunking."""

    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def send_text(self, peer_id: str, text: str) -> None:
        """Send text to peer. Chunks at 4096 chars, uses parse_mode=None (plain)."""
        if not text.strip():
            return

        chunks = _chunk_text(text)
        for i, chunk in enumerate(chunks):
            try:
                await self._bot.send_message(
                    chat_id=peer_id,
                    text=chunk,
                    parse_mode=None,
                )
                if i < len(chunks) - 1:
                    await asyncio.sleep(0.3)
            except Exception as e:
                logger.exception("Telegram send_text failed for chunk %s: %s", i + 1, e)
                raise

    async def send_media(self, peer_id: str, media_url: str, caption: str = "") -> None:
        """Send media (image/file) to peer."""
        try:
            if media_url.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp")):
                await self._bot.send_photo(
                    chat_id=peer_id,
                    photo=media_url,
                    caption=caption[:1024] if caption else None,
                )
            else:
                await self._bot.send_document(
                    chat_id=peer_id,
                    document=media_url,
                    caption=caption[:1024] if caption else None,
                )
        except Exception as e:
            logger.exception("Telegram send_media failed: %s", e)
            raise
