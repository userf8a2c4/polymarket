"""
utils/notifier.py — Telegram notification system
Sistema de notificaciones Telegram (estilo Centinel)
"""

from __future__ import annotations

import asyncio
import os
from typing import Optional

from loguru import logger

try:
    from telegram import Bot
    HAS_TELEGRAM = True
except ImportError:
    HAS_TELEGRAM = False


class TelegramNotifier:
    """Send alerts to Telegram / Enviar alertas a Telegram."""

    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "")
        self.enabled = bool(self.token and self.chat_id and HAS_TELEGRAM)

        if not HAS_TELEGRAM:
            logger.warning("python-telegram-bot not installed — notifications disabled")
        elif not self.token or not self.chat_id:
            logger.warning("Telegram credentials not set — notifications disabled")
        else:
            logger.info("Telegram notifier ready")

    async def send(self, message: str) -> bool:
        """Send a message via Telegram / Enviar mensaje por Telegram."""
        if not self.enabled:
            return False

        try:
            bot = Bot(token=self.token)
            await bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode="HTML",
            )
            logger.debug(f"Telegram sent: {message[:80]}...")
            return True
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False

    def send_sync(self, message: str) -> bool:
        """Synchronous wrapper / Wrapper síncrono."""
        try:
            return asyncio.get_event_loop().run_until_complete(self.send(message))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(self.send(message))
            loop.close()
            return result


# Convenience function / Función de conveniencia
_notifier: Optional[TelegramNotifier] = None


def get_notifier() -> TelegramNotifier:
    """Singleton notifier instance / Instancia singleton del notificador."""
    global _notifier
    if _notifier is None:
        _notifier = TelegramNotifier()
    return _notifier


async def notify(message: str) -> bool:
    """Quick send / Envío rápido."""
    return await get_notifier().send(message)
